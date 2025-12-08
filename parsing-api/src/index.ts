import express, { Request, Response, NextFunction } from 'express';
import cors from 'cors';
import helmet from 'helmet';
import rateLimit from 'express-rate-limit';
import config from './config/index.js';
import logger from './utils/logger.js';
import { authenticateApiKey } from './middleware/auth.middleware.js';
import parseRoutes from './routes/parse.routes.js';
import fs from 'fs';
import path from 'path';

const app = express();

// Create logs directory if it doesn't exist
const logsDir = path.join(process.cwd(), 'logs');
if (!fs.existsSync(logsDir)) {
  fs.mkdirSync(logsDir, { recursive: true });
}

// Security middleware
app.use(helmet());
app.use(cors({
  origin: config.nodeEnv === 'production' 
    ? process.env.ALLOWED_ORIGINS?.split(',') || []
    : '*',
  credentials: true,
}));

// Rate limiting
const limiter = rateLimit({
  windowMs: config.rateLimiting.windowMs,
  max: config.rateLimiting.maxRequests,
  message: {
    status: 'error',
    error: 'Too many requests. Please try again later.',
  },
  standardHeaders: true,
  legacyHeaders: false,
});

app.use('/api', limiter);

// Body parser
app.use(express.json());
app.use(express.urlencoded({ extended: true }));

// Request logging
app.use((req: Request, res: Response, next: NextFunction) => {
  logger.info('Incoming request', {
    method: req.method,
    path: req.path,
    ip: req.ip,
    userAgent: req.get('user-agent'),
  });
  next();
});

// Health check endpoint (no auth required)
app.get('/health', (req: Request, res: Response) => {
  res.json({
    status: 'ok',
    service: 'parsing-api',
    version: '1.0.0',
    timestamp: new Date().toISOString(),
    uptime: process.uptime(),
    provider: config.llm.provider,
  });
});

// API routes (require authentication)
app.use('/api/v1/parse', authenticateApiKey, parseRoutes);

// 404 handler
app.use((req: Request, res: Response) => {
  logger.warn('404 Not Found', { path: req.path, method: req.method });
  res.status(404).json({
    status: 'error',
    error: 'Endpoint not found',
  });
});

// Global error handler
app.use((err: Error, req: Request, res: Response, next: NextFunction) => {
  logger.error('Unhandled error', {
    error: err.message,
    stack: err.stack,
    path: req.path,
    method: req.method,
  });
  
  res.status(500).json({
    status: 'error',
    error: config.nodeEnv === 'production' 
      ? 'Internal server error' 
      : err.message,
  });
});

// Start server
app.listen(config.port, () => {
  logger.info(`Parsing API started`, {
    port: config.port,
    nodeEnv: config.nodeEnv,
    llmProvider: config.llm.provider,
  });
  
  console.log(`
╔═══════════════════════════════════════════════════════╗
║                                                       ║
║   🚀 Parsing API Microservice                        ║
║                                                       ║
║   Status: ✓ Running                                  ║
║   Port: ${config.port}                                        ║
║   Environment: ${config.nodeEnv}                           ║
║   LLM Provider: ${config.llm.provider}                        ║
║                                                       ║
║   Endpoints:                                          ║
║   • GET  /health                                      ║
║   • POST /api/v1/parse/resume                        ║
║   • POST /api/v1/parse/jd                            ║
║                                                       ║
╚═══════════════════════════════════════════════════════╝
  `);
});

export default app;

