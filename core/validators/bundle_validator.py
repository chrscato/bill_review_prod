# core/validators/bundle_validator.py
from typing import Dict, List, Set, Tuple, Optional
import json
from pathlib import Path

class BundleValidator:
    """
    A flexible validator for detecting and comparing procedure bundles
    between order data and HCFA data.
    """
    
    def __init__(self, bundle_config_path: Path = None):
        """
        Initialize the bundle validator with a configuration file.
        
        Args:
            bundle_config_path: Path to the bundle configuration JSON file
        """
        # Default path if none provided
        if bundle_config_path is None:
            bundle_config_path = Path(__file__).parent.parent.parent / "config" / "procedure_bundles.json"
            
        self.bundle_config = self._load_bundle_config(bundle_config_path)
        self.bundle_types = self._categorize_bundles()
        
    def _load_bundle_config(self, config_path: Path) -> Dict:
        """
        Load bundle configuration from JSON file.
        
        Args:
            config_path: Path to the configuration file
            
        Returns:
            Dict: Bundle configuration
        """
        if not config_path.exists():
            raise FileNotFoundError(f"Bundle configuration not found: {config_path}")
            
        with open(config_path, 'r') as f:
            return json.load(f)
        
    def _categorize_bundles(self) -> Dict:
        """
        Categorize bundles by type for easier lookup.
        
        Returns:
            Dict: Bundles organized by type
        """
        categories = {}
        
        for bundle_name, bundle_info in self.bundle_config.items():
            bundle_type = bundle_info.get('bundle_type', 'unknown')
            
            if bundle_type not in categories:
                categories[bundle_type] = {}
                
            body_part = bundle_info.get('body_part')
            if body_part:
                if body_part not in categories[bundle_type]:
                    categories[bundle_type][body_part] = []
                categories[bundle_type][body_part].append(bundle_name)
            else:
                if 'general' not in categories[bundle_type]:
                    categories[bundle_type]['general'] = []
                categories[bundle_type]['general'].append(bundle_name)
                
        return categories
    
    def detect_bundle(self, cpt_codes: Set[str]) -> Dict:
        """
        Detect if a set of CPT codes matches any known bundle pattern.
        
        Args:
            cpt_codes: Set of CPT codes to check
            
        Returns:
            Dict: Bundle information or empty dict if no bundle detected
        """
        best_match = {
            'bundle_name': None,
            'bundle_type': None,
            'body_part': None,
            'match_quality': 0,  # 0 = no match, 1 = partial match, 2 = full match
            'core_match_pct': 0,
            'missing_core': [],
            'missing_optional': [],
            'extra_codes': []
        }
        
        # Convert to a set for easier operations
        cpt_codes_set = set(cpt_codes)
        
        for bundle_name, bundle_info in self.bundle_config.items():
            core_codes = set(bundle_info.get('core_codes', []))
            optional_codes = set(bundle_info.get('optional_codes', []))
            all_codes = core_codes.union(optional_codes)
            
            # Skip if no core codes defined
            if not core_codes:
                continue
                
            # Calculate match quality
            core_matches = core_codes.intersection(cpt_codes_set)
            core_match_pct = len(core_matches) / len(core_codes) if core_codes else 0
            
            optional_matches = optional_codes.intersection(cpt_codes_set)
            optional_match_pct = len(optional_matches) / len(optional_codes) if optional_codes else 1
            
            # Extra codes not in the bundle
            extra_codes = cpt_codes_set - all_codes
            
            # Missing codes
            missing_core = core_codes - cpt_codes_set
            missing_optional = optional_codes - cpt_codes_set
            
            # Determine match quality
            match_quality = 0
            
            if core_match_pct == 1:
                # All core codes match - full match
                match_quality = 2
            elif core_match_pct >= 0.5:
                # At least half of core codes match - partial match
                match_quality = 1
            
            # Update best match if this is better
            if match_quality > best_match['match_quality'] or (
                match_quality == best_match['match_quality'] and 
                core_match_pct > best_match['core_match_pct']):
                
                best_match = {
                    'bundle_name': bundle_name,
                    'bundle_type': bundle_info.get('bundle_type'),
                    'body_part': bundle_info.get('body_part'),
                    'modality': bundle_info.get('modality'),
                    'match_quality': match_quality,
                    'core_match_pct': core_match_pct,
                    'optional_match_pct': optional_match_pct,
                    'missing_core': list(missing_core),
                    'missing_optional': list(missing_optional),
                    'extra_codes': list(extra_codes),
                    'all_bundle_codes': list(all_codes)
                }
        
        return best_match if best_match['match_quality'] > 0 else {}
    
    def compare_bundles(self, order_cpt_codes: Set[str], hcfa_cpt_codes: Set[str]) -> Dict:
        """
        Compare bundle detection between order and HCFA data.
        
        Args:
            order_cpt_codes: Set of CPT codes from order data
            hcfa_cpt_codes: Set of CPT codes from HCFA data
            
        Returns:
            Dict: Comparison results
        """
        # Detect bundles in order and HCFA data
        order_bundle = self.detect_bundle(order_cpt_codes)
        hcfa_bundle = self.detect_bundle(hcfa_cpt_codes)
        
        # Initialize result
        result = {
            'order_bundle': order_bundle,
            'hcfa_bundle': hcfa_bundle,
            'status': 'UNKNOWN',
            'message': '',
            'details': {}
        }
        
        # Handle case where no bundles were detected
        if not order_bundle and not hcfa_bundle:
            result['status'] = 'NO_BUNDLE'
            result['message'] = 'No bundles detected in order or HCFA data'
            return result
            
        # Handle case where only one side has a bundle
        if order_bundle and not hcfa_bundle:
            result['status'] = 'MISSING_BUNDLE'
            result['message'] = f"Bundle {order_bundle['bundle_name']} detected in order but not in HCFA"
            return result
            
        if not order_bundle and hcfa_bundle:
            result['status'] = 'UNEXPECTED_BUNDLE'
            result['message'] = f"Bundle {hcfa_bundle['bundle_name']} detected in HCFA but not in order"
            return result
        
        # Both sides have bundles - compare them
        order_type = order_bundle.get('bundle_type')
        hcfa_type = hcfa_bundle.get('bundle_type')
        order_body_part = order_bundle.get('body_part')
        hcfa_body_part = hcfa_bundle.get('body_part')
        order_modality = order_bundle.get('modality')
        hcfa_modality = hcfa_bundle.get('modality')
        
        # Check if bundle types match
        if order_type != hcfa_type:
            result['status'] = 'TYPE_MISMATCH'
            result['message'] = f"Bundle type mismatch: {order_type} in order, {hcfa_type} in HCFA"
            return result
        
        # Check if body parts match (if applicable)
        if order_body_part and hcfa_body_part and order_body_part != hcfa_body_part:
            result['status'] = 'BODY_PART_MISMATCH'
            result['message'] = f"Body part mismatch: {order_body_part} in order, {hcfa_body_part} in HCFA"
            return result
            
        # Check if modalities match (if applicable and not emg)
        if order_modality and hcfa_modality and order_modality != hcfa_modality and order_type != 'emg':
            result['status'] = 'MODALITY_MISMATCH'
            result['message'] = f"Modality mismatch: {order_modality} in order, {hcfa_modality} in HCFA"
            # For modality mismatch, we usually continue as this is often acceptable
            # But we mark it for reporting purposes
        
        # Determine overall match quality
        if order_bundle['match_quality'] == 2 and hcfa_bundle['match_quality'] == 2:
            # Both are full matches
            if order_bundle['bundle_name'] == hcfa_bundle['bundle_name']:
                result['status'] = 'EXACT_MATCH'
                result['message'] = f"Exact bundle match: {order_bundle['bundle_name']}"
            else:
                result['status'] = 'VARIANT_MATCH'
                result['message'] = f"Variant bundle match: {order_bundle['bundle_name']} vs {hcfa_bundle['bundle_name']}"
        else:
            # At least one is a partial match
            result['status'] = 'PARTIAL_MATCH'
            result['message'] = f"Partial bundle match of type {order_type}"
            
            # Add details about the partial match
            result['details'] = {
                'order_quality': order_bundle['match_quality'],
                'hcfa_quality': hcfa_bundle['match_quality'],
                'order_missing_core': order_bundle['missing_core'],
                'hcfa_missing_core': hcfa_bundle['missing_core'],
                'shared_codes': list(set(order_cpt_codes).intersection(set(hcfa_cpt_codes))),
                'order_only_codes': list(set(order_cpt_codes) - set(hcfa_cpt_codes)),
                'hcfa_only_codes': list(set(hcfa_cpt_codes) - set(order_cpt_codes))
            }
        
        return result
    
    def validate(self, order_data: Dict, hcfa_data: Dict) -> Dict:
        """
        Validate bundle matching between order and HCFA data.
        
        Args:
            order_data: Order data with CPT codes
            hcfa_data: HCFA data with CPT codes
            
        Returns:
            Dict: Validation results
        """
        # Extract CPT codes from order data
        order_cpt_codes = set()
        if 'line_items' in order_data and isinstance(order_data['line_items'], list):
            for line in order_data['line_items']:
                if 'CPT' in line:
                    order_cpt_codes.add(str(line['CPT']))
                elif 'cpt' in line:
                    order_cpt_codes.add(str(line['cpt']))
        
        # Extract CPT codes from HCFA data
        hcfa_cpt_codes = set()
        if 'line_items' in hcfa_data and isinstance(hcfa_data['line_items'], list):
            for line in hcfa_data['line_items']:
                if 'cpt' in line:
                    hcfa_cpt_codes.add(str(line['cpt']))
        
        # Compare bundles
        comparison = self.compare_bundles(order_cpt_codes, hcfa_cpt_codes)
        
        # Determine if validation passes or fails
        # These statuses are considered passes for bundle validation
        pass_statuses = {'EXACT_MATCH', 'VARIANT_MATCH', 'PARTIAL_MATCH', 'NO_BUNDLE', 'MODALITY_MISMATCH'}
        
        validation_result = {
            'status': 'PASS' if comparison['status'] in pass_statuses else 'FAIL',
            'validation_type': 'bundle',
            'bundle_comparison': comparison,
            'order_cpt_codes': list(order_cpt_codes),
            'hcfa_cpt_codes': list(hcfa_cpt_codes),
            'message': comparison['message']
        }
        
        return validation_result