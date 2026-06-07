const { Pool } = require('pg');
require('dotenv').config();

const pool = new Pool({
  connectionString: process.env.DATABASE_URL,
});

async function check() {
  try {
    const res = await pool.query("SELECT email FROM users");
    console.log("Registered emails:");
    res.rows.forEach(row => console.log(row.email));
  } catch (err) {
    console.error("Database error:", err.message);
  } finally {
    await pool.end();
  }
}

check();
