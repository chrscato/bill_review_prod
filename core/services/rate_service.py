import sqlite3
import logging
from pathlib import Path
from typing import Dict, List, Tuple, Any, Union, Set

logger = logging.getLogger(__name__)

class RateService:
    """
    Service for managing provider rates in the database.
    Handles rate lookups and updates for individual CPT codes and categories.
    """
    
    # CPT code categories mapping - must match JavaScript categories
    PROCEDURE_CATEGORIES = {
        "MRI w/o": [
            "70551", "72141", "73721", "73718", "70540", "72195", 
            "72146", "73221", "73218"
        ],
        "MRI w/": [
            "70552", "72142", "73722", "70542", "72196", 
            "72147", "73222", "73219"
        ],
        "MRI w/&w/o": [
            "70553", "72156", "73723", "70543", "72197", 
            "72157", "73223", "73220"
        ],
        "CT w/o": [
            "74176", "74150", "72125", "70450", "73700", 
            "72131", "70486", "70480", "72192", "70490", 
            "72128", "71250", "73200"
        ],
        "CT w/": [
            "74177", "74160", "72126", "70460", "73701", 
            "72132", "70487", "70481", "72193", "70491", 
            "72129", "71260", "73201"
        ],
        "CT w/&w/o": [
            "74178", "74170", "72127", "70470", "73702", 
            "72133", "70488", "70482", "72194", "70492", 
            "72130", "71270", "73202"
        ],
        "Xray": [
            "74010", "74000", "74020", "76080", "73050", 
            "73600", "73610", "77072", "77073", "73650", 
            "72040", "72050", "71010", "71021", "71023", 
            "71022", "71020", "71030", "71034", "71035", "73130"
        ],
        "Ultrasound": [
            "76700", "76705", "76770", "76775", "76536",
            "76604", "76642", "76856", "76857", "76870"
        ]
    }
    
    def __init__(self, db_path: Union[str, Path]):
        """
        Initialize the rate service with a database path.
        
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
            
        # Verify ppo table exists
        self._verify_ppo_table()
    
    def _verify_ppo_table(self):
        """
        Verify that the ppo table exists in the database.
        Creates the table if it doesn't exist.
        """
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                # Check if the table exists
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='ppo'")
                if not cursor.fetchone():
                    logger.warning("PPO table not found in database, creating it...")
                    
                    # Create the ppo table
                    cursor.execute("""
                        CREATE TABLE ppo (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            RenderingState TEXT,
                            TIN TEXT,
                            provider_name TEXT,
                            proc_cd TEXT,
                            modifier TEXT,
                            proc_desc TEXT,
                            proc_category TEXT,
                            rate REAL,
                            UNIQUE(TIN, proc_cd, modifier)
                        )
                    """)
                    conn.commit()
                    logger.info("PPO table created successfully")
                    
                else:
                    # Verify all required columns exist
                    cursor.execute("PRAGMA table_info(ppo)")
                    columns = {row['name'] for row in cursor.fetchall()}
                    
                    required_columns = {
                        'id', 'RenderingState', 'TIN', 'provider_name', 'proc_cd',
                        'modifier', 'proc_category', 'rate'
                    }
                    
                    missing_columns = required_columns - columns
                    if missing_columns:
                        # We could add missing columns here, but that's more complex
                        # For now, just report the issue
                        logger.error(f"PPO table is missing required columns: {missing_columns}")
                        raise ValueError(f"PPO table is missing required columns: {missing_columns}")
        
        except sqlite3.Error as e:
            logger.error(f"Database error when verifying PPO table: {e}")
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
    
    def get_provider_rates(self, tin: str) -> List[Dict[str, Any]]:
        """
        Get all rates for a provider by TIN.
        
        Args:
            tin: Provider's Tax ID Number
        
        Returns:
            List of dictionaries containing rate information
        """
        try:
            # Clean TIN - remove non-digits
            clean_tin = ''.join(c for c in tin if c.isdigit())
            
            # Validate TIN format
            if len(clean_tin) != 9:
                logger.warning(f"Invalid TIN format: {tin}")
                return []
            
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                query = """
                SELECT proc_cd, modifier, proc_category, rate
                FROM ppo
                WHERE TRIM(TIN) = ?
                """
                
                cursor.execute(query, (clean_tin,))
                rows = cursor.fetchall()
                
                # Convert to list of dictionaries
                return [
                    {
                        'cpt_code': row['proc_cd'],
                        'modifier': row['modifier'],
                        'category': row['proc_category'],
                        'rate': row['rate']
                    }
                    for row in rows
                ]
        
        except sqlite3.Error as e:
            logger.error(f"Database error getting provider rates: {e}")
            return []
    
    def get_provider_info(self, tin: str) -> Dict[str, Any]:
        """
        Get provider information by TIN.
        
        Args:
            tin: Provider's Tax ID Number
        
        Returns:
            Dictionary with provider information or empty dict if not found
        """
        try:
            # Clean TIN - remove non-digits
            clean_tin = ''.join(c for c in tin if c.isdigit())
            
            # Validate TIN format
            if len(clean_tin) != 9:
                logger.warning(f"Invalid TIN format: {tin}")
                return {}
            
            with self._get_connection() as conn:
                cursor = conn.cursor()
                
                query = """
                SELECT DISTINCT provider_name
                FROM ppo
                WHERE TRIM(TIN) = ?
                LIMIT 1
                """
                
                cursor.execute(query, (clean_tin,))
                row = cursor.fetchone()
                
                if row:
                    return {
                        'provider_name': row['provider_name'],
                        'tin': clean_tin
                    }
                
                # If not found in ppo, check providers table
                query = """
                SELECT "Name" as provider_name
                FROM providers
                WHERE TRIM(TIN) = ?
                LIMIT 1
                """
                
                cursor.execute(query, (clean_tin,))
                row = cursor.fetchone()
                
                if row:
                    return {
                        'provider_name': row['provider_name'],
                        'tin': clean_tin
                    }
                
                return {'tin': clean_tin}
        
        except sqlite3.Error as e:
            logger.error(f"Database error getting provider info: {e}")
            return {}
    
    def update_line_item_rates(
        self, 
        tin: str, 
        line_items: List[Dict],
        state: str = 'XX'  # Default state code
    ) -> Tuple[bool, str, List[Dict]]:
        """
        Update rates for specific line items.
        
        Args:
            tin: Provider's Tax ID Number
            line_items: List of dictionaries with cpt_code and rate
            state: State code (default: 'XX')
        
        Returns:
            Tuple of (success, message, updated_items)
        """
        if not line_items:
            return False, "No line items provided", []
        
        # Clean TIN - remove non-digits
        clean_tin = ''.join(c for c in tin if c.isdigit())
        
        # Validate TIN format
        if len(clean_tin) != 9:
            return False, f"Invalid TIN format: {tin}", []
        
        # Get provider info
        provider_info = self.get_provider_info(clean_tin)
        provider_name = provider_info.get('provider_name', 'Unknown Provider')
        
        updated_items = []
        
        try:
            with self._get_connection() as conn:
                # Start a transaction
                conn.execute("BEGIN TRANSACTION")
                cursor = conn.cursor()
                
                for item in line_items:
                    cpt_code = item.get('cpt_code')
                    rate = item.get('rate')
                    
                    if not cpt_code or rate is None:
                        continue
                    
                    # Determine category for the CPT code
                    category = self._get_category_for_code(cpt_code)
                    
                    # Determine if there's an existing record
                    cursor.execute(
                        "SELECT COUNT(*) as count FROM ppo WHERE TRIM(TIN) = ? AND TRIM(proc_cd) = ?",
                        (clean_tin, cpt_code)
                    )
                    result = cursor.fetchone()
                    exists = result['count'] > 0
                    
                    if exists:
                        # Update existing record
                        cursor.execute("""
                            UPDATE ppo 
                            SET rate = ?, 
                                proc_category = ?,
                                RenderingState = ?
                            WHERE TRIM(TIN) = ? AND TRIM(proc_cd) = ?
                        """, (rate, category, state, clean_tin, cpt_code))
                    else:
                        # Insert new record
                        cursor.execute("""
                            INSERT INTO ppo 
                            (RenderingState, TIN, provider_name, proc_cd, 
                            modifier, proc_category, rate)
                            VALUES (?, ?, ?, ?, ?, ?, ?)
                        """, (state, clean_tin, provider_name, cpt_code, 
                             '', category, rate))
                    
                    updated_items.append({
                        'cpt_code': cpt_code,
                        'rate': rate,
                        'category': category
                    })
                
                # Commit the transaction
                conn.commit()
                
                message = f"Updated {len(updated_items)} rates for provider {provider_name} (TIN: {clean_tin})"
                logger.info(message)
                return True, message, updated_items
                
        except sqlite3.Error as e:
            logger.error(f"Database error updating line item rates: {e}")
            return False, f"Database error: {str(e)}", []
        except Exception as e:
            logger.error(f"Error updating line item rates: {e}")
            return False, f"Error: {str(e)}", []
    
    def update_category_rates(
        self, 
        tin: str, 
        category_rates: Dict[str, float],
        state: str = 'XX'  # Default state code
    ) -> Tuple[bool, str, Dict[str, List[str]]]:
        """
        Update rates for entire categories of CPT codes.
        
        Args:
            tin: Provider's Tax ID Number
            category_rates: Dictionary mapping categories to rates
            state: State code (default: 'XX')
        
        Returns:
            Tuple of (success, message, updated_categories)
        """
        if not category_rates:
            return False, "No category rates provided", {}
        
        # Clean TIN - remove non-digits
        clean_tin = ''.join(c for c in tin if c.isdigit())
        
        # Validate TIN format
        if len(clean_tin) != 9:
            return False, f"Invalid TIN format: {tin}", {}
        
        # Get provider info
        provider_info = self.get_provider_info(clean_tin)
        provider_name = provider_info.get('provider_name', 'Unknown Provider')
        
        updated_categories = {}
        total_codes_updated = 0
        
        try:
            with self._get_connection() as conn:
                # Start a transaction
                conn.execute("BEGIN TRANSACTION")
                cursor = conn.cursor()
                
                for category, rate in category_rates.items():
                    # Get CPT codes for this category
                    cpt_codes = self.PROCEDURE_CATEGORIES.get(category, [])
                    
                    if not cpt_codes:
                        logger.warning(f"No CPT codes found for category: {category}")
                        continue
                    
                    updated_categories[category] = []
                    
                    for cpt_code in cpt_codes:
                        # Determine if there's an existing record
                        cursor.execute(
                            "SELECT COUNT(*) as count FROM ppo WHERE TRIM(TIN) = ? AND TRIM(proc_cd) = ?",
                            (clean_tin, cpt_code)
                        )
                        result = cursor.fetchone()
                        exists = result['count'] > 0
                        
                        if exists:
                            # Update existing record
                            cursor.execute("""
                                UPDATE ppo 
                                SET rate = ?, 
                                    proc_category = ?,
                                    RenderingState = ?
                                WHERE TRIM(TIN) = ? AND TRIM(proc_cd) = ?
                            """, (rate, category, state, clean_tin, cpt_code))
                        else:
                            # Insert new record
                            cursor.execute("""
                                INSERT INTO ppo 
                                (RenderingState, TIN, provider_name, proc_cd, 
                                modifier, proc_category, rate)
                                VALUES (?, ?, ?, ?, ?, ?, ?)
                            """, (state, clean_tin, provider_name, cpt_code, 
                                 '', category, rate))
                        
                        updated_categories[category].append(cpt_code)
                        total_codes_updated += 1
                
                # Commit the transaction
                conn.commit()
                
                message = (f"Updated {total_codes_updated} CPT codes across "
                          f"{len(category_rates)} categories for provider "
                          f"{provider_name} (TIN: {clean_tin})")
                
                logger.info(message)
                return True, message, updated_categories
                
        except sqlite3.Error as e:
            logger.error(f"Database error updating category rates: {e}")
            return False, f"Database error: {str(e)}", {}
        except Exception as e:
            logger.error(f"Error updating category rates: {e}")
            return False, f"Error: {str(e)}", {}
    
    def _get_category_for_code(self, cpt_code: str) -> str:
        """
        Determine which category a CPT code belongs to.
        
        Args:
            cpt_code: CPT code to categorize
        
        Returns:
            Category name or 'Uncategorized'
        """
        for category, codes in self.PROCEDURE_CATEGORIES.items():
            if cpt_code in codes:
                return category
        
        # If not found in any category, try to determine based on code prefix
        cpt_prefix = cpt_code[:3]
        
        # Simple categorization based on CPT code prefix
        if cpt_prefix in ['705', '707', '721', '722', '723', '732', '737']:
            if cpt_code[3:5] in ['51', '52', '53']:  # MRI codes often end with these
                return "MRI w/o"
            elif cpt_code[3:5] in ['21', '22', '23']:  # CT codes often end with these
                return "CT w/o"
        
        return "Uncategorized" 