

import os
import json
import datetime
from typing import List, Dict, Any, Tuple, Optional, Set
from urllib.parse import urlparse
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Tuple, Optional, Set


from utils import logger, model_usage


##############################################
# Memory System
##############################################

class MemoryItem(BaseModel):
    """Base class for items stored in agent memory."""
    created_at: str = Field(default_factory=lambda: datetime.datetime.now().isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.datetime.now().isoformat())


class SiteMemory(MemoryItem):
    """Memory about a specific website."""
    domain: str
    full_url: str
    visits: int = 1
    last_visit: str = Field(default_factory=lambda: datetime.datetime.now().isoformat())
    success_rate: float = 0.5  # Default neutral score
    navigation_paths: List[str] = []
    job_listings_path: Optional[str] = None
    search_form_path: Optional[str] = None
    known_job_ids: Set[str] = Field(default_factory=set)
    notes: str = ""


class JobMemory(MemoryItem):
    """Memory about a specific job opportunity."""
    url: str
    domain: str
    title: str
    relevance_score: float
    is_interim_suitable: bool
    description_summary: str
    keywords: List[str] = []
    location: Optional[str] = None
    requirements: List[str] = []
    still_active: bool = True
    last_checked: str = Field(default_factory=lambda: datetime.datetime.now().isoformat())


class PatternMemory(MemoryItem):
    """Memory about successful patterns."""
    pattern_type: str  # "navigation", "job_indicator", "search_term"
    pattern: str
    success_count: int = 1
    effectiveness: float = 0.5  # Default neutral score
    contexts: List[str] = []  # Domains or situations where this pattern worked


class AgentMemory:
    """Central memory system for all agents."""
    
    def __init__(self, memory_file: str = "agent_memory.json"):
        self.memory_file = memory_file
        self.sites: Dict[str, SiteMemory] = {}
        self.jobs: Dict[str, JobMemory] = {}
        self.patterns: Dict[str, PatternMemory] = {}
        self.load_memory()
    
    def load_memory(self):
        """Load memory from file if it exists."""
        try:
            if os.path.exists(self.memory_file):
                with open(self.memory_file, "r") as f:
                    data = json.load(f)
                    
                    # Convert dictionaries to appropriate objects
                    self.sites = {k: SiteMemory(**v) for k, v in data.get("sites", {}).items()}
                    self.jobs = {k: JobMemory(**v) for k, v in data.get("jobs", {}).items()}
                    self.patterns = {k: PatternMemory(**v) for k, v in data.get("patterns", {}).items()}
                    
                logger.info(f"Loaded memory: {len(self.sites)} sites, {len(self.jobs)} jobs, {len(self.patterns)} patterns")
            else:
                logger.info("No existing memory file found. Starting with fresh memory.")
        except Exception as e:
            logger.error(f"Error loading memory: {e}")
            # Start with empty memory if there's an error
    
    def save_memory(self):
        """Save memory to file."""
        try:
            # Convert objects to dictionaries with special handling for sets
            data = {
                "sites": {
                    k: {
                        **v.model_dump(),  # Using model_dump() for Pydantic v2
                        # Convert set to list for JSON serialization
                        "known_job_ids": list(v.known_job_ids) if hasattr(v, "known_job_ids") else []
                    } 
                    for k, v in self.sites.items()
                },
                "jobs": {k: v.model_dump() for k, v in self.jobs.items()},
                "patterns": {k: v.model_dump() for k, v in self.patterns.items()}
            }
            
            with open(self.memory_file, "w") as f:
                json.dump(data, f, indent=2)
                
            logger.info(f"Saved memory to {self.memory_file}")
        except Exception as e:
            logger.error(f"Error saving memory: {e}")
    

    def get_site_memory(self, url: str) -> Optional[SiteMemory]:
        """Get memory for a specific site."""
        domain = self._extract_domain(url)
        return self.sites.get(domain)
    
    def update_site_memory(self, url: str, updates: Dict[str, Any]):
        """Update memory for a specific site."""
        domain = self._extract_domain(url)
        now = datetime.datetime.now().isoformat()
        
        if domain in self.sites:
            # Update existing memory
            site_memory = self.sites[domain]
            for key, value in updates.items():
                if hasattr(site_memory, key):
                    setattr(site_memory, key, value)
            
            site_memory.visits += 1
            site_memory.updated_at = now
            site_memory.last_visit = now
        else:
            # Create new memory
            self.sites[domain] = SiteMemory(
                domain=domain,
                full_url=url,
                **updates
            )
        
        self.save_memory()
    
    def add_job(self, job_data: Dict[str, Any]) -> str:
        """Add a new job to memory."""
        # Create a unique ID for the job
        job_id = f"{self._extract_domain(job_data['url'])}_{hash(job_data['url'])}"
        
        # Create the job memory
        self.jobs[job_id] = JobMemory(**job_data)
        
        # Update site memory to include this job ID
        domain = self._extract_domain(job_data['url'])
        if domain in self.sites:
            if not hasattr(self.sites[domain], 'known_job_ids'):
                self.sites[domain].known_job_ids = set()
            self.sites[domain].known_job_ids.add(job_id)
        
        self.save_memory()
        return job_id
    
    def add_pattern(self, pattern_type: str, pattern: str, effectiveness: float, context: str):
        """Add or update a pattern in memory."""
        # Create a unique ID for the pattern
        pattern_id = f"{pattern_type}_{hash(pattern)}"
        
        if pattern_id in self.patterns:
            # Update existing pattern
            self.patterns[pattern_id].success_count += 1
            self.patterns[pattern_id].effectiveness = (
                (self.patterns[pattern_id].effectiveness * 
                 (self.patterns[pattern_id].success_count - 1) + 
                 effectiveness) / self.patterns[pattern_id].success_count
            )
            if context not in self.patterns[pattern_id].contexts:
                self.patterns[pattern_id].contexts.append(context)
            self.patterns[pattern_id].updated_at = datetime.datetime.now().isoformat()
        else:
            # Create new pattern
            self.patterns[pattern_id] = PatternMemory(
                pattern_type=pattern_type,
                pattern=pattern,
                effectiveness=effectiveness,
                contexts=[context]
            )
        
        self.save_memory()
        return pattern_id
    
    def get_best_patterns(self, pattern_type: str, context: Optional[str] = None, limit: int = 5) -> List[Tuple[str, float]]:
        """Get the most effective patterns of a specific type."""
        relevant_patterns = []
        
        for pattern_id, pattern in self.patterns.items():
            if pattern.pattern_type == pattern_type:
                # If context is specified, only include patterns that worked in that context
                if context is None or context in pattern.contexts:
                    relevant_patterns.append((pattern.pattern, pattern.effectiveness))
        
        # Sort by effectiveness
        relevant_patterns.sort(key=lambda x: x[1], reverse=True)
        
        return relevant_patterns[:limit]
    
    def get_prioritized_sites(self, limit: int = 10) -> List[Tuple[str, float]]:
        """Get sites prioritized by their potential value."""
        # Calculate a priority score for each site
        site_scores = []
        
        for domain, site in self.sites.items():
            # Base score is the success rate
            score = site.success_rate
            
            # Adjust for recency (prefer sites not visited recently)
            last_visit = datetime.datetime.fromisoformat(site.last_visit)
            days_since_visit = (datetime.datetime.now() - last_visit).days
            recency_factor = min(days_since_visit / 5, 1.0)  # Max boost for 5+ days
            
            # Adjust for number of visits (explore less-visited sites)
            visit_factor = max(1.0 - (site.visits / 10), 0.1)  # Min penalty for 10+ visits
            
            # Combine factors
            adjusted_score = score + (recency_factor * 0.2) + (visit_factor * 0.1)
            
            site_scores.append((site.full_url, adjusted_score))
        
        # Sort by score
        site_scores.sort(key=lambda x: x[1], reverse=True)
        
        return site_scores[:limit]
    
    def get_unexplored_domains(self, all_domains: List[str]) -> List[str]:
        """Get domains that haven't been explored yet."""
        explored_domains = set(self.sites.keys())
        return [domain for domain in all_domains if domain not in explored_domains]
    
    def _extract_domain(self, url: str) -> str:
        """Extract the domain from a URL."""
        parsed_url = urlparse(url)
        return parsed_url.netloc

