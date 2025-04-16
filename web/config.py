"""
Configuration settings for the web application.
"""
from pathlib import Path

# Base paths
BASE_PATH = Path(r"C:\Users\ChristopherCato\OneDrive - clarity-dx.com\Documents\Bill_Review_INTERNAL")

# Database path
DB_PATH = BASE_PATH / r"reference_tables\orders2.db"

# Folder paths with meaningful names
FOLDERS = {
    # Unmapped Review App folders
    'UNMAPPED_FOLDER': BASE_PATH / r"scripts\VAILIDATION\data\extracts\valid\unmapped",
    'MAPPED_FOLDER': BASE_PATH / r"scripts\VAILIDATION\data\extracts\valid\mapped",
    
    # OCR Corrections App folders
    'FAILS_FOLDER': BASE_PATH / r"scripts\VAILIDATION\data\extracts\review",
    'OUTPUT_FOLDER': BASE_PATH / r"scripts\VAILIDATION\data\extracts\corrections",
    'ORIGINALS_FOLDER': BASE_PATH / r"scripts\VAILIDATION\data\extracts\review\archive",
    
    # Shared folders
    'PDF_FOLDER': BASE_PATH / r"scripts\VAILIDATION\data\pdf\archive",
}

# Application settings
DEBUG = True
SECRET_KEY = 'your-secret-key-here'  # Change this in production

# Fuzzy matching settings
FUZZY_MATCH_THRESHOLD = 75  # Minimum score for fuzzy matches (0-100)
DEFAULT_MONTHS_RANGE = 3    # Default month range for DOS searches
MAX_SEARCH_RESULTS = 50     # Maximum search results to display 