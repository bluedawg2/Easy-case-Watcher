# Change Deduplication Implementation
# Handles cross-channel change deduplication for Phase 2

import hashlib
import time
from typing import Dict, List, Optional
from dataclasses import dataclass

@dataclass
class ChangeRecord:
    """Represents a detected change"""
    source_id: str
    content: str
    timestamp: float
    change_id: str
    
    def __post_init__(self):
        if not self.change_id:
            # Generate a unique ID for this change
            content_hash = hashlib.sha256(self.content.encode()).hexdigest()
            self.change_id = content_hash[:16]  # Use first 16 chars of hash

class ChangeDeduplicator:
    def __init__(self):
        self.known_changes = {}
        
    def is_duplicate(self, content: str, source_id: str) -> bool:
        """Check if a change is a duplicate of a previously seen change"""
        content_hash = hashlib.sha256(content.encode()).hexdigest()
        
        # Check if this exact content was seen before
        if content_hash in self.known_changes:
            previous_source = self.known_changes[content_hash]
            if previous_source != source_id:  # Different source, same content
                print(f"Duplicate change detected from different source: {source_id} vs {previous_source}")
                return True
        
        # Store this change
        self.known_changes[content_hash] = source_id
        return False
        
    def record_change(self, content: str, source_id: str) -> ChangeRecord:
        """Record a change and return a ChangeRecord object"""
        change_id = hashlib.sha256(content.encode()).hexdigest()[:16]
        return ChangeRecord(
            source_id=source_id,
            content=content,
            timestamp=time.time(),
            change_id=change_id
        )

# Example usage
def main():
    deduplicator = ChangeDeduplicator()
    
    # Simulate checking for duplicates
    content1 = "Example rule change content"
    content2 = "Different rule change content"
    
    # Check if changes are duplicates
    is_dup1 = deduplicator.is_duplicate(content1, "source_a")
    is_dup2 = deduplicator.is_duplicate(content2, "source_b")
    
    print(f"Content 1 duplicate check: {is_dup1}")
    print(f"Content 2 duplicate check: {is_dup2}")

if __name__ == "__main__":
    main()