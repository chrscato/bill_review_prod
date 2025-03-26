from pathlib import Path
import json
from typing import Dict, List, Optional
from datetime import datetime
import logging
from config.settings import settings

logger = logging.getLogger(__name__)

class HCFAService:
    """Service for handling HCFA (CMS-1500) data operations."""
    
    def __init__(self):
        """Initialize the HCFA service."""
        self.fails_dir = settings.FAILS_PATH
        
    def get_failed_files(self) -> List[Dict]:
        """
        Get all failed validation files with their details.
        
        Returns:
            List[Dict]: List of failed files with their details
        """
        failed_files = []
        
        try:
            logger.info(f"Reading failed files from: {self.fails_dir}")
            for file_path in self.fails_dir.glob("*.json"):
                try:
                    data = self._read_hcfa_file(file_path)
                    if data:
                        failed_files.append({
                            'filename': file_path.name,
                            'order_id': data.get('Order_ID', 'N/A'),
                            'patient_name': data.get('patient_info', {}).get('patient_name', 'N/A'),
                            'date_of_service': self._get_first_dos(data),
                            'total_charge': data.get('billing_info', {}).get('total_charge', '0.00'),
                            'validation_messages': data.get('validation_messages', []),
                            'last_modified': datetime.fromtimestamp(file_path.stat().st_mtime).strftime('%Y-%m-%d %H:%M:%S')
                        })
                except Exception as e:
                    logger.error(f"Error reading file {file_path}: {str(e)}")
                    continue
                    
        except Exception as e:
            logger.error(f"Error accessing fails directory: {str(e)}")
            
        return failed_files
    
    def get_hcfa_details(self, filename: str) -> Optional[Dict]:
        """
        Get detailed HCFA information for a specific file.
        
        Args:
            filename: Name of the HCFA file
            
        Returns:
            Optional[Dict]: HCFA details or None if not found
        """
        file_path = self.fails_dir / filename
        
        try:
            logger.info(f"Reading HCFA details from: {file_path}")
            if not file_path.exists():
                logger.error(f"File not found: {file_path}")
                return None
                
            data = self._read_hcfa_file(file_path)
            if not data:
                return None
                
            # Structure the response
            return {
                'patient_info': {
                    'name': data.get('patient_info', {}).get('patient_name', 'N/A'),
                    'dob': data.get('patient_info', {}).get('patient_dob', 'N/A'),
                    'zip': data.get('patient_info', {}).get('patient_zip', 'N/A')
                },
                'billing_info': {
                    'provider_name': data.get('billing_info', {}).get('billing_provider_name', 'N/A'),
                    'provider_npi': data.get('billing_info', {}).get('billing_provider_npi', 'N/A'),
                    'provider_tin': data.get('billing_info', {}).get('billing_provider_tin', 'N/A'),
                    'total_charge': data.get('billing_info', {}).get('total_charge', '0.00'),
                    'account_number': data.get('billing_info', {}).get('patient_account_no', 'N/A')
                },
                'service_lines': [{
                    'date_of_service': line.get('date_of_service', 'N/A'),
                    'cpt': line.get('cpt_code', 'N/A'),
                    'modifier': ', '.join(line.get('modifiers', [])) if line.get('modifiers') else 'N/A',
                    'units': line.get('units', 1),
                    'description': line.get('diagnosis_pointer', 'N/A'),
                    'charge_amount': line.get('charge_amount', '0.00'),
                    'place_of_service': line.get('place_of_service', 'N/A')
                } for line in data.get('service_lines', [])],
                'order_info': {
                    'order_id': data.get('Order_ID', 'N/A'),
                    'filemaker_number': data.get('filemaker_number', 'N/A')
                },
                'validation_messages': data.get('validation_messages', [])
            }
            
        except Exception as e:
            logger.error(f"Error reading HCFA details from {filename}: {str(e)}")
            return None
    
    def _read_hcfa_file(self, file_path: Path) -> Optional[Dict]:
        """
        Read and validate a HCFA JSON file.
        
        Args:
            file_path: Path to the HCFA file
            
        Returns:
            Optional[Dict]: Validated HCFA data or None if invalid
        """
        try:
            with open(file_path, 'r') as f:
                data = json.load(f)
                
            # Basic validation
            if not isinstance(data, dict):
                logger.error(f"Invalid JSON structure in {file_path}: not a dictionary")
                return None
                
            if 'Order_ID' not in data:
                logger.error(f"Missing Order_ID in {file_path}")
                return None
                
            return data
            
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in {file_path}: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"Error reading file {file_path}: {str(e)}")
            return None
    
    def _get_first_dos(self, data: Dict) -> str:
        """
        Get the first date of service from service lines.
        
        Args:
            data: HCFA data dictionary
            
        Returns:
            str: First date of service or 'N/A' if not found
        """
        service_lines = data.get('service_lines', [])
        if service_lines and isinstance(service_lines, list):
            return service_lines[0].get('date_of_service', 'N/A')
        return 'N/A' 