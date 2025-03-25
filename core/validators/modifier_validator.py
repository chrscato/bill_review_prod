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
    
    def validate(self, hcfa_data: Dict) -> Dict:
        """
        Validate modifiers in line items.
        
        Args:
            hcfa_data: HCFA data with line_items
            
        Returns:
            Dict: Validation results
        """
        if not hcfa_data or "line_items" not in hcfa_data:
            return {
                "status": "FAIL",
                "reason": "No line items to validate",
                "invalid_modifiers": [],
                "details": {
                    "total_checked": 0,
                    "total_invalid": 0
                }
            }
        
        invalid_modifiers = []
        incompatible_sets = []
        missing_required = []
        
        # Check for bundle information
        bundle_type = None
        bundle_name = None
        
        # If any line has bundle information, use it for all lines
        for line in hcfa_data.get('line_items', []):
            if line.get("bundle_type") and line.get("bundle_name"):
                bundle_type = line.get("bundle_type")
                bundle_name = line.get("bundle_name")
                break
        
        bundle_rules = self.bundle_modifier_rules.get(bundle_type, {}) if bundle_type else {}
        
        # Check each line item
        for line in hcfa_data.get('line_items', []):
            # Skip lines without CPT code
            if "cpt" not in line:
                continue
                
            cpt = clean_cpt_code(line.get('cpt', ''))
            
            # Parse modifiers from string or list
            modifiers = self._parse_modifiers(line.get('modifier'))
            
            # Get valid modifiers for this CPT code
            valid_modifiers = self._get_valid_modifiers(cpt, bundle_type)
            
            # Check for invalid modifiers
            for mod in modifiers:
                # Skip empty modifiers
                if not mod:
                    continue
                    
                # If this is a bundle with specific rules, use those
                if bundle_type and mod not in bundle_rules.get("allowed", []):
                    invalid_modifiers.append({
                        'cpt': cpt,
                        'modifier': mod,
                        'reason': f"Modifier {mod} not allowed for {bundle_type} bundle"
                    })
                # Otherwise check against general rules
                elif not bundle_type and self.invalid_modifiers and mod in self.invalid_modifiers:
                    invalid_modifiers.append({
                        'cpt': cpt,
                        'modifier': mod,
                        'reason': f"Modifier {mod} is globally invalid"
                    })
                elif not bundle_type and valid_modifiers and mod not in valid_modifiers:
                    invalid_modifiers.append({
                        'cpt': cpt,
                        'modifier': mod,
                        'reason': f"Modifier {mod} is not valid for CPT {cpt}"
                    })
            
            # Check for incompatible modifiers
            for incompatible_set in self.incompatible_modifiers:
                if len(incompatible_set.intersection(modifiers)) > 1:
                    incompatible_sets.append({
                        'cpt': cpt,
                        'modifiers': list(incompatible_set.intersection(modifiers)),
                        'reason': "These modifiers should not be used together"
                    })
            
            # Check for required modifiers in bundles
            if bundle_type and "required" in bundle_rules and bundle_rules["required"]:
                for required_mod in bundle_rules["required"]:
                    if required_mod not in modifiers:
                        missing_required.append({
                            'cpt': cpt,
                            'missing_modifier': required_mod,
                            'reason': f"Modifier {required_mod} is required for {bundle_type} bundle"
                        })
        
        # Combine all issues
        all_issues = invalid_modifiers + incompatible_sets + missing_required
        
        # Generate a detailed result
        result = {
            "status": "FAIL" if all_issues else "PASS",
            "invalid_modifiers": invalid_modifiers,
            "incompatible_modifiers": incompatible_sets,
            "missing_required": missing_required,
            "details": {
                "total_checked": len(hcfa_data.get('line_items', [])),
                "total_invalid": len(all_issues),
                "bundle_type": bundle_type,
                "bundle_name": bundle_name
            },
            "messages": self._generate_messages(invalid_modifiers, incompatible_sets, missing_required)
        }
        
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