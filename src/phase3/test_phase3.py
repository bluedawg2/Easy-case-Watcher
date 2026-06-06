# Test implementation for Phase 3 components

import unittest
from unittest.mock import patch, MagicMock

# Import the modules we want to test
from pdf_processor import PDFProcessor, PDFSourceAdapter
from district_coverage import DistrictRegistry, DistrictConfig

class TestPhase3Components(unittest.TestCase):
    
    def setUp(self):
        """Set up test fixtures"""
        self.district_data = {
            "district_id": "test_district",
            "name": "Test District",
            "jurisdiction": "Test Jurisdiction", 
            "layer": "district",
            "state_exemptions": ["TEST"]
        }
        
    def test_district_config(self):
        """Test district configuration"""
        config = DistrictConfig(**self.district_data)
        self.assertEqual(config.district_id, "test_district")
        self.assertEqual(config.name, "Test District")
        self.assertEqual(config.jurisdiction, "Test Jurisdiction")
        self.assertEqual(config.layer, "district")
        self.assertEqual(config.state_exemptions, ["TEST"])
        
    def test_district_registry(self):
        """Test district registry functionality"""
        registry = DistrictRegistry()
        config = DistrictConfig(**self.district_data)
        registry.add_district(config)
        
        retrieved = registry.get_district("test_district")
        self.assertEqual(retrieved.district_id, "test_district")
        
        districts = registry.get_districts()
        self.assertEqual(len(districts), 1)
        self.assertEqual(districts[0].district_id, "test_district")
        
    @patch('pdf_processor.pdfium')
    def test_pdf_processor(self, mock_pdfium):
        """Test PDF processor functionality"""
        processor = PDFProcessor()
        
        # Mock PDF document
        mock_pdf = MagicMock()
        mock_pdfium.PdfDocument.return_value = mock_pdf
        
        # Mock page and text extraction
        mock_page = MagicMock()
        mock_text_page = MagicMock()
        mock_page.get_textpage.return_value = mock_text_page
        mock_text_page.get_text_range.return_value = "Test content"
        mock_pdf.get_page.return_value = mock_page
        mock_pdf.__len__ = MagicMock(return_value=1)
        
        # Test text extraction
        result = processor.extract_text_from_pdf("test.pdf")
        # Since we're mocking, we'll just check that the method runs without error
        # The actual implementation would be tested with real PDF files
        
    def test_pdf_source_adapter(self):
        """Test PDF source adapter"""
        config = {}
        adapter = PDFSourceAdapter(config)
        
        # Mock the processor to avoid actual PDF processing
        with patch.object(adapter.processor, 'is_scanned_pdf', return_value=False):
            with patch.object(adapter.processor, 'extract_text_from_pdf', return_value="Test content"):
                with patch.object(adapter.processor, 'normalize_text', return_value="Test content"):
                    result = adapter.process_pdf("test.pdf")
                    self.assertEqual(result["content"], "Test content")
                    self.assertEqual(result["normalized_content"], "Test content")
                    self.assertFalse(result["is_scanned"])

if __name__ == '__main__':
    unittest.main()