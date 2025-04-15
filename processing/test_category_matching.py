import pandas as pd
import sqlite3
from pathlib import Path
from core.validators.intent_validator import ClinicalIntentValidator
from core.services.rate_service import RateService
from core.services.database import DatabaseService
from core.config import settings

def test_category_matching():
    # Initialize services
    db_service = DatabaseService()
    intent_validator = ClinicalIntentValidator()
    rate_service = RateService(db_path=settings.DB_PATH)
    
    # Test CPT codes
    test_codes = [
        "74181",  # MRI Abdomen w/&w/o
        "72146",  # MRI Lumbar Spine w/&w/o
        "70553",  # MRI Brain w/&w/o
        "72156",  # MRI Cervical Spine w/&w/o
        "74177",  # CT Abdomen w/
        "70460",  # CT Head w/
        "73040",  # X-ray Arthrogram
        "20610",  # Therapeutic Injection
        "95910",  # EMG
        "A9503",  # Ancillary code
        "77002"   # Imaging guidance
    ]
    
    print("\nCategory Matching Test Results:")
    print("=" * 80)
    
    with db_service.connect_db() as conn:
        # Get dim_proc data
        dim_proc_df = pd.read_sql_query("SELECT * FROM dim_proc", conn)
        
        for code in test_codes:
            print(f"\nCPT Code: {code}")
            print("-" * 40)
            
            # Get clinical intent categories
            intent_categories = intent_validator.get_procedure_categories(code)
            print(f"Clinical Intent Categories: {intent_categories}")
            
            # Get rate categories
            rate_category = rate_service._get_category_for_code(code)
            print(f"Rate Category: {rate_category}")
            
            # Get dim_proc category
            dim_proc_match = dim_proc_df[dim_proc_df['proc_cd'] == code]
            if not dim_proc_match.empty:
                dim_proc_category = dim_proc_match['proc_category'].iloc[0]
                print(f"dim_proc Category: {dim_proc_category}")
            else:
                print("Not found in dim_proc")

if __name__ == "__main__":
    test_category_matching() 