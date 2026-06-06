# Source Onboarding Implementation
# This handles config-only source onboarding for Phase 2

import json
from dataclasses import dataclass
from typing import Dict, Optional
import time

@dataclass
class SourceConfig:
    """Configuration for a court source"""
    source_id: str
    url: str
    jurisdiction: str
    layer: str
    content_selector: str
    rate_limit: int  # seconds between requests
    politeness_ceiling: int  # max requests per hour
    
class SourceRegistry:
    def __init__(self):
        self.sources: Dict[str, SourceConfig] = {}
        self.config_file = "source_registry.json"
        
    def add_source(self, source_config: SourceConfig):
        """Add a new source to the registry"""
        self.sources[source_config.source_id] = source_config
        self.save_registry()
        
    def get_source(self, source_id: str) -> Optional[SourceConfig]:
        """Get source configuration by ID"""
        return self.sources.get(source_id)
        
    def list_sources(self):
        """List all registered sources"""
        return list(self.sources.values())
        
    def save_registry(self):
        """Save registry to file"""
        data = {}
        for source_id, config in self.sources.items():
            data[source_id] = {
                'url': config.url,
                'jurisdiction': config.jurisdiction,
                'layer': config.layer,
                'content_selector': config.content_selector,
                'rate_limit': config.rate_limit,
                'politeness_ceiling': config.politeness_ceiling
            }
        with open(self.config_file, 'w') as f:
            json.dump(data, f, indent=2)
            
    def load_registry(self):
        """Load registry from file"""
        try:
            with open(self.config_file, 'r') as f:
                data = json.load(f)
                for source_id, config_data in data.items():
                    config = SourceConfig(
                        source_id=source_id,
                        url=config_data['url'],
                        jurisdiction=config_data['jurisdiction'],
                        layer=config_data['layer'],
                        content_selector=config_data['content_selector'],
                        rate_limit=config_data['rate_limit'],
                        politeness_ceiling=config_data['politeness_ceiling']
                    )
                    self.sources[source_id] = config
        except FileNotFoundError:
            pass

class PolitenessEnforcer:
    def __init__(self):
        self.request_times = {}
        
    def can_make_request(self, source_id: str, rate_limit: int) -> bool:
        """Check if we can make a request based on politeness policy"""
        now = time.time()
        last_request = self.request_times.get(source_id, 0)
        
        # Check if enough time has passed based on rate limit
        if now - last_request >= rate_limit:
            return True
        return False
        
    def record_request(self, source_id: str):
        """Record that a request was made"""
        self.request_times[source_id] = time.time()

# Example usage
def main():
    # Initialize components
    registry = SourceRegistry()
    politeness = PolitenessEnforcer()
    
    # Load existing registry
    registry.load_registry()
    
    # Add a new source (config-only, no code changes needed)
    new_source = SourceConfig(
        source_id="caed",
        url="https://www.caed.uscourts.gov",
        jurisdiction="Eastern District of California",
        layer="district",
        content_selector=".content",
        rate_limit=5,
        politeness_ceiling=100
    )
    
    registry.add_source(new_source)
    
    # Check if we can make a request
    if politeness.can_make_request("caed", new_source.rate_limit):
        print("Can make request to new source")
        politeness.record_request("caed")
    else:
        print("Rate limit exceeded for this source")

if __name__ == "__main__":
    main()