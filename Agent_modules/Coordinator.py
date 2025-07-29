import os
import json
import time
import datetime
from typing import List, Dict, Any, Optional
from urllib.parse import urlparse

from .BaseAgent import BaseAgent
from .AgentMemory import AgentMemory

from .Explorer import ExplorerAgent
from .Navigator import NavigatorAgent
from .Evaluator import EvaluatorAgent

from utils import logger, model_usage
from utils.config import config


####################################
class CoordinatorAgent(BaseAgent):
    """
    Main coordinator that orchestrates the workflow of all other agents.
    """
    ##################################################################
    def __init__(self, memory: AgentMemory, api_keys: dict, **kwargs):
        super().__init__(memory, api_keys, **kwargs)
        
        # Get configuration from kwargs if provided
        self.config = kwargs.get('config', config)
        
        # Initialize sub-agents without duplicating the config parameter
        self.explorer = ExplorerAgent(memory, api_keys, **kwargs)
        self.navigator = NavigatorAgent(memory, api_keys, **kwargs)
        self.evaluator = EvaluatorAgent(memory, api_keys, **kwargs)
            
        # Give the evaluator access to the navigator
        self.evaluator.navigator = self.navigator
        
        # Track results
        self.results = {
            "found_jobs": [],
            "visited_sites": [],
            "potential_portals": []
        }
    
    ################################
    def _save_interim_results(self):
        """Save intermediate results to file."""
        today_str = datetime.datetime.today().strftime('%Y-%m-%d')
        
        # Create results directory if it doesn't exist
        os.makedirs("results", exist_ok=True)
        
        # Create a simplified version of results that's JSON serializable
        simple_results = {
            "found_jobs": [
                {
                    "id": job.get("id", ""),
                    "url": job.get("url", ""),
                    "title": job.get("title", ""),
                    "score": job.get("score", 0),
                    "suitable": job.get("suitable", False)
                }
                for job in self.results["found_jobs"]
            ],
            "visited_sites": self.results["visited_sites"],
            "potential_portals": [
                {
                    "url": portal.get("url", ""),
                    "title": portal.get("title", ""),
                    "listings_count": len(portal.get("specific_listings", []))
                }
                for portal in self.results["potential_portals"]
            ]
        }
        
        with open(f"results/interim_results_{today_str}.json", "w") as f:
            json.dump(simple_results, f, indent=2)

        
    #################################
    def _generate_final_report(self):
        """Generate final report with all findings."""
        today_str = datetime.datetime.today().strftime('%Y-%m-%d')
        
        # Create results directory if it doesn't exist
        os.makedirs("results", exist_ok=True)
        
        # Create a simplified version of results that's JSON serializable
        simple_results = {
            "found_jobs": [
                {
                    "id": job.get("id", ""),
                    "url": job.get("url", ""),
                    "title": job.get("title", ""),
                    "score": job.get("score", 0),
                    "suitable": job.get("suitable", False)
                }
                for job in self.results["found_jobs"]
            ],
            "visited_sites": self.results["visited_sites"],
            "potential_portals": [
                {
                    "url": portal.get("url", ""),
                    "title": portal.get("title", ""),
                    "listings_count": len(portal.get("specific_listings", []))
                }
                for portal in self.results["potential_portals"]
            ]
        }
        
        # Save detailed results
        with open(f"results/final_results_{today_str}.json", "w") as f:
            json.dump(simple_results, f, indent=2)
        
        # Create HTML report
        self._create_html_report(today_str)


    #############################################
    def _create_html_report(self, date_str: str):
        """Create HTML report of findings."""
        # Get output configuration from config
        report_title = self.config.get("output.report_title", "Job Search Results")
        
        # Get color scheme from config or use defaults
        colors = {
            "primary": self.config.get("output.color_scheme.primary", "#2c3e50"),
            "secondary": self.config.get("output.color_scheme.secondary", "#3498db"),
            "success": self.config.get("output.color_scheme.success", "#27ae60"),
            "warning": self.config.get("output.color_scheme.warning", "#f39c12"),
            "danger": self.config.get("output.color_scheme.danger", "#e74c3c"),
            "background": self.config.get("output.color_scheme.background", "#f9f9f9"),
            "card_background": self.config.get("output.color_scheme.card_background", "#ffffff")
        }
        
        html_content = f"""<!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>{report_title} - {date_str}</title>
            <style>
                body {{
                    font-family: Arial, sans-serif;
                    margin: 20px;
                    padding: 20px;
                    line-height: 1.6;
                }}
                h1, h2, h3 {{
                    color: {colors["primary"]};
                }}
                .result-card {{
                    border: 1px solid #e1e1e1;
                    border-radius: 5px;
                    padding: 15px;
                    margin-bottom: 20px;
                    box-shadow: 0 2px 5px rgba(0,0,0,0.1);
                    background-color: {colors["card_background"]};
                }}
                .score-high {{
                    color: {colors["success"]};
                    font-weight: bold;
                }}
                .score-medium {{
                    color: {colors["warning"]};
                    font-weight: bold;
                }}
                .score-low {{
                    color: {colors["danger"]};
                    font-weight: bold;
                }}
                a {{
                    color: {colors["secondary"]};
                    text-decoration: none;
                }}
                a:hover {{
                    text-decoration: underline;
                }}
                .summary {{
                    background-color: {colors["background"]};
                    padding: 15px;
                    border-radius: 5px;
                    margin-bottom: 30px;
                }}
                .stats {{
                    display: flex;
                    justify-content: space-between;
                    flex-wrap: wrap;
                }}
                .stat-card {{
                    flex-basis: 48%;
                    background-color: {colors["card_background"]};
                    padding: 10px;
                    margin-bottom: 10px;
                    border-radius: 5px;
                    box-shadow: 0 1px 3px rgba(0,0,0,0.1);
                }}
                .stat-number {{
                    font-size: 24px;
                    font-weight: bold;
                    color: {colors["primary"]};
                }}
            </style>
        </head>
        <body>
            <h1>{report_title}</h1>
            <p>Report generated on {date_str}</p>
            
            <div class="summary">
                <h2>Summary</h2>
                <div class="stats">
                    <div class="stat-card">
                        <p>Sites Visited</p>
                        <p class="stat-number">{len(self.results['visited_sites'])}</p>
                    </div>
                    <div class="stat-card">
                        <p>Job Details Explored</p>
                        <p class="stat-number">{self.explorer.explored_jobs_count}</p>
                    </div>
                    <div class="stat-card">
                        <p>Relevant Jobs Found</p>
                        <p class="stat-number">{len(self.results['found_jobs'])}</p>
                    </div>
                    <div class="stat-card">
                        <p>Job Portals Identified</p>
                        <p class="stat-number">{len(self.results['potential_portals'])}</p>
                    </div>
                </div>
            </div>
            
            <h2>Relevant Job Positions</h2>
        """
        
        # Add all found jobs
        if self.results['found_jobs']:
            for job in self.results['found_jobs']:
                score_class = "score-low"
                if job['score'] >= 4:
                    score_class = "score-high"
                elif job['score'] >= 3:
                    score_class = "score-medium"
                
                html_content += f"""
                <div class="result-card">
                    <h3>{job['title']}</h3>
                    <p>Relevance: <span class="{score_class}">{job['score']}/5</span></p>
                    <p>Suitable for Interim Manager: {'Yes' if job['suitable'] else 'Potential'}</p>
                    <p><a href="{job['url']}" target="_blank">View Job Listing</a></p>
                </div>
                """
        else:
            html_content += "<p>No specific job positions found that meet the criteria.</p>"
        
        # Add potential portals
        html_content += "<h2>Job Portals with Potential Opportunities</h2>"
        
        if self.results['potential_portals']:
            for portal in self.results['potential_portals']:
                html_content += f"""
                <div class="result-card">
                    <h3>{portal['title']}</h3>
                    <p><a href="{portal['url']}" target="_blank">Visit Portal</a></p>
                    <h4>Potential Listings:</h4>
                    <ul>
                """
                
                # Handle different types of listings (TextCitation or dict)
                if 'specific_listings' in portal:
                    for listing in portal['specific_listings']:
                        # Check if listing is a TextDict object or a dictionary
                        if hasattr(listing, 'text_dict'):
                            # It's a TextDict object
                            # Parse the text_dict string to extract information
                            # This part depends on how text_dict is formatted, but likely something like:
                            import re
                            url_match = re.search(r'url[\'"]?\s*:\s*[\'"]([^\'"]+)[\'"]', listing.text_dict)
                            title_match = re.search(r'title[\'"]?\s*:\s*[\'"]([^\'"]+)[\'"]', listing.text_dict)
                            
                            listing_url = url_match.group(1) if url_match else portal['url']
                            listing_title = title_match.group(1) if title_match else 'Position'
                            html_content += f"""
                            <li><a href="{listing_url}" target="_blank">{listing_title}</a></li>
                            """
                        else:
                            # It's a regular dictionary
                            listing_url = listing.get('url', portal['url'])
                            listing_title = listing.get('title', 'Untitled Position')
                            listing_desc = listing.get('description', 'No description available')
                            html_content += f"""
                            <li><a href="{listing_url}" target="_blank">{listing_title}</a>: 
                                {listing_desc}</li>
                            """

                html_content += """
                    </ul>
                </div>
                """
        else:
            html_content += "<p>No job portals identified.</p>"
        
        # Add explored sites
        html_content += "<h2>Sites Visited</h2><ul>"
        for site in self.results['visited_sites']:
            domain = self.explorer._extract_domain(site)
            jobs_explored = self.explorer.jobs_explored_per_site.get(domain, 0)
            html_content += f"<li><a href='{site}' target='_blank'>{domain}</a> - Jobs explored: {jobs_explored}</li>"
        html_content += "</ul>"
        
        # Add model usage summary
        html_content += """
            <h2>Model Usage Summary</h2>
            <table border="1" cellpadding="5" cellspacing="0">
                <tr>
                    <th>Model</th>
                    <th>Cost Level</th>
                    <th>Calls</th>
                </tr>
        """

        usage_summary = model_usage.get_summary()
        for model, data in usage_summary.items():
            html_content += f"""
                <tr>
                    <td>{model}</td>
                    <td>{data['cost_level']}</td>
                    <td>{data['count']}</td>
                </tr>
            """
        
        html_content += """
            </table>
            
        </body>
        </html>
        """
        
        # Write the HTML to file
        with open(f"results/job_search_report_{date_str}.html", "w") as f:
            f.write(html_content)
        
        self.log(f"Created HTML report: results/job_search_report_{date_str}.html")
    
    ############################################
    def _extract_domain(self, url: str) -> str:
        """Extract the domain from a URL."""
        parsed_url = urlparse(url)
        return parsed_url.netloc


    ##############################################################
    ##############################################################
    def run(self, target_sites: List[str]) -> Dict[str, Any]:
        """
        Run the complete workflow, coordinating between agents.
        
        Args:
            target_sites: List of career sites to explore
            
        Returns:
            Dictionary containing final results
        """
        # Get the task name and description from config if available
        task_name = self.config.get("task_name", "Web Search")
        task_description = self.config.get("task_description", "Exploring websites to find relevant information")
        
        self.log(f"Starting {task_name}: {task_description}")
        start_time = time.time()
        
        # Create results directory if it doesn't exist
        os.makedirs("results", exist_ok=True)
        
        # Connect Explorer to Evaluator for job quota tracking
        self.evaluator.explorer = self.explorer
        
        # Main exploration loop
        while not self.explorer.is_satisfied():
            try:
                # 1. Select next site to visit
                site_url = self.explorer.select_next_site(target_sites)
                self.explorer.record_visit(site_url)
                self.results["visited_sites"].append(site_url)
                
                # 2. Explore the site structure
                status, navigation_data = self.navigator.explore_site(site_url)
                
                if status != "SUCCESS":
                    self.log(f"Skipping site due to status: {status}")
                    continue
                
                # 3. Handle navigation data differently based on chunking
                is_chunked = navigation_data.get("is_chunked", False)
                
                if is_chunked:
                    self.log(f"Site {site_url} was chunked into {navigation_data.get('chunk_count', 0)} parts")
                    
                    # Process each chunk separately
                    for chunk_data in navigation_data.get("chunks", []):
                        chunk_url = chunk_data.get("chunk_url", site_url)
                        chunk_id = chunk_data.get("chunk_id", 0)
                        
                        self.log(f"Processing chunk {chunk_id} from {site_url}")
                        
                        # 3a. If the chunk has job listings, evaluate them
                        if chunk_data.get("has_job_listings", False):
                            # Re-download the content, but this time just the chunk
                            chunk_content = self._get_chunk_content(site_url, chunk_id, navigation_data)
                            
                            if chunk_content:
                                # Evaluate the content
                                is_relevant, evaluation_data = self.evaluator.evaluate_content(chunk_url, chunk_content)
                                
                                # Process the evaluation results
                                self._process_evaluation_results(chunk_url, is_relevant, evaluation_data)
                        
                        # Always update site memory for this chunk
                        self._update_site_memory_for_chunk(site_url, chunk_data)
                
                else:
                    # Process the site normally (no chunking)
                    # 3b. If the site has job listings, evaluate them
                    if navigation_data.get("has_job_listings", False):
                        # Download the content again (this time we know it's valuable)
                        status, content = self.navigator._download_content(site_url)
                        
                        if status == "OK" and content:
                            # Evaluate the content
                            is_relevant, evaluation_data = self.evaluator.evaluate_content(site_url, content)
                            
                            # Process the evaluation results
                            self._process_evaluation_results(site_url, is_relevant, evaluation_data)
                    else:
                        # No job listings on this page
                        # Update site memory with navigation info for future visits
                        self.memory.update_site_memory(site_url, {
                            "success_rate": 0.4,  # Moderate score, might be useful later
                            "job_listings_path": navigation_data.get("job_listings_path")
                        })
                
                # Save intermediate results
                self._save_interim_results()

            except Exception as e:
                self.log(f"Error exploring site {site_url}: {e}")
                # Update site memory with failed status
                self.memory.update_site_memory(site_url, {"success_rate": 0.1})
                continue

        
        # Exploration complete
        end_time = time.time()
        duration = end_time - start_time
        
        self.log(f"Exploration complete after {len(self.results['visited_sites'])} site visits")
        self.log(f"Found {len(self.results['found_jobs'])} relevant jobs and {len(self.results['potential_portals'])} potential job portals")
        self.log(f"Total jobs explored: {self.explorer.explored_jobs_count}")
        self.log(f"Total duration: {duration:.2f} seconds")
        
        # Generate final report
        self._generate_final_report()
        
        # Print model usage summary
        model_usage.print_summary()
        
        return self.results
    ##############################################################
    ##############################################################



    # Add helper methods for chunk processing
    ##########################################################################################
    def _get_chunk_content(self, site_url: str, chunk_id: int, navigation_data: Dict[str, Any]) -> Optional[str]:
        """
        Get content for a specific chunk of a site.
        
        Args:
            site_url: Original site URL
            chunk_id: ID of the chunk
            navigation_data: Navigation data containing chunks
            
        Returns:
            str: Content of the chunk or None if not available
        """
        # Re-download the full content and extract the chunk
        status, full_content = self.navigator._download_content(site_url)
        
        if status != "OK" or not full_content:
            return None
        
        # Get the chunk boundaries from navigation data if available
        chunk_boundaries = None
        for chunk in navigation_data.get("chunks", []):
            if chunk.get("chunk_id") == chunk_id:
                chunk_boundaries = chunk.get("chunk_boundaries")
                break
        
        # If we have explicit boundaries, use them
        if chunk_boundaries and isinstance(chunk_boundaries, dict) and "start" in chunk_boundaries and "end" in chunk_boundaries:
            start = chunk_boundaries["start"]
            end = chunk_boundaries["end"]
            return full_content[start:end]
        
        # Otherwise, re-chunk the content and return the appropriate chunk
        if self.navigator._needs_chunking(full_content):
            chunks = self.navigator._chunk_content(full_content)
            if 0 <= chunk_id - 1 < len(chunks):
                return chunks[chunk_id - 1]
        
        # If all else fails, return None
        return None

    def _process_evaluation_results(self, url: str, is_relevant: bool, evaluation_data: Dict[str, Any]):
        """
        Process evaluation results for a site or chunk.
        
        Args:
            url: URL of the site or chunk
            is_relevant: Whether the content was relevant
            evaluation_data: Data from evaluator
        """
        if is_relevant:
            # Process based on whether it's a portal or specific job
            if evaluation_data.get("is_generic_portal", False):
                # Add to potential portals
                self.results["potential_portals"].append({
                    "url": url,
                    "title": evaluation_data.get("job_title", "Unknown Portal"),
                    "specific_listings": evaluation_data.get("specific_job_listings", [])
                })
                
                # Update site memory with higher success rate
                self.memory.update_site_memory(self._extract_base_url(url), {"success_rate": 0.8})

                # Check if we found relevant jobs on this portal
                if evaluation_data.get("found_relevant_jobs"):
                    for job_url, job_data in evaluation_data.get("found_relevant_jobs"):
                        # Extract text from TextCitation objects in keywords and requirements
                        keywords = []
                        for kw in (evaluation_data.get("keywords",[]) or []):
                            if hasattr(kw, 'text_snippet'):
                                keywords.append(kw.text_snippet)
                            else:
                                keywords.append(kw)

                        requirements = []
                        for req in evaluation_data.get("requirements", [] or []):
                            if hasattr(req, 'text_snippet'):
                                requirements.append(req.text_snippet)
                            else:
                                requirements.append(req)
                        # Add the job to memory
                        job_id = self.memory.add_job({
                            "url": url,
                            "domain": self._extract_domain(url),
                            "title": evaluation_data.get("job_title", "Unknown Position"),
                            "relevance_score": evaluation_data.get("relevance_score", 0),
                            "is_interim_suitable": evaluation_data.get("is_interim_suitable", False),
                            "description_summary": evaluation_data.get("description_summary", ""),
                            "keywords": keywords,
                            "location": evaluation_data.get("location"),
                            "requirements": requirements
                        })
                        
                        # Record the job as found
                        self.explorer.record_found_job(job_id)
                        self.results["found_jobs"].append({
                            "id": job_id,
                            "url": job_url,
                            "title": job_data.get("job_title", "Unknown Position"),
                            "score": job_data.get("relevance_score", 0),
                            "suitable": job_data.get("is_interim_suitable", False)
                        })
                        
                        self.log(f"Added relevant job from portal: {job_data.get('job_title')} (Score: {job_data.get('relevance_score', 0)})")
            else:
                # Extract text from TextCitation objects in keywords and requirements
                keywords = []
                for kw in (evaluation_data.get("keywords",[]) or []):
                    if hasattr(kw, 'text_snippet'):
                        keywords.append(kw.text_snippet)
                    else:
                        keywords.append(kw)

                requirements = []
                for req in evaluation_data.get("requirements", [] or []):
                    if hasattr(req, 'text_snippet'):
                        requirements.append(req.text_snippet)
                    else:
                        requirements.append(req)
                        
                # Add the job to memory
                job_id = self.memory.add_job({
                    "url": url,
                    "domain": self._extract_domain(url),
                    "title": evaluation_data.get("job_title", "Unknown Position"),
                    "relevance_score": evaluation_data.get("relevance_score", 0),
                    "is_interim_suitable": evaluation_data.get("is_interim_suitable", False),
                    "description_summary": evaluation_data.get("description_summary", ""),
                    "keywords": keywords,
                    "location": evaluation_data.get("location"),
                    "requirements": requirements
                })
                
                # Record the job as found
                self.explorer.record_found_job(job_id)
                self.results["found_jobs"].append({
                    "id": job_id,
                    "url": url,
                    "title": evaluation_data.get("job_title", "Unknown Position"),
                    "score": evaluation_data.get("relevance_score", 0),
                    "suitable": evaluation_data.get("is_interim_suitable", False)
                })
                
                # Update site memory with higher success rate
                self.memory.update_site_memory(self._extract_base_url(url), {"success_rate": 0.9})
        else:
            # Update site memory with lower success rate
            self.memory.update_site_memory(self._extract_base_url(url), {"success_rate": 0.3})


    ###
    def _update_site_memory_for_chunk(self, site_url: str, chunk_data: Dict[str, Any]):
        """
        Update site memory based on chunk data.
        
        Args:
            site_url: Original site URL
            chunk_data: Data from the chunk
        """
        # Calculate a success rate for this chunk
        success_rate = 0.3  # Default moderate-low score
        
        if chunk_data.get("has_job_listings", False):
            success_rate = 0.7  # Higher score if it has job listings
        
        # Get current site memory
        site_memory = self.memory.get_site_memory(site_url)
        
        if site_memory:
            # Update with chunk-specific paths if they seem useful
            updates = {}
            
            # If this chunk has job listings path and the main site doesn't, add it
            if chunk_data.get("job_listings_path") and not site_memory.job_listings_path:
                updates["job_listings_path"] = chunk_data.get("job_listings_path")
            
            # If this chunk has search form path and the main site doesn't, add it
            if chunk_data.get("search_form_path") and not site_memory.search_form_path:
                updates["search_form_path"] = chunk_data.get("search_form_path")
            
            # Add unique navigation paths
            if "navigation_paths" in chunk_data:
                new_paths = []
                for path in chunk_data["navigation_paths"]:
                    if path not in site_memory.navigation_paths:
                        new_paths.append(path)
                
                if new_paths:
                    updates["navigation_paths"] = site_memory.navigation_paths + new_paths
            
            # Only update if we have changes
            if updates:
                self.memory.update_site_memory(site_url, updates)
        else:
            # Create new site memory with this chunk's data
            self.memory.update_site_memory(site_url, {
                "navigation_paths": chunk_data.get("navigation_paths", []),
                "job_listings_path": chunk_data.get("job_listings_path"),
                "search_form_path": chunk_data.get("search_form_path"),
                "notes": chunk_data.get("site_structure", ""),
                "success_rate": success_rate
            })

    def _extract_base_url(self, url: str) -> str:
        """
        Extract the base URL from a chunk URL.
        
        Args:
            url: URL of the site or chunk
            
        Returns:
            str: Base URL without chunk identifier
        """
        # Remove chunk identifier (#chunk1, etc.)
        return url.split('#')[0]