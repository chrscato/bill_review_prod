from flask import Flask, render_template, jsonify, request
from pathlib import Path
import json
from typing import List, Dict
import logging
from datetime import datetime
from core.services.database import DatabaseService
from core.services.hcfa import HCFAService
from contextlib import contextmanager
from config.settings import settings

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here'  # Change this in production

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize services
db_service = DatabaseService()
hcfa_service = HCFAService()

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

def get_failed_files() -> List[Dict]:
    """Get all failed validation files with their details."""
    fails_dir = settings.FAILS_PATH
    failed_files = []
    
    try:
        logger.info(f"Reading failed files from: {fails_dir}")
        for file_path in fails_dir.glob("*.json"):
            try:
                with open(file_path, 'r') as f:
                    data = json.load(f)
                    failed_files.append({
                        'filename': file_path.name,
                        'order_id': data.get('Order_ID', 'N/A'),
                        'patient_name': data.get('patient_info', {}).get('patient_name', 'N/A'),
                        'date_of_service': data.get('service_lines', [{}])[0].get('date_of_service', 'N/A'),
                        'validation_messages': data.get('validation_messages', []),
                        'last_modified': datetime.fromtimestamp(file_path.stat().st_mtime).strftime('%Y-%m-%d %H:%M:%S')
                    })
            except Exception as e:
                logger.error(f"Error reading file {file_path}: {str(e)}")
                continue
                
    except Exception as e:
        logger.error(f"Error accessing fails directory: {str(e)}")
        
    return failed_files

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
        order_id = hcfa_data['order_info']['order_id']
        if order_id != 'N/A':
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

if __name__ == '__main__':
    app.run(debug=True) 