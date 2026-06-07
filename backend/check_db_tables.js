const { Pool } = require('pg');
require('dotenv').config();

const pool = new Pool({
  connectionString: process.env.DATABASE_URL,
});

async function check() {
  try {
    const res = await pool.query("SELECT table_name FROM information_schema.tables WHERE table_schema='public'");
    console.log("Tables found:");
    res.rows.forEach(row => console.log(row.table_name));
    
    const userCount = await pool.query("SELECT COUNT(*) FROM users");
    console.log(`Total users: ${userCount.rows[0].count}`);
  } catch (err) {
    console.error("Database error:", err.message);
  } finally {
    await pool.end();
  }
}

check();
