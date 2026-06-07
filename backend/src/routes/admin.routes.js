const express = require('express');
const authMiddleware = require('../middleware/auth.middleware');
const { requireRole } = require('../middleware/role.middleware');
const {
  getStats,
  getAllLogs,
  getAnalytics,
} = require('../controllers/admin.controller');

const router = express.Router();

// All admin routes require authenticated admin
router.use(authMiddleware, requireRole('admin'));

router.get('/stats', getStats);
router.get('/logs', getAllLogs);
router.get('/analytics', getAnalytics);

module.exports = router;


