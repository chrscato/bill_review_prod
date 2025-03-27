from flask import Blueprint, jsonify, request
from core.services.rate_service import RateService
import logging
from config import settings

logger = logging.getLogger(__name__)

# Create blueprint for rate routes
rate_bp = Blueprint('rates', __name__)

@rate_bp.route('/correct/line-items', methods=['POST'])
def correct_line_item_rates():
    """
    API endpoint to update rates for specific line items.
    
    Expected JSON payload:
    {
        "tin": "123456789",
        "line_items": [
            {"cpt_code": "70553", "rate": 800.00},
            {"cpt_code": "73221", "rate": 600.00}
        ]
    }
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        tin = data.get('tin')
        line_items = data.get('line_items', [])
        
        if not tin:
            return jsonify({'error': 'Provider TIN is required'}), 400
        
        if not line_items:
            return jsonify({'error': 'No line items provided'}), 400
        
        # Initialize the rate service
        rate_service = RateService(settings.DB_PATH)
        
        # Update rates
        success, message, updated_items = rate_service.update_line_item_rates(tin, line_items)
        
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
        logger.error(f"Error in line item rate correction: {e}")
        return jsonify({
            'status': 'error',
            'error': f"An unexpected error occurred: {str(e)}"
        }), 500

@rate_bp.route('/correct/category', methods=['POST'])
def correct_category_rates():
    """
    API endpoint to update rates by category.
    
    Expected JSON payload:
    {
        "tin": "123456789",
        "category_rates": {
            "MRI w/o": 800.00,
            "CT w/o": 600.00
        }
    }
    """
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        tin = data.get('tin')
        category_rates = data.get('category_rates', {})
        
        if not tin:
            return jsonify({'error': 'Provider TIN is required'}), 400
        
        if not category_rates:
            return jsonify({'error': 'No category rates provided'}), 400
        
        # Initialize the rate service
        rate_service = RateService(settings.DB_PATH)
        
        # Update rates
        success, message, updated_categories = rate_service.update_category_rates(tin, category_rates)
        
        if success:
            return jsonify({
                'status': 'success',
                'message': message,
                'updated_categories': updated_categories
            })
        else:
            return jsonify({
                'status': 'error',
                'error': message
            }), 500
    
    except Exception as e:
        logger.error(f"Error in category rate correction: {e}")
        return jsonify({
            'status': 'error',
            'error': f"An unexpected error occurred: {str(e)}"
        }), 500

@rate_bp.route('/provider/<tin>', methods=['GET'])
def get_provider_rates(tin):
    """Get existing rates for a provider."""
    try:
        # Initialize the rate service
        rate_service = RateService(settings.DB_PATH)
        
        # Get rates
        rates = rate_service.get_provider_rates(tin)
        provider_info = rate_service.get_provider_info(tin)
        
        return jsonify({
            'status': 'success',
            'provider': provider_info,
            'rates': rates,
            'total_rates': len(rates)
        })
    
    except Exception as e:
        logger.error(f"Error getting provider rates: {e}")
        return jsonify({
            'status': 'error',
            'error': f"An unexpected error occurred: {str(e)}"
        }), 500 