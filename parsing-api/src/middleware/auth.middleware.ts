import { Request, Response, NextFunction } from 'express';
import config from '../config/index.js';
import logger from '../utils/logger.js';

/**
 * API Key Authentication Middleware
 */
export function authenticateApiKey(req: Request, res: Response, next: NextFunction): void {
  const apiKey = req.headers['x-api-key'] as string;
  
  if (!apiKey) {
    logger.warn('Missing API key in request', { path: req.path, ip: req.ip });
    res.status(401).json({
      status: 'error',
      error: 'Missing API key. Include X-API-Key header.',
    });
    return;
  }
  
  if (apiKey !== config.apiKey) {
    logger.warn('Invalid API key attempt', { path: req.path, ip: req.ip });
    res.status(403).json({
      status: 'error',
      error: 'Invalid API key.',
    });
    return;
  }
  
  next();
}

export default {
  authenticateApiKey,
};

