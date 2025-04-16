#!/usr/bin/env python3
"""
Database Operations Module
Handles all database-related operations for provider outreach
"""

import logging
from pathlib import Path
from typing import Dict, Optional
import sqlite3

logger = logging.getLogger(__name__)

class DatabaseOperations:
    def __init__(self, db_path: str):
        """Initialize database connection"""
        self.db_path = Path(db_path)
        self.conn = None
        
    def connect(self) -> bool:
        """Establish database connection"""
        try:
            self.conn = sqlite3.connect(self.db_path)
            return True
        except Exception as e:
            logger.error(f"Database connection failed: {str(e)}")
            return False
            
    def disconnect(self):
        """Close database connection"""
        if self.conn:
            self.conn.close()
            
    def query_order_info(self, order_id: str) -> Optional[Dict]:
        """Query order and provider information from database"""
        if not self.conn:
            if not self.connect():
                return None
                
        try:
            cursor = self.conn.cursor()
            query = """
                SELECT
                    o.order_id,
                    o.FileMaker_Record_Number,
                    o.Patient_DOB,
                    o.PatientName,
                    o.Patient_Injury_Date,
                    p.[Billing Address 1],
                    p.[Billing Address 2],
                    p.[Billing Address City],
                    p.[Billing Address Postal Code],
                    p.[Billing Address State],
                    p.[Billing Name],
                    p.Email,
                    p.[Fax Number],
                    p.NPI,
                    p.TIN,
                    p.Website
                FROM orders o
                JOIN providers p
                ON o.provider_id = p.PrimaryKey
                WHERE o.order_id = ?
            """
            cursor.execute(query, (order_id,))
            row = cursor.fetchone()
            
            if row:
                # Convert row to dictionary
                columns = [description[0] for description in cursor.description]
                return dict(zip(columns, row))
            return None
            
        except Exception as e:
            logger.error(f"Error querying order info: {str(e)}")
            return None
            
    def query_denial_history(self, provider_tin: str) -> list:
        """Query denial history for a provider
        TODO: Implement if needed
        """
        return [] 