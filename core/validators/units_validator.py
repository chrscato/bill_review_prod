# Units validation 
# core/validators/units_validator.py
from typing import Dict, List, Set, Optional, Tuple
import pandas as pd
from utils.helpers import safe_int, clean_cpt_code

class UnitsValidator:
    """
    Validator for checking procedure code units.
    Ensures units are appropriate for the CPT codes, with special handling for bundles.
    """
    
    def __init__(self, dim_proc_df: Optional[pd.DataFrame] = None):
        """
        Initialize the units validator.
        
        Args:
            dim_proc_df: DataFrame with procedure code information (optional)
        """
        self.dim_proc_df = dim_proc_df
        
        # Set of CPT codes that can have multiple units regardless of category
        self.multi_unit_exempt_codes = {
            # Time-based codes
            "95910", "95911", "95912", "95913",  # Nerve conduction studies
            "97110", "97112", "97116", "97140", "97530",  # Therapeutic procedures (15-min increments)
            # Other exempt codes that commonly have multiple units
            "76140",  # X-ray consultation
            "96372",  # Therapeutic injection
            "96373",  # Intra-arterial injection
            "96374",  # IV push
        }
        
        # Maximum allowed units for any code (safety limit)
        self.max_allowed_units = 12
        
        # Bundle-specific unit rules
        self.bundle_unit_rules = {
            "emg": {
                # EMG nerve conduction studies
                "95907": 1, "95908": 1, "95909": 1, "95910": 1, "95911": 1, "95912": 1, "95913": 1,
                # EMG needle exam
                "95885": 4, "95886": 4, "95887": 1,
                # Office visit
                "99203": 1, "99204": 1, "99205": 1
            },
            "arthrogram": {
                # Imaging codes: always 1 unit
                "73040": 1, "73201": 1, "73222": 1, "73525": 1, "73580": 1, "73701": 1, "73722": 1,
                # Injection codes: always 1 unit
                "23350": 1, "24220": 1, "25246": 1, "27093": 1, "27370": 1, "27648": 1,
                # Guidance: always 1 unit
                "77002": 1
            },
            "therapeutic_injection": {
                # Injection codes: can have multiple units
                "20600": 2, "20604": 2, "20605": 2, "20606": 2, "20610": 2, "20611": 2,
                # Guidance: always 1 unit
                "77002": 1
            }
        }
    
    def get_proc_category(self, cpt: str) -> Optional[str]:
        """
        Get procedure category from reference data.
        
        Args:
            cpt: CPT code
            
        Returns:
            str: Procedure category or None if not found
        """
        if self.dim_proc_df is None:
            return None
            
        # Find matching procedure code
        match = self.dim_proc_df[self.dim_proc_df['proc_cd'] == str(cpt)]
        if match.empty:
            return None
            
        # Get category from first match
        category = match['proc_category'].iloc[0]
        
        # Handle empty or invalid categories
        if category is None or pd.isna(category) or str(category).strip() == "":
            return None
            
        return str(category).lower()
    
    def is_ancillary(self, cpt: str) -> bool:
        """
        Check if a CPT code is ancillary.
        
        Args:
            cpt: CPT code
            
        Returns:
            bool: True if ancillary, False otherwise
        """
        category = self.get_proc_category(cpt)
        return category == "ancillary" if category else False
    
    def get_max_units(self, cpt: str, bundle_type: Optional[str] = None) -> int:
        """
        Get maximum allowed units for a CPT code.
        
        Args:
            cpt: CPT code
            bundle_type: Bundle type (optional)
            
        Returns:
            int: Maximum allowed units
        """
        # For bundles, use bundle-specific rules
        if bundle_type and bundle_type in self.bundle_unit_rules and cpt in self.bundle_unit_rules[bundle_type]:
            return self.bundle_unit_rules[bundle_type][cpt]
            
        # For multi-unit exempt codes, allow multiple units
        if cpt in self.multi_unit_exempt_codes:
            return self.max_allowed_units
            
        # For ancillary codes, allow multiple units
        if self.is_ancillary(cpt):
            return self.max_allowed_units
            
        # Default to 1 unit for non-ancillary codes
        return 1
    
    def detect_bundle(self, line_items: List[Dict]) -> Dict:
        """
        Detect bundle type from line items.
        
        Args:
            line_items: List of line items
            
        Returns:
            Dict: Bundle detection result
        """
        # Extract CPT codes
        cpt_codes = {clean_cpt_code(line.get('cpt', '')) for line in line_items if line.get('cpt')}
        
        # Check for EMG bundle
        emg_codes = {
            "95907", "95908", "95909", "95910", "95911", "95912", "95913",  # NCS
            "95885", "95886", "95887",  # Needle EMG
            "99203", "99204", "99205"  # Office visit
        }
        emg_match = cpt_codes.intersection(emg_codes)
        if len(emg_match) >= 2 and any(code in cpt_codes for code in ["95885", "95886", "95887"]):
            return {
                "found": True,
                "type": "emg",
                "name": "EMG Study",
                "codes": list(emg_match)
            }
            
        # Check for arthrogram bundle
        arthrogram_imaging = {"73040", "73201", "73222", "73525", "73580", "73701", "73722"}
        arthrogram_injection = {"23350", "24220", "25246", "27093", "27370", "27648"}
        
        if cpt_codes.intersection(arthrogram_imaging) and cpt_codes.intersection(arthrogram_injection):
            return {
                "found": True,
                "type": "arthrogram",
                "name": "Arthrogram",
                "codes": list(cpt_codes.intersection(arthrogram_imaging.union(arthrogram_injection)))
            }
            
        # Check for therapeutic injection bundle
        injection_codes = {"20600", "20604", "20605", "20606", "20610", "20611"}
        guidance_codes = {"77002"}
        
        if cpt_codes.intersection(injection_codes) and cpt_codes.intersection(guidance_codes):
            return {
                "found": True,
                "type": "therapeutic_injection",
                "name": "Therapeutic Injection",
                "codes": list(cpt_codes.intersection(injection_codes.union(guidance_codes)))
            }
            
        # No bundle detected
        return {
            "found": False,
            "type": None,
            "name": None,
            "codes": []
        }
    
    def validate(self, hcfa_data: Dict) -> Dict:
        """
        Validate units in line items.
        
        Args:
            hcfa_data: HCFA data with line_items
            
        Returns:
            Dict: Validation results
        """
        if not hcfa_data or "line_items" not in hcfa_data:
            return {
                "status": "FAIL",
                "reason": "No line items to validate",
                "details": {
                    "total_checked": 0,
                    "total_invalid": 0
                }
            }
        
        line_items = hcfa_data.get('line_items', [])
        
        # First check if any line has bundle information
        bundle_type = None
        bundle_name = None
        
        for line in line_items:
            if line.get("bundle_type") and line.get("bundle_name"):
                bundle_type = line.get("bundle_type")
                bundle_name = line.get("bundle_name")
                break
        
        # If no bundle information found in lines, detect it
        bundle_info = None
        if not bundle_type:
            bundle_info = self.detect_bundle(line_items)
            if bundle_info["found"]:
                bundle_type = bundle_info["type"]
                bundle_name = bundle_info["name"]
        
        # Validate units for each line
        invalid_units = []
        
        for line in line_items:
            cpt = clean_cpt_code(line.get('cpt', ''))
            if not cpt:
                continue
                
            units = safe_int(line.get('units', 1))
            
            # Skip validation if units is 1 (always valid)
            if units <= 1:
                continue
                
            # Get maximum allowed units
            max_units = self.get_max_units(cpt, bundle_type)
            
            # Check if units exceed maximum
            if units > max_units:
                is_ancillary = self.is_ancillary(cpt)
                proc_category = self.get_proc_category(cpt)
                
                invalid_units.append({
                    "cpt": cpt,
                    "units": units,
                    "max_allowed": max_units,
                    "is_ancillary": is_ancillary,
                    "proc_category": proc_category or "unknown",
                    "bundle_type": bundle_type,
                    "reason": f"Units ({units}) exceed maximum allowed ({max_units})"
                })
        
        # Generate appropriate messages based on bundle type and validation results
        messages = []
        
        if bundle_type:
            messages.append(f"Bundle detected: {bundle_name} ({bundle_type})")
            
            if not invalid_units:
                messages.append(f"All units are valid for {bundle_type} bundle")
            else:
                messages.append(f"Found {len(invalid_units)} unit violation(s) in {bundle_type} bundle")
        else:
            if not invalid_units:
                messages.append("All units are valid")
            else:
                messages.append(f"Found {len(invalid_units)} unit violation(s)")
                
                # Count non-ancillary violations
                non_ancillary = [unit for unit in invalid_units if not unit.get("is_ancillary")]
                if non_ancillary:
                    messages.append(f"{len(non_ancillary)} non-ancillary CPT code(s) with multiple units")
        
        # Add details for first few violations
        for i, unit in enumerate(invalid_units[:3], 1):
            messages.append(f"  {i}. {unit['reason']} (CPT {unit['cpt']})")
            
        if len(invalid_units) > 3:
            messages.append(f"  ... and {len(invalid_units) - 3} more violations")
        
        # Return validation result
        return {
            "status": "FAIL" if invalid_units else "PASS",
            "details": {
                "all_unit_issues": invalid_units,
                "non_ancillary_violations": [unit for unit in invalid_units if not unit.get("is_ancillary")],
                "total_violations": len(invalid_units),
                "total_checked": len(line_items),
                "bundle_info": bundle_info or {"type": bundle_type, "name": bundle_name, "found": bool(bundle_type)}
            },
            "messages": messages
        }