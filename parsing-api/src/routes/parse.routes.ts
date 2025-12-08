import { Router, Request, Response } from 'express';
import { upload } from '../middleware/upload.middleware.js';
import { validateParseRequest, validateFileUpload } from '../middleware/validation.middleware.js';
import { extractDocument } from '../services/extraction.service.js';
import { classifyDocument, parseToTOON } from '../services/llm.service.js';
import logger from '../utils/logger.js';
import config from '../config/index.js';
import type { ParsingResponse } from '../../../shared/types/toon.js';

const router = Router();

/**
 * Parse Resume Endpoint
 * POST /api/v1/parse/resume
 */
router.post('/resume', upload.single('file'), validateFileUpload, async (req: Request, res: Response): Promise<void> => {
  const startTime = Date.now();
  const requestId = `req_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
  
  try {
    logger.info('Resume parsing request received', {
      requestId,
      filename: req.file?.originalname,
      mimetype: req.file?.mimetype,
      size: req.file?.size,
    });
    
    if (!req.file) {
      res.status(400).json({
        status: 'error',
        error: 'No file provided',
      } as ParsingResponse);
      return;
    }
    
    // Extract document text
    const extraction = await extractDocument(req.file.buffer, req.file.mimetype);
    
    // Classify document
    const classification = await classifyDocument(extraction.text);
    
    // Validate it's actually a resume
    if (classification.type === 'job_description') {
      logger.warn('Job description sent to resume endpoint', { requestId });
      res.status(400).json({
        status: 'error',
        document_type: 'job_description',
        confidence: classification.confidence,
        toon: null,
        raw_text: extraction.text.substring(0, 500),
        model_version: getModelVersion(),
        error: 'Document appears to be a job description, not a resume.',
        processing_time_ms: Date.now() - startTime,
      } as ParsingResponse);
      return;
    }
    
    if (classification.type === 'unknown') {
      logger.warn('Unknown document type', { requestId });
      res.status(400).json({
        status: 'error',
        document_type: 'unknown',
        confidence: classification.confidence,
        toon: null,
        raw_text: extraction.text.substring(0, 500),
        model_version: getModelVersion(),
        error: 'Unable to identify document type. Please ensure it is a valid resume.',
        processing_time_ms: Date.now() - startTime,
      } as ParsingResponse);
      return;
    }
    
    // Parse to TOON format
    const toon = await parseToTOON(extraction.text, 'resume');
    
    const processingTime = Date.now() - startTime;
    
    logger.info('Resume parsing completed', {
      requestId,
      confidence: classification.confidence,
      processingTime,
      wordCount: extraction.wordCount,
    });
    
    res.json({
      status: 'ok',
      document_type: 'resume',
      confidence: classification.confidence,
      toon,
      raw_text: extraction.text,
      model_version: getModelVersion(),
      processing_time_ms: processingTime,
    } as ParsingResponse);
    
  } catch (error) {
    const processingTime = Date.now() - startTime;
    logger.error('Resume parsing failed', {
      requestId,
      error: error instanceof Error ? error.message : 'Unknown error',
      stack: error instanceof Error ? error.stack : undefined,
      processingTime,
    });
    
    res.status(500).json({
      status: 'error',
      document_type: 'unknown',
      confidence: 0,
      toon: null,
      raw_text: '',
      model_version: getModelVersion(),
      error: error instanceof Error ? error.message : 'Internal server error',
      processing_time_ms: processingTime,
    } as ParsingResponse);
  }
});

/**
 * Parse Job Description Endpoint
 * POST /api/v1/parse/jd
 */
router.post('/jd', upload.single('file'), validateFileUpload, async (req: Request, res: Response): Promise<void> => {
  const startTime = Date.now();
  const requestId = `req_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
  
  try {
    logger.info('JD parsing request received', {
      requestId,
      filename: req.file?.originalname,
      mimetype: req.file?.mimetype,
      size: req.file?.size,
    });
    
    if (!req.file) {
      res.status(400).json({
        status: 'error',
        error: 'No file provided',
      } as ParsingResponse);
      return;
    }
    
    // Extract document text
    const extraction = await extractDocument(req.file.buffer, req.file.mimetype);
    
    // Classify document
    const classification = await classifyDocument(extraction.text);
    
    // Validate it's actually a job description
    if (classification.type === 'resume') {
      logger.warn('Resume sent to JD endpoint', { requestId });
      res.status(400).json({
        status: 'error',
        document_type: 'resume',
        confidence: classification.confidence,
        toon: null,
        raw_text: extraction.text.substring(0, 500),
        model_version: getModelVersion(),
        error: 'Document appears to be a resume, not a job description.',
        processing_time_ms: Date.now() - startTime,
      } as ParsingResponse);
      return;
    }
    
    if (classification.type === 'unknown') {
      logger.warn('Unknown document type', { requestId });
      res.status(400).json({
        status: 'error',
        document_type: 'unknown',
        confidence: classification.confidence,
        toon: null,
        raw_text: extraction.text.substring(0, 500),
        model_version: getModelVersion(),
        error: 'Unable to identify document type. Please ensure it is a valid job description.',
        processing_time_ms: Date.now() - startTime,
      } as ParsingResponse);
      return;
    }
    
    // Parse to TOON format
    const toon = await parseToTOON(extraction.text, 'job_description');
    
    const processingTime = Date.now() - startTime;
    
    logger.info('JD parsing completed', {
      requestId,
      confidence: classification.confidence,
      processingTime,
      wordCount: extraction.wordCount,
    });
    
    res.json({
      status: 'ok',
      document_type: 'job_description',
      confidence: classification.confidence,
      toon,
      raw_text: extraction.text,
      model_version: getModelVersion(),
      processing_time_ms: processingTime,
    } as ParsingResponse);
    
  } catch (error) {
    const processingTime = Date.now() - startTime;
    logger.error('JD parsing failed', {
      requestId,
      error: error instanceof Error ? error.message : 'Unknown error',
      stack: error instanceof Error ? error.stack : undefined,
      processingTime,
    });
    
    res.status(500).json({
      status: 'error',
      document_type: 'unknown',
      confidence: 0,
      toon: null,
      raw_text: '',
      model_version: getModelVersion(),
      error: error instanceof Error ? error.message : 'Internal server error',
      processing_time_ms: processingTime,
    } as ParsingResponse);
  }
});

/**
 * Get current model version
 */
function getModelVersion(): string {
  const provider = config.llm.provider;
  const models: Record<string, string> = {
    openai: config.llm.openai.model,
    anthropic: config.llm.anthropic.model,
    xai: config.llm.xai.model,
  };
  return `${provider}-${models[provider] || 'unknown'}`;
}

export default router;

