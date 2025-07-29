"""
curious_surfer.py

Main script to run the curious internet surfer job search system.
This script initializes the system and starts the exploration process.
"""

import os
import sys
import time
import datetime
import argparse
from typing import List

# Import the agent framework
from Agent_modules import agent_main
from utils.config import load_config, config




def parse_arguments():
    """
    Parse command line arguments:
    --exploration-rate:
    Default value: 0.3 (30%)
    Purpose: Controls the balance between exploring new sites versus exploiting known promising sites. 
    A higher value (closer to 1.0) means the system will more frequently choose to visit new, 
    unexplored sites rather than returning to sites it already knows are productive.
    Example: Setting it to 0.5 would make the system spend half its time exploring new options.


    --satisfaction-threshold:
    Default value: 15
    Purpose: Defines how many "good" jobs need to be found before the system considers its search complete and stops. 
    This is one of the termination conditions.
    Example: Setting it to 10 would make the system continue searching until it finds 10 relevant jobs.


    --max-visits:
    Default value: 20
    Purpose: Limits the total number of site visits the system will make, regardless of how many jobs it finds. 
    This is another termination condition to prevent excessive resource usage.
    Example: Setting it to 20 would allow the system to visit up to 20 different sites.


    --max-jobs-per-site:
    Default value: 5
    Purpose: Restricts how many job details the system will explore on a single site. 
    This prevents the system from getting stuck on a single site that might have many job listings.
    Example: Setting it to 5 would allow the system to explore up to 5 job detail pages per site.


    --max-total-jobs:
    Default value: 15
    Purpose: Caps the total number of job detail pages the system will explore across all sites. 
    This is another global limit to manage resource usage.
    Example: Setting it to 30 would allow the system to explore up to 30 job listings in total.


    --memory-file:
    Default value: "agent_memory.json"
    Purpose: Specifies the file path where the system stores its memory about sites visited, 
    jobs found, and successful patterns. This allows the system to learn from past runs.
    Example: Setting it to "custom_memory.json" would use that file to store and retrieve memory.


    --custom-sites:
    Default value: None
    Purpose: Allows specifying a JSON file containing a custom list of sites to visit, instead of using 
    the built-in target sites list.
    Example: Setting it to "my_sites.json" would load site URLs from that file.


    --config:
    Default value: None
    Purpose: Specifies the path to a YAML configuration file with domain-specific settings and prompts.
    Example: Setting it to "config.yaml" would load all domain configuration from that file.


    --verbose:
    Default: Not enabled (flag must be explicitly added)
    Purpose: Enables more detailed logging output for debugging and monitoring.
    Example: Adding --verbose would make the system output more detailed logs.
    
    """
    parser = argparse.ArgumentParser(description="Curious Internet Surfer for Job Search")
    
    parser.add_argument(
        "--exploration-rate", 
        type=float, 
        default=0.3,
        help="Rate of exploration vs. exploitation (0.0-1.0)"
    )
    
    parser.add_argument(
        "--satisfaction-threshold", 
        type=int, 
        default=10, ##########
        help="Number of good jobs to find before stopping"
    )
    
    parser.add_argument(
        "--max-visits", 
        type=int, 
        default=20, ##########
        help="Maximum number of site visits"
    )
    
    parser.add_argument(
        "--max-jobs-per-site", 
        type=int, 
        default=5,
        help="Maximum number of job listings to explore on a single site"
    )
    
    parser.add_argument(
        "--max-total-jobs", 
        type=int, 
        default=15,
        help="Maximum total number of job detail pages to explore"
    )
    
    parser.add_argument(
        "--memory-file", 
        type=str, 
        default="agent_memory.json",
        help="Path to memory file"
    )
    
    parser.add_argument(
        "--custom-sites", 
        type=str, 
        default=None,
        help="Path to JSON file with custom site list"
    )
    
    parser.add_argument(
        "--config", 
        type=str, 
        default="config.yaml",
        help="Path to YAML configuration file with domain-specific settings"
    )
    
    parser.add_argument(
        "--verbose", 
        action="store_true",
        help="Enable verbose logging"
    )
    
    return parser.parse_args()



################################################################
def run_with_progress():
    """Run the main workflow with progress tracking."""
    args = parse_arguments()
    
    # Load configuration
    if args.config:
        try:
            load_config(args.config)
            print(f"Loaded configuration from {args.config}")
        except Exception as e:
            print(f"Error loading configuration: {e}")
            print("Continuing with default settings...")
    
    print_banner()
    
    # Get task name from config or use default
    task_name = config.get("task_name", "Job Search")
    task_description = config.get("task_description", "Searching for relevant job listings")
    
    print(f"Starting {task_name} with the following parameters:")
    print(f"- Task: {task_description}")
    print(f"- Exploration rate: {args.exploration_rate}")
    print(f"- Satisfaction threshold: {args.satisfaction_threshold} jobs")
    print(f"- Maximum visits: {args.max_visits} sites")
    print(f"- Maximum jobs per site: {args.max_jobs_per_site}")
    print(f"- Maximum total jobs to explore: {args.max_total_jobs}")
    print(f"- Memory file: {args.memory_file}")
    print(f"- Configuration file: {args.config}")
    
    # Set up directory for results
    os.makedirs("results", exist_ok=True)
    
    # Modify sys.argv for the agent_main function
    # This allows us to pass arguments to the main function
    sys.argv = [
        sys.argv[0],
        f"--exploration-rate={args.exploration_rate}",
        f"--satisfaction-threshold={args.satisfaction_threshold}",
        f"--max-visits={args.max_visits}",
        f"--max-jobs-per-site={args.max_jobs_per_site}",
        f"--max-total-jobs-explored={args.max_total_jobs}",
        f"--memory-file={args.memory_file}",
        f"--config={args.config}"
    ]
    
    if args.verbose:
        sys.argv.append("--verbose")
    
    if args.custom_sites:
        custom_sites = load_custom_sites(args.custom_sites)
        if custom_sites:
            print(f"Loaded {len(custom_sites)} custom sites from {args.custom_sites}")
            sys.argv.append(f"--custom-sites={args.custom_sites}")
    
    # Start timing
    start_time = time.time()
    
    try:
        # Run the main agent workflow
        results = agent_main(args.config)
        
        # Calculate timing
        end_time = time.time()
        duration = end_time - start_time
        
        # Print final summary
        print("\n" + "="*60)
        print(f"Search completed in {duration:.2f} seconds")
        print(f"Visited {len(results['visited_sites'])} sites")
        print(f"Found {len(results['found_jobs'])} relevant results")
        print(f"Explored {results.get('total_jobs_explored', 'unknown')} listings")
        print(f"Identified {len(results['potential_portals'])} portals")
        
        # Print result titles
        if results['found_jobs']:
            print("\nRelevant results found:")
            for job in results['found_jobs']:
                print(f"- {job['title']} (Score: {job['score']}/5)")
        
        # Print report location
        today_str = datetime.datetime.today().strftime('%Y-%m-%d')
        print(f"\nDetailed report available at: results/job_search_report_{today_str}.html")
        
    except KeyboardInterrupt:
        print("\nSearch interrupted by user.")
        end_time = time.time()
        print(f"Ran for {end_time - start_time:.2f} seconds before interruption")
    except Exception as e:
        print(f"\nError during search: {e}")
        import traceback
        traceback.print_exc()


def print_banner():
    """Print a banner for the application."""
    # Get task name from config or use default
    task_name = config.get("task_name", "Job Search")
    
    banner = f"""
    ╔═══════════════════════════════════════════════════════════╗
    ║                                                           ║
    ║         Curious Internet Surfer - {task_name:<18}         ║
    ║                                                           ║
    ╚═══════════════════════════════════════════════════════════╝
    """
    print(banner)


####################################################
def load_custom_sites(file_path: str) -> List[str]:
    """Load custom sites from a JSON file."""
    import json
    
    try:
        with open(file_path, "r") as f:
            data = json.load(f)
            
        if isinstance(data, list):
            return data
        elif isinstance(data, dict) and "sites" in data:
            return data["sites"]
        else:
            print(f"Error: Invalid format in {file_path}. Expected a list or a dict with 'sites' key.")
            return []
    except Exception as e:
        print(f"Error loading custom sites: {e}")
        return []




if __name__ == "__main__":
    run_with_progress()