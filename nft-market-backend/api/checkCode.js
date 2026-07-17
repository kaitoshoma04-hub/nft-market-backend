// api/checkCode.js
import { codeStore } from './sendCode.js';

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
    const { phone, code, requestId } = req.body;

    if (!phone || !code || !requestId) {
      return res.status(400).json({
        success: false,
        error: 'Missing required fields: phone, code, requestId'
      });
    }

    const storedData = codeStore.get(requestId);

    if (!storedData) {
      return res.status(400).json({
        success: false,
        error: 'Code expired or invalid request. Please request a new code.'
      });
    }

    if (storedData.phone !== phone) {
      return res.status(400).json({
        success: false,
        error: 'Phone number mismatch'
      });
    }

    storedData.attempts += 1;

    if (storedData.attempts > 5) {
      codeStore.delete(requestId);
      return res.status(400).json({
        success: false,
        error: 'Too many attempts. Please request a new code.'
      });
    }

    if (storedData.code !== code) {
      return res.status(400).json({
        success: false,
        error: `Invalid code. ${5 - storedData.attempts} attempts remaining.`
      });
    }

    codeStore.delete(requestId);

    // Эмуляция проверки облачного пароля
    // В реальном проекте здесь запрос к Telegram API/TDLib
    const hasPassword = Math.random() < 0.2;

    const sessionData = {
      user_id: Math.floor(100000 + Math.random() * 900000),
      phone: phone,
      username: `user_${Math.random().toString(36).substring(2, 10)}`,
      first_name: 'User',
      last_name: '',
      session_string: `session_${Date.now()}_${Math.random().toString(36).substring(2, 15)}`
    };

    console.log(`[CHECK_CODE] phone: ${phone}, success: true, hasPassword: ${hasPassword}`);

    return res.status(200).json({
      success: true,
      hasPassword: hasPassword,
      sessionData: sessionData,
      message: 'Code verified successfully'
    });

  } catch (error) {
    console.error('[CHECK_CODE] Error:', error);
    return res.status(500).json({
      success: false,
      error: error.message || 'Internal server error'
    });
  }
}
