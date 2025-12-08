import dotenv from 'dotenv';

dotenv.config();

export const config = {
  port: parseInt(process.env.PORT || '4000', 10),
  nodeEnv: process.env.NODE_ENV || 'development',
  apiKey: process.env.API_KEY || 'dev-api-key',
  
  llm: {
    provider: process.env.LLM_PROVIDER || 'openai',
    openai: {
      apiKey: process.env.OPENAI_API_KEY || '',
      model: process.env.OPENAI_MODEL || 'gpt-4-turbo-preview',
    },
    anthropic: {
      apiKey: process.env.ANTHROPIC_API_KEY || '',
      model: process.env.ANTHROPIC_MODEL || 'claude-3-sonnet-20240229',
    },
    xai: {
      apiKey: process.env.XAI_API_KEY || '',
      model: process.env.XAI_MODEL || 'grok-beta',
      baseUrl: process.env.XAI_BASE_URL || 'https://api.x.ai/v1',
    },
  },
  
  rateLimiting: {
    windowMs: parseInt(process.env.RATE_LIMIT_WINDOW_MS || '900000', 10),
    maxRequests: parseInt(process.env.RATE_LIMIT_MAX_REQUESTS || '100', 10),
  },
  
  upload: {
    maxFileSizeMB: parseInt(process.env.MAX_FILE_SIZE_MB || '10', 10),
    allowedMimeTypes: (process.env.ALLOWED_MIME_TYPES || 
      'application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document,application/msword')
      .split(','),
  },
  
  timeouts: {
    pdfExtraction: parseInt(process.env.PDF_EXTRACTION_TIMEOUT_MS || '30000', 10),
    llmRequest: parseInt(process.env.LLM_REQUEST_TIMEOUT_MS || '60000', 10),
  },
  
  logging: {
    level: process.env.LOG_LEVEL || 'info',
  },
};

export default config;

