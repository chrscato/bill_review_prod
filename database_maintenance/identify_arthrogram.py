import logging
from pathlib import Path
from core.services.arthrogram_utils import ArthrogramUtils
from core.services.database import DatabaseService

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class ArthrogramIdentifier:
    def __init__(self, db_path: str):
        """
        Initialize the ArthrogramIdentifier with database path.
        
        Args:
            db_path: Path to the SQLite database
        """
        self.db_path = Path(db_path)
        if not self.db_path.exists():
            raise FileNotFoundError(f"Database not found at {db_path}")
        
    def process_orders(self) -> None:
        """
        Main method to process all orders and update arthrogram status.
        """
        conn = DatabaseService().connect_db()
        try:
            # Get all orders
            cursor = conn.cursor()
            cursor.execute("SELECT Order_ID FROM orders")
            order_ids = [row[0] for row in cursor.fetchall()]
            total_orders = len(order_ids)
            logger.info(f"Found {total_orders} orders to process")
            
            # Track statistics
            updated_count = 0
            already_arthrogram = 0
            
            # Process each order
            for i, order_id in enumerate(order_ids, 1):
                if i % 100 == 0:
                    logger.info(f"Processing order {i}/{total_orders}")
                
                # Check if order is already marked as arthrogram
                cursor.execute("""
                    SELECT bundle_type 
                    FROM orders 
                    WHERE Order_ID = ?
                """, (order_id,))
                result = cursor.fetchone()
                
                if result and result[0] == 'ARTHROGRAM':
                    already_arthrogram += 1
                    continue
                
                # Check if order contains arthrogram
                if ArthrogramUtils.check_db_order_for_arthrogram(order_id, conn):
                    if ArthrogramUtils.update_order_bundle_type(order_id, conn):
                        updated_count += 1
                        logger.info(f"Updated order {order_id} to ARTHROGRAM")
            
            # Print summary
            logger.info("\nProcessing Summary:")
            logger.info(f"Total orders processed: {total_orders}")
            logger.info(f"Orders already marked as ARTHROGRAM: {already_arthrogram}")
            logger.info(f"New orders updated to ARTHROGRAM: {updated_count}")
            
        except Exception as e:
            logger.error(f"Error processing orders: {str(e)}")
        finally:
            conn.close()

def main():
    # Database path - update this to your actual path
    db_path = r"C:\Users\ChristopherCato\OneDrive - clarity-dx.com\Documents\Bill_Review_INTERNAL\reference_tables\orders2.db"
    
    # Initialize the identifier
    identifier = ArthrogramIdentifier(db_path)
    
    # Process orders
    identifier.process_orders()

if __name__ == "__main__":
    main() 