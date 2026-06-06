# District Coverage Implementation
# This handles district-specific processing for Phase 3

import json
from dataclasses import dataclass
from typing import Dict, Optional, List
import time

@dataclass
class DistrictConfig:
    """Configuration for a court district"""
    district_id: str
    name: str
    jurisdiction: str
    layer: str
    state_exemptions: List[str]

class DistrictRegistry:
    def __init__(self):
        self.districts = {}
        self.config_file = "district_registry.json"
        
    def add_district(self, district_config: DistrictConfig):
        """Add a new district to the registry"""
        self.districts[district_config.district_id] = district_config
        
    def get_districts(self) -> List[DistrictConfig]:
        """Get all registered districts"""
        return list(self.districts.values())
        
    def get_district(self, district_id: str) -> Optional[DistrictConfig]:
        """Get district configuration by ID"""
        return self.districts.get(district_id)

# Example district configurations for the initial tranche
DISTRICTS = [
    {
        "district_id": "or_d",
        "name": "District of Oregon",
        "jurisdiction": "Oregon",
        "layer": "district",
        "state_exemptions": ["OR"]
    },
    {
        "district_id": "caed",
        "name": "Eastern District of California",
        "jurisdiction": "California",
        "layer": "district",
        "state_exemptions": ["CA"]
    },
    {
        "district_id": "txsd", 
        "name": "Southern District of Texas",
        "jurisdiction": "Texas",
        "layer": "district",
        "state_exemptions": ["TX"]
    }
]

def main():
    registry = DistrictRegistry()
    print("District registry initialized")
    
    # Add districts to registry
    for district_data in DISTRICTS:
        district = DistrictConfig(**district_data)
        registry.add_district(district)
        
    print("Districts added to registry")
    print(f"Total districts: {len(registry.districts)}")

if __name__ == "__main__":
    main()