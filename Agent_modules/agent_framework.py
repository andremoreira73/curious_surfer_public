"""
agent_framework.py

Core framework for the "curious internet surfer" approach to finding interim manager positions.
This system implements an organic, adaptive approach that explores career sites more like a
curious human would, rather than exhaustively scanning in a rigid manner.

The system features:
1. Exploratory browsing rather than exhaustive scanning
2. Memory of what works to guide future exploration
3. Adaptive navigation that learns site structures
4. Cost-aware AI model selection
5. Detailed logging of model usage and costs
"""

import os
import sys
import json
import datetime
from collections import defaultdict
import logging

from typing import Dict, Any

from .Coordinator import CoordinatorAgent
from .AgentMemory import AgentMemory

from utils import logger, model_usage
from utils.config import config, load_config



##############################################
# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] [%(name)s] [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(f"surfer_log_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.log")
    ]
)

# Create logger
logger = logging.getLogger("AgentFramework")


# Model cost indicators for logging
MODEL_COST = {
    "gpt-4o-mini": "$",
    "gpt-4o": "$$", 
    "o3-mini": "$$$"
}


##################################################
# Functions (outside of agents and memory system)
##################################################

def load_api_keys() -> Dict[str, str]:
    """
    Load API keys from files or environment variables.
    """
    api_keys = {}
    
    # Try to load OpenAI key
    try:
        with open("/home/memology/Documents/keys/OpenAI_keys_swarm.json", "r") as file:
            api_data = json.load(file)
            api_keys["oai_key"] = api_data.get("key")
    except Exception as e:
        logger.error(f"Could not load OpenAI key file: {e}")
        # Fallback to environment variable
        api_keys["oai_key"] = os.environ.get("OPENAI_API_KEY")
    
    # Try to load ScrapingBee key
    try:
        with open("/home/memology/Documents/keys/ScrapingBee_API.json", "r") as file:
            api_data = json.load(file)
            api_keys["SB_key"] = api_data.get("key")
            api_keys["SB_endpoint"] = api_data.get("endpoint")
    except Exception as e:
        logger.error(f"Could not load ScrapingBee key file: {e}")
        # Fallback to environment variables
        api_keys["SB_key"] = os.environ.get("SCRAPINGBEE_API_KEY")
        api_keys["SB_endpoint"] = os.environ.get("SCRAPINGBEE_ENDPOINT")
    
    # Try to load Google search key
    try:
        with open("/home/memology/Documents/keys/Google_search_API.json", "r") as file:
            api_data = json.load(file)
            api_keys["Google_key"] = api_data.get("key")
            api_keys["engine_ID"] = api_data.get("engine ID")
            api_keys["Google_endpoint"] = api_data.get("endpoint")
    except Exception as e:
        logger.error(f"Could not load Google API key file: {e}")
        # Fallback to environment variables
        api_keys["Google_key"] = os.environ.get("GOOGLE_API_KEY")
        api_keys["engine_ID"] = os.environ.get("GOOGLE_ENGINE_ID")
        api_keys["Google_endpoint"] = os.environ.get("GOOGLE_ENDPOINT")
    
    return api_keys




def agent_main(config_path: str = None):
    """
    Run the main workflow.
    
    Args:
        config_path: Optional path to configuration file
    """
    # Parse command line arguments if provided
    import argparse
    import sys
    
    parser = argparse.ArgumentParser(description="Curious Internet Surfer - Agent Framework")
    parser.add_argument("--exploration-rate", type=float, default=0.3)
    parser.add_argument("--satisfaction-threshold", type=int, default=5)
    parser.add_argument("--max-visits", type=int, default=10)
    parser.add_argument("--max-jobs-per-site", type=int, default=3)
    parser.add_argument("--max-total-jobs-explored", type=int, default=15)
    parser.add_argument("--memory-file", type=str, default="agent_memory.json")
    parser.add_argument("--custom-sites", type=str, default=None)
    parser.add_argument("--config", type=str, default=None)
    parser.add_argument("--verbose", action="store_true")
    
    args = parser.parse_args()
    
    # Load configuration
    config_path = args.config or config_path
    if config_path:
        load_config(config_path)
        logger.info(f"Loaded configuration from {config_path}")
    
    # Load API keys
    api_keys = load_api_keys()
    
    # Initialize memory
    memory = AgentMemory(args.memory_file)
    
    # Target sites - either use config or fall back to hardcoded list
    target_sites = config.get_target_sites()
    
    # If no target sites in config, use the previously hardcoded list
    if not target_sites:
        logger.warning("No target sites found in configuration, exiting")
        sys.exit() 
    
    # Load custom sites if provided
    if args.custom_sites:
        try:
            import json
            with open(args.custom_sites, 'r') as f:
                custom_data = json.load(f)
                if isinstance(custom_data, list):
                    target_sites = custom_data
                elif isinstance(custom_data, dict) and 'sites' in custom_data:
                    target_sites = custom_data['sites']
                logger.info(f"Loaded {len(target_sites)} custom sites from {args.custom_sites}")
        except Exception as e:
            logger.error(f"Error loading custom sites: {e}")
    
    # Create coordinator with configuration
    coordinator = CoordinatorAgent(
        memory,
        api_keys,
        exploration_rate=args.exploration_rate,
        satisfaction_threshold=args.satisfaction_threshold,
        max_visits=args.max_visits,
        max_jobs_per_site=args.max_jobs_per_site,
        max_total_jobs_explored=args.max_total_jobs_explored,
        config=config  # Pass the configuration to the coordinator
    )
    
    # Run the workflow
    results = coordinator.run(target_sites)
    
    # Add total jobs explored to results
    results['total_jobs_explored'] = coordinator.explorer.explored_jobs_count
    
    logger.info("Job search complete")
    
    return results




#if __name__ == "__main__":
#    main()