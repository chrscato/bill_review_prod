#!/usr/bin/env python3
"""
CO-50 Denial Handler
This script handles CO-50 medical necessity denials by:
1. Processing JSON denial files
2. Finding corresponding PDFs
3. Querying database for additional information
4. Generating outreach documents
"""

import os
import json
import logging
from pathlib import Path
from typing import Dict, Optional
import pandas as pd
from ..utils.db_operations import DatabaseOperations
from ..utils.document_operations import DocumentOperations

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('co50_handler.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class CO50DenialHandler:
    def __init__(self):
        self.denials_path = Path(r"C:\Users\ChristopherCato\OneDrive - clarity-dx.com\Documents\Bill_Review_INTERNAL\scripts\VAILIDATION\data\extracts\valid\mapped\staging\denials")
        self.pdf_archive_path = Path(r"C:\Users\ChristopherCato\OneDrive - clarity-dx.com\Documents\Bill_Review_INTERNAL\scripts\VAILIDATION\data\pdf\archive")
        self.db_path = Path(r"C:\Users\ChristopherCato\OneDrive - clarity-dx.com\Documents\Bill_Review_INTERNAL\reference_tables\orders2.db")
        self.template_path = Path(__file__).parent.parent / "templates" / "co50_template.docx"
        
        # Initialize database and document operations
        self.db_ops = DatabaseOperations(self.db_path)
        self.doc_ops = DocumentOperations(self.template_path)
        
    def find_co50_denials(self) -> list:
        """Find all CO-50 denial JSON files"""
        co50_denials = []
        for json_file in self.denials_path.glob("*.json"):
            try:
                with open(json_file, 'r') as f:
                    data = json.load(f)
                    if data.get('denial_reason', '').lower() == 'medical necessity co-50':
                        co50_denials.append({
                            'json_path': json_file,
                            'data': data
                        })
            except Exception as e:
                logger.error(f"Error processing {json_file}: {str(e)}")
        return co50_denials
    
    def find_corresponding_pdf(self, json_data: Dict) -> Optional[Path]:
        """Find the corresponding PDF file for a denial"""
        # Extract base name from JSON data (assuming Order_ID is the base name)
        base_name = json_data.get('Order_ID')
        if not base_name:
            return None
            
        pdf_path = self.pdf_archive_path / f"{base_name}.pdf"
        if pdf_path.exists():
            return pdf_path
        return None
    
    def query_database(self, json_data: Dict) -> Dict:
        """Query database for additional information"""
        order_id = json_data.get('Order_ID')
        if not order_id:
            logger.error("No Order_ID found in JSON data")
            return {}
            
        return self.db_ops.query_order_info(order_id) or {}
    
    def generate_outreach_document(self, json_data: Dict, db_data: Dict, pdf_path: Path) -> bool:
        """Generate outreach document"""
        # Create output directory if it doesn't exist
        output_dir = Path(__file__).parent.parent / "output" / "co50"
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Generate document name
        order_id = json_data.get('Order_ID', 'unknown')
        doc_path = output_dir / f"{order_id}_outreach.docx"
        pdf_output_path = output_dir / f"{order_id}_combined.pdf"
        
        # Generate the document
        if not self.doc_ops.generate_outreach_document(json_data, db_data, doc_path):
            return False
            
        # Merge with original PDF
        return self.doc_ops.merge_pdfs(doc_path, pdf_path, pdf_output_path)
    
    def process_denials(self):
        """Main processing function"""
        co50_denials = self.find_co50_denials()
        logger.info(f"Found {len(co50_denials)} CO-50 denials")
        
        for denial in co50_denials:
            try:
                pdf_path = self.find_corresponding_pdf(denial['data'])
                if not pdf_path:
                    logger.warning(f"No PDF found for {denial['json_path']}")
                    continue
                    
                db_data = self.query_database(denial['data'])
                if not db_data:
                    logger.warning(f"No database data found for {denial['json_path']}")
                    continue
                    
                success = self.generate_outreach_document(denial['data'], db_data, pdf_path)
                
                if success:
                    logger.info(f"Successfully processed {denial['json_path']}")
                else:
                    logger.error(f"Failed to process {denial['json_path']}")
                    
            except Exception as e:
                logger.error(f"Error processing {denial['json_path']}: {str(e)}")
                
        # Clean up database connection
        self.db_ops.disconnect()

def main():
    handler = CO50DenialHandler()
    handler.process_denials()

if __name__ == "__main__":
    main() 