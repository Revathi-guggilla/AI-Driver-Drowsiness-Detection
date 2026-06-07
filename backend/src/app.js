const express = require('express');
const cors = require('cors');
const morgan = require('morgan');
const env = require('./config/env');

const authRoutes = require('./routes/auth.routes');
const driverRoutes = require('./routes/driver.routes');
const adminRoutes = require('./routes/admin.routes');

const app = express();

const allowedOrigins = [
  env.clientUrl,
  'http://localhost:3000',
  'http://localhost:3001',
  'http://127.0.0.1:3000',
  'http://127.0.0.1:3001',
];

app.use(
  cors({
    origin: (origin, callback) => {
      if (!origin) return callback(null, true);
      if (allowedOrigins.includes(origin)) {
        return callback(null, true);
      }
      return callback(new Error('CORS block'), false);
    },
    credentials: true,
  })
);
app.use(express.json());

if (env.nodeEnv !== 'test') {
  app.use(morgan('dev'));
}

// Health check
app.get('/api/health', (req, res) =>
  res.json({ status: 'ok', service: 'ai-driver-drowsiness-backend' })
);

// API routes
app.use('/api/auth', authRoutes);
app.use('/api/driver', driverRoutes);
app.use('/api/admin', adminRoutes);

// 404 handler
app.use((req, res) => {
  return res.status(404).json({ message: 'Route not found' });
});

module.exports = app;


