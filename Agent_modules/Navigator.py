from pydantic import BaseModel
import tiktoken

from typing import List, Dict, Any, Tuple
from urllib.parse import urlparse

from .BaseAgent import BaseAgent
from .AgentMemory import AgentMemory

from utils import logger, model_usage
from utils.config import config

from .AI_API_call_functions import call_AI_OAI

from scraping_modules import scrape_and_check_spdr

"""
Note: when setting up assistants, you **MUST** set up the following (using these names)

variables:
-- structured_output_switch (boolean)

variables (as **kwargs --> MUST add a default value to each)
-- model
-- max_tk
-- tk_encoding_name
-- temperature

methods: 
-- generate_developer_prompt
-- generate_developer_prompt_memory
-- generate_user_prompt

classes:
if using structured output, MUST have this class
--- SOClass  (--> follows pydantic BaseModel)

The specifics of an assistant will be reflected in these variables and methods, which will be used
elsewhere to make API calls
"""

#### define here classes that you may need inside the assistants below ####


class TextCitation(BaseModel):
    text_snippet: str

class TextDict(BaseModel):
    text_dict: str




#########################################################################################
class SiteNavigationAssistant:
    """AI Assistant that analyzes website structure and identifies navigation paths."""
    
    class SOClass(BaseModel):
        """Structured output for navigation analysis."""
        has_job_listings: bool
        job_listings_path: str
        search_form_path: str
        navigation_pattern: str
        site_structure: str
        recommendations: list[TextCitation]
    
    def __init__(self, **kwargs):
        self.structured_output_switch = True
        self.model = kwargs.get('model', config.get_model('fast_model'))
        self.max_tk = kwargs.get('max_tk', 128000)
        self.max_time_out = kwargs.get('max_time_out', 20)
        self.tk_encoding_name = kwargs.get('tk_encoding_name', 'cl100k_base')
        self.temperature = kwargs.get('temperature', 1.0)
        
        # Store the current site and content
        self.current_site = None
        self.current_content = None
    
    def generate_developer_prompt(self) -> str:
        # Use configured prompt if available, otherwise use default
        prompt = config.get_prompt('site_navigation')
        if not prompt:
            # Fallback to original hardcoded prompt
            prompt = """
            You are an expert at analyzing website structure and navigation, especially for corporate career sites.
            You are given the HTML content of a webpage. Your task is to analyze it and determine:

            1. Whether this page contains job listings directly
            2. How to navigate to job listings if they're not on this page
            3. Whether the page has a search form for jobs
            4. The general structure of the site for navigation purposes

            IMPORTANT: Many German corporate sites use these terms for job listings:
            - "Stellenangebote" (Job Offers)
            - "Karriere" (Career)
            - "Offene Stellen" (Open Positions)
            - "Bewerbung" (Application)
            - "Aktuelle Vakanzen" (Current Vacancies)
            
            Focus on identifying:
            1. Links to job listing pages (may include words like "jobs", "careers", "positions")
            2. Search forms that can filter job listings
            3. Links to specific job postings
            4. Sections that might indicate this is already a job listing page
            
            For navigation paths, be specific about what links to click or search terms to use.
            
            Focus on identifying navigation elements that would lead to job listings, especially for senior or interim management positions.

            Provide your analysis in a structured format with the following fields:
            - has_job_listings: Boolean indicating if this page directly contains job listings
            - job_listings_path: String describing how to navigate to job listings (if not on this page)
            - search_form_path: String describing how to use the search functionality (if available)
            - navigation_pattern: String describing the typical navigation pattern of this site
            - site_structure: String describing the general structure of the site
            - recommendations: List of strings with recommendations for exploring this site
            """
        return prompt
    
    def generate_developer_prompt_memory(self) -> str:
        return self.generate_developer_prompt()
    
    def generate_user_prompt(self) -> str:
        if not self.current_site or not self.current_content:
            raise ValueError("No site or content provided")
        
        return f"Site URL: {self.current_site}\n\nPage Content:\n{self.current_content}"
    
    def __call__(self, site_url, content):
        self.current_site = site_url
        self.current_content = content
        return self





class NavigatorAgent(BaseAgent):
    """
    Agent responsible for navigating websites and finding job opportunities.
    """
    
    def __init__(self, memory: AgentMemory, api_keys: dict, **kwargs):
        super().__init__(memory, api_keys, **kwargs)
        
        # Get configuration from kwargs if provided
        self.config = kwargs.get('config', config)
        
        # Initialize AI assistants
        self.site_navigation_assistant = SiteNavigationAssistant(
            model=self.config.get_model('fast_model')
        )
    

    def _download_content(self, url: str) -> Tuple[str, str]:
        """
        Download content from a URL using the scraping service.
        """
        # Use existing scraping functionality
        #extra_params = {
        #    'wait_for': '.job-listing, .careers, .vacancies, .stellenangebote, article',
        #    'premium_proxy': 'False'
        #}
        return scrape_and_check_spdr(
            url,
            self.api_keys.get("SB_endpoint"),
            self.api_keys.get("SB_key")
            #extra_params=extra_params
        )


    def _analyze_site_navigation(self, site_url: str, content: str) -> Dict[str, Any]:
        """
        Analyze site structure to determine navigation paths.
        """
        # Log model usage
        model_usage.log_usage(
            self.site_navigation_assistant.model,
            f"SiteNavigationAssistant analyzing structure of {self._extract_domain(site_url)}"
        )
        
        # Use the SiteNavigationAssistant
        assistant = self.site_navigation_assistant(site_url, content)
        response = call_AI_OAI(assistant, self.api_keys.get("oai_key"))
        
        # initialize
        navigation_data = {
            "has_job_listings": False,  # Default to False
            "job_listings_path": "",    # Default to empty string
            "search_form_path": "",     # Default to empty string
            "navigation_pattern": "",   # Default to empty string
            "site_structure": "",       # Default to empty string
            "recommendations": []       # Default to empty list
        }

        # Process the response
        if response:
            navigation_data = {
                "has_job_listings": getattr(response, "has_job_listings", False),
                "job_listings_path": getattr(response, "job_listings_path", ""),
                "search_form_path": getattr(response, "search_form_path", ""),
                "navigation_pattern": getattr(response, "navigation_pattern", ""),
                "site_structure": getattr(response, "site_structure", ""),
                "recommendations": getattr(response, "recommendations", [])
            }
        
        return navigation_data
    
    
    
    def _extract_domain(self, url: str) -> str:
        """Extract the domain from a URL."""
        parsed_url = urlparse(url)
        return parsed_url.netloc



    def _needs_chunking(self, content: str) -> bool:
        """
        Check if content needs to be chunked based on token count.
        
        Args:
            content: The HTML content to check
            
        Returns:
            bool: True if content needs chunking, False otherwise
        """
        # Use the assistant's encoding to estimate token count
        encoding_name = self.site_navigation_assistant.tk_encoding_name
        max_tokens = self.site_navigation_assistant.max_tk
        
        try:
            encoding = tiktoken.get_encoding(encoding_name)
            token_count = len(encoding.encode(content))
            
            self.log(f"Content token count: {token_count}, Max tokens: {max_tokens}")
            return token_count > (max_tokens * 0.8)  # Use 80% as a safety margin
        except Exception as e:
            self.log(f"Error calculating token count: {e}")
            # If we can't calculate, assume chunking is needed for content longer than 100KB
            return len(content) > 100000

    def _chunk_content(self, content: str, max_chunks: int = 4) -> List[str]:
        """
        Split content into chunks based on simple length.
        
        Args:
            content: The HTML content to chunk
            max_chunks: Maximum number of chunks to create
            
        Returns:
            List[str]: List of content chunks
        """
        self.log(f"Chunking content of size {len(content)}")
        
        # Calculate chunk size with slight overlap
        chunk_size = len(content) // max_chunks
        overlap = min(2000, chunk_size // 10)  # 10% overlap, max 2000 chars
        
        chunks = []
        for i in range(max_chunks):
            start = max(0, i * chunk_size - (overlap if i > 0 else 0))
            end = min(len(content), (i + 1) * chunk_size + (overlap if i < max_chunks - 1 else 0))
            
            # Make sure we don't create empty chunks
            if end > start:
                chunks.append(content[start:end])
        
        self.log(f"Created {len(chunks)} chunks for processing")
        return chunks

    def _combine_navigation_data(self, all_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Combine navigation data from multiple chunks into a single result.
        
        Args:
            all_data: List of navigation data dictionaries from chunks
            
        Returns:
            Dict[str, Any]: Combined navigation data
        """
        if not all_data:
            return {}
        
        # Initialize with first chunk's data
        combined = all_data[0].copy()
        
        # Process each chunk's data
        for data in all_data[1:]:
            # For navigation paths, add unique paths
            if "navigation_paths" in data:
                for path in data.get("navigation_paths", []):
                    if path not in combined.get("navigation_paths", []):
                        if "navigation_paths" not in combined:
                            combined["navigation_paths"] = []
                        combined["navigation_paths"].append(path)
            
            # For Boolean flag, use OR logic (if any chunk has job listings, the page has job listings)
            if data.get("has_job_listings", False):
                combined["has_job_listings"] = True
            
            # For job listings path, keep track of all unique paths
            if data.get("job_listings_path") and data.get("job_listings_path") != combined.get("job_listings_path"):
                if "all_job_listings_paths" not in combined:
                    combined["all_job_listings_paths"] = [combined.get("job_listings_path")] if combined.get("job_listings_path") else []
                combined["all_job_listings_paths"].append(data.get("job_listings_path"))
            
            # For search form path, same approach
            if data.get("search_form_path") and data.get("search_form_path") != combined.get("search_form_path"):
                if "all_search_form_paths" not in combined:
                    combined["all_search_form_paths"] = [combined.get("search_form_path")] if combined.get("search_form_path") else []
                combined["all_search_form_paths"].append(data.get("search_form_path"))
            
            # For site structure, combine unique insights
            if data.get("site_structure"):
                if combined.get("site_structure"):
                    combined["site_structure"] += "\n\nAdditional Structure Information:\n" + data.get("site_structure")
                else:
                    combined["site_structure"] = data.get("site_structure")
            
            # For recommendations, add unique recommendations
            if "recommendations" in data:
                if "recommendations" not in combined:
                    combined["recommendations"] = []
                
                # Add all recommendations (duplicates will be handled by the LLM)
                combined["recommendations"].extend(data.get("recommendations", []))
        
        # If we have multiple paths, select the most likely one
        if "all_job_listings_paths" in combined:
            # For now, just pick the first one, but could implement more sophisticated selection
            if not combined.get("job_listings_path") and combined["all_job_listings_paths"]:
                combined["job_listings_path"] = combined["all_job_listings_paths"][0]
        
        if "all_search_form_paths" in combined:
            if not combined.get("search_form_path") and combined["all_search_form_paths"]:
                combined["search_form_path"] = combined["all_search_form_paths"][0]
        
        return combined

    # Modify the explore_site method to use chunking
    def explore_site(self, site_url: str) -> Tuple[str, Dict[str, Any]]:
        """
        Explore a website to find job opportunities, chunking large content if needed.
        
        Args:
            site_url: URL of the site to explore
            
        Returns:
            Tuple of (status, navigation_data)
            
        Note: navigation_data now includes:
        - 'is_chunked': Boolean indicating if the content was chunked
        - 'chunks': List of individual chunk data when content is chunked
        - Other standard navigation data, which may be combined from chunks or from a single analysis
        """
        self.log(f"Exploring site: {site_url}")
        
        # Download the main page
        status, content = self._download_content(site_url)
        
        if status != "OK" or not content:
            self.log(f"Failed to download content from {site_url} or content is clutter")
            self.memory.update_site_memory(site_url, {"success_rate": 0.1})  # Very low success rate
            return status, {}
        
        # Check if content needs chunking
        if self._needs_chunking(content):
            self.log(f"Content from {site_url} requires chunking due to size")
            chunks = self._chunk_content(content)
            
            # Process each chunk
            all_chunk_data = []
            for i, chunk in enumerate(chunks):
                self.log(f"Processing chunk {i+1}/{len(chunks)} from {site_url}")
                chunk_url = f"{site_url}#chunk{i+1}"  # Unique identifier for each chunk
                chunk_data = self._analyze_site_navigation(chunk_url, chunk)
                
                # Add chunk metadata
                chunk_data["chunk_id"] = i + 1
                chunk_data["chunk_url"] = chunk_url
                chunk_data["source_url"] = site_url
                
                all_chunk_data.append(chunk_data)
            
            # Create a combined view for site memory
            combined_data = self._combine_navigation_data(all_chunk_data)
            
            # Update site memory with combined information
            self.memory.update_site_memory(site_url, {
                "navigation_paths": combined_data.get("navigation_paths", []),
                "job_listings_path": combined_data.get("job_listings_path"),
                "search_form_path": combined_data.get("search_form_path"),
                "notes": combined_data.get("site_structure", ""),
                "is_chunked": True,
                "chunk_count": len(chunks)
            })
            
            # Create the result with both combined data and individual chunks
            navigation_data = {
                **combined_data,  # Include combined data for backward compatibility
                "is_chunked": True,
                "chunk_count": len(chunks),
                "chunks": all_chunk_data  # Include all individual chunk data
            }
            
            return "SUCCESS", navigation_data
        
        # No chunking needed, process normally
        navigation_data = self._analyze_site_navigation(site_url, content)
        
        # Add metadata for non-chunked content
        navigation_data["is_chunked"] = False
        navigation_data["chunk_count"] = 1
        
        # Update site memory with navigation information
        self.memory.update_site_memory(site_url, {
            "navigation_paths": navigation_data.get("navigation_paths", []),
            "job_listings_path": navigation_data.get("job_listings_path"),
            "search_form_path": navigation_data.get("search_form_path"),
            "notes": navigation_data.get("site_structure", ""),
            "is_chunked": False,
            "chunk_count": 1
        })
        
        return "SUCCESS", navigation_data