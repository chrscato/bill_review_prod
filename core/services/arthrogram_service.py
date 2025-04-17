from pathlib import Path
import json
import shutil
from typing import Dict, List, Optional
from core.services.database import DatabaseService
from core.services.arthrogram_utils import ArthrogramUtils
from core.settings import settings

class ArthrogramService:
    """Service for processing ARTHROGRAM files."""
    
    def __init__(self):
        self.db_service = DatabaseService()
        self.arthrogram_path = settings.ARTHROGRAM_PATH
        self.arthrogram_path.mkdir(exist_ok=True, parents=True)
    
    def process_arthrogram_files(self) -> Dict:
        """Process all files in staging directory for ARTHROGRAM identification."""
        bundle_counts = {}
        errors = []
        moved_files = []
        
        try:
            # Get all JSON files from staging
            staging_path = settings.STAGING_PATH
            json_files = list(staging_path.glob('*.json'))
            
            for file_path in json_files:
                try:
                    # Read JSON content
                    with open(file_path, 'r') as f:
                        raw_data = json.load(f)
                    
                    # Get order ID
                    order_id = raw_data.get('order_id')
                    if not order_id:
                        errors.append(f"Missing order_id in {file_path.name}")
                        continue
                    
                    # Check if JSON contains arthrogram codes
                    is_json_arthrogram = ArthrogramUtils.check_json_for_arthrogram(raw_data)
                    
                    # Get order details from database
                    with self.db_service.get_connection() as conn:
                        is_order_arthrogram = self.is_arthrogram(order_id, conn)
                    
                    # Add appropriate note to JSON
                    if is_json_arthrogram and is_order_arthrogram:
                        raw_data['arthrogram_note'] = 'arthrogram_providerbill_and_order'
                    elif is_json_arthrogram:
                        raw_data['arthrogram_note'] = 'arthrogram_providerbill'
                    elif is_order_arthrogram:
                        raw_data['arthrogram_note'] = 'arthrogram_order'
                    
                    # Save updated JSON
                    with open(file_path, 'w') as f:
                        json.dump(raw_data, f, indent=2)
                    
                    # Move file if it's an arthrogram
                    if is_json_arthrogram or is_order_arthrogram:
                        target_path = self.arthrogram_path / file_path.name
                        shutil.move(str(file_path), str(target_path))
                        moved_files.append({
                            'filename': file_path.name,
                            'order_id': order_id,
                            'note': raw_data['arthrogram_note'],
                            'target_path': str(target_path)
                        })
                    
                    # Track bundle type
                    bundle_type = raw_data.get('bundle_type', 'unknown')
                    bundle_counts[bundle_type] = bundle_counts.get(bundle_type, 0) + 1
                    
                except Exception as e:
                    errors.append(f"Error processing {file_path.name}: {str(e)}")
                    continue
            
            # Print summary
            print("\nArthrogram Processing Summary:")
            print(f"Total files processed: {len(json_files)}")
            print("\nBundle Types:")
            for bundle_type, count in bundle_counts.items():
                print(f"  {bundle_type}: {count}")
            print(f"\nErrors: {len(errors)}")
            if errors:
                print("\nError Details:")
                for error in errors:
                    print(f"  {error}")
            print("\nMoved Files:")
            for file_info in moved_files:
                print(f"  {file_info['filename']} (Order ID: {file_info['order_id']})")
                print(f"    Note: {file_info['note']}")
                print(f"    Moved to: {file_info['target_path']}")
            
            return {
                'total_files': len(json_files),
                'bundle_counts': bundle_counts,
                'errors': errors,
                'moved_files': moved_files
            }
            
        except Exception as e:
            print(f"Error in process_arthrogram_files: {str(e)}")
            raise
    
    def is_arthrogram(self, order_id: str, conn) -> bool:
        """Check if a given order_id is an ARTHROGRAM."""
        try:
            with conn.cursor() as cursor:
                cursor.execute("""
                    SELECT bundle_type 
                    FROM orders 
                    WHERE order_id = %s
                """, (order_id,))
                result = cursor.fetchone()
                return result and result[0] == 'ARTHROGRAM'
        except Exception as e:
            print(f"Error checking arthrogram status for order {order_id}: {str(e)}")
            return False
    
    def move_to_arthrogram(self, file_path: Path, order_id: str) -> bool:
        """Move a single file to the arthrogram directory."""
        try:
            target_path = self.arthrogram_path / file_path.name
            shutil.move(str(file_path), str(target_path))
            print(f"Moved {file_path.name} to arthrogram directory")
            return True
        except Exception as e:
            print(f"Error moving {file_path.name}: {str(e)}")
            return False 