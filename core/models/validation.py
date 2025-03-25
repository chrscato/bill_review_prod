# Validation data models 
# core/models/validation.py
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional
from datetime import datetime

@dataclass
class ValidationContext:
    """
    Context information for a validation operation.
    Contains basic information about the file being validated.
    """
    file_name: str
    patient_name: str
    date_of_service: str
    order_id: str

@dataclass
class ValidationResult:
    """
    Result of a validation operation.
    Contains detailed information about the validation outcome.
    """
    file_name: str
    timestamp: str
    status: str  # "PASS" or "FAIL"
    validation_type: str  # The type of validation performed (e.g., "bundle", "rate", "modifier")
    
    # Optional fields with default values
    patient_name: Optional[str] = None
    date_of_service: Optional[str] = None
    order_id: Optional[str] = None
    
    # Detailed validation information
    details: Dict[str, Any] = field(default_factory=dict)
    messages: List[str] = field(default_factory=list)
    
    # Source data for reference
    source_data: Dict[str, Any] = field(default_factory=dict)
    
    @classmethod
    def create_base_result(cls, file_path: str) -> Dict:
        """
        Create a base result dictionary with default values.
        
        Args:
            file_path: Path to the file being validated
            
        Returns:
            Dict: Base result dictionary
        """
        return {
            "file_name": str(file_path),
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "patient_name": None,
            "date_of_service": None,
            "order_id": None,
            "source_data": {}
        }
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert the validation result to a dictionary.
        
        Returns:
            Dict: Dictionary representation of the validation result
        """
        return {
            "file_name": self.file_name,
            "timestamp": self.timestamp,
            "patient_name": self.patient_name,
            "date_of_service": self.date_of_service,
            "order_id": self.order_id,
            "status": self.status,
            "validation_type": self.validation_type,
            "details": self.details,
            "messages": self.messages,
            "source_data": self.source_data
        }

@dataclass
class ValidationSession:
    """
    A session for performing multiple validations.
    Keeps track of all validation results.
    """
    session_id: str
    start_time: datetime
    end_time: Optional[datetime] = None
    results: List[ValidationResult] = field(default_factory=list)
    
    def add_result(self, result: ValidationResult) -> None:
        """
        Add a validation result to the session.
        
        Args:
            result: Validation result to add
        """
        self.results.append(result)
    
    def complete(self) -> None:
        """
        Mark the session as complete.
        """
        self.end_time = datetime.now()
    
    def get_summary(self) -> Dict[str, Any]:
        """
        Get a summary of the validation session.
        
        Returns:
            Dict: Summary information
        """
        pass_count = sum(1 for r in self.results if r.status == "PASS")
        fail_count = sum(1 for r in self.results if r.status == "FAIL")
        
        return {
            "session_id": self.session_id,
            "start_time": self.start_time.strftime("%Y-%m-%d %H:%M:%S"),
            "end_time": self.end_time.strftime("%Y-%m-%d %H:%M:%S") if self.end_time else None,
            "total_validations": len(self.results),
            "pass_count": pass_count,
            "fail_count": fail_count,
            "success_rate": (pass_count / len(self.results)) * 100 if self.results else 0,
            "validation_types": {r.validation_type for r in self.results}
        }