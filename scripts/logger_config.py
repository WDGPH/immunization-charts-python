"""
Centralized logging configuration for the pipeline.
Ensures consistent logging format and level across all modules.
"""

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from datetime import datetime

def get_logger(name: str, log_dir: Path, level: int = logging.INFO):
    """
    Configures and returns a logger with the specified name and log directory.
    
    Args:
        name (str): Name of the logger.
        log_dir (Path): Directory where log files will be stored.
        level (int): Logging level (default is logging.INFO).
        
    Returns:
        logging.Logger: Configured logger instance.
    """

    # Check for existence of log directory, create if it doesn't exist
    log_dir.mkdir(parents=True, exist_ok=True)

    log_file = log_dir / f"{name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    # Create handlers - stream handler for stdout and rotating file handler for file logging
    file_handler = RotatingFileHandler(log_file, maxBytes=5*1024*1024, backupCount=5)
    console_handler = logging.StreamHandler()
    
    # Create formatters and add them to handlers
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)
    
    # Add handlers to the logger
    if not logger.hasHandlers():
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)
    
    return logger