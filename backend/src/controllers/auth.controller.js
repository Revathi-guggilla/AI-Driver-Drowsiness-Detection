const bcrypt = require('bcryptjs');
const { randomUUID } = require('crypto');
const jwt = require('jsonwebtoken');
const env = require('../config/env');
const { isDbConnected, query } = require('../config/db');

const generateToken = (user) =>
  jwt.sign(
    {
      id: user.id,
      role: user.role,
      email: user.email,
    },
    env.jwtSecret,
    { expiresIn: '8h' }
  );

// POST /api/auth/register
const register = async (req, res) => {
  if (!isDbConnected()) {
    return res.status(503).json({ message: 'Database unavailable. Please try again later.' });
  }
  try {
    const { name, email, password, role } = req.body;

    if (!name || !email || !password) {
      return res.status(400).json({ message: 'Name, email and password are required' });
    }

    const normalizedEmail = email.toLowerCase();
    const existing = await query('SELECT id FROM users WHERE email = $1 LIMIT 1', [
      normalizedEmail,
    ]);
    if (existing.rows.length > 0) {
      return res.status(409).json({ message: 'Email already registered' });
    }

    const hashedPassword = await bcrypt.hash(password, 10);

    const userId = randomUUID();
    const userRole = role === 'admin' ? 'admin' : 'driver';
    const inserted = await query(
      `
      INSERT INTO users (id, name, email, password_hash, role)
      VALUES ($1, $2, $3, $4, $5)
      RETURNING id, name, email, role
    `,
      [userId, name, normalizedEmail, hashedPassword, userRole]
    );

    const user = inserted.rows[0];

    const token = generateToken(user);

    return res.status(201).json({
      user: {
        id: user.id,
        name: user.name,
        email: user.email,
        role: user.role,
      },
      token,
    });
  } catch (error) {
    // eslint-disable-next-line no-console
    console.error('Register error:', error);
    return res.status(500).json({ message: 'Server error during registration' });
  }
};

// POST /api/auth/login
const login = async (req, res) => {
  if (!isDbConnected()) {
    return res.status(503).json({ message: 'Database unavailable. Please try again later.' });
  }
  try {
    const { email, password } = req.body;

    if (!email || !password) {
      return res.status(400).json({ message: 'Email and password are required' });
    }

    const normalizedEmail = email.toLowerCase();
    const result = await query(
      'SELECT id, name, email, role, password_hash FROM users WHERE email = $1 LIMIT 1',
      [normalizedEmail]
    );
    if (result.rows.length === 0) {
      return res.status(401).json({ message: 'Invalid credentials' });
    }

    const user = result.rows[0];

    const isMatch = await bcrypt.compare(password, user.password_hash);
    if (!isMatch) {
      return res.status(401).json({ message: 'Invalid credentials' });
    }

    const token = generateToken(user);

    return res.json({
      user: {
        id: user.id,
        name: user.name,
        email: user.email,
        role: user.role,
      },
      token,
    });
  } catch (error) {
    // eslint-disable-next-line no-console
    console.error('Login error:', error);
    return res.status(500).json({ message: 'Server error during login' });
  }
};

module.exports = {
  register,
  login,
};


