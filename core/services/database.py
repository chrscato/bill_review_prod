# Database operations 
# core/services/database.py
import sqlite3
import pandas as pd
from typing import Dict, List, Optional, Any, Tuple, Set
from pathlib import Path
import json
from datetime import datetime
from config.settings import settings
import logging

class DatabaseService:
    """
    Enhanced database service for the Bill Review System 2.0.
    Provides robust data access methods and caching for improved performance.
    """
    
    def __init__(self, db_path: Optional[Path] = None):
        """
        Initialize the database service.
        
        Args:
            db_path: Path to the SQLite database (default: from settings)
        """
        self.db_path = db_path or settings.DB_PATH
        self._cache = {}  # Simple cache for frequently accessed data
        self.logger = logging.getLogger(__name__)
        
    def connect_db(self) -> sqlite3.Connection:
        """
        Create a database connection with proper configuration.
        
        Returns:
            sqlite3.Connection: Database connection
        """
        conn = sqlite3.connect(self.db_path)
        
        # Configure connection for better pandas integration
        conn.row_factory = sqlite3.Row
        
        return conn
    
    def get_line_items(self, order_id: str, conn: Optional[sqlite3.Connection] = None) -> pd.DataFrame:
        """
        Get line items for an order with enhanced error handling.
        
        Args:
            order_id: Order ID to get line items for
            conn: Database connection (optional)
            
        Returns:
            pd.DataFrame: DataFrame containing line items
        """
        # Use provided connection or create a new one
        close_conn = False
        if conn is None:
            conn = self.connect_db()
            close_conn = True
            
        try:
            query = """
            SELECT id, Order_ID, DOS, CPT, Modifier, Units, Description
            FROM line_items
            WHERE Order_ID = ?
            """
            
            # Execute query and handle empty results
            df = pd.read_sql_query(query, conn, params=[order_id])
            
            # Add enhanced error handling
            if df.empty:
                self.logger.warning(f"No line items found for Order_ID: {order_id}")
                
            return df
        except Exception as e:
            self.logger.error(f"Error getting line items for Order_ID {order_id}: {str(e)}")
            # Return empty DataFrame with expected columns
            return pd.DataFrame(columns=['id', 'Order_ID', 'DOS', 'CPT', 'Modifier', 'Units', 'Description'])
        finally:
            # Close connection if we created it
            if close_conn and conn:
                conn.close()
    
    def get_provider_details(self, order_id: str, conn: Optional[sqlite3.Connection] = None) -> Optional[Dict]:
        """
        Get provider details for an order with enhanced error handling and caching.
        
        Args:
            order_id: Order ID to get provider details for
            conn: Database connection (optional)
            
        Returns:
            Dict: Provider details or None if not found
        """
        # Check cache first
        cache_key = f"provider_details_{order_id}"
        if cache_key in self._cache:
            return self._cache[cache_key]
            
        # Use provided connection or create a new one
        close_conn = False
        if conn is None:
            conn = self.connect_db()
            close_conn = True
            
        try:
            query = """
            SELECT 
                p."Address 1 Full",
                p."Billing Address 1",
                p."Billing Address 2",
                p."Billing Address City",
                p."Billing Address Postal Code",
                p."Billing Address State",
                p."Billing Name",
                p."DBA Name Billing Name",
                p."Latitude",
                p."Location",
                p."Need OTA",
                p."Provider Network",
                p."Provider Status",
                p."Provider Type",
                p."TIN",
                p."NPI",
                p.PrimaryKey
            FROM orders o
            JOIN providers p ON o.provider_id = p.PrimaryKey
            WHERE o.Order_ID = ?
            """
            
            df = pd.read_sql_query(query, conn, params=[order_id])
            
            if df.empty:
                self.logger.warning(f"No provider details found for Order_ID: {order_id}")
                return None
                
            # Convert first row to dictionary
            provider_details = df.iloc[0].to_dict()
            
            # Cache the result
            self._cache[cache_key] = provider_details
            
            return provider_details
        except Exception as e:
            self.logger.error(f"Error getting provider details for Order_ID {order_id}: {str(e)}")
            return None
        finally:
            # Close connection if we created it
            if close_conn and conn:
                conn.close()
    
    def get_full_details(self, order_id: str, conn: Optional[sqlite3.Connection] = None) -> Dict:
        """
        Fetch all related data for an order in a single query with improved result handling.
        
        Args:
            order_id: Order ID to get details for
            conn: Database connection (optional)
            
        Returns:
            Dict: All related data for the order
        """
        # Use provided connection or create a new one
        close_conn = False
        if conn is None:
            conn = self.connect_db()
            close_conn = True
            
        try:
            queries = {
                "order_details": "SELECT * FROM orders WHERE Order_ID = ?",
                "provider_details": """
                SELECT p.* 
                FROM orders o
                JOIN providers p ON o.provider_id = p.PrimaryKey
                WHERE o.Order_ID = ?
                """,
                "line_items": "SELECT * FROM line_items WHERE Order_ID = ?"
            }
            
            results = {}
            
            for table_name, query in queries.items():
                try:
                    df = pd.read_sql_query(query, conn, params=[order_id])
                    
                    if not df.empty:
                        if table_name == "line_items":
                            # For line items, return all rows as a list of dictionaries
                            results[table_name] = df.to_dict('records')
                        else:
                            # For singular tables, return the first row as a dictionary
                            results[table_name] = df.iloc[0].to_dict()
                    else:
                        # Handle empty results with proper defaults
                        if table_name == "line_items":
                            results[table_name] = []
                        else:
                            results[table_name] = {}
                            
                except Exception as e:
                    self.logger.error(f"Error executing query for {table_name}: {str(e)}")
                    # Provide appropriate empty structure based on query type
                    if table_name == "line_items":
                        results[table_name] = []
                    else:
                        results[table_name] = {}
            
            return results
        except Exception as e:
            self.logger.error(f"Error getting full details for Order_ID {order_id}: {str(e)}")
            # Return a structured empty result
            return {
                "order_details": {},
                "provider_details": {},
                "line_items": []
            }
        finally:
            # Close connection if we created it
            if close_conn and conn:
                conn.close()
                
    def check_bundle(self, order_id: str, conn: Optional[sqlite3.Connection] = None) -> bool:
        """
        Check if an order is bundled with enhanced error handling.
        
        Args:
            order_id: Order ID to check
            conn: Database connection (optional)
            
        Returns:
            bool: True if the order is bundled, False otherwise
        """
        # Use provided connection or create a new one
        close_conn = False
        if conn is None:
            conn = self.connect_db()
            close_conn = True
            
        try:
            query = "SELECT bundle_type FROM orders WHERE Order_ID = ?"
            
            df = pd.read_sql_query(query, conn, params=[order_id])
            
            if df.empty:
                return False
                
            # Check if bundle_type is not null/NaN
            return pd.notna(df['bundle_type'].iloc[0]) and df['bundle_type'].iloc[0] != ''
        except Exception as e:
            self.logger.error(f"Error checking bundle for Order_ID {order_id}: {str(e)}")
            return False
        finally:
            # Close connection if we created it
            if close_conn and conn:
                conn.close()
    
    def get_procedure_categories(self, cpt_codes: List[str], conn: Optional[sqlite3.Connection] = None) -> Dict[str, str]:
        """
        Get procedure categories for multiple CPT codes.
        
        Args:
            cpt_codes: List of CPT codes
            conn: Database connection (optional)
            
        Returns:
            Dict: Mapping of CPT codes to categories
        """
        if not cpt_codes:
            return {}
            
        # Use provided connection or create a new one
        close_conn = False
        if conn is None:
            conn = self.connect_db()
            close_conn = True
            
        try:
            # Use parameterized query with placeholders for each CPT code
            placeholders = ','.join(['?' for _ in cpt_codes])
            query = f"SELECT proc_cd, proc_category FROM dim_proc WHERE proc_cd IN ({placeholders})"
            
            df = pd.read_sql_query(query, conn, params=cpt_codes)
            
            # Create mapping of CPT code to category
            categories = {}
            for _, row in df.iterrows():
                cpt = str(row['proc_cd'])
                category = row['proc_category']
                categories[cpt] = category
                
            # Add missing CPT codes with None category
            for cpt in cpt_codes:
                if cpt not in categories:
                    categories[cpt] = None
                    
            return categories
        except Exception as e:
            self.logger.error(f"Error getting procedure categories: {str(e)}")
            # Return a minimal valid result
            return {cpt: None for cpt in cpt_codes}
        finally:
            # Close connection if we created it
            if close_conn and conn:
                conn.close()
    
    def get_ppo_rates(self, provider_tin: str, cpt_codes: List[str], conn: Optional[sqlite3.Connection] = None) -> Dict[str, float]:
        """
        Get PPO rates for a provider and multiple CPT codes.
        
        Args:
            provider_tin: Provider TIN
            cpt_codes: List of CPT codes
            conn: Database connection (optional)
            
        Returns:
            Dict: Mapping of CPT codes to rates
        """
        if not cpt_codes or not provider_tin:
            return {}
            
        # Use provided connection or create a new one
        close_conn = False
        if conn is None:
            conn = self.connect_db()
            close_conn = True
            
        try:
            # Clean TIN and prepare CPT code placeholders
            clean_tin = provider_tin.replace("-", "").strip()
            placeholders = ','.join(['?' for _ in cpt_codes])
            
            query = f"""
            SELECT proc_cd, rate 
            FROM ppo 
            WHERE TRIM(TIN) = ? AND proc_cd IN ({placeholders})
            """
            
            params = [clean_tin] + cpt_codes
            df = pd.read_sql_query(query, conn, params=params)
            
            # Create mapping of CPT code to rate
            rates = {}
            for _, row in df.iterrows():
                cpt = str(row['proc_cd'])
                rate = float(row['rate'])
                rates[cpt] = rate
                
            return rates
        except Exception as e:
            self.logger.error(f"Error getting PPO rates for TIN {provider_tin}: {str(e)}")
            return {}
        finally:
            # Close connection if we created it
            if close_conn and conn:
                conn.close()
    
    def get_ota_rates(self, order_id: str, cpt_codes: List[str], conn: Optional[sqlite3.Connection] = None) -> Dict[str, float]:
        """
        Get OTA rates for an order and multiple CPT codes.
        
        Args:
            order_id: Order ID
            cpt_codes: List of CPT codes
            conn: Database connection (optional)
            
        Returns:
            Dict: Mapping of CPT codes to rates
        """
        if not cpt_codes or not order_id:
            return {}
            
        # Use provided connection or create a new one
        close_conn = False
        if conn is None:
            conn = self.connect_db()
            close_conn = True
            
        try:
            # Prepare CPT code placeholders
            placeholders = ','.join(['?' for _ in cpt_codes])
            
            query = f"""
            SELECT CPT, rate 
            FROM current_otas 
            WHERE ID_Order_PrimaryKey = ? AND CPT IN ({placeholders})
            """
            
            params = [order_id] + cpt_codes
            df = pd.read_sql_query(query, conn, params=params)
            
            # Create mapping of CPT code to rate
            rates = {}
            for _, row in df.iterrows():
                cpt = str(row['CPT'])
                rate = float(row['rate'])
                rates[cpt] = rate
                
            return rates
        except Exception as e:
            self.logger.error(f"Error getting OTA rates for Order ID {order_id}: {str(e)}")
            return {}
        finally:
            # Close connection if we created it
            if close_conn and conn:
                conn.close()
    
    def get_bundle_info(self, order_id: str, conn: Optional[sqlite3.Connection] = None) -> Optional[Dict]:
        """
        Get bundle information for an order.
        
        Args:
            order_id: Order ID
            conn: Database connection (optional)
            
        Returns:
            Dict: Bundle information or None if not a bundle
        """
        # Use provided connection or create a new one
        close_conn = False
        if conn is None:
            conn = self.connect_db()
            close_conn = True
            
        try:
            query = """
            SELECT bundle_type, bundle_name, bundle_rate
            FROM orders
            WHERE Order_ID = ? AND bundle_type IS NOT NULL
            """
            
            df = pd.read_sql_query(query, conn, params=[order_id])
            
            if df.empty:
                return None
                
            # Convert to dictionary
            bundle_info = df.iloc[0].to_dict()
            
            # Add line items for this bundle
            line_items_query = """
            SELECT CPT, Modifier, Units, Description
            FROM line_items
            WHERE Order_ID = ?
            """
            
            line_items_df = pd.read_sql_query(line_items_query, conn, params=[order_id])
            bundle_info['line_items'] = line_items_df.to_dict('records')
            
            return bundle_info
        except Exception as e:
            self.logger.error(f"Error getting bundle info for Order ID {order_id}: {str(e)}")
            return None
        finally:
            # Close connection if we created it
            if close_conn and conn:
                conn.close()
    
    def save_validation_result(self, validation_result: Dict, conn: Optional[sqlite3.Connection] = None) -> bool:
        """
        Save a validation result to the database.
        
        Args:
            validation_result: Validation result to save
            conn: Database connection (optional)
            
        Returns:
            bool: True if successful, False otherwise
        """
        # Use provided connection or create a new one
        close_conn = False
        if conn is None:
            conn = self.connect_db()
            close_conn = True
            
        try:
            query = """
            INSERT INTO validation_results (
                file_name, timestamp, patient_name, date_of_service, order_id,
                status, validation_type, details_json, messages_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """
            
            # Convert details and messages to JSON
            details_json = json.dumps(validation_result.get('details', {}))
            messages_json = json.dumps(validation_result.get('messages', []))
            
            # Execute query
            cursor = conn.cursor()
            cursor.execute(query, [
                validation_result.get('file_name'),
                validation_result.get('timestamp', datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
                validation_result.get('patient_name'),
                validation_result.get('date_of_service'),
                validation_result.get('order_id'),
                validation_result.get('status'),
                validation_result.get('validation_type'),
                details_json,
                messages_json
            ])
            
            conn.commit()
            return True
        except Exception as e:
            self.logger.error(f"Error saving validation result: {str(e)}")
            return False
        finally:
            # Close connection if we created it
            if close_conn and conn:
                conn.close()
    
    def get_ancillary_codes(self, conn: Optional[sqlite3.Connection] = None) -> Set[str]:
        """
        Get a set of all CPT codes categorized as ancillary.
        
        Args:
            conn: Database connection (optional)
            
        Returns:
            Set[str]: Set of ancillary CPT codes
        """
        # Check cache first
        cache_key = "ancillary_codes"
        if cache_key in self._cache:
            return self._cache[cache_key]
            
        # Use provided connection or create a new one
        close_conn = False
        if conn is None:
            conn = self.connect_db()
            close_conn = True
            
        try:
            query = "SELECT proc_cd FROM dim_proc WHERE LOWER(proc_category) = 'ancillary'"
            
            df = pd.read_sql_query(query, conn)
            
            # Convert to set of strings
            ancillary_codes = set(str(code) for code in df['proc_cd'])
            
            # Cache the result
            self._cache[cache_key] = ancillary_codes
            
            return ancillary_codes
        except Exception as e:
            self.logger.error(f"Error getting ancillary codes: {str(e)}")
            return set()
        finally:
            # Close connection if we created it
            if close_conn and conn:
                conn.close()
    
    def get_dim_proc_df(self, conn: Optional[sqlite3.Connection] = None) -> pd.DataFrame:
        """
        Get the dim_proc table as a DataFrame.
        
        Args:
            conn: Database connection (optional)
            
        Returns:
            pd.DataFrame: DataFrame containing the dim_proc table
        """
        # Check cache first
        cache_key = "dim_proc_df"
        if cache_key in self._cache:
            return self._cache[cache_key].copy()
            
        # Use provided connection or create a new one
        close_conn = False
        if conn is None:
            conn = self.connect_db()
            close_conn = True
            
        try:
            query = "SELECT * FROM dim_proc"
            
            df = pd.read_sql_query(query, conn)
            
            # Cache the result
            self._cache[cache_key] = df
            
            return df
        except Exception as e:
            self.logger.error(f"Error getting dim_proc table: {str(e)}")
            return pd.DataFrame()
        finally:
            # Close connection if we created it
            if close_conn and conn:
                conn.close()
                
    def clear_cache(self) -> None:
        """Clear the internal cache."""
        self._cache = {}
        
    def get_validation_failures(self, 
                              limit: int = 100, 
                              offset: int = 0, 
                              status: Optional[str] = None,
                              validation_type: Optional[str] = None,
                              conn: Optional[sqlite3.Connection] = None) -> pd.DataFrame:
        """
        Get validation failures from the database.
        
        Args:
            limit: Maximum number of results to return
            offset: Number of results to skip
            status: Filter by status (e.g., 'FAIL')
            validation_type: Filter by validation type
            conn: Database connection (optional)
            
        Returns:
            pd.DataFrame: DataFrame containing validation failures
        """
        # Use provided connection or create a new one
        close_conn = False
        if conn is None:
            conn = self.connect_db()
            close_conn = True
            
        try:
            # Build query with filters
            query = "SELECT * FROM validation_results"
            params = []
            
            # Add filters
            filters = []
            if status:
                filters.append("status = ?")
                params.append(status)
                
            if validation_type:
                filters.append("validation_type = ?")
                params.append(validation_type)
                
            # Add WHERE clause if there are filters
            if filters:
                query += " WHERE " + " AND ".join(filters)
                
            # Add ORDER BY, LIMIT, and OFFSET
            query += " ORDER BY timestamp DESC LIMIT ? OFFSET ?"
            params.extend([limit, offset])
            
            # Execute query
            df = pd.read_sql_query(query, conn, params=params)
            
            # Parse JSON columns
            if 'details_json' in df.columns:
                df['details'] = df['details_json'].apply(lambda x: json.loads(x) if x else {})
                
            if 'messages_json' in df.columns:
                df['messages'] = df['messages_json'].apply(lambda x: json.loads(x) if x else [])
                
            return df
        except Exception as e:
            self.logger.error(f"Error getting validation failures: {str(e)}")
            return pd.DataFrame()
        finally:
            # Close connection if we created it
            if close_conn and conn:
                conn.close()
                
    def get_validation_summary(self, 
                             start_date: Optional[str] = None,
                             end_date: Optional[str] = None,
                             conn: Optional[sqlite3.Connection] = None) -> Dict:
        """
        Get a summary of validation results.
        
        Args:
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            conn: Database connection (optional)
            
        Returns:
            Dict: Summary of validation results
        """
        # Use provided connection or create a new one
        close_conn = False
        if conn is None:
            conn = self.connect_db()
            close_conn = True
            
        try:
            # Build base query
            query = "SELECT status, validation_type, COUNT(*) as count FROM validation_results"
            params = []
            
            # Add date filters
            filters = []
            if start_date:
                filters.append("timestamp >= ?")
                params.append(start_date)
                
            if end_date:
                filters.append("timestamp <= ?")
                params.append(end_date + " 23:59:59")  # Include all of end date
                
            # Add WHERE clause if there are filters
            if filters:
                query += " WHERE " + " AND ".join(filters)
                
            # Add GROUP BY
            query += " GROUP BY status, validation_type"
            
            # Execute query
            df = pd.read_sql_query(query, conn, params=params)
            
            # Transform to summary format
            summary = {
                "total": df['count'].sum(),
                "by_status": {},
                "by_validation_type": {}
            }
            
            # Count by status
            for status in df['status'].unique():
                status_df = df[df['status'] == status]
                summary["by_status"][status] = status_df['count'].sum()
                
            # Count by validation type
            for vtype in df['validation_type'].unique():
                vtype_df = df[df['validation_type'] == vtype]
                summary["by_validation_type"][vtype] = vtype_df['count'].sum()
                
            # Add status breakdown for each validation type
            summary["by_validation_type_status"] = {}
            for vtype in df['validation_type'].unique():
                vtype_df = df[df['validation_type'] == vtype]
                summary["by_validation_type_status"][vtype] = {
                    status: count for status, count in zip(vtype_df['status'], vtype_df['count'])
                }
                
            return summary
        except Exception as e:
            self.logger.error(f"Error getting validation summary: {str(e)}")
            return {"total": 0, "by_status": {}, "by_validation_type": {}}
        finally:
            # Close connection if we created it
            if close_conn and conn:
                conn.close()