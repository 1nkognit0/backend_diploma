from fastapi import FastAPI, HTTPException, Depends, Request, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator
from typing import List, Optional, Literal
from pathlib import Path
from urllib.parse import urlencode
import asyncio
import os
import secrets
import uvicorn
from notifications import (
    send_email_notification,
    format_order_message
)
from sqlalchemy.orm import selectinload

from db import SessionLocal, Base, engine
from models import Order, OrderContact

app = FastAPI(title="Order Request API")

_BACKEND_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(_BACKEND_DIR / "templates"))

http_basic = HTTPBasic(auto_error=False)

# Допустимые поля для сортировки в админке (защита от произвольных имён колонок)
ADMIN_SORT_FIELDS = frozenset({"id", "created_at", "updated_at", "status", "work_type"})

STATUS_LABELS = {
    "new": "Новая",
    "processing": "В работе",
    "done": "Выполнена",
    "cancelled": "Отменена",
}


def verify_admin(credentials: HTTPBasicCredentials | None = Depends(http_basic)) -> None:
    """Доступ к /admin только по логину и паролю из переменных окружения."""
    password = os.getenv("ADMIN_PASSWORD", "").strip()
    if not password:
        raise HTTPException(
            status_code=503,
            detail="Админка не настроена: задайте ADMIN_PASSWORD в окружении",
        )
    if credentials is None:
        raise HTTPException(
            status_code=401,
            headers={"WWW-Authenticate": "Basic realm=admin"},
        )
    username = os.getenv("ADMIN_USERNAME", "admin")

    def same_len_digest(a: str, b: str) -> bool:
        if len(a) != len(b):
            return False
        # compare_digest имеет константное время выполнения, что позволяет избежать атак по времени
        return secrets.compare_digest(a.encode("utf-8"), b.encode("utf-8"))

    user_ok = same_len_digest(credentials.username, username)
    pass_ok = same_len_digest(credentials.password, password)
    if not (user_ok and pass_ok):
        raise HTTPException(
            status_code=401,
            detail="Неверный логин или пароль",
            headers={"WWW-Authenticate": "Basic realm=admin"},
        )

# Настройка CORS для работы с локальным фронтендом
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Для локальной разработки разрешаем все источники
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ContactData(BaseModel):
    """Модель контактных данных"""
    type: Literal["phone", "email"]
    value: str | EmailStr

    @model_validator(mode='after')
    def validate_contact_value(self):
        contact_type = self.type
        if contact_type == 'phone':
            if not self.value.replace('+', '').replace('-', '').replace(' ', '').replace('(', '').replace(')', '').isdigit():
                raise ValueError('Некорректный формат номера телефона')
        elif contact_type == 'email':
            if '@' not in self.value:
                raise ValueError('Некорректный формат email')
        return self


class OrderRequest(BaseModel):
    """Модель заявки на заказ"""
    name: Optional[str] = Field(None, max_length=200, description="Имя")
    work_type: Literal["Не указано", "Сантехника", "Электрика", "Кондиционеры"] = Field("Не указано", description="Тип работ")
    description: str = Field(..., min_length=1, max_length=2000, description="Описание заказа (обязательно)")
    contacts: List[ContactData] = Field(..., min_items=1, description="Контактные данные (минимум один)")

    @field_validator('contacts')
    @classmethod
    def validate_contacts(cls, v):
        if len(v) < 1:
            raise ValueError('Необходимо указать хотя бы один контакт')
        return v


@app.on_event("startup")
def on_startup():
    # Инициализация таблиц (если не существуют)
    Base.metadata.create_all(bind=engine)


@app.get("/")
async def root():
    return {"message": "order request api is running"}


@app.post("/api/submit")
async def submit_order(order_request: OrderRequest):  # добавили async
    def db_operation():  # выносим синхронную БД в отдельную функцию
        db = SessionLocal()
        try:
            new_order = Order(
                name=order_request.name,
                work_type=order_request.work_type,
                description=order_request.description,
                status="new"
            )
            db.add(new_order)
            db.flush()

            for c in order_request.contacts:
                db.add(OrderContact(order_id=new_order.id, type=c.type, value=str(c.value)))

            db.commit()
            db.refresh(new_order)
            return new_order
        except Exception as e:
            db.rollback()
            raise e
        finally:
            db.close()
    
    try:
        # Запускаем синхронную БД в отдельном потоке
        new_order = await asyncio.to_thread(db_operation)
        
        print(f"✅ Заявка сохранена в БД: order_id={new_order.id}")
        
        # Отправляем письмо (асинхронно). Используем данные запроса, чтобы не обращаться к ORM после закрытия сессии.
        message_text = format_order_message({
            "name": new_order.name,
            "work_type": new_order.work_type,
            "description": new_order.description,
            "contacts": [{"type": c.type, "value": str(c.value)} for c in order_request.contacts]
        })
        asyncio.create_task(send_email_notification(message_text))
        
        return {
            "status": "success",
            "message": "Заявка успешно получена",
            "order_id": new_order.id
        }
    except Exception as e:
        print(f"❌ Ошибка сохранения заявки: {e}")
        raise HTTPException(status_code=500, detail="Не удалось сохранить заявку")


def _admin_list_orders(sort: str, dir: str, status_filter: Optional[str]) -> list[dict]:
    if sort not in ADMIN_SORT_FIELDS:
        sort = "created_at"
    if dir not in ("asc", "desc"):
        dir = "desc"

    db = SessionLocal()
    try:
        q = db.query(Order).options(selectinload(Order.contacts))
        if status_filter:
            q = q.filter(Order.status == status_filter)
        col = getattr(Order, sort)
        q = q.order_by(col.desc() if dir == "desc" else col.asc())
        rows = q.all()
        out = []
        for o in rows:
            out.append(
                {
                    "id": o.id,
                    "name": o.name or "—",
                    "work_type": o.work_type,
                    "description": o.description,
                    "status": o.status,
                    "created_at": o.created_at,
                    "updated_at": o.updated_at,
                    "contacts": [{"type": c.type, "value": c.value} for c in o.contacts],
                }
            )
        return out
    finally:
        db.close()


def _admin_set_status(order_id: int, new_status: str) -> bool:
    db = SessionLocal()
    try:
        order = db.query(Order).filter(Order.id == order_id).first()
        if not order:
            return False
        order.status = new_status[:20]
        db.commit()
        return True
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


@app.get("/admin", response_class=HTMLResponse)
def admin_page(
    request: Request,
    sort: str = "created_at",
    dir: str = "desc",
    status: Optional[str] = None,
    _: None = Depends(verify_admin),
):
    if sort not in ADMIN_SORT_FIELDS:
        sort = "created_at"
    if dir not in ("asc", "desc"):
        dir = "desc"

    orders = _admin_list_orders(sort, dir, status)
    return templates.TemplateResponse(
        "admin.html",
        {
            "request": request,
            "orders": orders,
            "sort": sort,
            "dir": dir,
            "filter_status": status or "",
            "status_labels": STATUS_LABELS,
        },
    )


@app.post("/admin/order/{order_id}/status")
def admin_update_status(
    order_id: int,
    new_status: str = Form(...),
    sort: str = Form("created_at"),
    dir: str = Form("desc"),
    filter_status: str = Form(""),
    _: None = Depends(verify_admin),
):
    if sort not in ADMIN_SORT_FIELDS:
        sort = "created_at"
    if dir not in ("asc", "desc"):
        dir = "desc"

    ok = _admin_set_status(order_id, new_status.strip())
    if not ok:
        raise HTTPException(status_code=404, detail="Заявка не найдена")

    qs: dict[str, str] = {"sort": sort, "dir": dir}
    if filter_status.strip():
        qs["status"] = filter_status.strip()
    return RedirectResponse(url=f"/admin?{urlencode(qs)}", status_code=303)


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
