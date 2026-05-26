"""
Модуль для отправки уведомлений по Email
"""
import asyncio
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv
import os

# Загрузка переменных окружения
load_dotenv()

# Получение данных из .env
SMTP_LOGIN = os.getenv("SMTP_LOGIN")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
SMTP_SERVER = "smtp.yandex.ru"
SMTP_PORT = 465

def format_order_message(order_data: dict) -> str:
    """
    Форматирует данные заявки в читаемый текст
    """
    message = "📋 НОВАЯ ЗАЯВКА\n\n"
    if order_data.get('name'):
        message += f"🙍 Имя: {order_data['name']}\n"
    message += f"🧰 Тип работ: {order_data.get('work_type', 'Не указано')}\n"
    
    if order_data.get('description'):
        message += f"📝 Описание: {order_data['description']}\n"
    
    message += "\n📞 Контактные данные:\n"
    for i, contact in enumerate(order_data['contacts'], 1):
        contact_type = contact['type']
        contact_value = contact['value']
        
        # Иконки для разных типов контактов
        icons = {
            'phone': '📱',
            'email': '📧',
        }
        
        type_names = {
            'phone': 'Телефон',
            'email': 'Email',
        }
        
        icon = icons.get(contact_type, '•')
        type_name = type_names.get(contact_type, contact_type)
        message += f"{i}. {icon} {type_name}: {contact_value}\n"
    
    return message

async def send_email_notification(message_text: str) -> bool:
    """
    Отправляет уведомление на email через SMTP Яндекс
    """
    if not SMTP_LOGIN or not SMTP_PASSWORD:
        print("⚠️ SMTP_LOGIN или SMTP_PASSWORD не найдены в .env")
        return False
    
    try:
        # Создаем сообщение
        msg = MIMEMultipart()
        msg['From'] = SMTP_LOGIN
        msg['To'] = SMTP_LOGIN  # Отправляем на ту же почту
        msg['Subject'] = "Новая заявка на заказ"
        
        # Добавляем текст сообщения
        msg.attach(MIMEText(message_text, 'plain', 'utf-8'))
        
        # Отправляем через SMTP
        # Используем asyncio для неблокирующей отправки
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            _send_smtp_email,
            msg
        )
        print("✅ Email уведомление отправлено")
        return True
    except Exception as e:
        print(f"❌ Ошибка при отправке email: {e}")
        return False


def _send_smtp_email(msg: MIMEMultipart):
    """
    Синхронная функция для отправки email через SMTP
    """
    try:
        server = smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT)
        server.login(SMTP_LOGIN, SMTP_PASSWORD)
        server.send_message(msg)
        server.quit()
    except Exception as e:
        raise Exception(f"SMTP ошибка: {e}")
