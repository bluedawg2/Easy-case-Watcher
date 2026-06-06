# Main orchestrator for Phase 2 functionality
# Integrates HTML fetching, source health monitoring, and deduplication

import time
from html_fetcher import HTMLFetcher, SourceHealthMonitor
from source_onboarding import SourceRegistry, PolitenessEnforcer
from change_deduplicator import ChangeDeduplicator

class Phase2Orchestrator:
    def __init__(self):
        self.fetcher = HTMLFetcher({})
        self.monitor = SourceHealthMonitor()
        self.registry = SourceRegistry()
        self.politeness = PolitenessEnforcer()
        self.deduplicator = ChangeDeduplicator()
        
    def process_source(self, source_id: str):
        """Process a source through the full pipeline"""
        # Get source configuration
        source_config = self.registry.get_source(source_id)
        if not source_config:
            print(f"Source {source_id} not found in registry")
            return
            
        # Check politeness policy
        if not self.politeness.can_make_request(source_id, source_config.rate_limit):
            print(f"Rate limit exceeded for source {source_id}")
            return
            
        # Fetch content
        html_content = self.fetcher.fetch_html(source_config.url)
        if html_content:
            main_content = self.fetcher.extract_content(html_content, {
                'content_selector': source_config.content_selector
            })
            
            # Check source health
            health_status = self.monitor.check_source_health(source_id, main_content)
            print(f"Source health: {health_status}")
            
            # Record the request
            self.politeness.record_request(source_id)
            
            # Check for duplicates if content exists
            if main_content:
                is_duplicate = self.deduplicator.is_duplicate(main_content, source_id)
                if is_duplicate:
                    print("Duplicate content detected, skipping...")
                    return
            
        print(f"Processed source {source_id}")

# Example usage
def main():
    orchestrator = Phase2Orchestrator()
    
    # Load registry
    orchestrator.registry.load_registry()
    
    # Process a source
    orchestrator.process_source("caed")

if __name__ == "__main__":
    main()