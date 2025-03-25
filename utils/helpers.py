# Utility functions 
# utils/helpers.py
from typing import Any, Optional, List, Dict, Union
import re
import json
from datetime import datetime
from pathlib import Path
import logging

def clean_tin(tin: Any) -> Optional[str]:
    """
    Clean the TIN by removing dashes (-) and whitespace, ensuring 9 digits.
    
    Args:
        tin: TIN to clean, can be any type
        
    Returns:
        str: Cleaned TIN or None if invalid
    """
    if tin is None:
        return None
        
    # Convert to string
    tin_str = str(tin).strip()
    
    # Remove non-digit characters
    cleaned = re.sub(r'\D', '', tin_str)
    
    # Check if it's a valid 9-digit TIN
    if len(cleaned) == 9 and cleaned.isdigit():
        return cleaned
        
    return None

def safe_int(value: Any, default: int = 0) -> int:
    """
    Safely convert a value to integer, returning a default if conversion fails.
    
    Args:
        value: Value to convert
        default: Default value to return if conversion fails
        
    Returns:
        int: Converted integer or default
    """
    try:
        # Handle string with commas or other formatting
        if isinstance(value, str):
            value = value.replace(',', '').strip()
            
        return int(float(value))
    except (ValueError, TypeError):
        return default

def safe_float(value: Any, default: float = 0.0) -> float:
    """
    Safely convert a value to float, returning a default if conversion fails.
    
    Args:
        value: Value to convert
        default: Default value to return if conversion fails
        
    Returns:
        float: Converted float or default
    """
    try:
        # Handle string with commas or other formatting
        if isinstance(value, str):
            value = value.replace(',', '').strip()
            
        return float(value)
    except (ValueError, TypeError):
        return default

def format_currency(amount: Any) -> str:
    """
    Format a number as currency with dollar sign and two decimal places.
    
    Args:
        amount: Amount to format
        
    Returns:
        str: Formatted currency string
    """
    try:
        value = safe_float(amount)
        return f"${value:,.2f}"
    except (ValueError, TypeError):
        return "$0.00"

def string_similarity(s1: str, s2: str) -> float:
    """
    Calculate the similarity between two strings (0.0 to 1.0).
    Uses a simple Levenshtein distance ratio.
    
    Args:
        s1: First string
        s2: Second string
        
    Returns:
        float: Similarity ratio (0.0 to 1.0)
    """
    if s1 == s2:
        return 1.0
        
    if not s1 or not s2:
        return 0.0
        
    # Simple implementation of Levenshtein distance
    len_s1, len_s2 = len(s1), len(s2)
    
    # Create matrix of size (len_s1+1) x (len_s2+1)
    distance = [[0 for _ in range(len_s2 + 1)] for _ in range(len_s1 + 1)]
    
    # Initialize first row and column
    for i in range(len_s1 + 1):
        distance[i][0] = i
    for j in range(len_s2 + 1):
        distance[0][j] = j
    
    # Fill the matrix
    for i in range(1, len_s1 + 1):
        for j in range(1, len_s2 + 1):
            cost = 0 if s1[i-1] == s2[j-1] else 1
            distance[i][j] = min(
                distance[i-1][j] + 1,      # deletion
                distance[i][j-1] + 1,      # insertion
                distance[i-1][j-1] + cost  # substitution
            )
    
    # Calculate similarity ratio
    max_len = max(len_s1, len_s2)
    if max_len == 0:
        return 1.0
    
    similarity = 1.0 - (distance[len_s1][len_s2] / max_len)
    return similarity

def load_json_file(file_path: Union[str, Path]) -> Dict:
    """
    Load and parse a JSON file with error handling.
    
    Args:
        file_path: Path to the JSON file
        
    Returns:
        Dict: Parsed JSON data or empty dict if error
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (IOError, json.JSONDecodeError) as e:
        logger = logging.getLogger(__name__)
        logger.error(f"Error loading JSON file {file_path}: {e}")
        return {}

def save_json_file(data: Any, file_path: Union[str, Path], indent: int = 2) -> bool:
    """
    Save data to a JSON file with error handling.
    
    Args:
        data: Data to save
        file_path: Path to save the JSON file
        indent: Indentation level for formatting
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=indent)
        return True
    except (IOError, TypeError) as e:
        print(f"Error saving JSON file {file_path}: {e}")
        return False

def format_timestamp(dt: Optional[datetime] = None) -> str:
    """
    Format a timestamp for file naming.
    
    Args:
        dt: Datetime object to format (default: current time)
        
    Returns:
        str: Formatted timestamp
    """
    if dt is None:
        dt = datetime.now()
    return dt.strftime("%Y%m%d_%H%M%S")

def is_valid_date(date_str: str) -> bool:
    """
    Check if a string is a valid date.
    
    Args:
        date_str: Date string to validate
        
    Returns:
        bool: True if valid date, False otherwise
    """
    try:
        # Try parsing with standard ISO format
        datetime.fromisoformat(date_str)
        return True
    except ValueError:
        pass
    
    # Try other common formats
    formats = [
        "%Y-%m-%d",
        "%m/%d/%Y",
        "%d/%m/%Y",
        "%m-%d-%Y",
        "%d-%m-%Y",
        "%Y/%m/%d"
    ]
    
    for fmt in formats:
        try:
            datetime.strptime(date_str, fmt)
            return True
        except ValueError:
            continue
    
    return False

def clean_cpt_code(cpt: Any) -> str:
    """
    Clean and normalize a CPT code.
    
    Args:
        cpt: CPT code to clean
        
    Returns:
        str: Cleaned CPT code
    """
    if cpt is None:
        return ""
    
    # Convert to string and trim
    cpt_str = str(cpt).strip()
    
    # Remove non-alphanumeric characters
    cpt_str = re.sub(r'[^\w]', '', cpt_str)
    
    return cpt_str