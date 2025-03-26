# core/config/settings.py
from pathlib import Path
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Base paths
BASE_DIR = Path(__file__).parent.parent.parent
DATA_DIR = Path(r"C:\Users\ChristopherCato\OneDrive - clarity-dx.com\Documents\Bill_Review_INTERNAL\scripts\VAILIDATION\data")

# Database settings
DB_PATH = Path(r"C:\Users\ChristopherCato\OneDrive - clarity-dx.com\Documents\Bill_Review_INTERNAL\reference_tables\orders2.db")

# File paths
JSON_DIR = DATA_DIR / "extracts" / "valid" / "mapped" / "staging"
SUCCESS_DIR = JSON_DIR / "success"
FAILS_DIR = JSON_DIR / "fails"

# Application settings
DEBUG = True
SECRET_KEY = 'your-secret-key-here'  # Change this in production

# Create settings object for easy access
settings = {
    'DB_PATH': DB_PATH,
    'FAILS_DIR': FAILS_DIR,
    'SUCCESS_DIR': SUCCESS_DIR,
    'DEBUG': DEBUG,
    'SECRET_KEY': SECRET_KEY
}

class Settings:
    """
    Configuration settings for the Healthcare Bill Review System 2.0.
    """
    
    # Paths
    JSON_PATH = JSON_DIR
    SUCCESS_PATH = SUCCESS_DIR
    FAILS_PATH = FAILS_DIR
    DB_PATH = DB_PATH
    LOG_PATH = Path(r"C:\Users\ChristopherCato\OneDrive - clarity-dx.com\Documents\Bill_Review_INTERNAL\validation logs")
    
    # Configuration files
    BUNDLE_CONFIG = BASE_DIR / "config" / "procedure_bundles.json"
    CLINICAL_EQUIV_CONFIG = BASE_DIR / "config" / "clinical_equivalents.json"
    PROVIDER_RULES_CONFIG = BASE_DIR / "config" / "provider_rules.json"
    
    # Validation constants
    UNACCEPTABLE_CPTS = {"51655"}
    INVALID_MODIFIERS = {"26", "TC"}
    
    # Validation strategy
    COMPLETE_VALIDATION = True  # Continue validating after failures for complete reporting
    BUNDLE_AWARE_VALIDATION = True  # Use enhanced bundle detection
    CLINICAL_INTENT_VALIDATION = True  # Use clinical intent detection
    
    # Rate validation configuration
    BUNDLE_RATES_ENABLED = True  # Enable bundle-specific rates
    DEFAULT_BUNDLE_RATE = 500.00  # Default rate for bundles without specific rates
    
    # Reporting options
    GENERATE_HTML_REPORT = True
    GENERATE_EXCEL_REPORT = True
    
    # System options
    DEBUG = DEBUG
    THREADS = 1  # Number of processing threads (1 = single-threaded)

# Database settings
DB_SERVER = os.getenv('DB_SERVER', 'your_server_name')
DB_NAME = os.getenv('DB_NAME', 'your_database')
DB_DRIVER = os.getenv('DB_DRIVER', 'SQL Server')

# Application settings
SECRET_KEY = SECRET_KEY

settings = Settings() 