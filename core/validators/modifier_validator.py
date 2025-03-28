# core/validators/modifier_validator.py
from typing import Dict, List, Set, Optional, Any
from config.settings import settings
from utils.helpers import clean_cpt_code

class ModifierValidator:
    """
    Validator for checking CPT code modifiers.
    Ensures modifiers are valid and appropriate for the CPT codes.
    """
    
    def __init__(self, invalid_modifiers: Optional[Set[str]] = None):
        """
        Initialize the modifier validator.
        
        Args:
            invalid_modifiers: Set of invalid modifiers (default: from settings)
        """
        # Use settings value if none provided
        self.invalid_modifiers = invalid_modifiers or settings.INVALID_MODIFIERS
        
        # Map of valid modifiers per CPT code range
        self.cpt_modifier_map = {
            # Diagnostic Radiology services
            "7": ["TC", "26", "RT", "LT", "50"],
            
            # Surgery CPT codes
            "2": ["RT", "LT", "50", "59", "79", "80", "81", "82"],
            
            # Physical Medicine codes
            "97": ["GP", "GN", "GO", "59"]
        }
        
        # Special case modifiers that are valid for specific CPT codes regardless of range
        self.special_case_modifiers = {
            "95885": ["RT", "LT", "59"],
            "95886": ["RT", "LT", "59"],
            "95887": ["RT", "LT", "59"],
            "95907": ["59"],
            "95908": ["59"],
            "95909": ["59"],
            "95910": ["59"],
            "95911": ["59"],
            "95912": ["59"],
            "95913": ["59"]
        }
        
        # Bundle-specific modifier rules
        self.bundle_modifier_rules = {
            "emg": {
                "allowed": ["RT", "LT", "59"],
                "required": []
            },
            "arthrogram": {
                "allowed": ["RT", "LT", "F1", "F2", "F3", "F4", "F5", "F6", "F7", "F8", "F9", "FA"],
                "required": []
            },
            "therapeutic_injection": {
                "allowed": ["RT", "LT", "50", "59"],
                "required": []
            }
        }
        
        # Incompatible modifiers (should not be used together)
        self.incompatible_modifiers = [
            {"26", "TC"},  # Professional and Technical components
            {"RT", "LT", "50"},  # Right, Left, and Bilateral
            {"80", "81", "82"},  # Assistant surgeon modifiers
        ]
    
    def detect_component_modifiers(self, hcfa_data: Dict) -> Dict:
        """
        Detect and categorize TC (Technical Component) or 26 (Professional Component) modifiers.
        
        Args:
            hcfa_data: HCFA data with line_items
            
        Returns:
            Dict: Component billing information
        """
        result = {
            "is_component_billing": False,
            "component_type": None,
            "affected_line_items": [],
            "message": ""
        }
        
        if not hcfa_data or "line_items" not in hcfa_data:
            return result
        
        # Check each line item for TC or 26 modifiers
        for i, line in enumerate(hcfa_data.get('line_items', [])):
            modifiers = self._parse_modifiers(line.get('modifier'))
            
            if "TC" in modifiers:
                result["is_component_billing"] = True
                result["component_type"] = "technical"
                result["affected_line_items"].append({
                    "index": i,
                    "cpt": line.get('cpt', ''),
                    "modifier": "TC"
                })
            elif "26" in modifiers:
                result["is_component_billing"] = True
                result["component_type"] = "professional"
                result["affected_line_items"].append({
                    "index": i,
                    "cpt": line.get('cpt', ''),
                    "modifier": "26"
                })
        
        # Generate appropriate message
        if result["is_component_billing"]:
            if result["component_type"] == "technical":
                result["message"] = "This is a technical component (TC) bill, not a global bill."
            else:
                result["message"] = "This is a professional component (26) bill, not a global bill."
                
            if len(result["affected_line_items"]) > 1:
                result["message"] += f" ({len(result['affected_line_items'])} line items affected)"
        
        return result

    def validate(self, hcfa_data: Dict) -> Dict:
        """
        Validate modifiers in HCFA data.
        
        Args:
            hcfa_data: HCFA data with line_items
            
        Returns:
            Dict: Validation results
        """
        result = {
            "status": "PASS",
            "messages": [],
            "details": {
                "invalid_modifiers": [],
                "incompatible_sets": [],
                "missing_required": []
            }
        }
        
        if not hcfa_data or "line_items" not in hcfa_data:
            result["status"] = "FAIL"
            result["messages"].append("No line items found in HCFA data")
            return result
        
        # Track invalid modifiers and incompatible sets
        invalid_modifiers = []
        incompatible_sets = []
        missing_required = []
        
        # Check each line item
        for i, line in enumerate(hcfa_data.get('line_items', [])):
            cpt = line.get('cpt', '')
            if not cpt:
                continue
                
            # Clean CPT code
            cpt = clean_cpt_code(cpt)
            
            # Get bundle type if available
            bundle_type = line.get('bundle_type')
            
            # Get modifiers for this line
            modifiers = self._parse_modifiers(line.get('modifier'))
            
            # Get valid modifiers for this CPT code
            valid_modifiers = self._get_valid_modifiers(cpt, bundle_type)
            
            # Check for invalid modifiers
            invalid = modifiers - valid_modifiers
            if invalid:
                invalid_modifiers.append({
                    "line_index": i,
                    "cpt": cpt,
                    "modifiers": list(invalid)
                })
            
            # Check for incompatible modifier sets
            if "TC" in modifiers and "26" in modifiers:
                incompatible_sets.append({
                    "line_index": i,
                    "cpt": cpt,
                    "modifiers": ["TC", "26"]
                })
            
            # Check for required modifiers based on bundle type
            if bundle_type and bundle_type in self.bundle_modifier_rules:
                required = self.bundle_modifier_rules[bundle_type].get('required', set())
                missing = required - modifiers
                if missing:
                    missing_required.append({
                        "line_index": i,
                        "cpt": cpt,
                        "bundle_type": bundle_type,
                        "modifiers": list(missing)
                    })
        
        # Generate messages
        result["messages"] = self._generate_messages(
            invalid_modifiers,
            incompatible_sets,
            missing_required
        )
        
        # Update status if there are any issues
        if invalid_modifiers or incompatible_sets or missing_required:
            result["status"] = "FAIL"
        
        # Check for TC/26 component billing
        component_info = self.detect_component_modifiers(hcfa_data)
        if component_info["is_component_billing"]:
            # Add component billing information to result
            result["component_billing"] = component_info
            
            # Add component message to messages
            result["messages"].append(component_info["message"])
            
            # For reporting purposes, don't change the status (keep PASS/FAIL as determined)
            if result["status"] == "PASS":
                result["messages"].insert(0, "Non-global bill validation passed")
        
        return result
    
    def _parse_modifiers(self, modifier_value: Any) -> Set[str]:
        """
        Parse modifiers from various formats into a set of strings.
        
        Args:
            modifier_value: Modifier value (string, list, etc.)
            
        Returns:
            Set[str]: Set of modifier strings
        """
        if not modifier_value:
            return set()
            
        # If already a set, return as is
        if isinstance(modifier_value, set):
            return {str(m).strip().upper() for m in modifier_value if m}
            
        # If a list, convert to set
        if isinstance(modifier_value, list):
            return {str(m).strip().upper() for m in modifier_value if m}
            
        # If a string, split by common separators
        if isinstance(modifier_value, str):
            # Handle empty string
            if not modifier_value.strip():
                return set()
                
            # Split by comma or space
            if ',' in modifier_value:
                modifiers = modifier_value.split(',')
            else:
                modifiers = modifier_value.split()
                
            return {m.strip().upper() for m in modifiers if m.strip()}
            
        # For any other type, convert to string and return as single item
        return {str(modifier_value).strip().upper()} if str(modifier_value).strip() else set()
    
    def _get_valid_modifiers(self, cpt: str, bundle_type: Optional[str] = None) -> Set[str]:
        """
        Get valid modifiers for a CPT code.
        
        Args:
            cpt: CPT code
            bundle_type: Bundle type (optional)
            
        Returns:
            Set[str]: Set of valid modifiers
        """
        # For bundles, use bundle-specific rules
        if bundle_type and bundle_type in self.bundle_modifier_rules:
            return set(self.bundle_modifier_rules[bundle_type].get("allowed", []))
            
        # For special case CPT codes, use specific modifiers
        if cpt in self.special_case_modifiers:
            return set(self.special_case_modifiers[cpt])
            
        # For other codes, look up by prefix
        for prefix, modifiers in self.cpt_modifier_map.items():
            if cpt.startswith(prefix):
                return set(modifiers)
                
        # Default to empty set if no rules match
        return set()
    
    def _generate_messages(self, 
                          invalid_modifiers: List[Dict], 
                          incompatible_sets: List[Dict], 
                          missing_required: List[Dict]) -> List[str]:
        """
        Generate human-readable messages for validation results.
        
        Args:
            invalid_modifiers: List of invalid modifier details
            incompatible_sets: List of incompatible modifier sets
            missing_required: List of missing required modifiers
            
        Returns:
            List[str]: Human-readable messages
        """
        messages = []
        
        if not invalid_modifiers and not incompatible_sets and not missing_required:
            messages.append("All modifiers are valid")
            return messages
            
        if invalid_modifiers:
            messages.append(f"Found {len(invalid_modifiers)} invalid modifier(s)")
            for i, item in enumerate(invalid_modifiers[:3], 1):  # Show first 3 only
                messages.append(f"  {i}. {item['reason']} (CPT {item['cpt']}, Modifier {item['modifier']})")
                
            if len(invalid_modifiers) > 3:
                messages.append(f"  ... and {len(invalid_modifiers) - 3} more invalid modifiers")
                
        if incompatible_sets:
            messages.append(f"Found {len(incompatible_sets)} incompatible modifier combination(s)")
            for i, item in enumerate(incompatible_sets[:3], 1):  # Show first 3 only
                modifiers_str = ", ".join(item['modifiers'])
                messages.append(f"  {i}. Incompatible modifiers: {modifiers_str} (CPT {item['cpt']})")
                
            if len(incompatible_sets) > 3:
                messages.append(f"  ... and {len(incompatible_sets) - 3} more incompatible combinations")
                
        if missing_required:
            messages.append(f"Found {len(missing_required)} missing required modifier(s)")
            for i, item in enumerate(missing_required[:3], 1):  # Show first 3 only
                messages.append(f"  {i}. {item['reason']} (CPT {item['cpt']})")
                
            if len(missing_required) > 3:
                messages.append(f"  ... and {len(missing_required) - 3} more missing required modifiers")
                
        return messages