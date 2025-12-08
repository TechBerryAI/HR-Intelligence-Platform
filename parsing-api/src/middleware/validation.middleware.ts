import { Request, Response, NextFunction } from 'express';
import Joi from 'joi';
import logger from '../utils/logger.js';

/**
 * Validation schema for parse request
 */
const parseRequestSchema = Joi.object({
  endpoint_type: Joi.string().valid('resume', 'jd').required(),
  raw_file_id: Joi.string().uuid().optional(),
});

/**
 * Validate parse request body
 */
export function validateParseRequest(req: Request, res: Response, next: NextFunction): void {
  const { error } = parseRequestSchema.validate(req.body);
  
  if (error) {
    logger.warn('Validation error', {
      path: req.path,
      error: error.details[0].message,
    });
    
    res.status(400).json({
      status: 'error',
      error: `Validation error: ${error.details[0].message}`,
    });
    return;
  }
  
  next();
}

/**
 * Validate file was uploaded
 */
export function validateFileUpload(req: Request, res: Response, next: NextFunction): void {
  if (!req.file) {
    logger.warn('No file uploaded', { path: req.path });
    res.status(400).json({
      status: 'error',
      error: 'No file uploaded. Send file as multipart/form-data with field name "file".',
    });
    return;
  }
  
  next();
}

export default {
  validateParseRequest,
  validateFileUpload,
};

