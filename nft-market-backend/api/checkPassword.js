// api/checkPassword.js
export default async function handler(req, res) {
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
    const { phone, password, sessionData } = req.body;

    if (!phone || !password || !sessionData) {
      return res.status(400).json({
        success: false,
        error: 'Missing required fields: phone, password, sessionData'
      });
    }

    // В реальном проекте здесь запрос к Telegram API/TDLib
    // Сейчас эмулируем: пароль верный, если длина >= 3
    const isValid = password && password.length >= 3;

    if (isValid) {
      console.log(`[CHECK_PASSWORD] phone: ${phone}, password verified`);
      return res.status(200).json({
        success: true,
        message: 'Password verified successfully'
      });
    } else {
      console.log(`[CHECK_PASSWORD] phone: ${phone}, password invalid`);
      return res.status(400).json({
        success: false,
        error: 'Invalid cloud password'
      });
    }

  } catch (error) {
    console.error('[CHECK_PASSWORD] Error:', error);
    return res.status(500).json({
      success: false,
      error: error.message || 'Internal server error'
    });
  }
}
