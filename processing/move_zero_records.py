import os
import json
import logging
from pathlib import Path

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def delete_zero_records():
    """
    Delete files with FileMaker record numbers ending in 000000 from success folder.
    """
    # Define the absolute path to the success directory
    success_dir = Path(r"C:\Users\ChristopherCato\OneDrive - clarity-dx.com\Documents\Bill_Review_INTERNAL\scripts\VAILIDATION\data\extracts\valid\mapped\staging\success")
    
    # Counter for deleted files
    deleted_count = 0
    
    try:
        # Iterate through all JSON files in success directory
        for file_path in success_dir.glob("*.json"):
            try:
                # Read the JSON file
                with open(file_path, 'r') as f:
                    data = json.load(f)
                
                # Check if filemaker_number exists and ends with 000000
                record_number = data.get('filemaker_number', '')
                
                if record_number and str(record_number).endswith('000000'):
                    # Delete the file
                    os.remove(file_path)
                    deleted_count += 1
                    logger.info(f"Deleted {file_path.name} (Record #: {record_number})")
                
            except json.JSONDecodeError:
                logger.error(f"Error reading JSON file {file_path.name}")
            except Exception as e:
                logger.error(f"Error processing {file_path.name}: {str(e)}")
        
        logger.info(f"Completed deleting files. Total deleted: {deleted_count}")
        
    except Exception as e:
        logger.error(f"Error accessing directory: {str(e)}")

if __name__ == "__main__":
    delete_zero_records() 