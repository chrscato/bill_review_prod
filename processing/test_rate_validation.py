from core.validators.rate_validator import RateValidator
from config import settings
import sqlite3

def test_specific_rate():
    tin = "59-1262719"
    cpt = "73200"
    
    try:
        with sqlite3.connect(settings.DB_PATH) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # Clean TIN - remove non-digits
            clean_tin = ''.join(c for c in tin if c.isdigit())
            
            print(f"\nValidation Details for TIN {tin} and CPT {cpt}:")
            print("=" * 50)
            
            # 1. Check if TIN exists in providers table
            cursor.execute("""
                SELECT "Name" as provider_name
                FROM providers
                WHERE TRIM(TIN) = ?
            """, (clean_tin,))
            provider = cursor.fetchone()
            if provider:
                print(f"\nProvider found: {provider['provider_name']}")
            else:
                print("\nProvider not found in providers table")
            
            # 2. Check PPO rate
            cursor.execute("""
                SELECT rate, proc_category, modifier, provider_name
                FROM ppo 
                WHERE TRIM(TIN) = ? AND proc_cd = ?
            """, (clean_tin, cpt))
            
            ppo_result = cursor.fetchone()
            if ppo_result:
                print(f"\nPPO Rate found:")
                print(f"  Rate: ${float(ppo_result['rate']):.2f}")
                print(f"  Category: {ppo_result['proc_category']}")
                print(f"  Modifier: {ppo_result['modifier'] if ppo_result['modifier'] else 'None'}")
                print(f"  Provider Name in PPO: {ppo_result['provider_name']}")
            else:
                print("\nNo PPO rate found")
            
            # 3. Check procedure category
            cursor.execute("""
                SELECT proc_category
                FROM dim_proc
                WHERE proc_cd = ?
            """, (cpt,))
            
            proc_category = cursor.fetchone()
            if proc_category:
                print(f"\nProcedure Category from dim_proc: {proc_category['proc_category']}")
                
                # 4. Check for equivalent codes in same category
                cursor.execute("""
                    SELECT p.proc_cd, p.rate, p.proc_category
                    FROM ppo p
                    JOIN dim_proc d ON p.proc_cd = d.proc_cd
                    WHERE TRIM(p.TIN) = ? 
                    AND d.proc_category = ?
                    AND p.proc_cd != ?
                """, (clean_tin, proc_category['proc_category'], cpt))
                
                equivalent_rates = cursor.fetchall()
                if equivalent_rates:
                    print("\nEquivalent codes in same category:")
                    for rate in equivalent_rates:
                        print(f"  CPT {rate['proc_cd']}: ${float(rate['rate']):.2f}")
            else:
                print("\nProcedure not found in dim_proc table")
            
            # 5. Check if there are any special conditions or modifiers
            cursor.execute("""
                SELECT DISTINCT modifier
                FROM ppo
                WHERE TRIM(TIN) = ? AND modifier IS NOT NULL AND modifier != ''
            """, (clean_tin,))
            
            modifiers = cursor.fetchall()
            if modifiers:
                print("\nProvider has rates with these modifiers:")
                for mod in modifiers:
                    print(f"  {mod['modifier']}")
            else:
                print("\nNo special modifiers found for this provider")
            
    except sqlite3.Error as e:
        print(f"Database error: {e}")

if __name__ == "__main__":
    test_specific_rate() 