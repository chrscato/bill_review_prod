# Input data normalization 
# core/services/normalizer.py
from typing import Dict, List, Any, Optional
from datetime import datetime
import re
import json

def normalize_hcfa_format(data: dict) -> dict:
    """
    Convert various HCFA formats to a standardized format for processing.
    Handles both new format with service_lines and legacy format with line_items.
    
    Args:
        data: Dictionary containing HCFA data
        
    Returns:
        dict: Normalized HCFA data
    """
    # Check if the data is already in the expected format
    if "line_items" in data and isinstance(data["line_items"], list):
        # Data already has line_items, just ensure all fields are present
        return _ensure_standard_fields(data)
    
    # Check if this is the new format with service_lines
    if "service_lines" in data and isinstance(data["service_lines"], list):
        return _convert_service_lines_format(data)
    
    # If none of the above, try to infer the format
    return _infer_and_normalize_format(data)

def _ensure_standard_fields(data: dict) -> dict:
    """
    Ensure all standard fields are present in the data.
    
    Args:
        data: Dictionary containing HCFA data
        
    Returns:
        dict: HCFA data with all standard fields
    """
    normalized = data.copy()
    
    # Ensure basic fields exist
    if "patient_name" not in normalized:
        normalized["patient_name"] = None
    
    if "date_of_service" not in normalized:
        # Try to get date from first line item
        if normalized.get("line_items") and len(normalized["line_items"]) > 0:
            normalized["date_of_service"] = normalized["line_items"][0].get("date_of_service")
        else:
            normalized["date_of_service"] = None
    
    if "Order_ID" not in normalized:
        normalized["Order_ID"] = None
    
    # Normalize line items
    if "line_items" in normalized:
        for i, line in enumerate(normalized["line_items"]):
            # Ensure all line items have standard fields
            if "cpt" not in line:
                line["cpt"] = line.get("CPT", "")
            
            if "modifier" not in line:
                line["modifier"] = line.get("Modifier", "")
            
            if "units" not in line:
                line["units"] = line.get("Units", 1)
            
            if "charge" not in line:
                line["charge"] = line.get("Charge", "0.00")
                
            # Normalize modifiers to consistent format
            if isinstance(line["modifier"], list):
                line["modifier"] = ",".join(str(m) for m in line["modifier"])
            elif line["modifier"] is None:
                line["modifier"] = ""
    
    return normalized

def _convert_service_lines_format(data: dict) -> dict:
    """
    Convert new HCFA format with service_lines to the expected format with line_items.
    
    Args:
        data: Dictionary containing HCFA data with service_lines
        
    Returns:
        dict: Normalized HCFA data with line_items
    """
    normalized = {
        "patient_name": data.get("patient_info", {}).get("patient_name"),
        "date_of_service": data.get("service_lines", [{}])[0].get("date_of_service") if data.get("service_lines") else None,
        "Order_ID": data.get("Order_ID"),
        "billing_provider_tin": data.get("billing_info", {}).get("billing_provider_tin"),
        "billing_provider_npi": data.get("billing_info", {}).get("billing_provider_npi"),
        "billing_provider_name": data.get("billing_info", {}).get("billing_provider_name"),
        "total_charge": data.get("billing_info", {}).get("total_charge"),
        "raw_data": data,
        "line_items": []
    }
    
    # Convert service_lines to line_items
    for line in data.get("service_lines", []):
        normalized["line_items"].append({
            "cpt": line.get("cpt_code"),
            "modifier": ",".join(line.get("modifiers", [])) if line.get("modifiers") else "",
            "units": int(line.get("units", 1)),
            "charge": line.get("charge_amount", "0.00"),
            "date_of_service": line.get("date_of_service"),
            "place_of_service": line.get("place_of_service")
        })
    
    return normalized

def _infer_and_normalize_format(data: dict) -> dict:
    """
    Infer the format of the data and normalize it.
    Used when the format is not immediately apparent.
    
    Args:
        data: Dictionary containing HCFA data
        
    Returns:
        dict: Normalized HCFA data
    """
    normalized = {
        "patient_name": None,
        "date_of_service": None,
        "Order_ID": None,
        "line_items": []
    }
    
    # Infer fields from whatever is available
    for key, value in data.items():
        if key.lower() in ["patient", "patient_name", "patientname"]:
            normalized["patient_name"] = value
        elif key.lower() in ["dos", "date_of_service", "servicedate"]:
            normalized["date_of_service"] = value
        elif key.lower() in ["order_id", "orderid", "id"]:
            normalized["Order_ID"] = value
        elif key.lower() in ["billing_provider_tin", "tin", "providerin"]:
            normalized["billing_provider_tin"] = value
    
    # Try to find line items
    for key, value in data.items():
        if isinstance(value, list) and value and isinstance(value[0], dict):
            # This might be line items
            if any(k in value[0] for k in ["cpt", "CPT", "procedure", "code"]):
                for item in value:
                    line_item = {}
                    
                    # Map fields to standardized names
                    for item_key, item_value in item.items():
                        if item_key.lower() in ["cpt", "cptcode", "procedure", "code"]:
                            line_item["cpt"] = item_value
                        elif item_key.lower() in ["modifier", "mod", "modifiers"]:
                            line_item["modifier"] = item_value
                        elif item_key.lower() in ["units", "unit", "qty", "quantity"]:
                            line_item["units"] = int(item_value) if item_value else 1
                        elif item_key.lower() in ["charge", "amount", "fee"]:
                            line_item["charge"] = item_value
                    
                    normalized["line_items"].append(line_item)
    
    # Store original data for reference
    normalized["raw_data"] = data
    
    return _ensure_standard_fields(normalized)

def normalize_date(date_str: str) -> Optional[str]:
    """
    Normalize date to YYYY-MM-DD format.
    
    Args:
        date_str: Date string in various formats
        
    Returns:
        str: Normalized date string or None if invalid
    """
    if not date_str:
        return None
    
    # Try different date formats
    formats = [
        "%Y-%m-%d",      # 2024-01-01
        "%m/%d/%Y",      # 01/01/2024
        "%m-%d-%Y",      # 01-01-2024
        "%d/%m/%Y",      # 01/01/2024 (day first)
        "%d-%m-%Y",      # 01-01-2024 (day first)
        "%m/%d/%y",      # 01/01/24
        "%B %d, %Y",     # January 01, 2024
        "%d %B %Y",      # 01 January 2024
        "%Y%m%d"         # 20240101
    ]
    
    for fmt in formats:
        try:
            date_obj = datetime.strptime(date_str, fmt)
            return date_obj.strftime("%Y-%m-%d")
        except ValueError:
            continue
    
    # Try regex for other formats
    # Format like MM/DD/YYYY or MM-DD-YYYY
    match = re.match(r'(\d{1,2})[/\-](\d{1,2})[/\-](\d{2,4})', date_str)
    if match:
        month, day, year = match.groups()
        # Handle 2-digit years
        if len(year) == 2:
            year = f"20{year}" if int(year) < 50 else f"19{year}"
        try:
            date_obj = datetime(int(year), int(month), int(day))
            return date_obj.strftime("%Y-%m-%d")
        except ValueError:
            pass
    
    return None

def clean_modifiers(modifier_value: Any) -> List[str]:
    """
    Clean and normalize modifiers to a list format.
    
    Args:
        modifier_value: Modifier value in various formats
        
    Returns:
        List[str]: List of clean modifiers
    """
    if not modifier_value:
        return []
    
    # If already a list, just clean each item
    if isinstance(modifier_value, list):
        return [str(m).strip().upper() for m in modifier_value if m]
    
    # If string, split by common separators
    if isinstance(modifier_value, str):
        # Split by comma, space, or semicolon
        modifiers = re.split(r'[,;\s]+', modifier_value)
        return [m.strip().upper() for m in modifiers if m.strip()]
    
    # If something else, convert to string and return as single item
    return [str(modifier_value).strip().upper()]

def normalize_cpt_code(cpt: Any) -> str:
    """
    Normalize CPT code to standard format.
    
    Args:
        cpt: CPT code in various formats
        
    Returns:
        str: Normalized CPT code
    """
    if not cpt:
        return ""
    
    # Convert to string and remove any non-alphanumeric characters
    cpt_str = str(cpt).strip()
    
    # Remove any alpha prefix or suffix (like 'CPT:' or 'A')
    cpt_str = re.sub(r'^[A-Za-z]*[:\s]*', '', cpt_str)
    cpt_str = re.sub(r'[A-Za-z]*$', '', cpt_str)
    
    # Remove any leading zeros
    cpt_str = cpt_str.lstrip('0')
    
    # Ensure 5 digits for standard CPT codes
    if cpt_str.isdigit() and len(cpt_str) < 5:
        cpt_str = cpt_str.zfill(5)
    
    return cpt_str