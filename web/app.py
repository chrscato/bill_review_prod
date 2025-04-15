from flask import Flask, render_template, jsonify, request, send_from_directory, send_file, abort, redirect, url_for
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
from werkzeug.middleware.proxy_fix import ProxyFix  # Add this import
from web.routes.mapping_routes import mapping_bp

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes
app.config['SECRET_KEY'] = 'your-secret-key-here'  # Change this in production
app.wsgi_app = ProxyFix(app.wsgi_app)  # Add this line for proper URL handling

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize services
db_service = DatabaseService()
hcfa_service = HCFAService()

# Register blueprints
app.register_blueprint(rate_bp, url_prefix='/api/rates')
app.register_blueprint(ota_bp, url_prefix='/api/otas')
app.register_blueprint(mapping_bp, url_prefix='/mapping')

# Configure paths
app.config['JSON_PATH'] = r"C:\Users\ChristopherCato\OneDrive - clarity-dx.com\Documents\Bill_Review_INTERNAL\scripts\VAILIDATION\data\extracts\valid\mapped\staging"
app.config['SUCCESS_PATH'] = r"C:\Users\ChristopherCato\OneDrive - clarity-dx.com\Documents\Bill_Review_INTERNAL\scripts\VAILIDATION\data\extracts\valid\mapped\staging\success"
app.config['FAILS_PATH'] = r"C:\Users\ChristopherCato\OneDrive - clarity-dx.com\Documents\Bill_Review_INTERNAL\scripts\VAILIDATION\data\extracts\valid\mapped\staging\fails"
app.config['ESCALATE_PATH'] = r"C:\Users\ChristopherCato\OneDrive - clarity-dx.com\Documents\Bill_Review_INTERNAL\scripts\VAILIDATION\data\extracts\valid\mapped\staging\escalations"

# Process instructions data
PROCESS_INSTRUCTIONS = {
    'ota': {
        'title': 'OTA Corrections Process',
        'steps': [
            {
                'title': 'Click "OON Add OTA Rates" Button',
                'description': 'Locate and click the orange "OON Add OTA Rates" button in the bill details panel.',
                'alerts': [
                    {
                        'type': 'warning',
                        'icon': 'exclamation-triangle',
                        'text': 'This button is only available for out-of-network providers.'
                    }
                ]
            },
            {
                'title': 'Verify Non-Global Status',
                'description': 'Confirm that the bill is non-global by checking the service lines for TC or 26 modifiers.',
                'alerts': [
                    {
                        'type': 'danger',
                        'icon': 'x-circle',
                        'text': 'If the bill is non-global:\n1. Click the "Escalate Bill" button\n2. Add note: "Non-global bill - requires manual review"'
                    }
                ]
            },
            {
                'title': 'Check FileMaker for OTA Attachment',
                'description': 'Search for the OTA attachment in FileMaker using the order details provided.',
                'alerts': [
                    {
                        'type': 'info',
                        'icon': 'info-circle',
                        'text': 'Look for attachments in the order record.'
                    }
                ]
            },
            {
                'title': 'Check OneDrive Link',
                'description': 'Access the OneDrive link to search for the OTA document:',
                'alerts': [
                    {
                        'type': 'info',
                        'icon': 'link-45deg',
                        'text': 'OTA Documents OneDrive Folder',
                        'link': 'https://netorgft5472802-my.sharepoint.com/:f:/g/personal/kim_vileno_clarity-dx_com/ErDODDCwxSBKnWn02Ni8ZB0B5hSLxpPEgPz9BQixbUKusA?e=eH8wNR'
                    }
                ]
            },
            {
                'title': 'Check for Percentage-Based WCFS Rate',
                'description': 'If OTA document is found, check if it specifies a percentage of WCFS rate:',
                'alerts': [
                    {
                        'type': 'danger',
                        'icon': 'x-circle',
                        'text': 'If the OTA document specifies a percentage of WCFS rate:\n1. Click the "Escalate Bill" button\n2. Add note: "OTA document found with percentage-based WCFS rate: [X]%"'
                    }
                ]
            },
            {
                'title': 'Escalate if Not Found',
                'description': 'If the OTA document cannot be found in either FileMaker or OneDrive:',
                'alerts': [
                    {
                        'type': 'danger',
                        'icon': 'x-circle',
                        'text': '1. Click the "Escalate Bill" button\n2. Add note: "Unable to find OTA document in FileMaker or OneDrive"'
                    }
                ]
            }
        ]
    },
    'inn': {
        'title': 'INN Rate Corrections Process',
        'steps': [
            {
                'title': 'Lookup Provider in FileMaker',
                'description': 'Search for the provider using either:',
                'alerts': [
                    {
                        'type': 'info',
                        'icon': 'info-circle',
                        'text': '• TIN from the FileMaker order\n• DBA name listed with the FileMaker order'
                    }
                ]
            },
            {
                'title': 'Locate Contract Attachment',
                'description': 'Navigate to the attachments section and look for the contract document.',
                'alerts': [
                    {
                        'type': 'info',
                        'icon': 'link-45deg',
                        'text': 'Alternative: Search in Providers SharePoint Folder',
                        'link': 'https://netorgft5472802.sharepoint.com/sites/Providers'
                    }
                ]
            },
            {
                'title': 'Check Exhibit A for Rates',
                'description': 'In the contract, locate Exhibit A to find the rate information.',
                'alerts': [
                    {
                        'type': 'warning',
                        'icon': 'exclamation-triangle',
                        'text': 'Pay special attention to the rate structure type.'
                    }
                ]
            },
            {
                'title': 'Determine Rate Type',
                'description': 'Based on the contract terms:',
                'alerts': [
                    {
                        'type': 'success',
                        'icon': 'check-circle',
                        'text': 'If explicit dollar amounts for procedure categories:\n1. Make category corrections as needed\n2. Update rates according to contract amounts'
                    },
                    {
                        'type': 'danger',
                        'icon': 'x-circle',
                        'text': 'If percentage of WCFS:\n1. Click the "Escalate Bill" button\n2. Add note: "Percentage-based contract - requires manual calculation"'
                    }
                ]
            }
        ]
    }
}

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
    """Redirect to the portal home page."""
    return redirect(url_for('portal_home'))

@app.route('/portal')
def portal_home():
    """Render the main portal home page."""
    return render_template('portal_home.html')

@app.route('/mapping')
def mapping_home():
    """Render the mapping home page."""
    return render_template('mapping_home.html')

@app.route('/processing')
def processing_home():
    """Render the processing home page."""
    return render_template('processing_home.html')

@app.route('/escalations')
def escalations():
    """Render the escalations page."""
    return render_template('escalations.html')

@app.route('/unauthorized')
def unauthorized_services():
    """Render the unauthorized services page."""
    return render_template('unauthorized.html')

@app.route('/non-global')
def non_global_bills():
    """Render the non-global bills page."""
    return render_template('non_global.html')

@app.route('/rate-corrections')
def rate_corrections():
    """Render the rate corrections page."""
    return render_template('rate_corrections.html')

@app.route('/ota')
def ota_review():
    """Render the OTA review page."""
    return render_template('ota.html')

@app.route('/instructions')
def instructions():
    return render_template('instructions.html')

@app.route('/instructions/<process>')
def process_detail(process):
    if process not in PROCESS_INSTRUCTIONS:
        abort(404)
    return render_template('process_detail.html', 
                         process_title=PROCESS_INSTRUCTIONS[process]['title'],
                         steps=PROCESS_INSTRUCTIONS[process]['steps'])

@app.route('/api/failures')
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

@app.route('/dashboard')
def dashboard():
    """Render the dashboard page."""
    return render_template('dashboard.html')

@app.route('/api/dashboard')
def get_dashboard_data():
    """API endpoint to get dashboard data."""
    try:
        # Get all failures
        failures = hcfa_service.get_failed_files()
        
        # Count failures by type
        failure_counts = {
            'rate': 0,
            'unauthorized': 0,
            'component': 0,
            'intent': 0,
            'cpt': 0,
            'other': 0
        }
        
        network_status = {
            'In-Network': 0,
            'Out-of-Network': 0,
            'Unknown': 0
        }
        
        # Detailed breakdown by subcategory
        breakdown = {
            'rate': {},
            'unauthorized': {},
            'component': {},
            'cpt': {}
        }
        
        # Process each failure
        for failure in failures:
            # Determine failure type
            failure_type = 'other'
            
            # Check validation messages
            validation_messages = failure.get('validation_messages', [])
            messages_text = ' '.join(validation_messages).lower()
            
            # Check for CPT validation failures first
            if 'unknown cpt' in messages_text or 'cpt validation failed' in messages_text:
                failure_type = 'cpt'
                breakdown['cpt']['Unknown CPT'] = breakdown['cpt'].get('Unknown CPT', 0) + 1
                
            # Check for rate validation failures
            elif 'rate validation failed' in messages_text or 'rate issue' in messages_text:
                failure_type = 'rate'
                
                # Add to rate breakdown
                if 'missing rate' in messages_text:
                    breakdown['rate']['Missing Rate'] = breakdown['rate'].get('Missing Rate', 0) + 1
                elif 'incorrect rate' in messages_text:
                    breakdown['rate']['Incorrect Rate'] = breakdown['rate'].get('Incorrect Rate', 0) + 1
                else:
                    breakdown['rate']['Other Rate Issue'] = breakdown['rate'].get('Other Rate Issue', 0) + 1
                
            # Check for unauthorized services
            elif 'line_items validation failed' in messages_text or 'missing from order' in messages_text:
                failure_type = 'unauthorized'
                
                # Add to unauthorized breakdown
                if 'missing cpt codes' in messages_text:
                    breakdown['unauthorized']['Missing CPT'] = breakdown['unauthorized'].get('Missing CPT', 0) + 1
                elif 'unauthorized service' in messages_text:
                    breakdown['unauthorized']['Unauthorized Service'] = breakdown['unauthorized'].get('Unauthorized Service', 0) + 1
                else:
                    breakdown['unauthorized']['Other Line Item Issue'] = breakdown['unauthorized'].get('Other Line Item Issue', 0) + 1
                
            # Check for component billing
            elif 'technical component' in messages_text or 'professional component' in messages_text:
                failure_type = 'component'
                
                # Add to component breakdown
                if 'technical component' in messages_text:
                    breakdown['component']['Technical Component (TC)'] = breakdown['component'].get('Technical Component (TC)', 0) + 1
                elif 'professional component' in messages_text:
                    breakdown['component']['Professional Component (26)'] = breakdown['component'].get('Professional Component (26)', 0) + 1
                else:
                    breakdown['component']['Other Component Issue'] = breakdown['component'].get('Other Component Issue', 0) + 1
                
            # Check for clinical intent issues
            elif 'intent validation failed' in messages_text or 'clinical intent' in messages_text:
                failure_type = 'intent'
            
            # Count by failure type
            failure_counts[failure_type] = failure_counts.get(failure_type, 0) + 1
            
            # Count by network status
            provider_network = None
            if failure.get('database_details') and failure.get('database_details').get('provider_details'):
                provider_network = failure['database_details']['provider_details'].get('provider_network')
            
            if provider_network:
                if 'in network' in provider_network.lower() or 'in-network' in provider_network.lower():
                    network_status['In-Network'] += 1
                elif 'out of network' in provider_network.lower() or 'out-of-network' in provider_network.lower():
                    network_status['Out-of-Network'] += 1
                else:
                    network_status['Unknown'] += 1
            else:
                network_status['Unknown'] += 1
            
            # Add failure type to the failure object for the recent failures list
            failure['failure_type'] = failure_type
        
        # Get recent failures (last 10)
        recent_failures = []
        for failure in failures[:10]:
            recent_failures.append({
                'filename': failure.get('filename'),
                'order_id': failure.get('order_id'),
                'patient_name': failure.get('patient_name'),
                'date': failure.get('date_of_service'),
                'failure_type': failure.get('failure_type', 'other'),
                'validation_messages': failure.get('validation_messages', [])
            })
        
        # Remove empty categories from breakdown
        for category in list(breakdown.keys()):
            if not breakdown[category]:
                del breakdown[category]
        
        # Return dashboard data
        return jsonify({
            'status': 'success',
            'data': {
                'total_failures': len(failures),
                'failure_counts': failure_counts,
                'network_status': network_status,
                'recent_failures': recent_failures,
                'breakdown': breakdown
            }
        })
        
    except Exception as e:
        logger.error(f"Error getting dashboard data: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/api/pdf/<filename>')
def get_pdf(filename):
    """API endpoint to serve original PDF files associated with validation failures."""
    try:
        # Security check: Prevent directory traversal
        if '..' in filename or '/' in filename or '\\' in filename:
            logger.error(f"Invalid filename requested: {filename}")
            abort(404)
            
        # Convert JSON filename to PDF filename if needed
        if filename.endswith('.json'):
            pdf_filename = filename[:-5] + '.pdf'
        else:
            pdf_filename = filename + '.pdf'
            
        pdf_path = os.path.join(settings.PDF_ARCHIVE_PATH, pdf_filename)
        
        # Check if file exists
        if not os.path.isfile(pdf_path):
            logger.error(f"PDF file not found: {pdf_path}")
            return jsonify({
                'status': 'error',
                'message': 'PDF file not found'
            }), 404
            
        # Serve the file
        return send_file(pdf_path, mimetype='application/pdf')
    
    except Exception as e:
        logger.error(f"Error serving PDF file: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/api/failures/<filename>/escalate', methods=['POST'])
def escalate_failure(filename):
    try:
        # Get the message from the request body
        data = request.get_json()
        message = data.get('message', '') if data else ''
        
        # Check if the failure file exists
        failure_path = os.path.join(app.config['FAILS_PATH'], filename)
        if not os.path.exists(failure_path):
            return jsonify({'success': False, 'error': f'Failure file {filename} not found'}), 404

        # Read the failure file
        with open(failure_path, 'r') as f:
            failure_data = json.load(f)

        # Add escalation timestamp and message
        failure_data['escalated_at'] = datetime.now().isoformat()
        if message:
            failure_data['escalation_message'] = message

        # Write to escalate directory
        escalate_path = os.path.join(app.config['ESCALATE_PATH'], filename)
        os.makedirs(os.path.dirname(escalate_path), exist_ok=True)
        with open(escalate_path, 'w') as f:
            json.dump(failure_data, f, indent=4)

        # Remove from fails directory
        os.remove(failure_path)

        logger.info(f"Escalated failure: {filename}")
        if message:
            logger.info(f"Escalation message: {message}")
        return jsonify({'success': True})

    except Exception as e:
        logger.error(f"Error escalating failure {filename}: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/escalations')
def get_escalations():
    """API endpoint to get all escalated files with filtering options."""
    try:
        # Get query parameters
        filter_type = request.args.get('filter', 'all')
        
        # Get all escalated files
        escalated_files = []
        escalation_dir = Path(app.config['ESCALATE_PATH'])
        
        for file_path in escalation_dir.glob('*.json'):
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    
                # Add file info
                data['filename'] = file_path.name
                data['order_id'] = data.get('Order_ID', '')
                
                escalated_files.append(data)
                
            except Exception as e:
                logger.error(f"Error processing escalated file {file_path}: {e}")
                continue
        
        # Apply filtering based on type (same as normal failures)
        if filter_type == 'unauthorized':
            escalated_files = [f for f in escalated_files if _is_unauthorized_service(f)]
        elif filter_type == 'component':
            escalated_files = [f for f in escalated_files if _has_component_modifiers(f)]
        elif filter_type == 'rate':
            escalated_files = [f for f in escalated_files if _has_rate_issue(f)]
        
        # Sort by escalation date (newest first)
        escalated_files.sort(key=lambda x: x.get('escalated_at', ''), reverse=True)
        
        return jsonify({
            'status': 'success',
            'data': escalated_files
        })
    except Exception as e:
        logger.error(f"Error getting escalations: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/api/escalations/<filename>/resolve', methods=['POST'])
def resolve_escalation(filename):
    """API endpoint to mark an escalated bill as resolved and move it back to staging."""
    try:
        logger.info(f"Resolving escalated bill: {filename}")
        
        # Construct paths
        escalation_path = os.path.join(app.config['ESCALATE_PATH'], filename)
        staging_path = os.path.join(app.config['JSON_PATH'], filename)
        
        if not os.path.exists(escalation_path):
            logger.error(f"Escalated file not found: {escalation_path}")
            return jsonify({
                'status': 'error',
                'message': f'File not found: {filename}'
            }), 404
            
        # Read the escalated file
        with open(escalation_path, 'r') as f:
            data = json.load(f)
            
        # Remove escalation-specific fields
        if 'escalated_at' in data:
            del data['escalated_at']
        if 'escalation_message' in data:
            del data['escalation_message']
            
        # Remove validation messages to treat as resolved
        if 'validation_messages' in data:
            del data['validation_messages']
            
        # Write the modified data to the staging directory
        with open(staging_path, 'w') as f:
            json.dump(data, f, indent=2)
            
        # Remove the file from the escalations directory
        os.remove(escalation_path)
            
        logger.info(f"Successfully resolved escalated bill: {filename}")
        return jsonify({
            'status': 'success',
            'message': 'Escalated bill resolved successfully'
        })
        
    except Exception as e:
        logger.error(f"Error resolving escalated bill: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@app.route('/api/escalations/<filename>')
def get_escalation(filename):
    """API endpoint to get a specific escalated file."""
    try:
        escalation_path = os.path.join(app.config['ESCALATE_PATH'], filename)
        
        if not os.path.exists(escalation_path):
            logger.error(f"Escalated file not found: {escalation_path}")
            return jsonify({
                'status': 'error',
                'message': f'File not found: {filename}'
            }), 404
            
        with open(escalation_path, 'r') as f:
            data = json.load(f)
            
        return jsonify({
            'status': 'success',
            'data': data
        })
    except Exception as e:
        logger.error(f"Error getting escalation: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

# @app.route('/medical-records')
# def medical_records():
#     """Render the medical records page."""
#     return render_template('medical_records.html')

# @app.route('/medical-records/<path:path>', methods=['GET', 'POST'])
# def medical_records_proxy(path):
#     """Proxy requests to the medical records service."""
#     try:
#         # Remove the entire function body
#         pass
#     except Exception as e:
#         logger.error(f"Medical records proxy error: {str(e)}")
#         return jsonify({'error': str(e)}), 500

@app.route('/config/ancillary_codes.json')
def get_ancillary_codes():
    """API endpoint to serve the ancillary codes configuration file."""
    try:
        config_path = Path(__file__).parent.parent / 'config' / 'ancillary_codes.json'
        return send_file(str(config_path), mimetype='application/json')
    except Exception as e:
        logger.error(f"Error serving ancillary codes configuration: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))  # Default to port 8080 if not specified
    app.run(host='0.0.0.0', port=port, debug=True) 