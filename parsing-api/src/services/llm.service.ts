import OpenAI from 'openai';
import Anthropic from '@anthropic-ai/sdk';
import axios from 'axios';
import config from '../config/index.js';
import logger from '../utils/logger.js';
import type { ClassificationResult, TOON, ResumeTOON, JDTOON } from '../../../shared/types/toon.js';

/**
 * Initialize LLM clients based on configuration
 */
const openaiClient = config.llm.openai.apiKey 
  ? new OpenAI({ apiKey: config.llm.openai.apiKey })
  : null;

const anthropicClient = config.llm.anthropic.apiKey
  ? new Anthropic({ apiKey: config.llm.anthropic.apiKey })
  : null;

/**
 * Classify document type using LLM
 */
export async function classifyDocument(text: string): Promise<ClassificationResult> {
  const startTime = Date.now();
  const prompt = `Analyze the following document text and classify it as either a "resume" or "job_description".
Return ONLY a JSON object with this exact format:
{
  "type": "resume" | "job_description" | "unknown",
  "confidence": 0.0 to 1.0
}

Document text:
${text.substring(0, 2000)}`;

  try {
    let response: ClassificationResult;
    
    switch (config.llm.provider) {
      case 'openai':
        response = await classifyWithOpenAI(prompt);
        break;
      case 'anthropic':
        response = await classifyWithAnthropic(prompt);
        break;
      case 'xai':
        response = await classifyWithXAI(prompt);
        break;
      default:
        throw new Error(`Unknown LLM provider: ${config.llm.provider}`);
    }
    
    logger.info('Document classified', {
      type: response.type,
      confidence: response.confidence,
      duration: Date.now() - startTime,
    });
    
    return response;
  } catch (error) {
    logger.error('Classification failed', { error: error instanceof Error ? error.message : 'Unknown error' });
    throw error;
  }
}

/**
 * Parse document into TOON format using LLM
 */
export async function parseToTOON(text: string, documentType: 'resume' | 'job_description'): Promise<TOON> {
  const startTime = Date.now();
  const prompt = documentType === 'resume' 
    ? getResumeParsingPrompt(text)
    : getJDParsingPrompt(text);
  
  try {
    let toon: TOON;
    
    switch (config.llm.provider) {
      case 'openai':
        toon = await parseWithOpenAI(prompt, documentType);
        break;
      case 'anthropic':
        toon = await parseWithAnthropic(prompt, documentType);
        break;
      case 'xai':
        toon = await parseWithXAI(prompt, documentType);
        break;
      default:
        throw new Error(`Unknown LLM provider: ${config.llm.provider}`);
    }
    
    logger.info('Document parsed to TOON', {
      type: documentType,
      duration: Date.now() - startTime,
      provider: config.llm.provider,
    });
    
    return toon;
  } catch (error) {
    logger.error('TOON parsing failed', { error: error instanceof Error ? error.message : 'Unknown error' });
    throw error;
  }
}

/**
 * OpenAI Classification
 */
async function classifyWithOpenAI(prompt: string): Promise<ClassificationResult> {
  if (!openaiClient) throw new Error('OpenAI client not configured');
  
  const response = await openaiClient.chat.completions.create({
    model: config.llm.openai.model,
    messages: [{ role: 'user', content: prompt }],
    temperature: 0.1,
    response_format: { type: 'json_object' },
  });
  
  const content = response.choices[0].message.content || '{}';
  return JSON.parse(content) as ClassificationResult;
}

/**
 * OpenAI Parsing
 */
async function parseWithOpenAI(prompt: string, documentType: string): Promise<TOON> {
  if (!openaiClient) throw new Error('OpenAI client not configured');
  
  const response = await openaiClient.chat.completions.create({
    model: config.llm.openai.model,
    messages: [{ role: 'user', content: prompt }],
    temperature: 0.1,
    response_format: { type: 'json_object' },
  });
  
  const content = response.choices[0].message.content || '{}';
  const parsed = JSON.parse(content);
  
  return {
    ...parsed,
    type: documentType,
  } as TOON;
}

/**
 * Anthropic Classification
 */
async function classifyWithAnthropic(prompt: string): Promise<ClassificationResult> {
  if (!anthropicClient) throw new Error('Anthropic client not configured');
  
  const response = await anthropicClient.messages.create({
    model: config.llm.anthropic.model,
    max_tokens: 1024,
    messages: [{ role: 'user', content: prompt }],
  });
  
  const content = response.content[0];
  if (content.type !== 'text') throw new Error('Unexpected response type');
  
  // Extract JSON from response
  const jsonMatch = content.text.match(/\{[\s\S]*\}/);
  if (!jsonMatch) throw new Error('No JSON found in response');
  
  return JSON.parse(jsonMatch[0]) as ClassificationResult;
}

/**
 * Anthropic Parsing
 */
async function parseWithAnthropic(prompt: string, documentType: string): Promise<TOON> {
  if (!anthropicClient) throw new Error('Anthropic client not configured');
  
  const response = await anthropicClient.messages.create({
    model: config.llm.anthropic.model,
    max_tokens: 4096,
    messages: [{ role: 'user', content: prompt }],
  });
  
  const content = response.content[0];
  if (content.type !== 'text') throw new Error('Unexpected response type');
  
  // Extract JSON from response
  const jsonMatch = content.text.match(/\{[\s\S]*\}/);
  if (!jsonMatch) throw new Error('No JSON found in response');
  
  const parsed = JSON.parse(jsonMatch[0]);
  
  return {
    ...parsed,
    type: documentType,
  } as TOON;
}

/**
 * X.AI Grok Classification
 */
async function classifyWithXAI(prompt: string): Promise<ClassificationResult> {
  const response = await axios.post(
    `${config.llm.xai.baseUrl}/chat/completions`,
    {
      model: config.llm.xai.model,
      messages: [{ role: 'user', content: prompt }],
      temperature: 0.1,
    },
    {
      headers: {
        'Authorization': `Bearer ${config.llm.xai.apiKey}`,
        'Content-Type': 'application/json',
      },
      timeout: config.timeouts.llmRequest,
    }
  );
  
  const content = response.data.choices[0].message.content;
  const jsonMatch = content.match(/\{[\s\S]*\}/);
  if (!jsonMatch) throw new Error('No JSON found in response');
  
  return JSON.parse(jsonMatch[0]) as ClassificationResult;
}

/**
 * X.AI Grok Parsing
 */
async function parseWithXAI(prompt: string, documentType: string): Promise<TOON> {
  const response = await axios.post(
    `${config.llm.xai.baseUrl}/chat/completions`,
    {
      model: config.llm.xai.model,
      messages: [{ role: 'user', content: prompt }],
      temperature: 0.1,
    },
    {
      headers: {
        'Authorization': `Bearer ${config.llm.xai.apiKey}`,
        'Content-Type': 'application/json',
      },
      timeout: config.timeouts.llmRequest,
    }
  );
  
  const content = response.data.choices[0].message.content;
  const jsonMatch = content.match(/\{[\s\S]*\}/);
  if (!jsonMatch) throw new Error('No JSON found in response');
  
  const parsed = JSON.parse(jsonMatch[0]);
  
  return {
    ...parsed,
    type: documentType,
  } as TOON;
}

/**
 * Resume Parsing Prompt
 */
function getResumeParsingPrompt(text: string): string {
  return `Parse the following resume and extract information into this EXACT JSON format:

{
  "person": {
    "name": "Full Name",
    "email": "email@example.com",
    "phone": "+1234567890"
  },
  "summary": "Professional summary or objective",
  "skills": ["skill1", "skill2", "skill3"],
  "experience": [
    {
      "title": "Job Title",
      "company": "Company Name",
      "from": "YYYY-MM",
      "to": "YYYY-MM or Present",
      "years": 2.5,
      "description": "Brief description of role and achievements"
    }
  ],
  "education": [
    {
      "degree": "Degree Name",
      "field": "Field of Study",
      "institution": "University Name",
      "year": "YYYY",
      "gpa": "3.8/4.0"
    }
  ],
  "certifications": ["Cert 1", "Cert 2"],
  "languages": ["English", "Spanish"],
  "total_experience_years": 5
}

Important:
- Extract ALL information accurately
- Use "Present" for current positions
- Calculate years for experience entries
- Calculate total_experience_years as sum of all experience
- If information is missing, use empty string or empty array
- Return ONLY valid JSON, no additional text

Resume text:
${text}`;
}

/**
 * Job Description Parsing Prompt
 */
function getJDParsingPrompt(text: string): string {
  return `Parse the following job description and extract information into this EXACT JSON format:

{
  "title": "Job Title",
  "location": "City, State/Country",
  "employment_type": "Full-time/Part-time/Contract",
  "min_experience_years": 3,
  "max_experience_years": 5,
  "skills": ["skill1", "skill2", "skill3"],
  "responsibilities": ["responsibility1", "responsibility2"],
  "keywords": ["keyword1", "keyword2"],
  "qualifications": ["qualification1", "qualification2"],
  "salary_range": "$80,000 - $120,000",
  "company": "Company Name"
}

Important:
- Extract ALL information accurately
- For experience, parse "3-5 years" as min_experience_years: 3, max_experience_years: 5
- If only one number, set min_experience_years only
- Extract key technical skills separately from requirements
- Include all important keywords for matching
- If information is missing, use empty string, 0, or empty array
- Return ONLY valid JSON, no additional text

Job Description text:
${text}`;
}

export default {
  classifyDocument,
  parseToTOON,
};

