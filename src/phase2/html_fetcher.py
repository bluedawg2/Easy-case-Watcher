# HTML Fetcher Implementation
# This is a sample implementation for Phase 2 functionality

import requests
from bs4 import BeautifulSoup
import hashlib
import time

class HTMLFetcher:
    def __init__(self, config):
        self.config = config
        self.session = requests.Session()
        
    def fetch_html(self, url):
        """Fetch HTML content from URL with error handling"""
        try:
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            return response.text
        except requests.RequestException as e:
            print(f"Error fetching {url}: {e}")
            return None
    
    def extract_content(self, html_content, source_config):
        """Extract content based on source-specific configuration"""
        if html_content is None:
            return None
            
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Extract main content based on configuration
            content_selector = source_config.get('content_selector', 'body')
            content = soup.select_one(content_selector)
            
            if content:
                # Strip boilerplate and navigation
                self._strip_boilerplate(content)
                return str(content)
            return None
        except Exception as e:
            print(f"Error extracting content: {e}")
            return None

    def _strip_boilerplate(self, soup):
        """Remove boilerplate elements from HTML"""
        # Remove common boilerplate elements
        for element in soup.find_all(['script', 'style', 'nav', 'footer']):
            element.decompose()
        return soup

class SourceHealthMonitor:
    def __init__(self):
        self.content_fingerprints = {}
        
    def create_content_fingerprint(self, content):
        """Create a fingerprint of content for change detection"""
        if content is None:
            return None
        return hashlib.md5(content.encode()).hexdigest()
    
    def check_source_health(self, source_id, current_content):
        """Check source health and detect issues"""
        if current_content is None or len(current_content) == 0:
            return "FETCH_FAILED"
        else:
            # Store the new fingerprint
            self.content_fingerprints[source_id] = self.create_content_fingerprint(current_content)
            return "CHANGED"
            
    def detect_layout_drift(self, source_id, content):
        """Detect if content structure has changed significantly"""
        if content is None:
            return False
            
        fingerprint = self.create_content_fingerprint(content)
        previous_fingerprint = self.content_fingerprints.get(source_id)
        
        # If fingerprint changed significantly, it might indicate layout drift
        if previous_fingerprint and self._fingerprint_difference(fingerprint, previous_fingerprint) > 0.5:
            return True
        return False
        
    def _fingerprint_difference(self, fp1, fp2):
        """Calculate difference between two fingerprints"""
        if fp1 == fp2:
            return 0.0
        # Simple difference calculation
        return sum(c1 != c2 for c1, c2 in zip(fp1, fp2)) / len(fp1)

# Example usage
def main():
    # Configuration for HTML extraction
    config = {
        'content_selector': '.main-content',
        'rate_limit': 1  # seconds between requests
    }
    
    # Initialize components
    fetcher = HTMLFetcher(config)
    monitor = SourceHealthMonitor()
    
    # Example: Fetch and process a webpage
    url = "https://example.com"
    html_content = fetcher.fetch_html(url)
    
    if html_content:
        # Extract main content
        main_content = fetcher.extract_content(html_content, config)
        
        # Check source health
        health_status = monitor.check_source_health("source_1", main_content)
        print(f"Source health status: {health_status}")
        
        # Check for layout drift
        if monitor.detect_layout_drift("source_1", main_content):
            print("Layout drift detected!")
    else:
        print("Failed to fetch content")

if __name__ == "__main__":
    main()