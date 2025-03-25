# Enhanced error logging utility for Healthcare Bill Review System
# Create a new file: utils/logging_utils.py

import sys
import traceback
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any

# Configure logging
def setup_logging(log_dir: Path, log_level: int = logging.INFO) -> logging.Logger:
    """
    Set up logging with file and console handlers.
    
    Args:
        log_dir: Directory for log files
        log_level: Logging level (default: INFO)
        
    Returns:
        logging.Logger: Configured logger
    """
    log_dir.mkdir(exist_ok=True, parents=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = log_dir / f"bill_review_{timestamp}.log"
    
    # Create logger
    logger = logging.getLogger("bill_review")
    logger.setLevel(log_level)
    
    # Create file handler
    file_handler = logging.FileHandler(log_file)
    file_handler.setLevel(log_level)
    
    # Create console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_level)
    
    # Create formatter and add to handlers
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)
    
    # Add handlers to logger
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger

def log_exception(logger: logging.Logger, e: Exception, context: Optional[Dict[str, Any]] = None) -> str:
    """
    Log an exception with detailed information and context.
    
    Args:
        logger: Logger to use
        e: Exception to log
        context: Additional context information
        
    Returns:
        str: Formatted error message
    """
    exc_type, exc_value, exc_traceback = sys.exc_info()
    tb_lines = traceback.format_exception(exc_type, exc_value, exc_traceback)
    tb_text = ''.join(tb_lines)
    
    # Format context info
    context_str = ""
    if context:
        context_str = "\nContext:\n" + "\n".join(f"  {k}: {v}" for k, v in context.items())
    
    # Create detailed error message
    error_msg = f"Exception: {e.__class__.__name__}: {str(e)}{context_str}"
    
    # Log the error
    logger.error(error_msg)
    logger.debug(f"Traceback:\n{tb_text}")
    
    return error_msg

def get_error_details(e: Exception) -> Dict[str, str]:
    """
    Get detailed information about an exception.
    
    Args:
        e: Exception to analyze
        
    Returns:
        Dict: Detailed error information
    """
    exc_type, exc_value, exc_traceback = sys.exc_info()
    tb_lines = traceback.format_exception(exc_type, exc_value, exc_traceback)
    
    return {
        "error_type": e.__class__.__name__,
        "error_message": str(e),
        "traceback": ''.join(tb_lines),
        "error_location": tb_lines[-2] if len(tb_lines) >= 2 else "Unknown"
    }