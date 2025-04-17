from flask import Blueprint, jsonify, request, abort
from core.services.database import DatabaseService
from core.services.hcfa import HCFAService
import logging
import json
from pathlib import Path
from datetime import datetime

# Set up logging
logger = logging.getLogger(__name__)

# Initialize services
db_service = DatabaseService()
hcfa_service = HCFAService()

# Create blueprint
escalation_bp = Blueprint('escalations', __name__)

@escalation_bp.route('/')
def get_escalations():
    """API endpoint to get all escalations."""
    try:
        # Get the app config from current_app
        from flask import current_app
        escalate_path = Path(current_app.config['ESCALATE_PATH'])
        
        if not escalate_path.exists():
            logger.error(f"Escalation directory not found: {escalate_path}")
            return jsonify({
                'status': 'error',
                'message': 'Escalation directory not found'
            }), 404
            
        # Get all escalation files
        escalation_files = []
        for file_path in escalate_path.glob('*.json'):
            try:
                with open(file_path, 'r') as f:
                    data = json.load(f)
                    data['filename'] = file_path.name
                    escalation_files.append(data)
            except Exception as e:
                logger.warning(f"Error reading escalation file {file_path}: {str(e)}")
                continue
        
        # Sort by date (most recent first)
        escalation_files.sort(key=lambda x: x.get('date_of_service', ''), reverse=True)
        
        return jsonify({
            'status': 'success',
            'data': escalation_files
        })
        
    except Exception as e:
        logger.error(f"Error getting escalations: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@escalation_bp.route('/<filename>')
def get_escalation(filename):
    """API endpoint to get detailed information for a specific escalation."""
    try:
        # Get the app config from current_app
        from flask import current_app
        file_path = Path(current_app.config['ESCALATE_PATH']) / filename
        
        if not file_path.exists():
            logger.error(f"Escalation file not found: {file_path}")
            return jsonify({
                'status': 'error',
                'message': f'File not found: {filename}'
            }), 404
            
        # Read the escalation file
        with open(file_path, 'r') as f:
            data = json.load(f)
            
        # Get database details if we have an order ID
        order_id = data.get('Order_ID')
        if order_id and order_id != 'N/A':
            try:
                db_data = db_service.get_full_details(order_id)
                if db_data:
                    data['database_details'] = db_data
            except Exception as e:
                logger.warning(f"Failed to get database details for order {order_id}: {str(e)}")
        
        return jsonify({
            'status': 'success',
            'data': data
        })
        
    except Exception as e:
        logger.error(f"Error getting escalation details: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@escalation_bp.route('/<filename>/resolve', methods=['POST'])
def resolve_escalation(filename):
    """API endpoint to resolve an escalation."""
    try:
        # Get the app config from current_app
        from flask import current_app
        
        # Construct paths
        escalate_path = Path(current_app.config['ESCALATE_PATH']) / filename
        staging_path = Path(current_app.config['JSON_PATH']) / filename
        
        if not escalate_path.exists():
            logger.error(f"Escalation file not found: {escalate_path}")
            return jsonify({
                'status': 'error',
                'message': f'File not found: {filename}'
            }), 404
            
        # Read the escalation file
        with open(escalate_path, 'r') as f:
            data = json.load(f)
            
        # Remove escalation-specific fields
        if 'escalation_reason' in data:
            del data['escalation_reason']
        if 'escalation_date' in data:
            del data['escalation_date']
            
        # Write the modified data to the staging directory
        with open(staging_path, 'w') as f:
            json.dump(data, f, indent=2)
            
        # Remove the file from the escalations directory
        escalate_path.unlink()
            
        return jsonify({
            'status': 'success',
            'message': 'Escalation resolved successfully'
        })
        
    except Exception as e:
        logger.error(f"Error resolving escalation: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@escalation_bp.route('/deny', methods=['POST'])
def deny_escalation():
    """API endpoint to deny an escalation request."""
    try:
        # Get the request data
        data = request.get_json()
        filename = data.get('filename')
        reason = data.get('reason')
        
        if not filename or not reason:
            return jsonify({
                'status': 'error',
                'message': 'Missing required fields: filename and reason'
            }), 400
            
        # Get the app config from current_app
        from flask import current_app
        
        # Construct paths
        escalate_path = Path(current_app.config['ESCALATE_PATH']) / filename
        fails_path = Path(current_app.config['FAILS_PATH']) / filename
        
        if not escalate_path.exists():
            logger.error(f"Escalation file not found: {escalate_path}")
            return jsonify({
                'status': 'error',
                'message': f'File not found: {filename}'
            }), 404
            
        # Read the escalation file
        with open(escalate_path, 'r') as f:
            data = json.load(f)
            
        # Add denial reason
        data['denial_reason'] = reason
        data['denial_date'] = datetime.now().isoformat()
            
        # Write the modified data to the fails directory
        with open(fails_path, 'w') as f:
            json.dump(data, f, indent=2)
            
        # Remove the file from the escalations directory
        escalate_path.unlink()
            
        return jsonify({
            'status': 'success',
            'message': 'Escalation denied successfully'
        })
        
    except Exception as e:
        logger.error(f"Error denying escalation: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500 