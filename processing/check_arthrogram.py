import json
from pathlib import Path
from collections import defaultdict
from core.services.database import DatabaseService
from config.settings import settings
import shutil

def process_arthrogram_files():
    """Process files in staging directory, moving ARTHROGRAM files to arthrogram directory."""
    db_service = DatabaseService()
    
    # Create arthrogram directory if it doesn't exist
    arthrogram_path = Path(r"C:\Users\ChristopherCato\OneDrive - clarity-dx.com\Documents\Bill_Review_INTERNAL\scripts\VAILIDATION\data\extracts\valid\mapped\staging\arthrogram")
    arthrogram_path.mkdir(exist_ok=True, parents=True)
    print(f"ARTHROGRAM directory: {arthrogram_path}")
    
    # Get all JSON files in staging
    staging_files = list(settings.JSON_PATH.glob('*.json'))
    print(f"\nTotal files in staging directory: {len(staging_files)}")
    
    # Connect to database
    conn = db_service.connect_db()
    
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
                
                # Get order details from database
                order_details = db_service.get_full_details(order_id, conn)
                if not order_details:
                    bundle_counts['No DB Entry'] += 1
                    continue
                
                # Get bundle type
                bundle_type = order_details.get('order_details', {}).get('bundle_type')
                category = bundle_type if bundle_type else 'No Bundle Type'
                bundle_counts[category] += 1
                
                # If it's an ARTHROGRAM, move it
                if bundle_type == 'ARTHROGRAM':
                    target_path = arthrogram_path / file_path.name
                    shutil.move(str(file_path), str(target_path))
                    moved_files.append({
                        'file': file_path.name,
                        'order_id': order_id,
                        'target_path': str(target_path)
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
            print(f"Moved to: {move['target_path']}")
            print("-" * 30)
        print(f"\nTotal files moved: {len(moved_files)}")
    else:
        print("\nNo ARTHROGRAM files found to move.")

if __name__ == "__main__":
    process_arthrogram_files() 