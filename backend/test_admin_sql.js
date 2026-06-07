const { Pool } = require('pg');
require('dotenv').config();

const pool = new Pool({
  connectionString: process.env.DATABASE_URL,
});

async function check() {
  try {
    const res = await pool.query("SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'sessions'");
    console.log("Columns:", JSON.stringify(res.rows));
  } catch (err) {
    console.error("PG ERROR:", err.message);
  } finally {
    await pool.end();
  }
}

check();
