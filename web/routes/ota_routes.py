from flask import Blueprint, jsonify, request
from core.services.ota_service import OTAService
import logging
from config.settings import settings

logger = logging.getLogger(__name__)

# Create blueprint for OTA routes
ota_bp = Blueprint('otas', __name__)

@ota_bp.route('/order/<order_id>', methods=['GET'])
def get_order_otas(order_id):
    """
    API endpoint to get all OTA rates for an order.
    """
    try:
        # Initialize the OTA service
        ota_service = OTAService(settings.DB_PATH)
        
        # Get OTA rates
        ota_rates = ota_service.get_order_otas(order_id)
        
        return jsonify({
            'status': 'success',
            'order_id': order_id,
            'ota_rates': ota_rates,
            'total_rates': len(ota_rates)
        })
    
    except Exception as e:
        logger.error(f"Error getting OTA rates: {e}")
        return jsonify({
            'status': 'error',
            'error': f"An unexpected error occurred: {str(e)}"
        }), 500

@ota_bp.route('/correct/line-items', methods=['POST'])
def correct_ota_rates():
    """
    API endpoint to update OTA rates for specific line items.
    
    Expected JSON payload:
    {
        "order_id": "ORD123456",
        "line_items": [
            {"cpt_code": "70553", "rate": 800.00, "modifier": ""},
            {"cpt_code": "73221", "rate": 600.00, "modifier": "TC"}
        ]
    }
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        order_id = data.get('order_id')
        line_items = data.get('line_items', [])
        
        if not order_id:
            return jsonify({'error': 'Order ID is required'}), 400
        
        if not line_items:
            return jsonify({'error': 'No line items provided'}), 400
        
        # Initialize the OTA service
        ota_service = OTAService(settings.DB_PATH)
        
        # Update OTA rates
        success, message, updated_items = ota_service.update_ota_rates(order_id, line_items)
        
        if success:
            return jsonify({
                'status': 'success',
                'message': message,
                'updated_items': updated_items
            })
        else:
            return jsonify({
                'status': 'error',
                'error': message
            }), 500
    
    except Exception as e:
        logger.error(f"Error in OTA rate correction: {e}")
        return jsonify({
            'status': 'error',
            'error': f"An unexpected error occurred: {str(e)}"
        }), 500 