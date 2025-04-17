import psycopg2
from typing import Dict, List, Optional
from core.services.arthrogram_utils import ArthrogramUtils

def identify_arthrograms():
    """Identify and update arthrogram orders in the database."""
    try:
        # Connect to database
        conn = psycopg2.connect(
            dbname="orders2",
            user="postgres",
            password="postgres",
            host="localhost"
        )
        
        with conn.cursor() as cursor:
            # Get all orders
            cursor.execute("""
                SELECT o.order_id, o.bundle_type, li.cpt_code
                FROM orders o
                LEFT JOIN line_items li ON o.order_id = li.order_id
                ORDER BY o.order_id
            """)
            
            current_order = None
            current_cpts = set()
            arthrogram_orders = set()
            
            # Process results
            for row in cursor.fetchall():
                order_id, bundle_type, cpt_code = row
                
                # New order
                if order_id != current_order:
                    if current_order:
                        # Check if previous order was an arthrogram
                        if ArthrogramUtils.check_line_items_for_arthrogram([
                            {'cpt_code': cpt} for cpt in current_cpts
                        ]):
                            arthrogram_orders.add(current_order)
                    
                    current_order = order_id
                    current_cpts = set()
                
                if cpt_code:
                    current_cpts.add(cpt_code)
            
            # Check last order
            if current_order and ArthrogramUtils.check_line_items_for_arthrogram([
                {'cpt_code': cpt} for cpt in current_cpts
            ]):
                arthrogram_orders.add(current_order)
            
            # Update arthrogram orders
            for order_id in arthrogram_orders:
                cursor.execute("""
                    UPDATE orders 
                    SET bundle_type = 'ARTHROGRAM'
                    WHERE order_id = %s
                """, (order_id,))
            
            conn.commit()
            print(f"Updated {len(arthrogram_orders)} orders to ARTHROGRAM")
            
    except Exception as e:
        print(f"Error identifying arthrograms: {str(e)}")
        raise
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    identify_arthrograms() 