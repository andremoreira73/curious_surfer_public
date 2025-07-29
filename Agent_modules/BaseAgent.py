
from .AgentMemory import AgentMemory
from utils import logger, model_usage



class BaseAgent:
    """Base class for all agents in the system."""
    
    def __init__(self, memory: AgentMemory, api_keys: dict, **kwargs):
        self.memory = memory
        self.api_keys = api_keys
        self.config = kwargs
        self.name = self.__class__.__name__
    
    def process(self, *args, **kwargs):
        """Process method to be implemented by specific agents."""
        raise NotImplementedError("Each agent must implement its own process method")
    
    def log(self, message: str):
        """Log messages with agent name."""
        logger.info(f"[{self.name}] {message}")