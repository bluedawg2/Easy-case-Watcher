# PDF Processor Implementation
# This is a sample implementation for Phase 3 functionality

import pypdfium2 as pdfium
import io
from typing import Optional, Dict, Any
import hashlib

class PDFProcessor:
    def __init__(self):
        pass
        
    def extract_text_from_pdf(self, pdf_path: str) -> Optional[str]:
        """Extract text from PDF using pypdfium2"""
        try:
            # Open the PDF
            pdf = pdfium.PdfDocument(pdf_path)
            
            # Extract text from all pages
            text = ""
            for page_number in range(len(pdf)):
                page = pdf.get_page(page_number)
                text_page = page.get_textpage()
                text += text_page.get_text_range() + "\n"
                text_page.close()
                page.close()
            
            pdf.close()
            return text if text.strip() else None
        except Exception as e:
            print(f"Error extracting text from PDF {pdf_path}: {e}")
            return None
            
    def is_scanned_pdf(self, pdf_path: str) -> bool:
        """Detect if PDF is scanned (image-only)"""
        try:
            pdf = pdfium.PdfDocument(pdf_path)
            is_scanned = True
            
            # Check if PDF has text layer
            for page_number in range(min(3, len(pdf))):  # Check first 3 pages
                page = pdf.get_page(page_number)
                text_page = page.get_textpage()
                if text_page.get_text_range().strip():
                    is_scanned = False
                    text_page.close()
                    page.close()
                    break
                text_page.close()
                page.close()
                
            pdf.close()
            return is_scanned
        except Exception as e:
            print(f"Error checking if PDF is scanned {pdf_path}: {e}")
            return False
            
    def normalize_text(self, text: str) -> str:
        """Normalize extracted text"""
        if not text:
            return ""
            
        # Remove hyphens at line breaks
        lines = text.split('\n')
        normalized_lines = []
        for line in lines:
            # Remove trailing hyphens that might be line continuation
            if line.endswith('-'):
                line = line[:-1]  # Remove the hyphen
            normalized_lines.append(line)
            
        # Join lines and clean up
        normalized_text = '\n'.join(normalized_lines)
        
        # Remove extra whitespace
        normalized_text = ' '.join(normalized_text.split())
        
        return normalized_text

class PDFSourceAdapter:
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.processor = PDFProcessor()
        
    def process_pdf(self, pdf_path: str) -> Dict[str, Any]:
        """Process a PDF through the full pipeline"""
        result = {
            "content": None,
            "is_scanned": False,
            "normalized_content": None,
            "error": None
        }
        
        try:
            # Check if PDF is scanned
            result["is_scanned"] = self.processor.is_scanned_pdf(pdf_path)
            
            # Extract text if not scanned
            if not result["is_scanned"]:
                content = self.processor.extract_text_from_pdf(pdf_path)
                if content:
                    result["content"] = content
                    result["normalized_content"] = self.processor.normalize_text(content)
            else:
                # For scanned PDFs, would route to OCR
                result["error"] = "Scanned PDF requires OCR processing"
                
        except Exception as e:
            result["error"] = str(e)
            
        return result

# Example usage
def main():
    # Configuration for PDF processing
    config = {
        'district': 'example',
        'jurisdiction': 'federal'
    }
    
    # Initialize components
    adapter = PDFSourceAdapter(config)
    
    # Process a PDF
    result = adapter.process_pdf("example.pdf")
    print(f"PDF processing result: {result}")

if __name__ == "__main__":
    main()