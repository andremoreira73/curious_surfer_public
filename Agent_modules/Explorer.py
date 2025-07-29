import random
from urllib.parse import urlparse
from collections import defaultdict
from typing import List, Dict

from .BaseAgent import BaseAgent
from .AgentMemory import AgentMemory

from utils import logger, model_usage
from utils.config import config


class ExplorerAgent(BaseAgent):
    """
    Agent responsible for selecting sites to explore and deciding exploration strategy.
    """
    
    def __init__(self, memory: AgentMemory, api_keys: dict, **kwargs):
        super().__init__(memory, api_keys, **kwargs)
        
        # Get configuration from kwargs if provided
        self.config = kwargs.get('config', config)
        
        # Get configuration values with defaults from kwargs if provided
        self.exploration_rate = kwargs.get('exploration_rate', 0.3)
        self.satisfaction_threshold = kwargs.get('satisfaction_threshold', 5)  # Number of good jobs to find
        self.max_visits = kwargs.get('max_visits', 10)  # Maximum number of site visits
        self.max_jobs_per_site = kwargs.get('max_jobs_per_site', 3)  # Max job listings to explore per site
        self.max_total_jobs_explored = kwargs.get('max_total_jobs_explored', 15)  # Max job details to explore overall
        
        # Track session information
        self.visited_sites = []
        self.found_jobs = []
        self.current_visit_count = 0
        self.explored_jobs_count = 0
        self.jobs_explored_per_site = defaultdict(int)  # Track jobs explored per site domain
    
    def select_next_site(self, available_sites: List[str]) -> str:
        """
        Select the next site to visit based on memory and exploration strategy.
        
        Args:
            available_sites: List of all available sites to choose from
            
        Returns:
            URL of the next site to visit
        """
        self.log(f"Selecting next site from {len(available_sites)} options")
        
        if not available_sites:
            raise ValueError("No sites available to select from")
        
        # Exclude sites that recently failed
        recently_failed_sites = set()
        for site_url in self.visited_sites[-5:]:  # Look at last 5 visited sites
            domain = self._extract_domain(site_url)
            if domain in self.memory.sites:
                site_memory = self.memory.sites[domain]
                if site_memory.success_rate < 0.2:  # Consider as failed
                    recently_failed_sites.add(domain)
        
        # Also exclude sites where we've already explored the maximum number of jobs
        sites_at_quota = set()
        for domain, count in self.jobs_explored_per_site.items():
            if count >= self.max_jobs_per_site:
                sites_at_quota.add(domain)
                self.log(f"Site {domain} has reached exploration quota ({count} jobs)")
        
        # Filter out recently failed sites and sites at quota, unless we have no alternatives
        filtered_sites = [site for site in available_sites 
                        if self._extract_domain(site) not in recently_failed_sites
                        and self._extract_domain(site) not in sites_at_quota]
        
        # If we've filtered out too many, allow some failed sites back in but still respect quota
        if len(filtered_sites) < max(3, len(available_sites) * 0.1):
            self.log("Too many filtered sites, allowing some previously failed sites")
            filtered_sites = [site for site in available_sites 
                            if self._extract_domain(site) not in sites_at_quota]
        
        # If we still have no sites, reset exploration quotas as a last resort
        if not filtered_sites:
            self.log("All sites at exploration quota - resetting quotas for least recently visited sites")
            self.jobs_explored_per_site.clear()
            filtered_sites = available_sites
        
        # Extract domains for checking unexplored sites
        all_domains = [self._extract_domain(site) for site in filtered_sites]
        unexplored_domains = self.memory.get_unexplored_domains(all_domains)
        
        # Decide whether to explore or exploit
        if random.random() < self.exploration_rate or not self.memory.sites:
            # Exploration mode: prefer unexplored sites
            if unexplored_domains:
                # Find corresponding full URLs
                unexplored_sites = [
                    site for site in filtered_sites 
                    if self._extract_domain(site) in unexplored_domains
                ]
                selected_site = random.choice(unexplored_sites)
                self.log(f"Exploring new site: {selected_site}")
                return selected_site
        
        # Exploitation mode: use prioritized sites from memory
        prioritized_sites = self.memory.get_prioritized_sites()
        
        if prioritized_sites:
            # Select from prioritized sites, but only those in the available list
            available_prioritized = [
                (site, score) for site, score in prioritized_sites
                if any(self._extract_domain(site) == self._extract_domain(available_site) 
                       for available_site in filtered_sites)
            ]
            
            if available_prioritized:
                # Use weighted random selection based on scores
                total_score = sum(score for _, score in available_prioritized)
                selection_point = random.uniform(0, total_score)
                
                cumulative_score = 0
                for site, score in available_prioritized:
                    cumulative_score += score
                    if cumulative_score >= selection_point:
                        self.log(f"Selected prioritized site: {site} (score: {score:.2f})")
                        return site
        
        # Fallback: random selection
        selected_site = random.choice(filtered_sites)
        self.log(f"Selected random site: {selected_site}")
        return selected_site
    
    def is_satisfied(self) -> bool:
        """
        Check if we've found enough good jobs or reached visit/exploration limits.
        
        Returns:
            Boolean indicating whether to stop exploration
        """
        # Check if we've found enough good jobs
        if len(self.found_jobs) >= self.satisfaction_threshold:
            self.log(f"Satisfied with {len(self.found_jobs)} good jobs found")
            return True
        
        # Check if we've reached the maximum number of visits
        if self.current_visit_count >= self.max_visits:
            self.log(f"Reached maximum visit count ({self.max_visits})")
            return True
        
        # Check if we've reached the maximum number of job detail pages explored
        if self.explored_jobs_count >= self.max_total_jobs_explored:
            self.log(f"Reached maximum job exploration count ({self.max_total_jobs_explored})")
            return True
        
        # Not satisfied yet
        return False
    
    def record_visit(self, site_url: str):
        """Record that a site has been visited."""
        self.visited_sites.append(site_url)
        self.current_visit_count += 1
    
    def record_found_job(self, job_id: str):
        """Record that a good job has been found."""
        self.found_jobs.append(job_id)
    
    def record_job_exploration(self, site_url: str):
        """Record that a job detail page has been explored on a specific site."""
        domain = self._extract_domain(site_url)
        self.jobs_explored_per_site[domain] += 1
        self.explored_jobs_count += 1
        self.log(f"Recorded job exploration on {domain} (total: {self.jobs_explored_per_site[domain]})")
    
    def get_remaining_job_quota(self, site_url: str) -> int:
        """Get the remaining number of jobs that can be explored on a site."""
        domain = self._extract_domain(site_url)
        return max(0, self.max_jobs_per_site - self.jobs_explored_per_site[domain])
    
    def _extract_domain(self, url: str) -> str:
        """Extract the domain from a URL."""
        parsed_url = urlparse(url)
        return parsed_url.netloc