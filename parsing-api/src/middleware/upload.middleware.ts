import multer from 'multer';
import { Request } from 'express';
import config from '../config/index.js';
import logger from '../utils/logger.js';

const maxFileSize = config.upload.maxFileSizeMB * 1024 * 1024;

/**
 * File filter for multer
 * Checks both MIME type and file extension (browsers sometimes set incorrect MIME types)
 */
function fileFilter(req: Request, file: Express.Multer.File, cb: multer.FileFilterCallback): void {
  const allowedExtensions = ['.pdf', '.doc', '.docx'];
  const fileExt = file.originalname.toLowerCase().slice(file.originalname.lastIndexOf('.'));
  
  // Check MIME type first
  if (config.upload.allowedMimeTypes.includes(file.mimetype)) {
    cb(null, true);
  }
  // Fallback to extension check (more reliable for some browsers)
  else if (allowedExtensions.includes(fileExt)) {
    logger.info('Accepting file based on extension (MIME type mismatch)', {
      mimetype: file.mimetype,
      filename: file.originalname,
      extension: fileExt,
    });
    cb(null, true);
  }
  // Reject if neither check passes
  else {
    logger.warn('Rejected file with invalid type', {
      mimetype: file.mimetype,
      filename: file.originalname,
      extension: fileExt,
    });
    cb(new Error(`Invalid file type. Please upload PDF, DOC, or DOCX files only.`));
  }
}

/**
 * Multer configuration - store files in memory as buffers
 */
export const upload = multer({
  storage: multer.memoryStorage(),
  limits: {
    fileSize: maxFileSize,
    files: 1,
  },
  fileFilter,
});

export default upload;

