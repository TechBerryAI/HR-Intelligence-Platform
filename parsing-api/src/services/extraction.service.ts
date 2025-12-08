import pdfParse from 'pdf-parse';
import mammoth from 'mammoth';
import logger from '../utils/logger.js';
import config from '../config/index.js';

export interface ExtractionResult {
  text: string;
  pageCount?: number;
  wordCount: number;
}

/**
 * Extract text from PDF file
 */
export async function extractPDF(buffer: Buffer): Promise<ExtractionResult> {
  const startTime = Date.now();
  
  try {
    const data = await Promise.race([
      pdfParse(buffer),
      new Promise<never>((_, reject) => 
        setTimeout(() => reject(new Error('PDF extraction timeout')), config.timeouts.pdfExtraction)
      ),
    ]);
    
    const text = data.text.trim();
    const wordCount = text.split(/\s+/).length;
    
    logger.info('PDF extracted successfully', {
      pageCount: data.numpages,
      wordCount,
      duration: Date.now() - startTime,
    });
    
    return {
      text,
      pageCount: data.numpages,
      wordCount,
    };
  } catch (error) {
    logger.error('PDF extraction failed', { error: error instanceof Error ? error.message : 'Unknown error' });
    throw new Error(`Failed to extract PDF: ${error instanceof Error ? error.message : 'Unknown error'}`);
  }
}

/**
 * Extract text from DOCX file
 */
export async function extractDOCX(buffer: Buffer): Promise<ExtractionResult> {
  const startTime = Date.now();
  
  try {
    const result = await Promise.race([
      mammoth.extractRawText({ buffer }),
      new Promise<never>((_, reject) => 
        setTimeout(() => reject(new Error('DOCX extraction timeout')), config.timeouts.pdfExtraction)
      ),
    ]);
    
    const text = result.value.trim();
    const wordCount = text.split(/\s+/).length;
    
    logger.info('DOCX extracted successfully', {
      wordCount,
      duration: Date.now() - startTime,
    });
    
    return {
      text,
      wordCount,
    };
  } catch (error) {
    logger.error('DOCX extraction failed', { error: error instanceof Error ? error.message : 'Unknown error' });
    throw new Error(`Failed to extract DOCX: ${error instanceof Error ? error.message : 'Unknown error'}`);
  }
}

/**
 * Extract text from DOC file (legacy format)
 */
export async function extractDOC(buffer: Buffer): Promise<ExtractionResult> {
  // DOC files are harder to parse, we'll use mammoth which handles some DOC files
  // For production, consider using a more robust solution like LibreOffice conversion
  return extractDOCX(buffer);
}

/**
 * Normalize extracted text
 * - Remove excessive whitespace
 * - Fix common OCR errors
 * - Standardize line breaks
 */
export function normalizeText(text: string): string {
  return text
    // Remove multiple spaces
    .replace(/\s+/g, ' ')
    // Remove multiple line breaks (keep max 2)
    .replace(/\n{3,}/g, '\n\n')
    // Trim each line
    .split('\n')
    .map(line => line.trim())
    .join('\n')
    // Remove leading/trailing whitespace
    .trim();
}

/**
 * Main extraction function - routes to appropriate extractor based on mime type
 */
export async function extractDocument(buffer: Buffer, mimeType: string): Promise<ExtractionResult> {
  logger.info('Starting document extraction', { mimeType, size: buffer.length });
  
  let result: ExtractionResult;
  
  switch (mimeType) {
    case 'application/pdf':
      result = await extractPDF(buffer);
      break;
    case 'application/vnd.openxmlformats-officedocument.wordprocessingml.document':
      result = await extractDOCX(buffer);
      break;
    case 'application/msword':
      result = await extractDOC(buffer);
      break;
    default:
      throw new Error(`Unsupported file type: ${mimeType}`);
  }
  
  // Normalize the extracted text
  result.text = normalizeText(result.text);
  
  logger.info('Document extraction complete', {
    mimeType,
    wordCount: result.wordCount,
    textLength: result.text.length,
  });
  
  return result;
}

