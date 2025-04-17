from flask import Blueprint, render_template, jsonify, request, send_file, abort
from core.services.database import DatabaseService
from core.services.hcfa import HCFAService
import logging
import json
from pathlib import Path

# Set up logging
logger = logging.getLogger(__name__)

# Initialize services
db_service = DatabaseService()
hcfa_service = HCFAService()

# Create blueprint
processing_bp = Blueprint('processing', __name__)

@processing_bp.route('/')
def processing_home():
    """Render the processing home page."""
    return render_template('processing_home.html')

@processing_bp.route('/unauthorized')
def unauthorized_services():
    """Render the unauthorized services page."""
    return render_template('unauthorized.html')

@processing_bp.route('/non-global')
def non_global_bills():
    """Render the non-global bills page."""
    return render_template('non_global.html')

@processing_bp.route('/rate-corrections')
def rate_corrections():
    """Render the rate corrections page."""
    return render_template('rate_corrections.html')

@processing_bp.route('/ota')
def ota_review():
    """Render the OTA review page."""
    return render_template('ota.html')

@processing_bp.route('/api/pdf/<filename>')
def get_pdf(filename):
    """API endpoint to get a PDF file."""
    try:
        # Get the app config from current_app
        from flask import current_app
        pdf_path = Path(current_app.config['PDF_PATH']) / filename
        
        if not pdf_path.exists():
            logger.error(f"PDF file not found: {pdf_path}")
            return jsonify({
                'status': 'error',
                'message': f'File not found: {filename}'
            }), 404
            
        return send_file(
            pdf_path,
            mimetype='application/pdf',
            as_attachment=True,
            download_name=filename
        )
        
    except Exception as e:
        logger.error(f"Error getting PDF: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@processing_bp.route('/api/order/<order_id>')
def get_order_details(order_id):
    """API endpoint to get order details."""
    try:
        # Get order details from database
        order_details = db_service.get_full_details(order_id)
        
        if not order_details:
            logger.warning(f"No order details found for order ID: {order_id}")
            return jsonify({
                'status': 'error',
                'message': f'No details found for order ID: {order_id}'
            }), 404
            
        return jsonify({
            'status': 'success',
            'data': order_details
        })
        
    except Exception as e:
        logger.error(f"Error getting order details: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@processing_bp.route('/api/order/<order_id>', methods=['PUT'])
def update_order_details(order_id):
    """API endpoint to update order details."""
    try:
        # Get the updated data from the request
        updated_data = request.get_json()
        
        # Update order details in database
        db_service.update_order_details(order_id, updated_data)
        
        return jsonify({
            'status': 'success',
            'message': 'Order details updated successfully'
        })
        
    except Exception as e:
        logger.error(f"Error updating order details: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500 