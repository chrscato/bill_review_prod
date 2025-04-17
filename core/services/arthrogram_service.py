import json
from pathlib import Path
from collections import defaultdict
from core.services.database import DatabaseService
from config.settings import settings
import shutil
from core.services.arthrogram_utils import ArthrogramUtils

class ArthrogramService:
    """Service for handling ARTHROGRAM files."""
    
    def __init__(self):
        """Initialize the Arthrogram Service."""
        self.db_service = DatabaseService()
        self.arthrogram_path = settings.ARTHROGRAM_PATH
        self.arthrogram_path.mkdir(exist_ok=True, parents=True)
    
    def process_arthrogram_files(self) -> None:
        """Process files in staging directory, moving ARTHROGRAM files to arthrogram directory."""
        # Get all JSON files in staging
        staging_files = list(settings.JSON_PATH.glob('*.json'))
        print(f"\nTotal files in staging directory: {len(staging_files)}")
        
        # Connect to database
        conn = self.db_service.connect_db()
        
        # Track counts by bundle type
        bundle_counts = defaultdict(int)
        errors = 0
        moved_files = []
        
        try:
            for file_path in staging_files:
                try:
                    # Read JSON file
                    with open(file_path, 'r', encoding='utf-8') as f:
                        raw_data = json.load(f)
                    
                    # Get order ID (check both cases)
                    order_id = raw_data.get('Order_ID') or raw_data.get('order_id')
                    if not order_id:
                        bundle_counts['No Order_ID'] += 1
                        continue
                    
                    # Check if JSON contains arthrogram
                    is_json_arthrogram = ArthrogramUtils.check_json_for_arthrogram(raw_data)
                    
                    # Get order details from database
                    order_details = self.db_service.get_full_details(order_id, conn)
                    if not order_details:
                        bundle_counts['No DB Entry'] += 1
                        continue
                    
                    # Get bundle type
                    bundle_type = order_details.get('order_details', {}).get('bundle_type')
                    category = bundle_type if bundle_type else 'No Bundle Type'
                    bundle_counts[category] += 1
                    
                    # Determine if order is arthrogram
                    is_order_arthrogram = bundle_type == 'ARTHROGRAM'
                    
                    # Only process if it's an arthrogram (either from JSON or order)
                    if is_json_arthrogram or is_order_arthrogram:
                        # Add appropriate arthrogram note to JSON
                        if is_json_arthrogram and is_order_arthrogram:
                            raw_data['arthrogram_note'] = 'arthrogram_providerbill_and_order'
                        elif is_json_arthrogram:
                            raw_data['arthrogram_note'] = 'arthrogram_providerbill'
                        else:  # is_order_arthrogram
                            raw_data['arthrogram_note'] = 'arthrogram_order'
                        
                        # Save updated JSON
                        with open(file_path, 'w', encoding='utf-8') as f:
                            json.dump(raw_data, f, indent=4)
                        
                        # Move file to arthrogram directory
                        target_path = self.arthrogram_path / file_path.name
                        shutil.move(str(file_path), str(target_path))
                        moved_files.append({
                            'file': file_path.name,
                            'order_id': order_id,
                            'target_path': str(target_path),
                            'note': raw_data['arthrogram_note']
                        })
                    
                except Exception as e:
                    errors += 1
                    print(f"Error processing {file_path.name}: {str(e)}")
                    continue
        
        finally:
            conn.close()
        
        # Print summary
        print("\nBundle Type Summary:")
        print("-" * 50)
        for bundle_type, count in sorted(bundle_counts.items()):
            print(f"{bundle_type}: {count}")
        print(f"Errors: {errors}")
        print("-" * 50)
        
        # Print moved files summary
        if moved_files:
            print("\nMoved ARTHROGRAM files:")
            print("-" * 50)
            for move in moved_files:
                print(f"File: {move['file']}")
                print(f"Order ID: {move['order_id']}")
                print(f"Note: {move['note']}")
                print(f"Moved to: {move['target_path']}")
                print("-" * 30)
            print(f"\nTotal files moved: {len(moved_files)}")
        else:
            print("\nNo ARTHROGRAM files found to move.")
        
        return {
            'total_files': len(staging_files),
            'bundle_counts': dict(bundle_counts),
            'errors': errors,
            'moved_files': moved_files
        }
    
    def is_arthrogram(self, order_id: str, conn) -> bool:
        """Check if a given order_id is an ARTHROGRAM."""
        order_details = self.db_service.get_full_details(order_id, conn)
        if not order_details:
            return False
        return order_details.get('order_details', {}).get('bundle_type') == 'ARTHROGRAM'
    
    def move_to_arthrogram(self, file_path: Path, order_id: str) -> bool:
        """Move a single file to the arthrogram directory."""
        try:
            target_path = self.arthrogram_path / file_path.name
            shutil.move(str(file_path), str(target_path))
            return True
        except Exception as e:
            print(f"Error moving file {file_path.name}: {str(e)}")
            return False 