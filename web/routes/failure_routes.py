from flask import Blueprint, jsonify, request, send_file, abort
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
failure_bp = Blueprint('failures', __name__)

@failure_bp.route('/')
def get_failures():
    """API endpoint to get all validation failures with filtering options."""
    try:
        # Get query parameters
        filter_type = request.args.get('filter', 'all')
        
        # Get all failures first
        failed_files = hcfa_service.get_failed_files()
        
        # Apply filtering based on type
        if filter_type == 'unauthorized':
            # Filter for unauthorized services (line item mismatches)
            failed_files = [f for f in failed_files if _is_unauthorized_service(f)]
        elif filter_type == 'component':
            # Filter for non-global bills (TC/26 modifiers)
            failed_files = [f for f in failed_files if _has_component_modifiers(f)]
        elif filter_type == 'rate':
            # Filter for rate issues (both in-network and out-of-network)
            failed_files = [f for f in failed_files if _has_rate_issue(f)]
        
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

@failure_bp.route('/<filename>')
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

@failure_bp.route('/<filename>', methods=['PUT'])
def update_failure_details(filename):
    """API endpoint to update HCFA file details."""
    try:
        logger.info(f"Updating HCFA details for file: {filename}")
        # Get the app config from current_app
        from flask import current_app
        file_path = Path(current_app.config['FAILS_PATH']) / filename
        
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

@failure_bp.route('/<filename>/resolve', methods=['POST'])
def resolve_failure(filename):
    """API endpoint to mark a failure as resolved and move it back to staging."""
    try:
        logger.info(f"Resolving failure: {filename}")
        
        # Get the app config from current_app
        from flask import current_app
        
        # Construct paths
        fails_path = Path(current_app.config['FAILS_PATH']) / filename
        staging_path = Path(current_app.config['JSON_PATH']) / filename
        
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

# Helper functions
def _is_unauthorized_service(failure):
    """Check if failure is due to unauthorized services."""
    # Look for LINE_ITEMS validation failures
    if 'validation_messages' in failure:
        for message in failure['validation_messages']:
            if ('LINE_ITEMS' in message and 'Validation Failed' in message) or \
               ('missing from order' in message.lower()):
                return True
    
    # Check failure types
    if 'failure_types' in failure and 'LINE_ITEMS' in failure['failure_types']:
        return True
    
    return False

def _has_component_modifiers(failure):
    """Check if failure contains TC or 26 modifiers."""
    # Check service lines for TC or 26 modifiers
    if 'service_lines' in failure:
        for line in failure['service_lines']:
            if isinstance(line.get('modifiers'), list):
                if 'TC' in line['modifiers'] or '26' in line['modifiers']:
                    return True
            elif isinstance(line.get('modifiers'), str):
                if 'TC' in line['modifiers'] or '26' in line['modifiers']:
                    return True
    
    # Check validation messages
    if 'validation_messages' in failure:
        for message in failure['validation_messages']:
            if 'technical component' in message.lower() or \
               'professional component' in message.lower() or \
               'modifier TC' in message or \
               'modifier 26' in message:
                return True
                
    return False

def _has_rate_issue(failure):
    """Check if failure has any rate-related issues."""
    # Look for RATE validation failures in messages
    if 'validation_messages' in failure:
        for message in failure['validation_messages']:
            if ('RATE' in message and 'Validation Failed' in message) or \
               'rate validation failed' in message.lower() or \
               'rate issue' in message.lower() or \
               'no rate found' in message.lower() or \
               'missing rate' in message.lower():
                return True
    
    # Check failure types
    if 'failure_types' in failure and 'RATE' in failure['failure_types']:
        return True
    
    return False 