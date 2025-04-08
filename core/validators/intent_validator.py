# core/validators/intent_validator.py
from typing import Dict, List, Set, Optional
import json
from pathlib import Path
import pandas as pd

class ClinicalIntentValidator:
    """
    Validator for clinical intent matching between order and HCFA data.
    Focuses on the clinical purpose rather than exact CPT code matching.
    """
    
    def __init__(self, clinical_equiv_path: Path = None, dim_proc_df: Optional[pd.DataFrame] = None):
        """
        Initialize the clinical intent validator.
        
        Args:
            clinical_equiv_path: Path to clinical equivalence mapping file
            dim_proc_df: DataFrame with procedure codes and categories (optional)
        """
        # Default path if none provided
        if clinical_equiv_path is None:
            clinical_equiv_path = Path(__file__).parent.parent.parent / "config" / "clinical_equivalents.json"
        
        self.equivalence_map = self._load_equivalence_map(clinical_equiv_path)
        self.dim_proc_df = dim_proc_df
        
        # Define common procedure categories and body part mappings
        self.procedure_categories = {
            "MRI": ["70540", "70543", "70551", "70553", "71550", "71552", "72141", "72156", 
                   "72146", "72157", "72148", "72158", "72195", "72197", "73218", "73220", 
                   "73221", "73223", "73718", "73720", "73721", "73723", "74181", "74183"],
            "CT": ["70450", "70460", "70470", "70480", "70481", "70482", "70486", "70487", 
                  "70488", "70490", "70491", "70492", "71250", "71260", "71270", "72125", 
                  "72126", "72127", "72128", "72129", "72130", "72131", "72132", "72133", 
                  "72192", "72193", "72194", "73200", "73201", "73202", "73700", "73701", 
                  "73702", "74150", "74160", "74170", "74176", "74177", "74178"],
            "X-ray": ["70100", "70110", "70140", "70150", "70160", "70200", "70210", 
                     "70220", "70250", "70260", "71045", "71046", "71047", "71048", 
                     "72020", "72040", "72050", "72052", "72070", "72072", "72080", 
                     "72100", "72110", "73000", "73010", "73020", "73030", "73060", 
                     "73070", "73090", "73100", "73110", "73120", "73130", "73140", 
                     "73560", "73562", "73564", "73565", "73590", "73600", "73610", 
                     "73620", "73630", "74018", "74019", "74021", "74022"],
            "Arthrogram": ["73040", "73201", "73222", "73525", "73580", "73701", "73722", 
                          "23350", "24220", "25246", "27093", "27370", "27648", "77002"],
            "Therapeutic Injection": ["20605", "20610", "77002"],
            "EMG": ["95907", "95908", "95909", "95910", "95911", "95912", "95913", 
                   "95885", "95886", "95887", "99203", "99204", "99205"],
            "Ultrasound": ["76536", "76604", "76641", "76642", "76700", "76705", "76770", 
                          "76775", "76830", "76856", "76857", "76870", "76872"]
        }
        
        # Body part mapping based on CPT code patterns
        self.body_part_mapping = {
            # Head and neck
            "70": "head_neck",
            # Chest
            "71": "chest",
            # Spine
            "72": "spine",
            # Upper extremity
            "73000": "shoulder", "73010": "shoulder", "73020": "shoulder", "73030": "shoulder", 
            "73050": "shoulder", "73221": "upper_extremity", "73222": "upper_extremity",
            # Lower extremity
            "73560": "knee", "73562": "knee", "73564": "knee", "73565": "knee",
            "73580": "knee", "73700": "lower_extremity", "73701": "lower_extremity", 
            "73721": "lower_extremity", "73722": "lower_extremity",
            # Abdomen
            "74": "abdomen",
            # Vascular
            "75": "vascular",
            # Ultrasound
            "76": "ultrasound"
        }
    
    def _load_equivalence_map(self, config_path: Path) -> Dict:
        """
        Load clinical equivalence mapping from JSON file.
        
        Args:
            config_path: Path to the configuration file
            
        Returns:
            Dict: Clinical equivalence mapping
        """
        if not config_path.exists():
            # Return empty dict if file doesn't exist yet
            return {}
            
        with open(config_path, 'r') as f:
            return json.load(f)
    
    def get_procedure_categories(self, cpt_code: str) -> List[str]:
        """
        Get categories for a CPT code.
        
        Args:
            cpt_code: CPT code to categorize
            
        Returns:
            List[str]: Categories for the CPT code
        """
        categories = []
        
        # Check from dim_proc if available
        if self.dim_proc_df is not None:
            try:
                # First try with proc_cd column
                if 'proc_cd' in self.dim_proc_df.columns:
                    match = self.dim_proc_df[self.dim_proc_df['proc_cd'] == str(cpt_code)]
                    if not match.empty and 'proc_category' in self.dim_proc_df.columns:
                        proc_category = match['proc_category'].iloc[0]
                        if proc_category:
                            categories.append(proc_category.lower())
                # Also try with CPT column (might be capitalized differently)
                elif 'CPT' in self.dim_proc_df.columns:
                    match = self.dim_proc_df[self.dim_proc_df['CPT'] == str(cpt_code)]
                    if not match.empty and 'proc_category' in self.dim_proc_df.columns:
                        proc_category = match['proc_category'].iloc[0]
                        if proc_category:
                            categories.append(proc_category.lower())
                # Try other common column names
                elif 'cpt' in self.dim_proc_df.columns:
                    match = self.dim_proc_df[self.dim_proc_df['cpt'] == str(cpt_code)]
                    if not match.empty and 'proc_category' in self.dim_proc_df.columns:
                        proc_category = match['proc_category'].iloc[0]
                        if proc_category:
                            categories.append(proc_category.lower())
            except Exception as e:
                # Log the error but continue with other categorization methods
                print(f"Warning: Error looking up procedure category for CPT {cpt_code}: {str(e)}")
        
        # Check from predefined categories
        for category, codes in self.procedure_categories.items():
            if cpt_code in codes:
                categories.append(category.lower())
                
        # Check code pattern if no specific category found
        if not categories:
            # First 3 digits often indicate the body system
            prefix = cpt_code[:3]
            if prefix in ["721", "722", "723"]:
                categories.append("spine_procedure")
            elif prefix in ["732", "733"]:
                categories.append("upper_extremity_procedure")
            elif prefix in ["737", "738"]:
                categories.append("lower_extremity_procedure")
            elif prefix in ["707", "708"]:
                categories.append("head_procedure")
            elif prefix in ["712", "713"]:
                categories.append("chest_procedure")
            elif prefix in ["741", "742"]:
                categories.append("abdomen_procedure")
        
        return categories
    
    def get_body_part(self, cpt_code: str) -> Optional[str]:
        """
        Determine the body part from a CPT code.
        
        Args:
            cpt_code: CPT code to analyze
            
        Returns:
            Optional[str]: Body part or None if undetermined
        """
        # Exact match
        if cpt_code in self.body_part_mapping:
            return self.body_part_mapping[cpt_code]
        
        # Match by prefix
        prefix_matches = []
        for prefix, body_part in self.body_part_mapping.items():
            if isinstance(prefix, str) and len(prefix) < 5 and cpt_code.startswith(prefix):
                prefix_matches.append((len(prefix), body_part))
        
        # Return the longest prefix match if any
        if prefix_matches:
            prefix_matches.sort(reverse=True)  # Sort by prefix length (longest first)
            return prefix_matches[0][1]
        
        return None
    
    def classify_intent(self, cpt_codes: Set[str]) -> Dict:
        """
        Classify the clinical intent of a set of CPT codes.
        
        Args:
            cpt_codes: Set of CPT codes to classify
            
        Returns:
            Dict: Clinical intent classification
        """
        if not cpt_codes:
            return {"intent": "unknown", "confidence": 0}
        
        # Count categories across all CPT codes
        category_counts = {}
        body_parts = set()
        modalities = set()
        
        for code in cpt_codes:
            # Get categories
            categories = self.get_procedure_categories(code)
            for category in categories:
                if category:
                    category_counts[category] = category_counts.get(category, 0) + 1
            
            # Get body part
            body_part = self.get_body_part(code)
            if body_part:
                body_parts.add(body_part)
            
            # Modality detection
            if code.startswith('7'):
                # Imaging codes
                if any(code in self.procedure_categories[cat] for cat in ["MRI", "CT", "X-ray", "Ultrasound"]):
                    for modality in ["MRI", "CT", "X-ray", "Ultrasound"]:
                        if code in self.procedure_categories[modality]:
                            modalities.add(modality.lower())
            
            # Therapeutic procedures
            if code.startswith('2'):
                modalities.add("therapeutic")
        
        # Determine dominant category
        dominant_category = None
        max_count = 0
        for category, count in category_counts.items():
            if count > max_count:
                dominant_category = category
                max_count = count
        
        # Calculate confidence based on category dominance
        total_codes = len(cpt_codes)
        confidence = (max_count / total_codes) * 100 if total_codes > 0 else 0
        
        return {
            "intent": dominant_category or "unknown",
            "body_parts": list(body_parts) if body_parts else ["unknown"],
            "modalities": list(modalities) if modalities else ["unknown"],
            "categories": category_counts,
            "confidence": confidence
        }
    
    def compare_intents(self, order_cpt_codes: Set[str], hcfa_cpt_codes: Set[str]) -> Dict:
        """
        Compare clinical intents between order and HCFA CPT codes.
        
        Args:
            order_cpt_codes: CPT codes from order
            hcfa_cpt_codes: CPT codes from HCFA
            
        Returns:
            Dict: Comparison results
        """
        order_intent = self.classify_intent(order_cpt_codes)
        hcfa_intent = self.classify_intent(hcfa_cpt_codes)
        
        result = {
            'status': 'PASS',
            'message': 'Clinical intents match',
            'details': {
                'order_intent': order_intent,
                'hcfa_intent': hcfa_intent
            }
        }
        
        # Check for contrast mismatch
        if (order_intent['intent'] == 'unknown' or hcfa_intent['intent'] == 'unknown'):
            result['status'] = 'INCOMPLETE_DATA'
            result['message'] = 'Unable to determine clinical intent from codes'
            return result
        
        # Check for contrast mismatch
        if (order_intent['intent'] == hcfa_intent['intent'] and
            order_intent['body_parts'] == hcfa_intent['body_parts'] and
            order_intent['modalities'] == hcfa_intent['modalities']):
            
            result['status'] = 'FULL_MATCH'
            result['message'] = f"Clinical intent matches: {order_intent['intent']}"
            
            # Check body parts
            order_body_parts = set(order_intent['body_parts'])
            hcfa_body_parts = set(hcfa_intent['body_parts'])
            
            if order_body_parts.intersection(hcfa_body_parts) or 'unknown' in order_body_parts or 'unknown' in hcfa_body_parts:
                # At least one body part matches or unknown
                result['status'] = 'FULL_MATCH'
                result['message'] += f" for body part(s): {', '.join(order_body_parts.intersection(hcfa_body_parts))}"
            else:
                # No matching body parts
                result['status'] = 'BODY_PART_MISMATCH'
                result['message'] = f"Intent matches but body parts differ: {', '.join(order_body_parts)} vs {', '.join(hcfa_body_parts)}"
        else:
            # Intent mismatch
            result['status'] = 'INTENT_MISMATCH'
            result['message'] = f"Clinical intent mismatch: {order_intent['intent']} in order vs {hcfa_intent['intent']} in HCFA"
        
        # Add detailed comparison
        result['details'] = {
            'category_overlap': {
                cat: min(order_intent['categories'].get(cat, 0), hcfa_intent['categories'].get(cat, 0))
                for cat in set(order_intent['categories'].keys()).union(set(hcfa_intent['categories'].keys()))
            },
            'modality_overlap': set(order_intent['modalities']).intersection(set(hcfa_intent['modalities'])),
            'body_part_overlap': set(order_intent['body_parts']).intersection(set(hcfa_intent['body_parts'])),
            'confidence': min(order_intent['confidence'], hcfa_intent['confidence'])
        }
        
        return result
    
    def validate(self, order_data: Dict, hcfa_data: Dict) -> Dict:
        """
        Validate clinical intent matching between order and HCFA data.
        
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
                    cpt = str(line['cpt'])
                    # Skip ancillary codes
                    if cpt in self.procedure_categories and self.procedure_categories[cpt][0].lower() == 'ancillary':
                        continue
                    hcfa_cpt_codes.add(cpt)
        
        # If no non-ancillary codes to validate, return PASS
        if not hcfa_cpt_codes:
            return {
                'status': 'PASS',
                'message': 'No non-ancillary codes to validate',
                'validation_type': 'clinical_intent',
                'intent_comparison': None,
                'order_cpt_codes': list(order_cpt_codes),
                'hcfa_cpt_codes': []
            }
        
        # Compare clinical intents
        comparison = self.compare_intents(order_cpt_codes, hcfa_cpt_codes)
        
        # Determine if validation passes or fails
        # These statuses are considered passes for intent validation
        pass_statuses = {'FULL_MATCH', 'INTENT_MATCH', 'INCOMPLETE_DATA'}
        
        validation_result = {
            'status': 'PASS' if comparison['status'] in pass_statuses else 'FAIL',
            'validation_type': 'clinical_intent',
            'intent_comparison': comparison,
            'order_cpt_codes': list(order_cpt_codes),
            'hcfa_cpt_codes': list(hcfa_cpt_codes),
            'message': comparison['message']
        }
        
        return validation_result

    def from_cpt_codes(self, cpt_codes: Set[str]) -> Dict:
        """
        Create a ClinicalIntent from a set of CPT codes.
        
        Args:
            cpt_codes: Set of CPT codes to analyze
            
        Returns:
            Dict: Classified clinical intent
        """
        intent = self.classify_intent(cpt_codes)
        
        # Determine contrast status from CPT codes
        for cpt_code in cpt_codes:
            contrast_status = ClinicalIntent.detect_contrast_from_cpt(cpt_code)
            if contrast_status is not None:
                intent['contrast'] = contrast_status
                break
        
        # Calculate confidence based on number of codes
        intent['confidence'] = 100 if len(cpt_codes) == 1 else max(30, 100 - (len(cpt_codes) - 1) * 10)
        
        return intent