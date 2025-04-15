from typing import Dict, List, Any
from core.services.database import DatabaseService

class CPTValidator:
    """
    Validator for checking if CPT codes exist in the dim_proc table.
    """
    
    def __init__(self):
        """Initialize the CPT validator with database service."""
        self.db_service = DatabaseService()
        
    def validate(self, hcfa_data: Dict) -> Dict:
        """
        Validate that all CPT codes in the HCFA data exist in dim_proc table.
        
        Args:
            hcfa_data: Dictionary containing HCFA data including line items
            
        Returns:
            Dict: Validation result with status and details
        """
        try:
            # Get all CPT codes from HCFA data
            cpt_codes = []
            for line_item in hcfa_data.get('line_items', []):
                cpt = line_item.get('cpt')
                if cpt:
                    cpt_codes.append(str(cpt))
            
            if not cpt_codes:
                return {
                    'status': 'PASS',
                    'message': 'No CPT codes to validate',
                    'details': {}
                }
            
            # Get dim_proc DataFrame
            conn = self.db_service.connect_db()
            try:
                dim_proc_df = self.db_service.get_dim_proc_df(conn)
                
                # Check each CPT code
                unknown_cpts = []
                for cpt in cpt_codes:
                    if cpt not in dim_proc_df['CPT'].values:
                        unknown_cpts.append(cpt)
                
                if unknown_cpts:
                    return {
                        'status': 'FAIL',
                        'message': 'Unknown CPT codes found',
                        'details': {
                            'unknown_cpts': unknown_cpts,
                            'failure_reason': 'unknown CPT'
                        }
                    }
                
                return {
                    'status': 'PASS',
                    'message': 'All CPT codes validated successfully',
                    'details': {}
                }
                
            finally:
                conn.close()
                
        except Exception as e:
            return {
                'status': 'ERROR',
                'message': f'Error during CPT validation: {str(e)}',
                'details': {}
            } 