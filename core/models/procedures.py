# core/models/procedures.py
from dataclasses import dataclass, field
from typing import Dict, List, Set, Optional, Any
from enum import Enum
from datetime import date

class ProcedureStatus(Enum):
    """Procedure status."""
    ORDERED = "ordered"
    SCHEDULED = "scheduled"
    COMPLETED = "completed"
    CANCELED = "canceled"
    BILLED = "billed"
    VALIDATED = "validated"
    REJECTED = "rejected"
    UNKNOWN = "unknown"

@dataclass
class ProcedureCode:
    """Represents a procedure code with its modifiers and units."""
    code: str
    modifiers: List[str] = field(default_factory=list)
    units: int = 1
    description: Optional[str] = None
    fee: Optional[float] = None
    rate: Optional[float] = None
    
    def matches(self, other: 'ProcedureCode', modifier_match: bool = True) -> bool:
        """
        Compare two procedure codes for matching.
        
        Args:
            other: Another ProcedureCode to compare to
            modifier_match: Whether modifiers must match exactly
            
        Returns:
            bool: True if codes match based on criteria
        """
        if self.code != other.code:
            return False
            
        if modifier_match:
            # Check if modifiers match, regardless of order
            return set(self.modifiers) == set(other.modifiers)
        
        return True
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for serialization."""
        return {
            "code": self.code,
            "modifiers": self.modifiers,
            "units": self.units,
            "description": self.description,
            "fee": self.fee,
            "rate": self.rate
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'ProcedureCode':
        """Create from dictionary."""
        return cls(
            code=data.get("code", ""),
            modifiers=data.get("modifiers", []),
            units=data.get("units", 1),
            description=data.get("description"),
            fee=data.get("fee"),
            rate=data.get("rate")
        )

@dataclass
class ProcedureBundle:
    """
    Represents a bundle of procedures that are typically performed together.
    Used for recognizing and validating procedure bundles.
    """
    name: str
    bundle_type: str
    codes: List[ProcedureCode] = field(default_factory=list)
    body_part: Optional[str] = None
    modality: Optional[str] = None
    core_codes: List[str] = field(default_factory=list)
    optional_codes: List[str] = field(default_factory=list)
    rate: Optional[float] = None
    
    def contains_code(self, code: str) -> bool:
        """Check if this bundle contains a specific code."""
        return any(proc.code == code for proc in self.codes)
        
    def matches(self, codes: List[ProcedureCode], partial_match: bool = True) -> Dict:
        """
        Check if a list of procedure codes matches this bundle.
        
        Args:
            codes: List of procedure codes to check
            partial_match: Whether to allow partial matches (missing optional codes)
            
        Returns:
            Dict: Matching result with details
        """
        code_set = {proc.code for proc in codes}
        core_match = all(core_code in code_set for core_code in self.core_codes)
        
        if not core_match and not partial_match:
            return {
                "match": False,
                "reason": "Missing core codes",
                "missing_core": [code for code in self.core_codes if code not in code_set]
            }
        
        # For partial match, require at least half of core codes
        if not core_match and partial_match:
            core_match_count = sum(1 for code in self.core_codes if code in code_set)
            core_match_pct = core_match_count / len(self.core_codes) if self.core_codes else 0
            
            if core_match_pct < 0.5:
                return {
                    "match": False,
                    "reason": "Insufficient core codes",
                    "match_percentage": core_match_pct * 100,
                    "missing_core": [code for code in self.core_codes if code not in code_set]
                }
        
        # Check optional codes
        missing_optional = [code for code in self.optional_codes if code not in code_set]
        
        # Extra codes not in the bundle
        extra_codes = code_set - set(self.core_codes) - set(self.optional_codes)
        
        return {
            "match": True,
            "complete": core_match and not missing_optional,
            "match_quality": "full" if core_match else "partial",
            "missing_core": [] if core_match else [code for code in self.core_codes if code not in code_set],
            "missing_optional": missing_optional,
            "extra_codes": list(extra_codes)
        }
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for serialization."""
        return {
            "name": self.name,
            "bundle_type": self.bundle_type,
            "codes": [code.to_dict() for code in self.codes],
            "body_part": self.body_part,
            "modality": self.modality,
            "core_codes": self.core_codes,
            "optional_codes": self.optional_codes,
            "rate": self.rate
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'ProcedureBundle':
        """Create from dictionary."""
        return cls(
            name=data.get("name", ""),
            bundle_type=data.get("bundle_type", ""),
            codes=[ProcedureCode.from_dict(code) for code in data.get("codes", [])],
            body_part=data.get("body_part"),
            modality=data.get("modality"),
            core_codes=data.get("core_codes", []),
            optional_codes=data.get("optional_codes", []),
            rate=data.get("rate")
        )

@dataclass
class Procedure:
    """
    Represents a medical procedure with detailed information.
    Used for representing both ordered and billed procedures.
    """
    procedure_code: ProcedureCode
    date_of_service: Optional[date] = None
    status: ProcedureStatus = ProcedureStatus.UNKNOWN
    provider_id: Optional[str] = None
    provider_name: Optional[str] = None
    provider_tin: Optional[str] = None
    order_id: Optional[str] = None
    patient_id: Optional[str] = None
    patient_name: Optional[str] = None
    icd_codes: List[str] = field(default_factory=list)
    bundle_name: Optional[str] = None
    is_bundle_component: bool = False
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for serialization."""
        return {
            "procedure_code": self.procedure_code.to_dict(),
            "date_of_service": self.date_of_service.isoformat() if self.date_of_service else None,
            "status": self.status.value,
            "provider_id": self.provider_id,
            "provider_name": self.provider_name,
            "provider_tin": self.provider_tin,
            "order_id": self.order_id,
            "patient_id": self.patient_id,
            "patient_name": self.patient_name,
            "icd_codes": self.icd_codes,
            "bundle_name": self.bundle_name,
            "is_bundle_component": self.is_bundle_component
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'Procedure':
        """Create from dictionary."""
        return cls(
            procedure_code=ProcedureCode.from_dict(data.get("procedure_code", {})),
            date_of_service=date.fromisoformat(data.get("date_of_service")) if data.get("date_of_service") else None,
            status=ProcedureStatus(data.get("status", "unknown")),
            provider_id=data.get("provider_id"),
            provider_name=data.get("provider_name"),
            provider_tin=data.get("provider_tin"),
            order_id=data.get("order_id"),
            patient_id=data.get("patient_id"),
            patient_name=data.get("patient_name"),
            icd_codes=data.get("icd_codes", []),
            bundle_name=data.get("bundle_name"),
            is_bundle_component=data.get("is_bundle_component", False)
        )
    
    @classmethod
    def from_line_item(cls, line_item: Dict, context: Dict = None) -> 'Procedure':
        """
        Create a Procedure from a line item dictionary.
        
        Args:
            line_item: Dictionary containing line item data
            context: Optional context with additional information
            
        Returns:
            Procedure: Created procedure instance
        """
        context = context or {}
        
        # Parse modifiers (may be in different formats)
        modifiers = []
        if 'modifier' in line_item:
            if isinstance(line_item['modifier'], str):
                if ',' in line_item['modifier']:
                    modifiers = line_item['modifier'].split(',')
                else:
                    modifiers = [line_item['modifier']]
            elif isinstance(line_item['modifier'], list):
                modifiers = line_item['modifier']
        
        # Create procedure code
        procedure_code = ProcedureCode(
            code=str(line_item.get('cpt', line_item.get('CPT', ''))),
            modifiers=modifiers,
            units=int(line_item.get('units', line_item.get('Units', 1))),
            description=line_item.get('description', line_item.get('Description', '')),
            fee=float(line_item.get('charge', 0)) if 'charge' in line_item else None
        )
        
        # Parse date of service
        dos = None
        if 'date_of_service' in line_item:
            try:
                dos = date.fromisoformat(line_item['date_of_service'])
            except (ValueError, TypeError):
                pass
                
        # Create procedure
        return cls(
            procedure_code=procedure_code,
            date_of_service=dos,
            provider_id=context.get('provider_id'),
            provider_name=context.get('provider_name'),
            provider_tin=context.get('provider_tin'),
            order_id=context.get('order_id'),
            patient_id=context.get('patient_id'),
            patient_name=context.get('patient_name'),
            bundle_name=line_item.get('bundle_name'),
            is_bundle_component=bool(line_item.get('bundle_name'))
        )

def extract_procedures_from_hcfa(hcfa_data: Dict) -> List[Procedure]:
    """
    Extract procedures from HCFA data.
    
    Args:
        hcfa_data: HCFA data dictionary
        
    Returns:
        List[Procedure]: Extracted procedures
    """
    procedures = []
    
    # Context information
    context = {
        'order_id': hcfa_data.get('Order_ID'),
        'patient_name': hcfa_data.get('patient_name'),
        'provider_tin': hcfa_data.get('billing_provider_tin'),
        'provider_name': hcfa_data.get('billing_provider_name')
    }
    
    # Extract from line_items
    if 'line_items' in hcfa_data and isinstance(hcfa_data['line_items'], list):
        for line_item in hcfa_data['line_items']:
            procedure = Procedure.from_line_item(line_item, context)
            procedure.status = ProcedureStatus.BILLED
            procedures.append(procedure)
    
    # Extract from service_lines (alternative format)
    elif 'service_lines' in hcfa_data and isinstance(hcfa_data['service_lines'], list):
        for service_line in hcfa_data['service_lines']:
            # Convert service_line to line_item format
            line_item = {
                'cpt': service_line.get('cpt_code'),
                'modifier': service_line.get('modifiers', []),
                'units': service_line.get('units', 1),
                'charge': service_line.get('charge_amount'),
                'date_of_service': service_line.get('date_of_service')
            }
            
            procedure = Procedure.from_line_item(line_item, context)
            procedure.status = ProcedureStatus.BILLED
            procedures.append(procedure)
    
    return procedures

def extract_procedures_from_order(order_data: Dict) -> List[Procedure]:
    """
    Extract procedures from order data.
    
    Args:
        order_data: Order data dictionary
        
    Returns:
        List[Procedure]: Extracted procedures
    """
    procedures = []
    
    # Context information
    context = {
        'order_id': order_data.get('Order_ID'),
        'patient_name': order_data.get('Patient_Name'),
        'provider_id': order_data.get('provider_id')
    }
    
    # Extract from line_items
    if 'line_items' in order_data and isinstance(order_data['line_items'], list):
        for line_item in order_data['line_items']:
            # Convert line_item to common format if needed
            if 'CPT' in line_item and 'cpt' not in line_item:
                line_item['cpt'] = line_item['CPT']
            if 'Modifier' in line_item and 'modifier' not in line_item:
                line_item['modifier'] = line_item['Modifier']
            if 'Units' in line_item and 'units' not in line_item:
                line_item['units'] = line_item['Units']
            if 'Description' in line_item and 'description' not in line_item:
                line_item['description'] = line_item['Description']
                
            procedure = Procedure.from_line_item(line_item, context)
            procedure.status = ProcedureStatus.ORDERED
            procedures.append(procedure)
    
    return procedures