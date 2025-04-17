from pathlib import Path
import json
from typing import Dict, List, Optional
from datetime import datetime
import logging
from core.config.settings import settings

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
        total_files = 0
        skipped_files = 0
        error_files = 0
        
        try:
            logger.info(f"Reading failed files from: {self.fails_dir}")
            for file_path in self.fails_dir.glob("*.json"):
                total_files += 1
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
                    else:
                        skipped_files += 1
                except Exception as e:
                    logger.error(f"Error reading file {file_path}: {str(e)}")
                    error_files += 1
                    continue
                    
            # Log summary statistics
            logger.info(f"File processing summary:")
            logger.info(f"Total JSON files found: {total_files}")
            logger.info(f"Successfully processed files: {len(failed_files)}")
            logger.info(f"Skipped files (invalid format): {skipped_files}")
            logger.info(f"Error files: {error_files}")
                    
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
                
            # Add the filename to the data
            data['filename'] = filename
                
            # Return the data as-is without transformation
            return data
            
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