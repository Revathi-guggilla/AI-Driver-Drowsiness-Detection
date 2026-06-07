const express = require('express');
const authMiddleware = require('../middleware/auth.middleware');
const { requireRole } = require('../middleware/role.middleware');
const {
  saveLog,
  getDriverLogs,
  getCurrentSession,
} = require('../controllers/driver.controller');

const router = express.Router();

// Unauthenticated endpoint for webcam mode (called by Python service)
const { saveWebcamLog } = require('../controllers/driver.controller');
router.post('/webcam-log', saveWebcamLog);

// All other driver routes require authenticated driver
router.use(authMiddleware, requireRole('driver'));

router.post('/log', saveLog);
router.get('/logs', getDriverLogs);
router.get('/session', getCurrentSession);

module.exports = router;


