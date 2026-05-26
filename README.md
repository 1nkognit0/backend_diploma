# Приложение для заявок на заказ

Простое приложение на FastAPI с фронтендом для оформления заявок на заказ.

## Структура проекта

```
collage/
├── backend/          # FastAPI приложение
│   ├── main.py      # Основной файл приложения
│   ├── notifications.py  # Отправка уведомлений по Email
│   └── requirements.txt
├── frontend/        # Фронтенд (HTML/CSS/JS)
│   ├── index.html
│   ├── style.css
│   └── script.js
├── venv/           # Виртуальное окружение
├── .env            # Переменные окружения (создать самостоятельно)
└── README.md
```

## Установка и запуск

### 1. Создание виртуального окружения

```bash
python -m venv venv
```

### 2. Активация виртуального окружения

**Windows:**
```bash
venv\Scripts\activate
```

**Linux/Mac:**
```bash
source venv/bin/activate
```

### 3. Установка зависимостей

```bash
cd backend
pip install -r requirements.txt
```

### 4. Настройка переменных окружения

Создайте файл `.env` в корне проекта со следующим содержимым:

```env
# Yandex SMTP Configuration
SMTP_LOGIN=your_email@yandex.ru
SMTP_PASSWORD=your_app_password_here
```

**Как получить пароль приложения для Яндекс почты:**
1. Зайдите в настройки аккаунта Яндекс
2. Перейдите в раздел "Безопасность"
3. Создайте пароль приложения
4. Используйте его в `SMTP_PASSWORD`

### 5. Запуск бэкенда

```bash
cd backend
python main.py
```

Бэкенд будет доступен по адресу: `http://localhost:8000`

### 6. Запуск фронтенда

Просто откройте файл `frontend/index.html` в браузере или используйте простой HTTP сервер:

```bash
cd frontend
python -m http.server 8080
```

Затем откройте в браузере: `http://localhost:8080`

## API

### POST /api/submit

Принимает заявку на заказ.

**Тело запроса:**
```json
{
  "order_name": "Название заказа",
  "description": "Описание заказа",
  "quantity": 5,
  "contacts": [
    {
      "type": "phone",
      "value": "+79991234567"
    },
    {
      "type": "email",
      "value": "user@example.com"
    }
  ]
}
```

**Типы контактов:**
- `phone` - номер телефона
- `email` - email адрес
- `telegram` - Telegram ник

## Функционал уведомлений
При отправке заявки автоматически уходит письмо на адрес `SMTP_LOGIN` через Яндекс SMTP.

## Примечания

- Для локальной разработки CORS настроен на разрешение всех источников
- Валидация данных выполняется на бэкенде через Pydantic
- Фронтенд отправляет данные в формате JSON на эндпоинт `/api/submit`
- Уведомления отправляются асинхронно и не блокируют ответ API
