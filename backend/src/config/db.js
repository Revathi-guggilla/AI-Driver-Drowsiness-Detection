const { Pool } = require('pg');
const env = require('./env');

const RETRY_SECONDS = 15;

let pool;
let dbConnected = false;

const getPool = () => {
  if (!pool) {
    pool = new Pool({
      connectionString: env.databaseUrl,
      ssl: env.pgSsl ? { rejectUnauthorized: false } : undefined,
    });
  }
  return pool;
};

const ensureSchema = async () => {
  const p = getPool();

  // Users
  await p.query(`
    CREATE TABLE IF NOT EXISTS users (
      id uuid PRIMARY KEY,
      name text NOT NULL,
      email text NOT NULL UNIQUE,
      password_hash text NOT NULL,
      role text NOT NULL CHECK (role IN ('driver', 'admin')),
      created_at timestamptz NOT NULL DEFAULT now(),
      updated_at timestamptz NOT NULL DEFAULT now()
    );
  `);

  // Sessions (grouped by day; start_time is day start)
  await p.query(`
    CREATE TABLE IF NOT EXISTS sessions (
      id bigserial PRIMARY KEY,
      user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
      start_time timestamptz NOT NULL,
      end_time timestamptz DEFAULT NULL,
      total_alerts integer NOT NULL DEFAULT 0,
      created_at timestamptz NOT NULL DEFAULT now(),
      updated_at timestamptz NOT NULL DEFAULT now(),
      UNIQUE (user_id, start_time)
    );
  `);

  // Drowsiness logs
  await p.query(`
    CREATE TABLE IF NOT EXISTS drowsiness_logs (
      id bigserial PRIMARY KEY,
      user_id uuid NOT NULL REFERENCES users(id) ON DELETE CASCADE,
      ear_value double precision NOT NULL,
      status text NOT NULL CHECK (status IN ('AWAKE', 'WARNING', 'DROWSY')),
      blink_rate integer DEFAULT NULL,
      confidence double precision DEFAULT NULL CHECK (confidence IS NULL OR (confidence >= 0 AND confidence <= 1)),
      timestamp timestamptz NOT NULL DEFAULT now()
    );
  `);

  // Dataset mode results (offline evaluation per video)
  await p.query(`
    CREATE TABLE IF NOT EXISTS dataset_results (
      id bigserial PRIMARY KEY,
      source text NOT NULL DEFAULT 'DATASET',
      video_name text NOT NULL,
      avg_ear double precision NOT NULL,
      min_ear double precision NOT NULL,
      blink_rate integer NOT NULL DEFAULT 0,
      label text NOT NULL CHECK (label IN ('AWAKE', 'DROWSY')),
      predicted text NOT NULL CHECK (predicted IN ('AWAKE', 'DROWSY')),
      created_at timestamptz NOT NULL DEFAULT now()
    );
  `);

  await p.query(
    `CREATE INDEX IF NOT EXISTS idx_drowsiness_logs_user_time ON drowsiness_logs(user_id, timestamp DESC);`
  );
  await p.query(
    `CREATE INDEX IF NOT EXISTS idx_drowsiness_logs_time ON drowsiness_logs(timestamp DESC);`
  );
  await p.query(
    `CREATE INDEX IF NOT EXISTS idx_sessions_user_start ON sessions(user_id, start_time DESC);`
  );
  await p.query(
    `CREATE INDEX IF NOT EXISTS idx_dataset_results_created ON dataset_results(created_at DESC);`
  );
};

const connectDB = async () => {
  try {
    const p = getPool();
    await p.query('SELECT 1');
    await ensureSchema();
    dbConnected = true;
    // eslint-disable-next-line no-console
    console.log('✅ PostgreSQL connected');
  } catch (error) {
    dbConnected = false;
    // eslint-disable-next-line no-console
    console.error(
      '❌ PostgreSQL connection error:',
      error?.message || String(error)
    );
    // eslint-disable-next-line no-console
    if (error?.code) console.error('   → code:', error.code);
    // eslint-disable-next-line no-console
    console.log(`   → Retrying connection in ${RETRY_SECONDS}s...`);
    setTimeout(connectDB, RETRY_SECONDS * 1000);
  }
};

const isDbConnected = () => dbConnected;

const query = (text, params) => getPool().query(text, params);

module.exports = connectDB;
module.exports.isDbConnected = isDbConnected;
module.exports.query = query;


