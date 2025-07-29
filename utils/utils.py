
import logging
import sys
import datetime
from collections import defaultdict

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

class ModelUsage:
    """Tracks model usage and associated costs."""
    
    def __init__(self):
        self.usage = defaultdict(lambda: {"count": 0, "tokens": 0})
        
    def log_usage(self, model: str, purpose: str, tokens: int = 0):
        """Log usage of an AI model."""
        self.usage[model]["count"] += 1
        self.usage[model]["tokens"] += tokens
        
        # Log to console with cost indicator
        cost_indicator = MODEL_COST.get(model, "?")
        logger.info(f"[MODEL CALL] {model} ({cost_indicator}) - {purpose}")
    
    def get_summary(self) -> dict:
        """Get summary of model usage."""
        summary = {}
        for model, data in self.usage.items():
            cost_indicator = MODEL_COST.get(model, "?")
            summary[model] = {
                "count": data["count"],
                "estimated_tokens": data["tokens"],
                "cost_level": cost_indicator
            }
        return summary
    
    def print_summary(self):
        """Print summary of model usage to console."""
        summary = self.get_summary()
        
        logger.info("===== MODEL USAGE SUMMARY =====")
        for model, data in summary.items():
            logger.info(f"{model} ({data['cost_level']}): {data['count']} calls, ~{data['estimated_tokens']} tokens")
        logger.info("===============================")

# Global model usage tracker
model_usage = ModelUsage()