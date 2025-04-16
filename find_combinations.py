import json
from pathlib import Path
from collections import defaultdict
from typing import Dict, List, Any
import pandas as pd
from datetime import datetime
from core.services.database import DatabaseService

class BillCombinationFinder:
    def __init__(self):
        self.staging_path = Path("data/extracts/valid/mapped/staging")
        self.db_service = DatabaseService()
        self.db_service.clear_cache()
        
    def load_json_files(self) -> List[Dict]:
        """Load all JSON files from staging directory"""
        json_files = []
        for json_file in self.staging_path.glob("*.json"):
            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    data['file_name'] = json_file.name
                    json_files.append(data)
            except Exception as e:
                print(f"Error loading {json_file}: {str(e)}")
        return json_files
    
    def group_by_order_id(self, files: List[Dict]) -> Dict[str, List[Dict]]:
        """Group files by Order_ID"""
        groups = defaultdict(list)
        for file in files:
            if 'Order_ID' in file:
                groups[file['Order_ID']].append(file)
        return groups
    
    def group_by_name_dos(self, files: List[Dict]) -> Dict[str, List[Dict]]:
        """Group files by patient name and date of service"""
        groups = defaultdict(list)
        for file in files:
            if 'patient_info' in file and 'service_lines' in file:
                name = file['patient_info'].get('patient_name', '').upper()
                # Get the first date of service from service lines
                dos = file['service_lines'][0]['date_of_service'] if file['service_lines'] else None
                if name and dos:
                    key = f"{name}_{dos}"
                    groups[key].append(file)
        return groups
    
    def get_service_line_summary(self, file: Dict) -> str:
        """Get a summary of service lines for comparison"""
        if 'service_lines' not in file:
            return ""
        return "|".join([
            f"{line['cpt_code']}({line.get('modifiers', [])})"
            for line in file['service_lines']
        ])
    
    def get_order_details(self, order_id: str) -> Dict:
        """Get order details from database"""
        try:
            with self.db_service.connect_db() as conn:
                provider_info = self.db_service.get_provider_details(order_id, conn)
                order_details = self.db_service.get_full_details(order_id, conn)
                order_lines = self.db_service.get_line_items(order_id, conn)
                return {
                    'provider_info': provider_info,
                    'order_details': order_details,
                    'order_lines': order_lines.to_dict('records') if not order_lines.empty else []
                }
        except Exception as e:
            print(f"Error getting order details for {order_id}: {str(e)}")
            return {}
    
    def find_potential_combinations(self):
        """Find potential bill combinations"""
        print("Loading JSON files...")
        files = self.load_json_files()
        
        print("\nGrouping by Order_ID...")
        order_id_groups = self.group_by_order_id(files)
        
        print("\nGrouping by Name and Date of Service...")
        name_dos_groups = self.group_by_name_dos(files)
        
        print("\nPotential Combinations:")
        print("=" * 80)
        
        # Check Order_ID groups
        for order_id, group in order_id_groups.items():
            if len(group) > 1:
                print(f"\nOrder_ID: {order_id}")
                print("-" * 40)
                for file in group:
                    print(f"File: {file['file_name']}")
                    print(f"Service Lines: {self.get_service_line_summary(file)}")
                    print(f"Total Charge: {file['billing_info']['total_charge']}")
                    print("-" * 20)
                
                # Get order details
                order_details = self.get_order_details(order_id)
                if order_details:
                    print("\nOrder Details from Database:")
                    print(f"Provider: {order_details.get('provider_info', {}).get('Billing Name', 'N/A')}")
                    print(f"Patient: {order_details.get('order_details', {}).get('order_details', {}).get('PatientName', 'N/A')}")
                    print("-" * 40)
        
        # Check Name + DOS groups
        for key, group in name_dos_groups.items():
            if len(group) > 1:
                name, dos = key.split('_')
                print(f"\nPatient: {name} | Date of Service: {dos}")
                print("-" * 40)
                for file in group:
                    print(f"File: {file['file_name']}")
                    print(f"Order_ID: {file.get('Order_ID', 'N/A')}")
                    print(f"Service Lines: {self.get_service_line_summary(file)}")
                    print(f"Total Charge: {file['billing_info']['total_charge']}")
                    print("-" * 20)
                
                # Get order details for each Order_ID
                for file in group:
                    if 'Order_ID' in file:
                        order_details = self.get_order_details(file['Order_ID'])
                        if order_details:
                            print(f"\nOrder Details for {file['Order_ID']}:")
                            print(f"Provider: {order_details.get('provider_info', {}).get('Billing Name', 'N/A')}")
                            print(f"Patient: {order_details.get('order_details', {}).get('order_details', {}).get('PatientName', 'N/A')}")
                            print("-" * 40)

if __name__ == "__main__":
    finder = BillCombinationFinder()
    finder.find_potential_combinations() 