const http = require('http');
const app = require('./src/app');
const connectDB = require('./src/config/db');
const env = require('./src/config/env');

const server = http.createServer(app);

const start = async () => {
  await connectDB();

  server.listen(env.port, () => {
    // eslint-disable-next-line no-console
    console.log(
      `🚀 Server running in ${env.nodeEnv} mode on port ${env.port}`
    );
  });
};

start().catch((error) => {
  // eslint-disable-next-line no-console
  console.error('Failed to start server:', error);
  process.exit(1);
});


