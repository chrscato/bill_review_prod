# config/settings.py
from pathlib import Path

class Settings:
    """
    Configuration settings for the Healthcare Bill Review System 2.0.
    """
    
    # Paths
    JSON_PATH = Path(r"C:\Users\ChristopherCato\OneDrive - clarity-dx.com\Documents\Bill_Review_INTERNAL\scripts\VAILIDATION\data\extracts\valid\mapped\staging")
    DB_PATH = Path(r"C:\Users\ChristopherCato\OneDrive - clarity-dx.com\Documents\Bill_Review_INTERNAL\reference_tables\orders2.db")
    LOG_PATH = Path(r"C:\Users\ChristopherCato\OneDrive - clarity-dx.com\Documents\Bill_Review_INTERNAL\validation logs")
    
    # Configuration files
    BUNDLE_CONFIG = Path(r"C:\Users\ChristopherCato\OneDrive - clarity-dx.com\Documents\Bill_Review_INTERNAL\scripts\VAILIDATION\BRsystem\config\procedure_bundles.json")
    CLINICAL_EQUIV_CONFIG = Path(r"C:\Users\ChristopherCato\OneDrive - clarity-dx.com\Documents\Bill_Review_INTERNAL\scripts\VAILIDATION\BRsystem\config\clinical_equivalents.json")
    PROVIDER_RULES_CONFIG = Path(r"C:\Users\ChristopherCato\OneDrive - clarity-dx.com\Documents\Bill_Review_INTERNAL\scripts\VAILIDATION\BRsystem\config\provider_rules.json")
    
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
    DEBUG = False  # Enable debug output
    THREADS = 1  # Number of processing threads (1 = single-threaded)

settings = Settings()