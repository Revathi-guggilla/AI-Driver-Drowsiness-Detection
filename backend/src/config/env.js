const dotenv = require('dotenv');

dotenv.config();

const env = {
  nodeEnv: process.env.NODE_ENV || 'development',
  port: process.env.PORT || 5000,
  // PostgreSQL (preferred)
  // Example: postgres://postgres:password@localhost:5432/ai_driver_drowsiness
  databaseUrl:
    process.env.DATABASE_URL ||
    process.env.POSTGRES_URL ||
    'postgres://postgres:postgres@localhost:5432/ai_driver_drowsiness',
  // Set to "true" if you're using a hosted Postgres that requires SSL
  pgSsl: (process.env.PG_SSL || '').toLowerCase() === 'true',
  jwtSecret: process.env.JWT_SECRET || 'change_this_jwt_secret_in_env',
  clientUrl: process.env.CLIENT_URL || 'http://localhost:3000',
};

module.exports = env;


