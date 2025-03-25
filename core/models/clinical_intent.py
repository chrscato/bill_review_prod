# core/models/clinical_intent.py
from dataclasses import dataclass, field
from typing import Dict, List, Set, Optional, Any
from enum import Enum

class Modality(Enum):
    """Imaging or procedure modality."""
    MRI = "mri"
    CT = "ct"
    XRAY = "xray"
    ULTRASOUND = "ultrasound"
    FLUOROSCOPY = "fluoroscopy"
    THERAPEUTIC = "therapeutic"
    DIAGNOSTIC = "diagnostic"
    UNKNOWN = "unknown"

class BodyRegion(Enum):
    """Body region for procedures."""
    HEAD = "head"
    NECK = "neck"
    SPINE = "spine"
    CHEST = "chest"
    ABDOMEN = "abdomen"
    PELVIS = "pelvis"
    UPPER_EXTREMITY = "upper_extremity"
    LOWER_EXTREMITY = "lower_extremity"
    UNKNOWN = "unknown"

class BodyPart(Enum):
    """Specific body part."""
    BRAIN = "brain"
    CERVICAL_SPINE = "cervical_spine"
    THORACIC_SPINE = "thoracic_spine"
    LUMBAR_SPINE = "lumbar_spine"
    SHOULDER = "shoulder"
    ELBOW = "elbow"
    WRIST = "wrist"
    HAND = "hand"
    HIP = "hip"
    KNEE = "knee"
    ANKLE = "ankle"
    FOOT = "foot"
    UNKNOWN = "unknown"

class IntentCategory(Enum):
    """Clinical intent category."""
    DIAGNOSTIC_IMAGING = "diagnostic_imaging"
    THERAPEUTIC_PROCEDURE = "therapeutic_procedure"
    DIAGNOSTIC_PROCEDURE = "diagnostic_procedure"
    ARTHROGRAM = "arthrogram"
    EMG = "emg"
    INJECTION = "injection"
    UNKNOWN = "unknown"

@dataclass
class ClinicalIntent:
    """
    Represents the clinical intent of a procedure or set of procedures.
    Used to determine if different CPT codes have the same clinical purpose.
    """
    category: IntentCategory = IntentCategory.UNKNOWN
    modality: Modality = Modality.UNKNOWN
    body_region: BodyRegion = BodyRegion.UNKNOWN
    body_part: Optional[BodyPart] = None
    laterality: Optional[str] = None  # "left", "right", "bilateral", None
    contrast: Optional[bool] = None  # True, False, None (not applicable)
    cpt_codes: Set[str] = field(default_factory=set)
    confidence: float = 0.0  # 0-100 confidence score
    
    @classmethod
    def from_cpt_codes(cls, cpt_codes: Set[str], intent_mapper: Any = None) -> 'ClinicalIntent':
        """
        Create a ClinicalIntent instance from a set of CPT codes.
        
        Args:
            cpt_codes: Set of CPT codes to analyze
            intent_mapper: Optional mapper to assist with classification
            
        Returns:
            ClinicalIntent: Classified clinical intent
        """
        if not cpt_codes:
            return cls()
            
        # Use the intent mapper if provided, otherwise do basic classification
        if intent_mapper:
            return intent_mapper.classify_intent(cpt_codes)
            
        # Basic classification based on code patterns
        intent = cls(cpt_codes=cpt_codes)
        
        # Determine modality and category from code patterns
        has_mri = any(code.startswith('7') and code[2:4] in ('05', '15', '22', '25', '55') for code in cpt_codes)
        has_ct = any(code.startswith('7') and code[2:4] in ('04', '12', '13', '14', '17', '48') for code in cpt_codes)
        has_xray = any(code.startswith('7') and code[2:4] in ('01', '02', '10', '20', '60') for code in cpt_codes)
        has_injection = any(code.startswith('206') for code in cpt_codes)
        has_emg = any(code.startswith('958') or code.startswith('959') for code in cpt_codes)
        
        if has_mri:
            intent.modality = Modality.MRI
            intent.category = IntentCategory.DIAGNOSTIC_IMAGING
        elif has_ct:
            intent.modality = Modality.CT
            intent.category = IntentCategory.DIAGNOSTIC_IMAGING
        elif has_xray:
            intent.modality = Modality.XRAY
            intent.category = IntentCategory.DIAGNOSTIC_IMAGING
        elif has_injection:
            intent.modality = Modality.THERAPEUTIC
            intent.category = IntentCategory.INJECTION
        elif has_emg:
            intent.category = IntentCategory.EMG
            
        # Determine body region
        head_codes = {'7055', '7054', '7045', '7048'}
        spine_codes = {'721', '722', '723'}
        extremity_codes = {'737', '732', '733'}
        
        for code in cpt_codes:
            prefix = code[:4]
            if prefix[:3] in spine_codes:
                intent.body_region = BodyRegion.SPINE
                break
            elif prefix[:4] in head_codes:
                intent.body_region = BodyRegion.HEAD
                break
            elif prefix[:3] in extremity_codes:
                if prefix.startswith('732'):
                    intent.body_region = BodyRegion.UPPER_EXTREMITY
                else:
                    intent.body_region = BodyRegion.LOWER_EXTREMITY
                break
        
        # Calculate confidence - more CPT codes generally means lower confidence
        # in a single clinical intent
        intent.confidence = 100 if len(cpt_codes) == 1 else max(30, 100 - (len(cpt_codes) - 1) * 10)
        
        return intent
    
    def matches(self, other: 'ClinicalIntent', threshold: float = 70.0) -> bool:
        """
        Determine if this clinical intent matches another one.
        
        Args:
            other: Another ClinicalIntent to compare to
            threshold: Confidence threshold for matching
            
        Returns:
            bool: True if intents match, False otherwise
        """
        # If either intent has low confidence, require higher similarity
        if self.confidence < threshold or other.confidence < threshold:
            return False
            
        # Different categories never match
        if self.category != other.category and self.category != IntentCategory.UNKNOWN and other.category != IntentCategory.UNKNOWN:
            return False
            
        # Different body regions never match (unless unknown)
        if self.body_region != other.body_region and self.body_region != BodyRegion.UNKNOWN and other.body_region != BodyRegion.UNKNOWN:
            return False
            
        # If both have body parts specified, they must match
        if self.body_part and other.body_part and self.body_part != other.body_part:
            return False
            
        # Modality mismatch is acceptable in some cases (e.g., MRI vs CT for same region)
        modality_match = (
            self.modality == other.modality or 
            self.modality == Modality.UNKNOWN or 
            other.modality == Modality.UNKNOWN or
            (self.modality in [Modality.MRI, Modality.CT] and other.modality in [Modality.MRI, Modality.CT])
        )
        
        if not modality_match:
            return False
            
        # Laterality should match if specified
        if self.laterality and other.laterality and self.laterality != other.laterality:
            return False
            
        # CPT overlap gives higher confidence
        cpt_overlap = len(self.cpt_codes.intersection(other.cpt_codes))
        has_cpt_match = cpt_overlap > 0 or len(self.cpt_codes) == 0 or len(other.cpt_codes) == 0
        
        # Consider diagnostic equivalence
        if has_cpt_match:
            return True
            
        # Final determination based on weighted criteria
        # In a real system, this would be more sophisticated
        return (self.category == other.category and 
                self.body_region == other.body_region and 
                modality_match)
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for serialization."""
        return {
            "category": self.category.value,
            "modality": self.modality.value,
            "body_region": self.body_region.value,
            "body_part": self.body_part.value if self.body_part else None,
            "laterality": self.laterality,
            "contrast": self.contrast,
            "cpt_codes": list(self.cpt_codes),
            "confidence": self.confidence
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'ClinicalIntent':
        """Create from dictionary."""
        return cls(
            category=IntentCategory(data.get("category", "unknown")),
            modality=Modality(data.get("modality", "unknown")),
            body_region=BodyRegion(data.get("body_region", "unknown")),
            body_part=BodyPart(data.get("body_part")) if data.get("body_part") else None,
            laterality=data.get("laterality"),
            contrast=data.get("contrast"),
            cpt_codes=set(data.get("cpt_codes", [])),
            confidence=data.get("confidence", 0.0)
        )