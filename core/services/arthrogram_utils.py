from typing import Dict, List, Optional

class ArthrogramUtils:
    """Utility class for arthrogram-related operations."""
    
    # Set of CPT codes that indicate an arthrogram
    ARTHROGRAM_CPTS = {
        '77002',  # Fluoroscopic guidance
        '77003',  # Fluoroscopic guidance
    }
    
    # Set of fluoroscopic guidance codes
    FLUORO_CODES = {
        '77002',  # Fluoroscopic guidance
        '77003',  # Fluoroscopic guidance
    }
    
    @staticmethod
    def check_json_for_arthrogram(json_data: Dict) -> bool:
        """Check if JSON data contains arthrogram indicators."""
        try:
            # Check service lines
            service_lines = json_data.get('service_lines', [])
            return ArthrogramUtils.check_line_items_for_arthrogram(service_lines)
        except Exception as e:
            print(f"Error checking JSON for arthrogram: {str(e)}")
            return False
    
    @staticmethod
    def check_line_items_for_arthrogram(line_items: List[Dict]) -> bool:
        """Check if line items contain arthrogram indicators."""
        try:
            for item in line_items:
                cpt_code = item.get('cpt_code')
                if not cpt_code:
                    continue
                
                # Check for fluoroscopic guidance or injection codes
                if cpt_code in ArthrogramUtils.FLUORO_CODES or cpt_code.startswith('2'):
                    return True
            
            return False
        except Exception as e:
            print(f"Error checking line items for arthrogram: {str(e)}")
            return False
    
    @staticmethod
    def check_db_order_for_arthrogram(order_data: Dict) -> bool:
        """Check if database order data contains arthrogram indicators."""
        try:
            # Check line items
            line_items = order_data.get('line_items', [])
            return ArthrogramUtils.check_line_items_for_arthrogram(line_items)
        except Exception as e:
            print(f"Error checking DB order for arthrogram: {str(e)}")
            return False 