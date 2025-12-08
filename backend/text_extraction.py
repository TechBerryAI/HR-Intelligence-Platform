"""
Text Extraction from PDF and DOCX files
"""
import io
from typing import Optional
import PyPDF2
from docx import Document


def extract_text_from_pdf(file_data: bytes) -> str:
    """
    Extract text from PDF file
    
    Args:
        file_data: PDF file bytes
    
    Returns:
        Extracted text
    """
    try:
        pdf_file = io.BytesIO(file_data)
        pdf_reader = PyPDF2.PdfReader(pdf_file)
        
        text_parts = []
        for page in pdf_reader.pages:
            text = page.extract_text()
            if text:
                text_parts.append(text)
        
        return '\n\n'.join(text_parts)
    except Exception as e:
        raise ValueError(f"Failed to extract text from PDF: {str(e)}")


def extract_text_from_docx(file_data: bytes) -> str:
    """
    Extract text from DOCX file
    
    Args:
        file_data: DOCX file bytes
    
    Returns:
        Extracted text
    """
    try:
        docx_file = io.BytesIO(file_data)
        doc = Document(docx_file)
        
        text_parts = []
        for paragraph in doc.paragraphs:
            if paragraph.text.strip():
                text_parts.append(paragraph.text)
        
        # Also extract text from tables
        for table in doc.tables:
            for row in table.rows:
                for cell in row.cells:
                    if cell.text.strip():
                        text_parts.append(cell.text)
        
        return '\n\n'.join(text_parts)
    except Exception as e:
        raise ValueError(f"Failed to extract text from DOCX: {str(e)}")


def extract_text(file_data: bytes, filename: str) -> str:
    """
    Extract text from file based on extension
    
    Args:
        file_data: File bytes
        filename: Original filename
    
    Returns:
        Extracted text
    """
    ext = filename.lower().rsplit('.', 1)[-1] if '.' in filename else ''
    
    if ext == 'pdf':
        return extract_text_from_pdf(file_data)
    elif ext in ('docx', 'doc'):
        return extract_text_from_docx(file_data)
    else:
        raise ValueError(f"Unsupported file type: {ext}")

