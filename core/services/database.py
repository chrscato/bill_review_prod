# Database operations 
# core/services/database.py
import sqlite3
import pandas as pd
from typing import Dict, List, Optional, Any, Tuple, Set
from pathlib import Path
import json
from datetime import datetime
from core.config.settings import settings
import logging

logger = logging.getLogger(__name__)

class DatabaseService:
    """
    Database service for the Bill Review System.
    Provides data access methods with proper error handling and logging.
    """
    
    def __init__(self):
        """Initialize database connection parameters."""
        self.db_path = settings.DB_PATH
        self._cache = {}  # Initialize cache dictionary

    def connect_db(self):
        """Establish a connection to the database."""
        try:
            if not self.db_path.exists():
                logger.error(f"Database file not found at: {self.db_path}")
                raise FileNotFoundError(f"Database file not found at: {self.db_path}")
            
            logger.info(f"Attempting to connect to database at: {self.db_path}")
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row  # Enable row factory for better dictionary-like access
            logger.info("Successfully connected to database")
            return conn
        except sqlite3.Error as e:
            logger.error(f"SQLite error connecting to database: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"Failed to connect to database: {str(e)}")
            raise
    
    @staticmethod
    def get_line_items(order_id: str, conn: sqlite3.Connection) -> pd.DataFrame:
        """
        Get line items for an order with error handling.
        
        Args:
            order_id: Order ID to get line items for
            conn: Database connection
            
        Returns:
            pd.DataFrame: DataFrame containing line items
        """
        try:
            query = """
            SELECT id, Order_ID, DOS, CPT, Modifier, Units, Description
            FROM line_items
            WHERE Order_ID = ?
            """
            df = pd.read_sql_query(query, conn, params=[order_id])
            
            if df.empty:
                logging.warning(f"No line items found for Order_ID: {order_id}")
                
            return df
        except Exception as e:
            logging.error(f"Error getting line items for Order_ID {order_id}: {str(e)}")
            return pd.DataFrame(columns=['id', 'Order_ID', 'DOS', 'CPT', 'Modifier', 'Units', 'Description'])
    
    @staticmethod
    def get_provider_details(order_id: str, conn: sqlite3.Connection) -> Optional[Dict]:
        """
        Get provider details through the orders-providers relationship.
        
        Args:
            order_id: Order ID to get provider details for
            conn: Database connection
            
        Returns:
            Dict: Provider details or None if not found
        """
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
                p.PrimaryKey,
                p.State
            FROM orders o
            JOIN providers p ON o.provider_id = p.PrimaryKey
            WHERE o.Order_ID = ?
            """
            
            df = pd.read_sql_query(query, conn, params=[order_id])
            if df.empty:
                logging.warning(f"No provider details found for Order_ID: {order_id}")
                return None
                
            # Convert to dictionary and clean up NaN values
            provider_details = df.iloc[0].to_dict()
            return {k: v for k, v in provider_details.items() if pd.notna(v)}
            
        except Exception as e:
            logging.error(f"Error getting provider details for Order_ID {order_id}: {str(e)}")
            return None
    
    def get_full_details(self, order_id: str, conn: Optional[sqlite3.Connection] = None) -> Dict:
        """
        Get full order details including provider and line items.
        
        Args:
            order_id: Order ID to get details for
            conn: Optional database connection to use
            
        Returns:
            Dict: Full order details
        """
        try:
            # Use provided connection or create new one
            should_close = False
            if conn is None:
                conn = self.connect_db()
                should_close = True
                
            try:
                cursor = conn.cursor()
                
                # Get order details
                cursor.execute("""
                    SELECT 
                        o.Order_ID,
                        o.FileMaker_Record_Number,
                        o.PatientName,
                        o.Patient_DOB,
                        o.Patient_Zip,
                        o.Order_Type,
                        o.bundle_type,
                        o.created_at,
                        o.provider_id,
                        o.provider_name
                    FROM orders o
                    WHERE o.Order_ID = ?
                """, (order_id,))
                
                order_details = cursor.fetchone()
                if not order_details:
                    return None
                
                # Get provider details
                cursor.execute("""
                    SELECT 
                        p."DBA Name Billing Name",
                        p.NPI,
                        p.TIN,
                        p."Provider Status",
                        p."Provider Network",
                        p."Billing Address 1",
                        p."Billing Address City",
                        p."Billing Address Postal Code",
                        p."Billing Address State",
                        p."Billing Name"
                    FROM providers p
                    WHERE p.PrimaryKey = ?
                """, (order_details[8],))  # provider_id
                provider_details = cursor.fetchone()
                
                # Get line items
                cursor.execute("""
                    SELECT 
                        li.DOS,
                        li.CPT,
                        li.Modifier,
                        li.Units,
                        li.Description,
                        li.Charge,
                        li.BR_paid,
                        li.BR_rate,
                        li.EOBR_doc_no,
                        li.HCFA_doc_no,
                        li.BR_date_processed
                    FROM line_items li
                    WHERE li.Order_ID = ?
                    ORDER BY li.line_number
                """, (order_id,))
                
                line_items = cursor.fetchall()
                
                # Convert to dictionaries
                order_dict = {
                    'Order_ID': order_details[0],
                    'FileMaker_Record_Number': order_details[1],
                    'PatientName': order_details[2],
                    'Patient_DOB': order_details[3],
                    'Patient_Zip': order_details[4],
                    'Order_Type': order_details[5],
                    'bundle_type': order_details[6],
                    'created_date': order_details[7],
                    'provider_id': order_details[8],
                    'provider_name': order_details[9]
                }
                
                # Map provider details
                provider_dict = {
                    'provider_name': provider_details[0] if provider_details else None,
                    'npi': provider_details[1] if provider_details else None,
                    'tin': provider_details[2] if provider_details else None,
                    'network_status': provider_details[3] if provider_details else None,
                    'provider_network': provider_details[4] if provider_details else None,
                    'billing_address_1': provider_details[5] if provider_details else None,
                    'billing_address_city': provider_details[6] if provider_details else None,
                    'billing_address_postal_code': provider_details[7] if provider_details else None,
                    'billing_address_state': provider_details[8] if provider_details else None,
                    'billing_name': provider_details[9] if provider_details else None
                }
                
                line_items_list = [{
                    'DOS': item[0],
                    'CPT': item[1],
                    'Modifier': item[2],
                    'Units': item[3],
                    'Description': item[4],
                    'Charge': item[5],
                    'BR_paid': item[6],
                    'BR_rate': item[7],
                    'EOBR_doc_no': item[8],
                    'HCFA_doc_no': item[9],
                    'BR_date_processed': item[10]
                } for item in line_items]
                
                return {
                    'order_details': order_dict,
                    'provider_details': provider_dict,
                    'line_items': line_items_list
                }
                
            except Exception as e:
                logger.error(f"Error getting full details for order {order_id}: {str(e)}")
                raise
                
            finally:
                # Close connection if we created it
                if should_close and conn:
                    conn.close()
                
        except Exception as e:
            logger.error(f"Database connection error while getting full details for order {order_id}: {str(e)}")
            raise
    
    @staticmethod
    def check_bundle(order_id: str, conn: sqlite3.Connection) -> bool:
        """
        Check if order is bundled.
        
        Args:
            order_id: Order ID to check
            conn: Database connection
            
        Returns:
            bool: True if the order is bundled, False otherwise
        """
        try:
            query = "SELECT bundle_type FROM orders WHERE Order_ID = ?"
            df = pd.read_sql_query(query, conn, params=[order_id])
            
            if df.empty:
                return False
                
            return pd.notna(df['bundle_type'].iloc[0]) and df['bundle_type'].iloc[0] != ''
        except Exception as e:
            logging.error(f"Error checking bundle for Order_ID {order_id}: {str(e)}")
            return False
    
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
            logger.error(f"Error getting procedure categories: {str(e)}")
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
            logger.error(f"Error getting PPO rates for TIN {provider_tin}: {str(e)}")
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
            logger.error(f"Error getting OTA rates for Order ID {order_id}: {str(e)}")
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
            logger.error(f"Error getting bundle info for Order ID {order_id}: {str(e)}")
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
            logger.error(f"Error saving validation result: {str(e)}")
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
            logger.error(f"Error getting ancillary codes: {str(e)}")
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
            logger.error(f"Error getting dim_proc table: {str(e)}")
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
            logger.error(f"Error getting validation failures: {str(e)}")
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
            logger.error(f"Error getting validation summary: {str(e)}")
            return {"total": 0, "by_status": {}, "by_validation_type": {}}
        finally:
            # Close connection if we created it
            if close_conn and conn:
                conn.close()

    def update_order_details(self, order_id: str, data: Dict) -> bool:
        """
        Update order details, provider details, and line items in the database.
        
        Args:
            order_id: Order ID to update
            data: Dictionary containing updated data
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            conn = self.connect_db()
            
            try:
                # Start a transaction
                conn.execute("BEGIN TRANSACTION")
                
                # Update order details
                if "order_details" in data:
                    order_updates = []
                    order_values = []
                    
                    # Get list of valid columns from the orders table
                    cursor = conn.execute("PRAGMA table_info(orders)")
                    valid_columns = [row[1] for row in cursor.fetchall()]
                    
                    for field, value in data["order_details"].items():
                        if field != "Order_ID" and field in valid_columns:  # Don't update the primary key and only update valid columns
                            order_updates.append(f"{field} = ?")
                            order_values.append(value)
                    
                    if order_updates:
                        order_query = f"""
                        UPDATE orders 
                        SET {', '.join(order_updates)}
                        WHERE Order_ID = ?
                        """
                        order_values.append(order_id)
                        conn.execute(order_query, order_values)
                
                # Update provider details if provider_id is present
                if "provider_details" in data and "provider_id" in data.get("order_details", {}):
                    provider_id = data["order_details"]["provider_id"]
                    provider_updates = []
                    provider_values = []
                    
                    # Get list of valid columns from the providers table
                    cursor = conn.execute("PRAGMA table_info(providers)")
                    valid_columns = [row[1] for row in cursor.fetchall()]
                    
                    for field, value in data["provider_details"].items():
                        # Map field names to database column names
                        db_field = field
                        if field == "provider_name":
                            db_field = "Name"
                        elif field == "network_status":
                            db_field = "Provider Status"
                        elif field == "provider_network":
                            db_field = "Provider Network"
                        
                        if db_field in valid_columns:  # Only update valid columns
                            provider_updates.append(f'"{db_field}" = ?')
                            provider_values.append(value)
                    
                    if provider_updates:
                        provider_query = f"""
                        UPDATE providers
                        SET {', '.join(provider_updates)}
                        WHERE PrimaryKey = ?
                        """
                        provider_values.append(provider_id)
                        conn.execute(provider_query, provider_values)
                
                # Update line items
                if "line_items" in data:
                    # Get list of valid columns from the line_items table
                    cursor = conn.execute("PRAGMA table_info(line_items)")
                    valid_columns = [row[1] for row in cursor.fetchall()]
                    
                    for item in data["line_items"]:
                        # Skip if no id is provided
                        if "id" not in item:
                            continue
                            
                        item_id = item["id"]
                        item_updates = []
                        item_values = []
                        
                        for field, value in item.items():
                            if field != "id" and field in valid_columns:  # Don't update the primary key and only update valid columns
                                item_updates.append(f"{field} = ?")
                                item_values.append(value)
                        
                        if item_updates:
                            item_query = f"""
                            UPDATE line_items
                            SET {', '.join(item_updates)}
                            WHERE id = ? AND Order_ID = ?
                            """
                            item_values.extend([item_id, order_id])
                            conn.execute(item_query, item_values)
                
                # Commit the transaction
                conn.commit()
                logger.info(f"Successfully updated database for Order ID: {order_id}")
                return True
                
            except Exception as e:
                # Rollback on error
                conn.rollback()
                logger.error(f"Error updating order details for {order_id}: {str(e)}")
                return False
                
            finally:
                conn.close()
                
        except Exception as e:
            logger.error(f"Database connection error while updating order {order_id}: {str(e)}")
            return False