import sqlite3
from pathlib import Path
import logging
from typing import List, Set, Dict, Any, Optional

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class ArthrogramUtils:
    """Shared utilities for arthrogram identification and processing."""
    
    # Set of CPT codes that indicate arthrogram
    ARTHROGRAM_CPTS = {
        '77002',  # Fluoroscopic guidance
        '77003',  # Fluoroscopic guidance
        # Injection codes (starting with 2)
        '23350',  # Shoulder injection
        '27093',  # Hip injection
        '27370',  # Knee injection
        '25246',  # Wrist injection
        '24220',  # Elbow injection
        '27648',  # Ankle injection
        '20610',  # Large joint injection
        '20605',  # Intermediate joint injection
    }
    
    # Set of fluoroscopic guidance codes
    FLUORO_CODES = {'77002', '77003'}
    
    @staticmethod
    def is_arthrogram_cpt(cpt: str) -> bool:
        """Check if a CPT code indicates an arthrogram."""
        return cpt and (cpt in ArthrogramUtils.ARTHROGRAM_CPTS or cpt.startswith('2'))
    
    @staticmethod
    def is_arthrogram_description(description: str) -> bool:
        """Check if a description contains arthrogram-related text."""
        return description and "arthrogram" in description.lower()
    
    @staticmethod
    def check_line_items_for_arthrogram(line_items: List[Dict[str, Any]]) -> bool:
        """
        Check if any line item indicates an arthrogram.
        
        Args:
            line_items: List of line items to check
            
        Returns:
            bool: True if any line item indicates an arthrogram
        """
        for item in line_items:
            cpt = item.get('cpt_code') or item.get('CPT')
            
            # Check for fluoroscopic guidance codes
            if cpt in ArthrogramUtils.FLUORO_CODES:
                return True
                
            # Check for injection codes
            if cpt and cpt.startswith('2'):
                return True
                
        return False
    
    @staticmethod
    def check_json_for_arthrogram(json_data: Dict[str, Any]) -> bool:
        """
        Check if a JSON file contains arthrogram-related data.
        
        Args:
            json_data: JSON data to check
            
        Returns:
            bool: True if JSON contains arthrogram indicators
        """
        # Check service lines
        service_lines = json_data.get('service_lines', [])
        return service_lines and ArthrogramUtils.check_line_items_for_arthrogram(service_lines)
    
    @staticmethod
    def check_db_order_for_arthrogram(order_id: str, conn: sqlite3.Connection) -> bool:
        """
        Check if a database order contains arthrogram-related data.
        
        Args:
            order_id: Order ID to check
            conn: Database connection
            
        Returns:
            bool: True if order contains arthrogram indicators
        """
        cursor = conn.cursor()
        cursor.execute("""
            SELECT CPT, Description 
            FROM line_items 
            WHERE Order_ID = ?
        """, (order_id,))
        
        for cpt, description in cursor.fetchall():
            # Check for fluoroscopic guidance codes
            if cpt in ArthrogramUtils.FLUORO_CODES:
                return True
                
            # Check for injection codes
            if cpt and cpt.startswith('2'):
                return True
                
        return False
    
    @staticmethod
    def update_order_bundle_type(order_id: str, conn: sqlite3.Connection) -> bool:
        """
        Update the bundle_type of an order to 'ARTHROGRAM'.
        
        Args:
            order_id: Order ID to update
            conn: Database connection
            
        Returns:
            bool: True if update was successful, False otherwise
        """
        try:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE orders 
                SET bundle_type = 'ARTHROGRAM' 
                WHERE Order_ID = ?
            """, (order_id,))
            conn.commit()
            return True
        except Exception as e:
            logger.error(f"Error updating order {order_id}: {str(e)}")
            return False 