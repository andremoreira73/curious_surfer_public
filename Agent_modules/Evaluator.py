from pydantic import BaseModel

from typing import Dict, Any, Tuple
import datetime

import logging

from .BaseAgent import BaseAgent
from .AgentMemory import AgentMemory

from .AI_API_call_functions import call_AI_OAI

from utils import logger, model_usage
from utils.config import config


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


#################################################################################
class JobRelevanceAssistant:
    """AI Assistant that evaluates job listings for interim manager relevance."""
    
    class SOClass(BaseModel):
        """Structured output for job relevance evaluation."""
        relevance_score: int  # 0-5 scale
        is_interim_suitable: bool
        job_title: str
        key_qualifications: list[TextCitation]
        seniority_level: str
        explanation: str
        specific_matches: list[TextCitation]
    
    def __init__(self, **kwargs):
        self.structured_output_switch = True
        self.model = kwargs.get('model', config.get_model('advanced_model'))
        self.max_tk = kwargs.get('max_tk', 128000)
        self.max_time_out = kwargs.get('max_time_out', 60)
        self.tk_encoding_name = kwargs.get('tk_encoding_name', 'cl100k_base')
        self.temperature = kwargs.get('temperature', 1.0)
        
        # Store the current content
        self.current_content = None
    
    def generate_developer_prompt(self) -> str:
        # Use configured prompt if available, otherwise use default
        prompt = config.get_prompt('job_relevance')
        if not prompt:
            # Fallback to original hardcoded prompt
            prompt = """
            You are an expert at evaluating job listings for their suitability for interim managers.
            
            An ideal interim manager position:
            - Is senior level (Director, VP, Head of Department, Senior Manager, Project Lead)
            - Involves project management, transformation, technical leadership, or strategic roles
            - Requires significant experience (5+ years)
            - Is often but not always described as temporary, contract, project-based, or fixed-term
            - Typically involves change management, turnaround, or solving specific business challenges
            - Is NOT entry-level, junior, or support staff
            
            German terms to look for:
            - "Interimsmanager" (interim manager)
            - "Projektleiter" (project leader)
            - "befristete Stelle" (temporary position)
            - "Führungskraft auf Zeit" (temporary leadership)
            - "Veränderungsprozess" (change process)
            - "Restrukturierung" (restructuring)
            
            IMPORTANT NOTES FOR SCORING:
            - Even if a job isn't explicitly described as "interim" but is at a senior level with project or transformation responsibilities, consider it potentially suitable
            - While temporary positions are ideal, senior management roles with project responsibility should still score at least 3, even if permanent
            - The most important criteria are level of seniority, leadership responsibilities, and project-oriented nature
            
            Analyze the provided job description and determine:
            1. Overall relevance score (0-5) for an interim manager
               - Score 0-1: Definitely not suitable (junior, entry-level, long-term operational)
               - Score 2: Has some senior aspects but lacks other key criteria
               - Score 3: Good match in seniority/scope, even if permanent position 
               - Score 4-5: Strong match including temporary nature or explicit interim roles
            2. Whether this job is suitable for an interim manager
            3. Key qualifications required
            4. Seniority level
            5. Specific aspects that make it suitable or unsuitable
            
            Provide your analysis in a structured format with the following fields:
            - relevance_score: Integer from 0-5
            - is_interim_suitable: Boolean (true if score ≥ 3)
            - job_title: String
            - key_qualifications: List of strings
            - seniority_level: String
            - explanation: String explaining your assessment
            - specific_matches: List of strings with specific text from the job that indicates suitability
            """
        return prompt
    
    def generate_developer_prompt_memory(self) -> str:
        return self.generate_developer_prompt()
    
    def generate_user_prompt(self) -> str:
        if not self.current_content:
            raise ValueError("No content provided")
        
        return self.current_content
    
    def __call__(self, content):
        self.current_content = content
        return self

###################################################################################

class JobPreFilterAssistant:
    """AI Assistant that quickly assesses if a job might be suitable for interim managers."""
    
    class SOClass(BaseModel):
        """Structured output for job pre-filtering."""
        is_potentially_relevant: bool  
        #confidence: int  # 1-5 scale
        #reason: str
    
    def __init__(self, **kwargs):
        self.structured_output_switch = True
        self.model = kwargs.get('model', config.get_model('fast_model'))
        self.max_tk = kwargs.get('max_tk', 128000)  # Smaller context window
        self.max_time_out = kwargs.get('max_time_out', 20)  # Quick timeout
        self.tk_encoding_name = kwargs.get('tk_encoding_name', 'cl100k_base')
        self.temperature = kwargs.get('temperature', 0.0)  # More deterministic
        
        # Store current evaluation targets
        self.job_title = None
        self.job_description = None
    
    def generate_developer_prompt(self) -> str:
        # Use configured prompt if available, otherwise use default
        prompt = config.get_prompt('job_pre_filter')
        if not prompt:
            # Fallback to original hardcoded prompt
            prompt = """
            You are a job seniority evaluator specializing in identifying positions suitable for interim managers.
            
            Ideal interim manager positions are:
            - Senior level (Director, VP, Head of Department, Manager, Project Lead)
            - NOT entry-level, junior, student, internship, or trainee positions
            
            Quickly determine if the job title and description suggest a senior-level position.
            
            Immediate rejection indicators:
            - "Auszubildende", "Azubi" (apprentice)
            - "Praktikum", "Schülerpraktikum" (internship)
            - "Werkstudent" (working student)
            - "Duales Studium" (dual study)
            - "Trainee" (entry-level training position)
            - "Junior", "Entry-level"
            - Any student-targeted position
            
            Provide a boolean judgment: is this potentially a senior position?
            """
        return prompt
    
    def generate_user_prompt(self) -> str:
        if not self.job_title:
            raise ValueError("No job title provided")
        
        job_desc = self.job_description if self.job_description else "No description available"
        return f"Job Title: {self.job_title}\n\nJob Description: {job_desc}"
    
    def __call__(self, title, description=""):
        self.job_title = title
        self.job_description = description
        return self

#################################################################################
class OpportunityExtractorAssistant:
    """AI Assistant that extracts structured job information from listings."""
    
    class SOClass(BaseModel):
        """Structured output for job information extraction."""
        job_title: str
        company_name: str
        location: str
        job_type: str
        description_summary: str
        responsibilities: list[TextCitation]
        requirements: list[TextCitation]
        keywords: list[TextCitation]
        url_found: str
        url_more_details: str
        is_generic_portal: bool
        specific_job_listings: list[TextDict]
    
    def __init__(self, **kwargs):
        self.structured_output_switch = True
        self.model = kwargs.get('model', config.get_model('advanced_model'))
        self.max_tk = kwargs.get('max_tk', 128000)
        self.max_time_out = kwargs.get('max_time_out', 20)
        self.tk_encoding_name = kwargs.get('tk_encoding_name', 'cl100k_base')
        self.temperature = kwargs.get('temperature', 1.0)
        
        # Store the current content and URL
        self.current_content = None
        self.current_url = None
    
    def generate_developer_prompt(self) -> str:
        # Use configured prompt if available, otherwise use default
        prompt = config.get_prompt('opportunity_extractor')
        if not prompt:
            # Fallback to original hardcoded prompt
            prompt = """
            You are an expert at extracting structured job information from websites.
            
            Analyze the provided webpage content and extract detailed information about job opportunities.
            Determine whether this is:
            1. A specific job listing page with a single position, OR
            2. A generic job portal/listing page with multiple positions
            
            For a specific job listing, extract comprehensive details.
            For a generic portal, identify individual job listings that might be relevant for interim managers.
            
            Provide the information in a structured format with the following fields:
            - job_title: String (main job title or portal title)
            - company_name: String
            - location: String (if available)
            - job_type: String (if available)
            - description_summary: String summarizing the job or portal
            - responsibilities: List of strings (for specific job)
            - requirements: List of strings (for specific job)
            - keywords: List of strings with key terms from the job
            - url_found: String (URL where you found this job)
            - url_more_details: String (URL that points to more details about this job)
            - is_generic_portal: Boolean
            - specific_job_listings: List of dictionaries with {"title": "job title", "description": "short description", "url": "link"} for each job found on a portal page
            """
        return prompt
    
    def generate_developer_prompt_memory(self) -> str:
        return self.generate_developer_prompt()
    
    def generate_user_prompt(self) -> str:
        if not self.current_content or not self.current_url:
            raise ValueError("No content or URL provided")
        
        return f"URL: {self.current_url}\n\nPage Content:\n{self.current_content}"
    
    def __call__(self, content, url):
        self.current_content = content
        self.current_url = url
        return self





###########################################################################################
class EvaluatorAgent(BaseAgent):
    """
    Agent responsible for evaluating job content for relevance to interim managers.
    """
    
    def __init__(self, memory: AgentMemory, api_keys: dict, **kwargs):
        super().__init__(memory, api_keys, **kwargs)
        
        # Get configuration from kwargs if provided
        self.config = kwargs.get('config', config)
        
        # Initialize AI assistants
        # note the long time out, as we use a reasoning model and probably need more time...
        self.job_relevance_assistant = JobRelevanceAssistant(
            model=self.config.get_model('advanced_model'), 
            max_tk=128000, 
            max_time_out=60
        )
        
        self.opportunity_extractor = OpportunityExtractorAssistant(
            model=self.config.get_model('advanced_model'), 
            max_tk=128000, 
            max_time_out=60
        )
        
        self.job_pre_filter = JobPreFilterAssistant(
            model=self.config.get_model('fast_model'), 
            max_tk=128000, 
            max_time_out=20
        )
        
        # Set up detailed logging
        self.setup_detailed_logging()


    def pre_filter_job(self, title: str, description: str = "") -> bool:
        """
        Use an LLM to quickly determine if a job might be suitable for an interim manager.
        """
        # Log model usage
        model_usage.log_usage(
            self.job_pre_filter.model,
            "JobPreFilter assessing job relevance"
        )
        
        # Use the JobPreFilterAssistant
        assistant = self.job_pre_filter(title, description)
        response = call_AI_OAI(assistant, self.api_keys.get("oai_key"))
        
        is_relevant = getattr(response, "is_potentially_relevant", False)
        #reason = getattr(response, "reason", "")
        
        if not is_relevant:
            #self.log(f"Pre-filtered out job: '{title}' - Reason: {reason}")
            self.log(f"Pre-filtered out job: '{title}'")
        
        return is_relevant


    def setup_detailed_logging(self):
        """Set up detailed logging for debugging."""
        self.log_file = f"evaluator_details_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        
        # Create a detailed logger
        self.detailed_logger = logging.getLogger("EvaluatorDetail")
        self.detailed_logger.setLevel(logging.DEBUG)
        
        # Add file handler
        file_handler = logging.FileHandler(self.log_file)
        file_handler.setLevel(logging.DEBUG)
        formatter = logging.Formatter('[%(asctime)s] [%(name)s] %(message)s')
        file_handler.setFormatter(formatter)
        self.detailed_logger.addHandler(file_handler)
        
        self.log(f"Detailed logging enabled to {self.log_file}")

    def log_detail(self, message, data=None):
        """Log detailed information for debugging."""
        if not hasattr(self, 'detailed_logger'):
            self.setup_detailed_logging()
        
        self.detailed_logger.debug(message)
        if data:
            import json
            try:
                self.detailed_logger.debug(json.dumps(data, indent=2, default=str))
            except:
                self.detailed_logger.debug(f"Could not serialize data: {type(data)}")

    ###################################################
    def evaluate_content(self, url: str, content: str) -> Tuple[bool, Dict[str, Any]]:
        """
        Evaluate content to determine if it contains relevant job opportunities.
        
        Args:
            url: URL where content was found
            content: Page content to evaluate
            
        Returns:
            Tuple of (is_relevant, evaluation_data)
        """
        self.log(f"Evaluating content from: {url}")
        
        # First, extract structured job information
        try:
            job_data = self._extract_job_information(url, content)
        except Exception as e:
            self.log(f"Error extracting job information: {e}")
            job_data = {}  # Default empty dictionary


        # Check if this is a generic portal
        if job_data.get("is_generic_portal", False):
            self.log(f"Identified as generic job portal with {len(job_data.get('specific_job_listings', []))} potential listings")
            
            # Explore specific job listings on the portal
            found_jobs = self.explore_specific_jobs(job_data, url)
            
            if found_jobs:
                self.log(f"Found {len(found_jobs)} relevant jobs on the portal")
                job_data["found_relevant_jobs"] = found_jobs
                
            return True, job_data
        
        # For specific job listings, evaluate relevance
        try:
            relevance_data = self._evaluate_job_relevance(content)
        except Exception as e:
            self.log(f"Error evaluating job relevance: {e}")
            relevance_data = {}
        
        # Combine the information
        combined_data = {**job_data, **relevance_data}
        
        # Get relevance threshold from configuration or use default
        relevance_threshold = self.config.get("evaluation.relevance_threshold", 3)
        
        # Determine if this is relevant enough based on relevance threshold
        relevance_score = relevance_data.get("relevance_score", 0)
        is_interim_suitable = relevance_data.get("is_interim_suitable", False) 
        
        # Use our adjusted criteria - either explicitly suitable or high score
        is_relevant = relevance_score >= relevance_threshold or is_interim_suitable
        
        # Check if there's a URL for more details and this listing looks promising
        more_details_url = job_data.get("url_more_details")
        if is_relevant and more_details_url and more_details_url != url and more_details_url.startswith(("http://", "https://")):
            self.log(f"Found more details URL: {more_details_url} - fetching additional information")
            # Download the content from the more details URL
            detail_status, detail_content = self.navigator._download_content(more_details_url)
            
            if detail_status == "OK" and detail_content:
                self.log(f"Successfully fetched more details from {more_details_url}")
                # Extract more detailed job information
                detailed_job_data = self._extract_job_information(more_details_url, detail_content)
                detailed_relevance_data = self._evaluate_job_relevance(detail_content)
                
                # Update with more detailed information if available
                for key, value in detailed_job_data.items():
                    if value and (key not in combined_data or not combined_data[key]):
                        combined_data[key] = value
                
                # Update relevance if better information available
                if detailed_relevance_data.get("relevance_score", 0) > relevance_data.get("relevance_score", 0):
                    combined_data["relevance_score"] = detailed_relevance_data.get("relevance_score", 0)
                    combined_data["is_interim_suitable"] = detailed_relevance_data.get("is_interim_suitable", False)
                    combined_data["explanation"] = detailed_relevance_data.get("explanation", combined_data.get("explanation", ""))
                    
                # Store the URL we used to get more details
                combined_data["followed_detail_url"] = more_details_url
        
        if is_relevant:
            self.log(f"Found relevant job: {job_data.get('job_title')} (Score: {relevance_data.get('relevance_score')})")
        else:
            self.log(f"Job not relevant: {job_data.get('job_title')} (Score: {relevance_data.get('relevance_score')})")
        
        return is_relevant, combined_data
    


    #############################################################################
    def _extract_job_information(self, url: str, content: str) -> Dict[str, Any]:
        """
        Extract structured job information from content.
        """
        # Log model usage
        model_usage.log_usage(
            self.opportunity_extractor.model,
            "OpportunityExtractor extracting job details"
        )
        
        # Use the OpportunityExtractor
        assistant = self.opportunity_extractor(content, url)
        response = call_AI_OAI(assistant, self.api_keys.get("oai_key"))
        
        # Convert to dictionary
        job_data = {}
        for field in self.opportunity_extractor.SOClass.__annotations__.keys():
            job_data[field] = getattr(response, field, None)
        
        # Log detailed information
        self.log_detail(f"Extracted job information from {url}", job_data)
        
        return job_data
    
    ###################################################################
    def _evaluate_job_relevance(self, content: str) -> Dict[str, Any]:
        """
        Evaluate job relevance for interim managers.
        """
        # Log model usage
        model_usage.log_usage(
            self.job_relevance_assistant.model,
            "JobRelevanceAssistant evaluating position suitability"
        )
        
        # Use the JobRelevanceAssistant
        assistant = self.job_relevance_assistant(content)
        response = call_AI_OAI(assistant, self.api_keys.get("oai_key"))
        
        # Convert to dictionary
        relevance_data = {}
        for field in self.job_relevance_assistant.SOClass.__annotations__.keys():
            relevance_data[field] = getattr(response, field, None)
        
        # Log detailed information
        self.log_detail(f"Evaluated job relevance", relevance_data)
        
        return relevance_data    


    ####################################################
    def explore_specific_jobs(self, job_data, base_url):
        """
        Explore specific job listings found on a generic portal.
        
        Args:
            job_data: Data about the generic portal
            base_url: Base URL of the portal
            
        Returns:
            List of found jobs
        """
        found_jobs = []
        
        # Extract specific job listings
        specific_listings = job_data.get("specific_job_listings", [])
        
        # Check if we have an explorer to track quotas, if not proceed normally
        explorer = getattr(self, 'explorer', None)
        
        # Get maximum jobs we can explore for this site
        max_jobs_to_explore = 3  # Default
        if explorer:
            max_jobs_to_explore = explorer.get_remaining_job_quota(base_url)
            self.log(f"Site quota allows exploration of up to {max_jobs_to_explore} jobs")
            
            if max_jobs_to_explore <= 0:
                self.log(f"Site {explorer._extract_domain(base_url)} has reached exploration quota - skipping job details")
                return found_jobs
        else:
            self.log(f"No explorer detected, using default max of {max_jobs_to_explore} jobs")
        
        # First pass: Pre-filter all jobs to find potentially relevant ones
        potentially_relevant_jobs = []
        
        self.log(f"Pre-filtering {len(specific_listings)} job listings")
        
        for listing in specific_listings:
            job_url = None
            job_title = None
            job_description = ""
            
            # Extract data from TextDict (string representation of a dictionary)
            if hasattr(listing, "text_dict"):
                try:
                    # Try to parse the string as a dictionary
                    import json
                    import ast
                    
                    # First try json.loads
                    try:
                        parsed_dict = json.loads(listing.text_dict)
                    except json.JSONDecodeError:
                        # If that fails, try ast.literal_eval for more permissive parsing
                        try:
                            parsed_dict = ast.literal_eval(listing.text_dict)
                        except (SyntaxError, ValueError):
                            # If both fail, use regex to extract data
                            import re
                            url_match = re.search(r'[\'"]url[\'"]\s*:\s*[\'"]([^\'"]*)[\'"]\s*', listing.text_dict)
                            title_match = re.search(r'[\'"]title[\'"]\s*:\s*[\'"]([^\'"]*)[\'"]\s*', listing.text_dict)
                            
                            if url_match:
                                job_url = url_match.group(1)
                            if title_match:
                                job_title = title_match.group(1)
                            
                            parsed_dict = {}
                    
                    # Extract URL and title from the parsed dictionary
                    if isinstance(parsed_dict, dict):
                        job_url = parsed_dict.get("url")
                        job_title = parsed_dict.get("title")
                        job_description = parsed_dict.get("description", "")
                except Exception as e:
                    self.log(f"Error parsing text_dict: {e}")
                    continue
                    
            # If it's a TextCitation, parse it as before
            elif hasattr(listing, "text_snippet"):
                import re
                text = listing.text_snippet
                
                # Try to extract URL from text
                url_match = re.search(r'URL: (https?://[^\s]+)', text)
                if url_match:
                    job_url = url_match.group(1)
                else:
                    # Look for any URL
                    url_match = re.search(r'(https?://[^\s]+)', text)
                    if url_match:
                        job_url = url_match.group(1)
                
                # Try to extract title
                title_match = re.search(r'Title: ([^\|]+)', text)
                if title_match:
                    job_title = title_match.group(1).strip()
                else:
                    # More general title extraction
                    title_match = re.search(r'([^|:]+)(?: \| |\:)', text)
                    if title_match:
                        job_title = title_match.group(1).strip()
            else:
                # Unknown format - skip
                continue
            
            # If we still don't have a URL, try to build one from the base
            if not job_url or job_url == base_url:
                if job_title:
                    # Try to create a search URL
                    clean_title = job_title.replace(' ', '+').replace('/', '%2F')
                    job_url = f"{base_url}?q={clean_title}"
                else:
                    # No usable information - skip
                    continue
            
            # Clean up the URL if needed
            if not job_url.startswith(('http://', 'https://')):
                # Assume it's a relative URL
                if job_url.startswith('/'):
                    # Get the base domain
                    from urllib.parse import urlparse
                    parsed_url = urlparse(base_url)
                    job_url = f"{parsed_url.scheme}://{parsed_url.netloc}{job_url}"
                else:
                    # Append to the base URL
                    if base_url.endswith('/'):
                        job_url = f"{base_url}{job_url}"
                    else:
                        job_url = f"{base_url}/{job_url}"
            
            # Apply pre-filter to check if this job is potentially relevant
            if not self.pre_filter_job(job_title or "Unknown Position", job_description):
                # Skip jobs that don't pass the pre-filter
                self.log(f"Pre-filtered out job: '{job_title or 'Unknown'}'")
                continue
            
            # If it passes the pre-filter, add it to our list of potentially relevant jobs
            self.log(f"Job potentially relevant: '{job_title or 'Unknown'}'")
            potentially_relevant_jobs.append({
                'job_url': job_url,
                'job_title': job_title or "Unknown Position",
                'job_description': job_description
            })
        
        # Second pass: Select up to max_jobs_to_explore from potentially relevant jobs
        self.log(f"Found {len(potentially_relevant_jobs)} potentially relevant jobs out of {len(specific_listings)}")
        
        # Limit to max jobs we can explore
        if len(potentially_relevant_jobs) > max_jobs_to_explore:
            self.log(f"Limiting to {max_jobs_to_explore} jobs due to site quota")
            potentially_relevant_jobs = potentially_relevant_jobs[:max_jobs_to_explore]
        
        # Counter to detect if we're getting stuck in URL exploration loops
        explored_urls = set()
        max_url_duplicates = 3  # Maximum times we should see URL patterns repeat
        
        # Now explore the selected potentially relevant jobs in detail
        for job in potentially_relevant_jobs:
            job_url = job['job_url']
            job_title = job['job_title']
            
            # Check for URL pattern repetition - helps detect getting stuck
            url_pattern = job_url.split('?')[0]  # Base URL without query parameters
            if url_pattern in explored_urls:
                self.log(f"Warning: Already explored URL pattern {url_pattern} - possible exploration loop")
                # Skip if we've seen this pattern too many times
                pattern_count = sum(1 for url in explored_urls if url == url_pattern)
                if pattern_count >= max_url_duplicates:
                    self.log(f"Detected URL exploration loop - skipping further exploration of similar URLs")
                    continue
            
            explored_urls.add(url_pattern)
            
            # Download and evaluate the job content
            self.log(f"Checking specific job: {job_title} at {job_url}")
            status, content = self.navigator._download_content(job_url)
            
            # Record job exploration in Explorer if available
            if explorer:
                explorer.record_job_exploration(job_url)
            
            if status == "OK" and content:
                is_relevant, evaluation_data = self.evaluate_content(job_url, content)
                
                if is_relevant:
                    self.log(f"Found relevant job: {evaluation_data.get('job_title', job_title)}")
                    found_jobs.append((job_url, evaluation_data))
        
        return found_jobs