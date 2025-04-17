import os
from pathlib import Path

class Config:
    """Base configuration."""
    SECRET_KEY = 'your-secret-key-here'
    DEBUG = False
    TESTING = False
    
    # Base paths
    BASE_DIR = Path(__file__).parent.parent
    DATA_DIR = Path(r"C:\Users\ChristopherCato\OneDrive - clarity-dx.com\Documents\Bill_Review_INTERNAL\scripts\VAILIDATION\data")
    
    # File paths
    JSON_DIR = DATA_DIR / "extracts" / "valid" / "mapped" / "staging"
    SUCCESS_DIR = JSON_DIR / "success"
    FAILS_DIR = JSON_DIR / "fails"
    ESCALATE_DIR = JSON_DIR / "escalations"
    PDF_DIR = JSON_DIR / "pdfs"
    
    # Process instructions data
    PROCESS_INSTRUCTIONS = {
        'unauthorized': {
            'title': 'Unauthorized Services',
            'steps': [
                'Review the service lines in the HCFA file',
                'Compare with the order details',
                'Identify any unauthorized services',
                'Update the HCFA file with correct services',
                'Resolve the failure'
            ]
        },
        'non-global': {
            'title': 'Non-Global Bills',
            'steps': [
                'Check for TC or 26 modifiers',
                'Verify if the service is global or component',
                'Update the HCFA file accordingly',
                'Resolve the failure'
            ]
        },
        'rate': {
            'title': 'Rate Corrections',
            'steps': [
                'Review the rate in the HCFA file',
                'Check the provider network status',
                'Verify the correct rate for the service',
                'Update the HCFA file with the correct rate',
                'Resolve the failure'
            ]
        },
        'ota': {
            'title': 'OTA Review',
            'steps': [
                'Review the OTA details',
                'Verify the service codes',
                'Update the HCFA file if needed',
                'Resolve the failure'
            ]
        }
    }

class DevelopmentConfig(Config):
    """Development configuration."""
    DEBUG = True
    
class ProductionConfig(Config):
    """Production configuration."""
    # Override settings as needed for production
    pass

class TestingConfig(Config):
    """Testing configuration."""
    TESTING = True
    # Use test-specific paths

# Dictionary of configurations
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}

def get_config(config_name=None):
    """Get the config class based on the environment."""
    if not config_name:
        config_name = os.environ.get('FLASK_ENV', 'default')
    return config.get(config_name, config['default']) 