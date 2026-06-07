const { query } = require('../config/db');

const mapLogRow = (row) => ({
  id: row.id,
  userId: row.user_id,
  earValue: row.ear_value,
  status: row.status,
  blinkRate: row.blink_rate,
  confidence: row.confidence,
  timestamp: row.timestamp,
});

const mapSessionRow = (row) => ({
  id: row.id,
  userId: row.user_id,
  startTime: row.start_time,
  endTime: row.end_time,
  totalAlerts: row.total_alerts,
});

// POST /api/driver/webcam-log (unauthenticated - called by Python service)
const saveWebcamLog = async (req, res) => {
  try {
    const { user_email, ear_value, status, blink_rate, confidence, timestamp } = req.body;

    if (!user_email || typeof ear_value !== 'number' || !status) {
      return res.status(400).json({ message: 'user_email, ear_value (number), and status are required' });
    }

    // Look up user by email
    const userResult = await query(
      'SELECT id FROM users WHERE email = $1',
      [user_email]
    );

    if (userResult.rows.length === 0) {
      return res.status(404).json({ message: `User not found with email: ${user_email}` });
    }

    const userId = userResult.rows[0].id;
    const logTimestamp = timestamp ? new Date(timestamp) : new Date();

    const insertedLog = await query(
      `
      INSERT INTO drowsiness_logs (user_id, ear_value, status, blink_rate, confidence, timestamp)
      VALUES ($1, $2, $3, $4, $5, $6)
      RETURNING id, user_id, ear_value, status, blink_rate, confidence, timestamp
    `,
      [userId, ear_value, status, blink_rate ?? null, confidence ?? null, logTimestamp]
    );

    const log = mapLogRow(insertedLog.rows[0]);

    // Simple session handling: group by day per driver.
    const sessionDayStart = new Date(log.timestamp);
    sessionDayStart.setHours(0, 0, 0, 0);

    const incAlerts = status === 'DROWSY' || status === 'WARNING' ? 1 : 0;

    const upsertedSession = await query(
      `
      INSERT INTO sessions (user_id, start_time, end_time, total_alerts)
      VALUES ($1, $2, $3, $4)
      ON CONFLICT (user_id, start_time)
      DO UPDATE SET
        end_time = EXCLUDED.end_time,
        total_alerts = sessions.total_alerts + $4,
        updated_at = now()
      RETURNING id, user_id, start_time, end_time, total_alerts
    `,
      [userId, sessionDayStart, log.timestamp, incAlerts]
    );

    const session = mapSessionRow(upsertedSession.rows[0]);

    return res.status(201).json({ log, session });
  } catch (error) {
    // eslint-disable-next-line no-console
    console.error('saveWebcamLog error:', error);
    return res.status(500).json({ message: 'Server error while saving webcam log' });
  }
};

// POST /api/driver/log
// This endpoint is meant to be called after the Python AI service computes EAR + status.
const saveLog = async (req, res) => {
  try {
    const userId = req.user.id;
    const { earValue, status, blinkRate, confidence, timestamp } = req.body;

    if (typeof earValue !== 'number' || !status) {
      return res.status(400).json({ message: 'earValue (number) and status are required' });
    }

    const logTimestamp = timestamp ? new Date(timestamp) : new Date();
    const insertedLog = await query(
      `
      INSERT INTO drowsiness_logs (user_id, ear_value, status, blink_rate, confidence, timestamp)
      VALUES ($1, $2, $3, $4, $5, $6)
      RETURNING id, user_id, ear_value, status, blink_rate, confidence, timestamp
    `,
      [userId, earValue, status, blinkRate ?? null, confidence ?? null, logTimestamp]
    );

    const log = mapLogRow(insertedLog.rows[0]);

    // Simple session handling: group by day per driver.
    const sessionDayStart = new Date(log.timestamp);
    sessionDayStart.setHours(0, 0, 0, 0);

    const incAlerts = status === 'DROWSY' || status === 'WARNING' ? 1 : 0;

    const upsertedSession = await query(
      `
      INSERT INTO sessions (user_id, start_time, end_time, total_alerts)
      VALUES ($1, $2, $3, $4)
      ON CONFLICT (user_id, start_time)
      DO UPDATE SET
        end_time = EXCLUDED.end_time,
        total_alerts = sessions.total_alerts + $4,
        updated_at = now()
      RETURNING id, user_id, start_time, end_time, total_alerts
    `,
      [userId, sessionDayStart, log.timestamp, incAlerts]
    );

    const session = mapSessionRow(upsertedSession.rows[0]);

    return res.status(201).json({ log, session });
  } catch (error) {
    // eslint-disable-next-line no-console
    console.error('saveLog error:', error);
    return res.status(500).json({ message: 'Server error while saving log' });
  }
};

// GET /api/driver/logs
const getDriverLogs = async (req, res) => {
  try {
    const userId = req.user.id;
    const { limit = 50 } = req.query;

    const limitNum = Math.max(1, Math.min(500, Number(limit) || 50));
    const result = await query(
      `
      SELECT id, user_id, ear_value, status, blink_rate, confidence, timestamp
      FROM drowsiness_logs
      WHERE user_id = $1
      ORDER BY timestamp DESC
      LIMIT $2
    `,
      [userId, limitNum]
    );
    const logs = result.rows.map(mapLogRow);

    return res.json({ logs });
  } catch (error) {
    // eslint-disable-next-line no-console
    console.error('getDriverLogs error:', error);
    return res.status(500).json({ message: 'Server error while fetching logs' });
  }
};

// GET /api/driver/session
// Returns a high-level summary for the current (today's) driving session.
const getCurrentSession = async (req, res) => {
  try {
    const userId = req.user.id;

    const now = new Date();
    const dayStart = new Date(now);
    dayStart.setHours(0, 0, 0, 0);

    const sessionResult = await query(
      `
      SELECT id, user_id, start_time, end_time, total_alerts
      FROM sessions
      WHERE user_id = $1 AND start_time >= $2
      ORDER BY start_time DESC
      LIMIT 1
    `,
      [userId, dayStart]
    );
    const session = sessionResult.rows[0]
      ? mapSessionRow(sessionResult.rows[0])
      : null;

    const logsResult = await query(
      `
      SELECT id, user_id, ear_value, status, blink_rate, confidence, timestamp
      FROM drowsiness_logs
      WHERE user_id = $1 AND timestamp >= $2
      ORDER BY timestamp ASC
    `,
      [userId, dayStart]
    );
    const logs = logsResult.rows.map(mapLogRow);

    const response = {
      session,
      metrics: {
        totalLogs: logs.length,
        totalAlerts: logs.filter(
          (l) => l.status === 'DROWSY' || l.status === 'WARNING'
        ).length,
        firstEventAt: logs[0]?.timestamp || null,
        lastEventAt: logs[logs.length - 1]?.timestamp || null,
      },
    };

    return res.json(response);
  } catch (error) {
    // eslint-disable-next-line no-console
    console.error('getCurrentSession error:', error);
    return res.status(500).json({ message: 'Server error while fetching session' });
  }
};

module.exports = {
  saveLog,
  saveWebcamLog,
  getDriverLogs,
  getCurrentSession,
};


