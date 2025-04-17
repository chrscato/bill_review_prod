from flask import Blueprint, jsonify
from core.services.database import DatabaseService
import logging

# Set up logging
logger = logging.getLogger(__name__)

# Initialize services
db_service = DatabaseService()

# Create blueprint
order_bp = Blueprint('order', __name__)

@order_bp.route('/<order_id>')
def get_order(order_id):
    """Get order details by ID."""
    try:
        # Get order details from database
        order = db_service.get_full_details(order_id)
        
        if not order:
            return jsonify({
                'status': 'error',
                'message': f'Order {order_id} not found'
            }), 404
            
        return jsonify({
            'status': 'success',
            'data': order
        })
        
    except Exception as e:
        logger.error(f"Error getting order details: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500 