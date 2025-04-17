from flask import Blueprint, render_template, jsonify
from core.services.hcfa import HCFAService
import logging

logger = logging.getLogger(__name__)

# Initialize services
hcfa_service = HCFAService()

# Create blueprint
dashboard_bp = Blueprint('dashboard', __name__)

@dashboard_bp.route('/')
def dashboard():
    """Render the dashboard page."""
    return render_template('dashboard.html')

@dashboard_bp.route('/api/data')
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