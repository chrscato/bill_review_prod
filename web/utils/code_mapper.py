# CPT code mapping utilities 
# utils/code_mapper.py
from typing import Dict, List, Set, Optional, Tuple, Any
import json
from pathlib import Path

class CodeMapper:
    """
    Utility for mapping between CPT codes, finding equivalents, and categorizing procedures.
    """
    
    def __init__(self, clinical_equiv_path: Optional[Path] = None):
        """
        Initialize the code mapper.
        
        Args:
            clinical_equiv_path: Path to clinical equivalence JSON file
        """
        # Default path if none provided
        if clinical_equiv_path is None:
            clinical_equiv_path = Path(__file__).parent.parent / "config" / "clinical_equivalents.json"
        
        self.equivalence_map = self._load_equivalence_map(clinical_equiv_path)
        
        # Define common procedure categories
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
            "Therapeutic Injection": ["20600", "20604", "20605", "20606", "20610", "20611", "77002"],
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
            print(f"Warning: Clinical equivalence map not found at {config_path}")
            return {
                "equivalent_groups": [],
                "clinical_substitutes": [],
                "provider_specific_equivalents": {}
            }
            
        try:
            with open(config_path, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            print(f"Error loading clinical equivalence map: {e}")
            return {
                "equivalent_groups": [],
                "clinical_substitutes": [],
                "provider_specific_equivalents": {}
            }
    
    def get_procedure_category(self, cpt_code: str) -> List[str]:
        """
        Get categories for a CPT code.
        
        Args:
            cpt_code: CPT code to categorize
            
        Returns:
            List[str]: Categories for the CPT code
        """
        categories = []
        
        # Check from predefined categories
        for category, codes in self.procedure_categories.items():
            if cpt_code in codes:
                categories.append(category.lower())
                
        # If no specific category found, infer from code pattern
        if not categories:
            # First 3 digits often indicate the body system
            prefix = cpt_code[:3]
            if prefix in ["721", "722", "723"]:
                categories.append("spine_imaging")
            elif prefix in ["732", "733"]:
                categories.append("extremity_imaging")
            elif prefix in ["707", "708"]:
                categories.append("head_imaging")
            elif prefix in ["712", "713"]:
                categories.append("chest_imaging")
            elif prefix in ["741", "742"]:
                categories.append("abdomen_imaging")
            elif prefix.startswith("20"):
                categories.append("injection")
                
            # Very generic categories based on CPT code ranges
            if prefix.startswith("7"):
                categories.append("imaging")
            elif prefix.startswith("9"):
                categories.append("evaluation")
        
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
            if isinstance(prefix, str) and len(prefix) <= 5 and cpt_code.startswith(prefix):
                prefix_matches.append((len(prefix), body_part))
        
        # Return the longest prefix match if any
        if prefix_matches:
            prefix_matches.sort(reverse=True)  # Sort by prefix length (longest first)
            return prefix_matches[0][1]
        
        return None
    
    def find_equivalent_codes(self, cpt_code: str, provider_tin: str = None) -> List[str]:
        """
        Find clinically equivalent CPT codes.
        
        Args:
            cpt_code: CPT code to find equivalents for
            provider_tin: Optional provider TIN for provider-specific mappings
            
        Returns:
            List[str]: Equivalent CPT codes
        """
        equivalents = []
        
        # Check provider-specific mappings first
        if provider_tin and provider_tin in self.equivalence_map.get('provider_specific_equivalents', {}):
            provider_mappings = self.equivalence_map['provider_specific_equivalents'][provider_tin]
            for mapping in provider_mappings:
                if cpt_code in mapping.get('primary_codes', []):
                    equivalents.extend(mapping.get('substitute_codes', []))
                elif cpt_code in mapping.get('substitute_codes', []):
                    equivalents.extend(mapping.get('primary_codes', []))
        
        # Check equivalent groups
        for group in self.equivalence_map.get('equivalent_groups', []):
            if cpt_code in group.get('codes', []):
                # Add all codes in the group except the original one
                equivalents.extend([code for code in group.get('codes', []) if code != cpt_code])
        
        # Check clinical substitutes
        for substitute in self.equivalence_map.get('clinical_substitutes', []):
            if cpt_code in substitute.get('primary_codes', []):
                equivalents.extend(substitute.get('substitute_codes', []))
            elif cpt_code in substitute.get('substitute_codes', []):
                equivalents.extend(substitute.get('primary_codes', []))
        
        return list(set(equivalents))  # Remove duplicates
    
    def is_similar_procedure(self, cpt_code1: str, cpt_code2: str) -> Tuple[bool, float]:
        """
        Determine if two CPT codes represent similar procedures.
        
        Args:
            cpt_code1: First CPT code
            cpt_code2: Second CPT code
            
        Returns:
            Tuple[bool, float]: (is_similar, similarity_score)
        """
        # Direct equivalence check
        if cpt_code1 == cpt_code2:
            return True, 1.0
            
        # Check if they are in known equivalent groups
        for group in self.equivalence_map.get('equivalent_groups', []):
            if cpt_code1 in group.get('codes', []) and cpt_code2 in group.get('codes', []):
                return True, 0.9
        
        # Check categories and body parts
        categories1 = set(self.get_procedure_category(cpt_code1))
        categories2 = set(self.get_procedure_category(cpt_code2))
        
        body_part1 = self.get_body_part(cpt_code1)
        body_part2 = self.get_body_part(cpt_code2)
        
        # Calculate similarity score
        score = 0.0
        
        # Category match provides high similarity
        common_categories = categories1.intersection(categories2)
        if common_categories:
            score += 0.6
            
        # Body part match is important for similarity
        if body_part1 and body_part2 and body_part1 == body_part2:
            score += 0.3
            
        # Code pattern similarity
        prefix_length = self._get_common_prefix_length(cpt_code1, cpt_code2)
        if prefix_length >= 3:
            score += 0.1
            
        is_similar = score >= 0.6  # Threshold for similarity
        
        return is_similar, score
    
    def _get_common_prefix_length(self, code1: str, code2: str) -> int:
        """Get length of common prefix between two codes."""
        for i in range(min(len(code1), len(code2))):
            if code1[i] != code2[i]:
                return i
        return min(len(code1), len(code2))
    
    def categorize_cpt_codes(self, cpt_codes: Set[str]) -> Dict[str, List[str]]:
        """
        Categorize a set of CPT codes by procedure type and body part.
        
        Args:
            cpt_codes: Set of CPT codes to categorize
            
        Returns:
            Dict: Categorization by procedure type and body part
        """
        result = {
            "by_category": {},
            "by_body_part": {},
            "by_modality": {}
        }
        
        for code in cpt_codes:
            # Categorize by procedure type
            categories = self.get_procedure_category(code)
            for category in categories:
                if category not in result["by_category"]:
                    result["by_category"][category] = []
                result["by_category"][category].append(code)
            
            # Categorize by body part
            body_part = self.get_body_part(code)
            if body_part:
                if body_part not in result["by_body_part"]:
                    result["by_body_part"][body_part] = []
                result["by_body_part"][body_part].append(code)
            
            # Determine modality
            modality = None
            for category_name, category_codes in self.procedure_categories.items():
                if code in category_codes and category_name in ["MRI", "CT", "X-ray", "Ultrasound"]:
                    modality = category_name.lower()
                    break
                    
            if modality:
                if modality not in result["by_modality"]:
                    result["by_modality"][modality] = []
                result["by_modality"][modality].append(code)
        
        return result