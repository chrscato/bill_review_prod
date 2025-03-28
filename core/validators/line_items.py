# core/validators/line_items.py
from typing import Dict, List, Set, Tuple, Optional, Any
import pandas as pd
import logging
import traceback
from utils.helpers import clean_cpt_code, string_similarity

class LineItemValidator:
    """
    Enhanced validator for matching line items between order and HCFA data.
    Features improved error reporting and diagnostics.
    """
    
    def __init__(self, dim_proc_df: Optional[pd.DataFrame] = None, logger: Optional[logging.Logger] = None):
        """
        Initialize the line items validator.
        
        Args:
            dim_proc_df: DataFrame with procedure code information (optional)
            logger: Logger for diagnostic information (optional)
        """
        self.dim_proc_df = dim_proc_df
        self.logger = logger or logging.getLogger(__name__)
        
        # Setup CPT code mapping from dim_proc if available
        self.cpt_categories = {}
        if self.dim_proc_df is not None:
            for _, row in self.dim_proc_df.iterrows():
                if pd.notna(row.get('proc_cd')) and pd.notna(row.get('proc_category')):
                    self.cpt_categories[str(row['proc_cd'])] = str(row['proc_category'])
    
    def validate(self, hcfa_lines: List[Dict], order_lines: pd.DataFrame) -> Dict:
        """
        Validate line items between HCFA data and order data.
        
        Args:
            hcfa_lines: Line items from HCFA data
            order_lines: DataFrame with line items from order data
            
        Returns:
            Dict: Validation results
        """
        try:
            # Handle empty inputs
            if not hcfa_lines:
                return {
                    "status": "FAIL",
                    "message": "No line items in HCFA data",
                    "messages": ["No line items in HCFA data"],
                    "details": {
                        "missing_codes": [],
                        "mismatched_codes": [],
                        "component_billing": {
                            "is_component_billing": False,
                            "component_type": None,
                            "affected_line_items": [],
                            "message": ""
                        }
                    }
                }
            
            if order_lines.empty:
                return {
                    "status": "FAIL",
                    "message": "No line items in order data",
                    "messages": ["No line items in order data"],
                    "details": {
                        "missing_codes": [],
                        "mismatched_codes": [],
                        "component_billing": {
                            "is_component_billing": False,
                            "component_type": None,
                            "affected_line_items": [],
                            "message": ""
                        }
                    }
                }
            
            # Track component billing information
            component_billing_info = {
                "is_component_billing": False,
                "component_type": None,
                "affected_line_items": [],
                "message": ""
            }
            
            # Track missing and mismatched codes
            missing_codes = []
            mismatched_codes = []
            
            # Process each HCFA line
            for h_idx, h_line in enumerate(hcfa_lines):
                h_cpt = clean_cpt_code(h_line.get('cpt', ''))
                if not h_cpt:
                    continue
                
                # Find matching order line
                match_found = False
                matched_order_line = None
                
                for _, o_line in order_lines.iterrows():
                    o_cpt = clean_cpt_code(o_line.get('CPT', ''))
                    if not o_cpt:
                        continue
                    
                    # Check for exact match or clinical equivalence
                    if h_cpt == o_cpt or self._is_clinically_equivalent(h_cpt, o_cpt):
                        match_found = True
                        matched_order_line = o_line
                        break
                
                # After finding a match, check component modifiers
                if match_found:
                    component_check = self._check_component_modifiers(h_line, matched_order_line)
                    
                    if component_check["component_type"]:
                        component_billing_info["is_component_billing"] = True
                        component_billing_info["component_type"] = component_check["component_type"]
                        component_billing_info["affected_line_items"].append({
                            "index": h_idx,
                            "cpt": h_cpt,
                            "modifier": "TC" if component_check["component_type"] == "technical" else "26"
                        })
                        
                    if component_check["has_component_mismatch"]:
                        # Record the mismatch but don't necessarily fail the validation
                        # Just note it for reporting
                        if not component_billing_info["message"]:
                            component_billing_info["message"] = component_check["message"]
                else:
                    missing_codes.append(h_cpt)
            
            # Generate result
            result = {
                "status": "PASS" if not missing_codes else "FAIL",
                "message": "Line items match" if not missing_codes else f"Missing {len(missing_codes)} line items",
                "messages": [],
                "details": {
                    "missing_codes": missing_codes,
                    "mismatched_codes": mismatched_codes,
                    "component_billing": component_billing_info
                }
            }
            
            # Add messages
            if missing_codes:
                result["messages"].append(f"Missing {len(missing_codes)} line items: {', '.join(missing_codes)}")
            
            # Update messages if this is a non-global bill
            if component_billing_info["is_component_billing"]:
                component_type = "technical component (TC)" if component_billing_info["component_type"] == "technical" else "professional component (26)"
                
                if result["status"] == "PASS":
                    result["messages"].insert(0, f"Non-global bill validation passed ({component_type})")
                else:
                    # Add component info to failure message, but don't change the main status
                    result["messages"].append(f"Note: This is a {component_type} bill, not a global bill")
            
            return result
            
        except Exception as e:
            self.logger.error(f"Error in line items validation: {str(e)}")
            self.logger.error(traceback.format_exc())
            return {
                "status": "FAIL",
                "message": f"Error in validation: {str(e)}",
                "messages": [f"Error in validation: {str(e)}"],
                "details": {
                    "error": str(e),
                    "traceback": traceback.format_exc(),
                    "component_billing": {
                        "is_component_billing": False,
                        "component_type": None,
                        "affected_line_items": [],
                        "message": ""
                    }
                }
            }
    
    def _format_hcfa_line(self, line: Dict) -> Dict:
        """Format HCFA line item for comparison and reporting."""
        return {
            "cpt": clean_cpt_code(line.get('cpt', '')),
            "units": line.get('units', 1),
            "modifier": line.get('modifier', ''),
            "charge": line.get('charge', 0)
        }
    
    def _format_order_line(self, row: pd.Series) -> Dict:
        """Format order line item for comparison and reporting."""
        return {
            "cpt": clean_cpt_code(str(row.get('CPT', ''))),
            "units": row.get('Units', 1),
            "modifier": row.get('Modifier', ''),
            "description": row.get('Description', '')
        }
    
    def _is_clinically_equivalent(self, cpt1: str, cpt2: str) -> bool:
        """
        Check if two CPT codes are clinically equivalent.
        This is a simplified implementation - in a real system, this would use 
        a comprehensive mapping of equivalent codes.
        """
        # Check if they're the same code
        if cpt1 == cpt2:
            return True
            
        # Check if they are in the same category
        cat1 = self.cpt_categories.get(cpt1)
        cat2 = self.cpt_categories.get(cpt2)
        
        if cat1 and cat2 and cat1 == cat2:
            # Codes in same category might be equivalent
            
            # Check for common patterns of equivalent codes:
            # MRI with/without contrast: codes often differ only in last digit
            if cpt1[:4] == cpt2[:4] and cpt1.startswith('7'):
                # First 4 digits match for imaging codes
                return True
                
            # Therapeutic procedures with similar descriptions
            if cpt1.startswith('2') and cpt2.startswith('2'):
                # Both are therapeutic procedures, check code similarity
                return self._code_similarity(cpt1, cpt2) >= 0.8
        
        # Not clinically equivalent
        return False
    
    def _code_similarity(self, cpt1: str, cpt2: str) -> float:
        """
        Calculate similarity between two CPT codes.
        Returns a value between 0.0 and 1.0.
        """
        # Exact match
        if cpt1 == cpt2:
            return 1.0
            
        # Calculate prefix similarity
        prefix_len = 0
        for i in range(min(len(cpt1), len(cpt2))):
            if cpt1[i] == cpt2[i]:
                prefix_len += 1
            else:
                break
                
        # Calculate similarity score
        max_len = max(len(cpt1), len(cpt2))
        if max_len == 0:
            return 0.0
            
        return prefix_len / max_len

    def _check_component_modifiers(self, hcfa_line: Dict, order_line: Dict) -> Dict:
        """
        Check if there are component modifiers (TC or 26) that affect matching.
        
        Args:
            hcfa_line: HCFA line item
            order_line: Order line item
            
        Returns:
            Dict: Component modifier assessment
        """
        result = {
            "has_component_mismatch": False,
            "component_type": None,
            "message": ""
        }
        
        # Get modifiers from both sides
        hcfa_modifiers = set(str(hcfa_line.get('modifier', '')).split(',')) if hcfa_line.get('modifier') else set()
        order_modifiers = set(str(order_line.get('Modifier', '')).split(',')) if order_line.get('Modifier') else set()
        
        # Clean modifiers
        hcfa_modifiers = {mod.strip().upper() for mod in hcfa_modifiers if mod.strip()}
        order_modifiers = {mod.strip().upper() for mod in order_modifiers if mod.strip()}
        
        # Check for component modifiers
        hcfa_has_tc = "TC" in hcfa_modifiers
        hcfa_has_26 = "26" in hcfa_modifiers
        order_has_tc = "TC" in order_modifiers
        order_has_26 = "26" in order_modifiers
        
        # Determine component type in HCFA
        if hcfa_has_tc:
            result["component_type"] = "technical"
        elif hcfa_has_26:
            result["component_type"] = "professional"
            
        # Check for mismatches
        if (hcfa_has_tc and not order_has_tc) or (hcfa_has_26 and not order_has_26):
            result["has_component_mismatch"] = True
            
            if hcfa_has_tc:
                result["message"] = "Order is for global service but bill is for technical component (TC) only"
            else:
                result["message"] = "Order is for global service but bill is for professional component (26) only"
        
        # Also check the reverse
        if (order_has_tc and not hcfa_has_tc) or (order_has_26 and not hcfa_has_26):
            result["has_component_mismatch"] = True
            
            if order_has_tc:
                result["message"] = "Order is for technical component (TC) only but bill is for global service"
            else:
                result["message"] = "Order is for professional component (26) only but bill is for global service"
        
        return result