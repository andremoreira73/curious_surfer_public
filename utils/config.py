
"""
Configuration loader for the Curious Internet Surfer.
Reads and provides access to domain-specific configuration.
"""

import os
import yaml
from typing import Dict, Any, List, Optional

# Default configuration file path
DEFAULT_CONFIG_PATH = "config.yaml"

class Config:
    """
    Configuration manager for the Curious Internet Surfer.
    Handles loading and accessing configuration values.
    """
    
    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize the configuration manager.
        
        Args:
            config_path: Path to the configuration file. If None, uses DEFAULT_CONFIG_PATH.
        """
        self.config_path = config_path or DEFAULT_CONFIG_PATH
        self.config_data = {}
        self.load_config()
    
    def load_config(self) -> None:
        """Load configuration from file."""
        try:
            with open(self.config_path, 'r', encoding='utf-8') as file:
                self.config_data = yaml.safe_load(file)
                
            # Log successful loading
            print(f"Loaded configuration from {self.config_path}")
        except Exception as e:
            print(f"Error loading configuration from {self.config_path}: {e}")
            # Initialize with empty config to avoid errors
            self.config_data = {}
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        Get a configuration value by dot-separated key path.
        
        Args:
            key: Dot-separated path to configuration value (e.g., "models.fast_model")
            default: Default value to return if key is not found
            
        Returns:
            Configuration value or default if not found
        """
        # Handle dot notation for nested keys
        if '.' in key:
            parts = key.split('.')
            value = self.config_data
            
            for part in parts:
                if isinstance(value, dict) and part in value:
                    value = value[part]
                else:
                    return default
                    
            return value
        
        # Simple key access
        return self.config_data.get(key, default)
    
    def get_prompt(self, prompt_name: str) -> str:
        """
        Get a prompt template by name.
        
        Args:
            prompt_name: Name of the prompt (e.g., "job_relevance")
            
        Returns:
            Prompt template string or empty string if not found
        """
        return self.get(f"prompts.{prompt_name}", "")
    
    def get_target_sites(self) -> List[str]:
        """
        Get the list of target sites to search.
        
        Returns:
            List of site URLs
        """
        return self.get("target_sites", [])
    
    def get_model(self, model_type: str) -> str:
        """
        Get an AI model name by type.
        
        Args:
            model_type: Type of model (e.g., "fast_model", "standard_model", "advanced_model")
            
        Returns:
            Model name string or default model if not found
        """
        model = self.get(f"models.{model_type}")
        if not model:
            # Default to fast model if not found
            model = self.get("models.fast_model", "gpt-4o-mini")
        return model
    
    def get_domain_terms(self, category: str = None) -> List[str]:
        """
        Get domain-specific terminology.
        
        Args:
            category: Optional category of terms (e.g., "german", "english", "negative_indicators")
            
        Returns:
            List of terms or empty list if not found
        """
        if category:
            return self.get(f"domain_terms.{category}", [])
        
        # If no category specified, combine all terms
        all_terms = []
        domain_terms = self.get("domain_terms", {})
        
        if isinstance(domain_terms, dict):
            for term_list in domain_terms.values():
                if isinstance(term_list, list):
                    all_terms.extend(term_list)
        
        return all_terms
    
    def get_evaluation_criteria(self) -> Dict[str, Any]:
        """
        Get evaluation criteria configuration.
        
        Returns:
            Dictionary of evaluation criteria
        """
        return self.get("evaluation", {})

# Create a global instance for easy access throughout the application
config = Config()

def load_config(config_path: str = None) -> Config:
    """
    Load or reload configuration.
    
    Args:
        config_path: Optional path to configuration file
        
    Returns:
        Config instance
    """
    global config
    config = Config(config_path)
    return config