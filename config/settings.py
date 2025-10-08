"""
Configuration management for immunization charts.

This module handles loading and managing configuration from YAML files
and provides a centralized configuration interface.
"""

import yaml
from pathlib import Path
from typing import Dict, Any, List
import logging

logger = logging.getLogger(__name__)


class Config:
    """Configuration manager for the immunization charts application."""
    
    def __init__(self, config_dir: Path = None):
        """Initialize configuration manager.
        
        Args:
            config_dir: Path to configuration directory. Defaults to current directory.
        """
        if config_dir is None:
            config_dir = Path(__file__).parent
        
        self.config_dir = config_dir
        self._parameters = None
        self._disease_map = None
        self._vaccine_reference = None
        
    def load_parameters(self) -> Dict[str, Any]:
        """Load parameters from YAML file."""
        if self._parameters is None:
            params_file = self.config_dir / "parameters.yaml"
            try:
                with open(params_file, 'r', encoding='utf-8') as f:
                    self._parameters = yaml.safe_load(f)
                logger.info(f"Loaded parameters from {params_file}")
            except FileNotFoundError:
                logger.error(f"Parameters file not found: {params_file}")
                raise
            except yaml.YAMLError as e:
                logger.error(f"Error parsing parameters file: {e}")
                raise
        
        return self._parameters
    
    def load_disease_map(self) -> Dict[str, str]:
        """Load disease mapping from JSON file."""
        if self._disease_map is None:
            disease_file = self.config_dir / "disease_map.json"
            try:
                import json
                with open(disease_file, 'r', encoding='utf-8') as f:
                    self._disease_map = json.load(f)
                logger.info(f"Loaded disease map from {disease_file}")
            except FileNotFoundError:
                logger.error(f"Disease map file not found: {disease_file}")
                raise
            except json.JSONDecodeError as e:
                logger.error(f"Error parsing disease map file: {e}")
                raise
        
        return self._disease_map
    
    def load_vaccine_reference(self) -> Dict[str, Any]:
        """Load vaccine reference from JSON file."""
        if self._vaccine_reference is None:
            vaccine_file = self.config_dir / "vaccine_reference.json"
            try:
                import json
                with open(vaccine_file, 'r', encoding='utf-8') as f:
                    self._vaccine_reference = json.load(f)
                logger.info(f"Loaded vaccine reference from {vaccine_file}")
            except FileNotFoundError:
                logger.error(f"Vaccine reference file not found: {vaccine_file}")
                raise
            except json.JSONDecodeError as e:
                logger.error(f"Error parsing vaccine reference file: {e}")
                raise
        
        return self._vaccine_reference
    
    @property
    def parameters(self) -> Dict[str, Any]:
        """Get parameters configuration."""
        return self.load_parameters()
    
    @property
    def disease_map(self) -> Dict[str, str]:
        """Get disease mapping configuration."""
        return self.load_disease_map()
    
    @property
    def vaccine_reference(self) -> Dict[str, Any]:
        """Get vaccine reference configuration."""
        return self.load_vaccine_reference()
    
    @property
    def batch_size(self) -> int:
        """Get batch size from parameters."""
        return self.parameters.get('batch_size', 100)
    
    @property
    def delivery_date(self) -> str:
        """Get delivery date from parameters."""
        return self.parameters.get('delivery_date', '2025-04-08')
    
    @property
    def data_date(self) -> str:
        """Get data date from parameters."""
        return self.parameters.get('data_date', '2025-04-01')
    
    @property
    def min_rows(self) -> int:
        """Get minimum rows from parameters."""
        return self.parameters.get('min_rows', 5)
    
    @property
    def expected_columns(self) -> List[str]:
        """Get expected columns from parameters."""
        return self.parameters.get('expected_columns', [])
    
    @property
    def chart_diseases_header(self) -> List[str]:
        """Get chart diseases header from parameters."""
        return self.parameters.get('chart_diseases_header', [])
    
    @property
    def ignore_agents(self) -> List[str]:
        """Get ignore agents from parameters."""
        return self.parameters.get('ignore_agents', [])


# Global configuration instance
config = Config()
