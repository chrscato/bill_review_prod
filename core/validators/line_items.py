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
                        "hcfa_line_count": 0,
                        "order_line_count": len(order_lines) if not order_lines.empty else 0,
                        "matching_lines": [],
                        "missing_from_order": [],
                        "missing_from_hcfa": [],
                        "diagnostic_info": {
                            "error": "No line items in HCFA data to validate"
                        }
                    }
                }
                
            if order_lines.empty:
                return {
                    "status": "FAIL",
                    "message": "No line items in order data",
                    "messages": ["No line items in order data"],
                    "details": {
                        "hcfa_line_count": len(hcfa_lines),
                        "order_line_count": 0,
                        "matching_lines": [],
                        "missing_from_order": [self._format_hcfa_line(line) for line in hcfa_lines],
                        "missing_from_hcfa": [],
                        "diagnostic_info": {
                            "error": "No line items in order data to compare against"
                        }
                    }
                }
            
            # Extract CPT codes from both datasets
            hcfa_cpts = set(clean_cpt_code(line.get('cpt', '')) for line in hcfa_lines if line.get('cpt'))
            order_cpts = set(clean_cpt_code(str(cpt)) for cpt in order_lines['CPT'].tolist() if pd.notna(cpt))
            
            # Match line items
            matched_order_indices = set()
            matched_hcfa_indices = set()
            matches = []
            
            # First pass: exact CPT matches
            for h_idx, h_line in enumerate(hcfa_lines):
                h_cpt = clean_cpt_code(h_line.get('cpt', ''))
                if not h_cpt:
                    continue
                    
                for o_idx, o_row in order_lines.iterrows():
                    if o_idx in matched_order_indices:
                        continue
                        
                    o_cpt = clean_cpt_code(str(o_row['CPT']))
                    if h_cpt == o_cpt:
                        # Match found
                        matches.append({
                            'hcfa_idx': h_idx,
                            'order_idx': o_idx,
                            'cpt': h_cpt,
                            'match_type': 'exact',
                            'match_quality': 1.0,
                            'hcfa_line': self._format_hcfa_line(h_line),
                            'order_line': self._format_order_line(o_row)
                        })
                        matched_hcfa_indices.add(h_idx)
                        matched_order_indices.add(o_idx)
                        break
            
            # Second pass: fuzzy matches for remaining unmatched lines
            for h_idx, h_line in enumerate(hcfa_lines):
                if h_idx in matched_hcfa_indices:
                    continue
                    
                h_cpt = clean_cpt_code(h_line.get('cpt', ''))
                if not h_cpt:
                    continue
                
                best_match = None
                best_score = 0.0
                
                for o_idx, o_row in order_lines.iterrows():
                    if o_idx in matched_order_indices:
                        continue
                        
                    o_cpt = clean_cpt_code(str(o_row['CPT']))
                    
                    # Check for clinical equivalence
                    if self._is_clinically_equivalent(h_cpt, o_cpt):
                        match_quality = 0.9  # High but not exact
                        if match_quality > best_score:
                            best_score = match_quality
                            best_match = {
                                'hcfa_idx': h_idx,
                                'order_idx': o_idx,
                                'cpt': h_cpt,
                                'match_type': 'clinical_equivalent',
                                'match_quality': match_quality,
                                'hcfa_line': self._format_hcfa_line(h_line),
                                'order_line': self._format_order_line(o_row)
                            }
                
                if best_match and best_score >= 0.7:  # Only accept good matches
                    matches.append(best_match)
                    matched_hcfa_indices.add(h_idx)
                    matched_order_indices.add(best_match['order_idx'])
            
            # Identify unmatched lines
            unmatched_hcfa = [
                self._format_hcfa_line(hcfa_lines[i]) 
                for i in range(len(hcfa_lines)) 
                if i not in matched_hcfa_indices
            ]
            
            unmatched_order = [
                self._format_order_line(order_lines.iloc[i]) 
                for i in range(len(order_lines)) 
                if i not in matched_order_indices
            ]
            
            # Check for special cases - all CPTs missing from one side
            all_hcfa_missing = len(matched_hcfa_indices) == 0
            all_order_missing = len(matched_order_indices) == 0
            
            # Generate detailed validation result
            result = {
                "status": "PASS" if not (unmatched_hcfa or unmatched_order) else "FAIL",
                "details": {
                    "hcfa_line_count": len(hcfa_lines),
                    "order_line_count": len(order_lines),
                    "matching_lines_count": len(matches),
                    "matching_lines": matches,
                    "missing_from_order": unmatched_hcfa,
                    "missing_from_hcfa": unmatched_order,
                    "diagnostic_info": {
                        "all_hcfa_missing": all_hcfa_missing,
                        "all_order_missing": all_order_missing,
                        "hcfa_cpts": list(hcfa_cpts),
                        "order_cpts": list(order_cpts)
                    }
                }
            }
            
            # Create human-readable messages
            messages = []
            
            if result["status"] == "PASS":
                messages.append(f"All {len(matches)} line items matched successfully")
            else:
                if all_hcfa_missing:
                    messages.append("None of the HCFA line items matched order data")
                elif all_order_missing:
                    messages.append("None of the order line items matched HCFA data")
                else:
                    if unmatched_hcfa:
                        messages.append(f"{len(unmatched_hcfa)} HCFA line items not found in order data")
                        for i, line in enumerate(unmatched_hcfa[:3]):
                            messages.append(f"  - Missing in order: CPT {line.get('cpt')}")
                        if len(unmatched_hcfa) > 3:
                            messages.append(f"  - ... and {len(unmatched_hcfa) - 3} more")
                    
                    if unmatched_order:
                        messages.append(f"{len(unmatched_order)} order line items not found in HCFA data")
                        for i, line in enumerate(unmatched_order[:3]):
                            messages.append(f"  - Missing in HCFA: CPT {line.get('cpt')}")
                        if len(unmatched_order) > 3:
                            messages.append(f"  - ... and {len(unmatched_order) - 3} more")
            
            result["message"] = messages[0] if messages else ""
            result["messages"] = messages
            
            return result
            
        except Exception as e:
            # Capture traceback for better error reporting
            error_traceback = traceback.format_exc()
            error_message = f"Error during line item validation: {str(e)}"
            
            # Log the error with full details
            if self.logger:
                self.logger.error(error_message)
                self.logger.error(error_traceback)
            
            # Return structured error response
            return {
                "status": "FAIL",
                "message": error_message,
                "messages": [
                    error_message,
                    f"Error type: {e.__class__.__name__}"
                ],
                "details": {
                    "error": str(e),
                    "error_type": e.__class__.__name__,
                    "error_traceback": error_traceback,
                    "hcfa_line_count": len(hcfa_lines) if hcfa_lines else 0,
                    "order_line_count": len(order_lines) if not order_lines.empty else 0,
                    "diagnostic_info": {
                        "hcfa_sample": hcfa_lines[0] if hcfa_lines else None,
                        "order_sample": order_lines.iloc[0].to_dict() if not order_lines.empty else None
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