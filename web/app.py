from flask import Flask, render_template, jsonify, request, send_from_directory
from pathlib import Path
import json
from typing import List, Dict
import logging
from datetime import datetime
from core.services.database import DatabaseService
from core.services.hcfa import HCFAService
from contextlib import contextmanager
from config.settings import settings
from flask_cors import CORS
import os
from core.services.normalizer import normalize_hcfa_format
from web.routes.rate_routes import rate_bp  # Import the rate routes blueprint
from web.routes.ota_routes import ota_bp

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes
app.config['SECRET_KEY'] = 'your-secret-key-here'  # Change this in production

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize services
db_service = DatabaseService()
hcfa_service = HCFAService()

# Register blueprints
app.register_blueprint(rate_bp, url_prefix='/api/rates')
app.register_blueprint(ota_bp, url_prefix='/api/otas')

@contextmanager
def get_db_connection():
    """Context manager for database connections."""
    conn = None
    try:
        conn = db_service.connect_db()
        yield conn
    except Exception as e:
        logger.error(f"Database connection error: {str(e)}")
        raise
    finally:
        if conn:
            conn.close()

def get_failed_files():
    """Get all failed validation files with their details."""
    try:
        failed_files = []
        failed_dir = Path(settings.FAILED_DIR)
        
        # Define failure categories and their patterns
        failure_categories = {
            'RATE': ['rate validation failed', 'rate issue', 'rate problem'],
            'CPT': ['cpt validation failed', 'cpt code issue', 'invalid cpt'],
            'MODIFIER': ['modifier validation failed', 'modifier issue', 'invalid modifier'],
            'DIAGNOSIS': ['diagnosis validation failed', 'diagnosis code issue', 'invalid diagnosis'],
            'PROVIDER': ['provider validation failed', 'provider issue', 'invalid provider'],
            'PATIENT': ['patient validation failed', 'patient info issue', 'invalid patient'],
            'DATE': ['date validation failed', 'date issue', 'invalid date'],
            'AMOUNT': ['amount validation failed', 'amount issue', 'invalid amount'],
            'NETWORK': ['network validation failed', 'network issue', 'invalid network status']
        }
        
        for file_path in failed_dir.glob('*.json'):
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    
                # Extract failure types from validation messages
                failure_types = set()
                if 'validation_messages' in data:
                    for msg in data['validation_messages']:
                        msg_lower = msg.lower()
                        for category, patterns in failure_categories.items():
                            if any(pattern in msg_lower for pattern in patterns):
                                failure_types.add(category)
                
                # Add failure types to the data
                data['failure_types'] = list(failure_types)
                
                # Add file info
                data['filename'] = file_path.name
                data['order_id'] = data.get('Order_ID', '')
                
                failed_files.append(data)
                
            except Exception as e:
                logger.error(f"Error processing file {file_path}: {e}")
                continue
        
        # Sort by filename
        failed_files.sort(key=lambda x: x['filename'])
        
        return {
            'status': 'success',
            'data': failed_files
        }
        
    except Exception as e:
        logger.error(f"Error getting failed files: {e}")
        return {
            'status': 'error',
            'message': str(e)
        }

@app.route('/')
def index():
    """Render the main page."""
    return render_template('index.html')

@app.route('/api/failures')
def get_failures():
    """API endpoint to get all validation failures."""
    try:
        failed_files = hcfa_service.get_failed_files()
        return jsonify({
            'status': 'success',
            'data': failed_files
        })
    except Exception as e:
        logger.error(f"Error getting failures: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/api/failures/<filename>')
def get_failure_details(filename):
    """API endpoint to get detailed information for a specific failure."""
    try:
        logger.info(f"Fetching HCFA details for file: {filename}")
        hcfa_data = hcfa_service.get_hcfa_details(filename)
        
        if not hcfa_data:
            logger.warning(f"No HCFA details found for file: {filename}")
            return jsonify({
                'status': 'error',
                'message': f'No details found for file: {filename}'
            }), 404
            
        # Get database details if we have an order ID
        order_id = hcfa_data.get('Order_ID')
        if order_id and order_id != 'N/A':
            try:
                db_data = db_service.get_full_details(order_id)
                if db_data:
                    hcfa_data['database_details'] = db_data
            except Exception as e:
                logger.warning(f"Failed to get database details for order {order_id}: {str(e)}")
        
        logger.info(f"Successfully retrieved details for file: {filename}")
        return jsonify({
            'status': 'success',
            'data': hcfa_data
        })
        
    except Exception as e:
        logger.error(f"Error getting failure details: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/api/order/<order_id>')
def get_order_details(order_id):
    """API endpoint to get order details from the database."""
    try:
        logger.info(f"Fetching details for order: {order_id}")
        details = db_service.get_full_details(order_id)
        
        if not details:
            logger.warning(f"No details found for order: {order_id}")
            return jsonify({
                'status': 'error',
                'message': f'No details found for order: {order_id}'
            }), 404
            
        logger.info(f"Successfully retrieved details for order: {order_id}")
        return jsonify({
            'status': 'success',
            'data': details
        })
        
    except Exception as e:
        logger.error(f"Error getting order details: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/api/failures/<filename>', methods=['PUT'])
def update_failure_details(filename):
    """API endpoint to update HCFA file details."""
    try:
        logger.info(f"Updating HCFA details for file: {filename}")
        file_path = settings.FAILS_PATH / filename
        
        if not file_path.exists():
            logger.error(f"File not found: {file_path}")
            return jsonify({
                'status': 'error',
                'message': f'File not found: {filename}'
            }), 404
            
        # Get the updated data from the request
        updated_data = request.get_json()
        
        # Write the updated data back to the file
        with open(file_path, 'w') as f:
            json.dump(updated_data, f, indent=2)
            
        logger.info(f"Successfully updated file: {filename}")
        return jsonify({
            'status': 'success',
            'message': 'File updated successfully'
        })
        
    except Exception as e:
        logger.error(f"Error updating file: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/api/failures/<filename>/resolve', methods=['POST'])
def resolve_failure(filename):
    """API endpoint to mark a failure as resolved and move it back to staging."""
    try:
        logger.info(f"Resolving failure: {filename}")
        
        # Construct paths
        fails_path = settings.FAILS_PATH / filename
        staging_path = settings.JSON_PATH / filename
        
        if not fails_path.exists():
            logger.error(f"Failure file not found: {fails_path}")
            return jsonify({
                'status': 'error',
                'message': f'File not found: {filename}'
            }), 404
            
        # Read the failure file
        with open(fails_path, 'r') as f:
            data = json.load(f)
            
        # Remove validation messages
        if 'validation_messages' in data:
            del data['validation_messages']
            
        # Write the modified data to the staging directory
        with open(staging_path, 'w') as f:
            json.dump(data, f, indent=2)
            
        # Remove the file from the fails directory
        fails_path.unlink()
            
        logger.info(f"Successfully resolved failure: {filename}")
        return jsonify({
            'status': 'success',
            'message': 'Failure resolved successfully'
        })
        
    except Exception as e:
        logger.error(f"Error resolving failure: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/api/order/<order_id>', methods=['PUT'])
def update_order_details(order_id):
    """API endpoint to update order details in the database."""
    try:
        logger.info(f"Updating database details for order: {order_id}")
        updated_data = request.get_json()
        logger.info(f"Received update data: {json.dumps(updated_data, indent=2)}")
        
        success = db_service.update_order_details(order_id, updated_data)
        
        if not success:
            logger.error(f"Failed to update order: {order_id}")
            return jsonify({
                'status': 'error',
                'message': f'Failed to update order: {order_id}'
            }), 500
            
        logger.info(f"Successfully updated order: {order_id}")
        return jsonify({
            'status': 'success',
            'message': 'Order updated successfully'
        })
        
    except Exception as e:
        logger.error(f"Error updating order: {str(e)}", exc_info=True)
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

if __name__ == '__main__':
    app.run(debug=True) 