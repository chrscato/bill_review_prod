import sqlite3
import logging
from pathlib import Path
from typing import Dict, List, Tuple, Any, Union, Set

logger = logging.getLogger(__name__)

class OTAService:
    """
    Service for managing OTA (One Time Agreement) rates in the database.
    Handles OTA rate lookups and updates for out-of-network providers.
    """
    
    def __init__(self, db_path: Union[str, Path]):
        """
        Initialize the OTA service with a database path.
        
        Args:
            db_path: Path to the SQLite database
        """
        self.db_path = Path(db_path)
        
        # Set up logging if not already configured
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            handler.setFormatter(formatter)
            logger.addHandler(handler)
            logger.setLevel(logging.INFO)
        
        # Verify database exists
        if not self.db_path.exists():
            logger.error(f"Database file not found: {self.db_path}")
            raise FileNotFoundError(f"Database file not found: {self.db_path}")
            
        # Verify current_otas table exists
        self._verify_current_otas_table()
    
    def _verify_current_otas_table(self):
        """
        Verify that the current_otas table exists in the database.
        Creates the table if it doesn't exist.
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                # Check if the table exists
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='current_otas'")
                if not cursor.fetchone():
                    logger.warning("current_otas table not found in database, creating it...")
                    
                    # Create the current_otas table
                    cursor.execute("""
                        CREATE TABLE current_otas (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            ID_Order_PrimaryKey TEXT,
                            CPT TEXT,
                            modifier TEXT,
                            rate REAL,
                            UNIQUE(ID_Order_PrimaryKey, CPT, modifier)
                        )
                    """)
                    conn.commit()
                    logger.info("current_otas table created successfully")
                    
                else:
                    # Verify all required columns exist
                    cursor.execute("PRAGMA table_info(current_otas)")
                    columns = {row['name'] for row in cursor.fetchall()}
                    
                    required_columns = {
                        'ID_Order_PrimaryKey', 'CPT', 'modifier', 'rate'
                    }
                    
                    missing_columns = required_columns - columns
                    if missing_columns:
                        logger.error(f"current_otas table is missing required columns: {missing_columns}")
                        raise ValueError(f"current_otas table is missing required columns: {missing_columns}")
        
        except sqlite3.Error as e:
            logger.error(f"Database error when verifying current_otas table: {e}")
            raise
    
    def _get_connection(self) -> sqlite3.Connection:
        """
        Get a SQLite database connection with row factory enabled.
        
        Returns:
            sqlite3.Connection: Database connection
        """
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            return conn
        except sqlite3.Error as e:
            logger.error(f"Error connecting to database: {e}")
            raise
    
    def get_order_otas(self, order_id: str) -> List[Dict[str, Any]]:
        """
        Get all OTA rates for an order.
        
        Args:
            order_id: Order ID
        
        Returns:
            List of dictionaries containing OTA rate information
        """
        try:
            if not order_id:
                logger.warning("No order ID provided")
                return []
            
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                query = """
                SELECT ID_Order_PrimaryKey, CPT, modifier, rate
                FROM current_otas
                WHERE ID_Order_PrimaryKey = ?
                """
                
                cursor.execute(query, (order_id,))
                rows = cursor.fetchall()
                
                # Convert to list of dictionaries
                return [
                    {
                        'order_id': row['ID_Order_PrimaryKey'],
                        'cpt_code': row['CPT'],
                        'modifier': row['modifier'],
                        'rate': row['rate']
                    }
                    for row in rows
                ]
        
        except sqlite3.Error as e:
            logger.error(f"Database error getting OTA rates: {e}")
            return []
    
    def update_ota_rates(
        self, 
        order_id: str, 
        line_items: List[Dict]
    ) -> Tuple[bool, str, List[Dict]]:
        """
        Update OTA rates for specific line items.
        
        Args:
            order_id: Order ID
            line_items: List of dictionaries with cpt_code and rate
        
        Returns:
            Tuple of (success, message, updated_items)
        """
        if not order_id:
            return False, "No order ID provided", []
            
        if not line_items:
            return False, "No line items provided", []
        
        updated_items = []
        
        try:
            with self._get_connection() as conn:
                # Start a transaction
                conn.execute("BEGIN TRANSACTION")
                cursor = conn.cursor()
                
                for item in line_items:
                    cpt_code = item.get('cpt_code')
                    rate = item.get('rate')
                    modifier = item.get('modifier', '')
                    
                    if not cpt_code or rate is None:
                        continue
                    
                    # Determine if there's an existing record
                    cursor.execute(
                        "SELECT COUNT(*) as count FROM current_otas WHERE ID_Order_PrimaryKey = ? AND CPT = ? AND modifier = ?",
                        (order_id, cpt_code, modifier)
                    )
                    result = cursor.fetchone()
                    exists = result['count'] > 0
                    
                    if exists:
                        # Update existing record
                        cursor.execute("""
                            UPDATE current_otas 
                            SET rate = ?
                            WHERE ID_Order_PrimaryKey = ? AND CPT = ? AND modifier = ?
                        """, (rate, order_id, cpt_code, modifier))
                    else:
                        # Insert new record
                        cursor.execute("""
                            INSERT INTO current_otas 
                            (ID_Order_PrimaryKey, CPT, modifier, rate)
                            VALUES (?, ?, ?, ?)
                        """, (order_id, cpt_code, modifier, rate))
                    
                    updated_items.append({
                        'order_id': order_id,
                        'cpt_code': cpt_code,
                        'modifier': modifier,
                        'rate': rate
                    })
                
                # Commit the transaction
                conn.commit()
                
                message = f"Updated {len(updated_items)} OTA rates for order {order_id}"
                logger.info(message)
                return True, message, updated_items
                
        except sqlite3.Error as e:
            logger.error(f"Database error updating OTA rates: {e}")
            return False, f"Database error: {str(e)}", []
        except Exception as e:
            logger.error(f"Error updating OTA rates: {e}")
            return False, f"Error: {str(e)}", [] 