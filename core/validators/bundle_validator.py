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
        Compare bundles between order and HCFA CPT codes.
        
        Args:
            order_cpt_codes: CPT codes from order
            hcfa_cpt_codes: CPT codes from HCFA
            
        Returns:
            Dict: Comparison results
        """
        order_bundle = self.detect_bundle(order_cpt_codes)
        hcfa_bundle = self.detect_bundle(hcfa_cpt_codes)
        
        result = {
            'status': 'NO_BUNDLE',
            'message': 'No matching bundles found',
            'order_bundle': order_bundle,
            'hcfa_bundle': hcfa_bundle,
            'details': {}
        }
        
        # If either bundle is not found, return early
        if not order_bundle or not hcfa_bundle:
            return result
            
        # For imaging bundles, check contrast status
        if (order_bundle.get('modality') in ['MR', 'CT'] and 
            hcfa_bundle.get('modality') in ['MR', 'CT']):
            
            # Extract contrast status from bundle codes
            order_codes = set(order_cpt_codes)
            hcfa_codes = set(hcfa_cpt_codes)
            
            # Look at the first code to determine contrast
            order_contrast = None
            hcfa_contrast = None
            
            if order_codes and hcfa_codes:
                order_contrast = ClinicalIntent.detect_contrast_from_cpt(next(iter(order_codes)))
                hcfa_contrast = ClinicalIntent.detect_contrast_from_cpt(next(iter(hcfa_codes)))
                
                if order_contrast is not None and hcfa_contrast is not None:
                    if order_contrast is False and hcfa_contrast is True:
                        result['status'] = 'CONTRAST_MISMATCH'
                        result['message'] = "Contrast mismatch: without contrast ordered but with contrast billed"
                        return result
                    elif order_contrast is True and hcfa_contrast is False:
                        result['status'] = 'CONTRAST_MISMATCH'
                        result['message'] = "Contrast mismatch: with contrast ordered but without contrast billed"
                        return result
        
        # Rest of the existing bundle comparison logic
        if order_bundle['bundle_name'] == hcfa_bundle['bundle_name']:
            result['status'] = 'EXACT_MATCH'
            result['message'] = f"Exact bundle match: {order_bundle['bundle_name']}"
        else:
            result['status'] = 'VARIANT_MATCH'
            result['message'] = f"Variant bundle match: {order_bundle['bundle_name']} vs {hcfa_bundle['bundle_name']}"
            
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
        
        # Check for contrast mismatch separately, as it's a critical clinical issue
        if validation_result['status'] == 'PASS' and comparison['status'] != 'NO_BUNDLE':
            # Check contrast for imaging procedures
            order_bundle = comparison.get('order_bundle', {})
            hcfa_bundle = comparison.get('hcfa_bundle', {})
            
            if order_bundle.get('modality') in ['MR', 'CT'] and hcfa_bundle.get('modality') in ['MR', 'CT']:
                # Extra validation for contrast status
                order_codes = set(order_cpt_codes)
                hcfa_codes = set(hcfa_cpt_codes)
                
                order_contrast = None
                hcfa_contrast = None
                
                for code in order_codes:
                    contrast = ClinicalIntent.detect_contrast_from_cpt(code)
                    if contrast is not None:
                        order_contrast = contrast
                        break
                        
                for code in hcfa_codes:
                    contrast = ClinicalIntent.detect_contrast_from_cpt(code)
                    if contrast is not None:
                        hcfa_contrast = contrast
                        break
                
                if order_contrast is not None and hcfa_contrast is not None:
                    if order_contrast != hcfa_contrast:
                        validation_result['status'] = 'FAIL'
                        validation_result['message'] = "Contrast mismatch between order and billed codes"
                        validation_result['bundle_comparison']['contrast_mismatch'] = {
                            'order_contrast': "with" if order_contrast else "without",
                            'hcfa_contrast': "with" if hcfa_contrast else "without"
                        }
        
        return validation_result