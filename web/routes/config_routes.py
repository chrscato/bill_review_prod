from flask import Blueprint, send_file, jsonify
import logging
from pathlib import Path

# Set up logging
logger = logging.getLogger(__name__)

# Create blueprint
config_bp = Blueprint('config', __name__)

@config_bp.route('/ancillary_codes.json')
def get_ancillary_codes():
    """API endpoint to serve the ancillary codes configuration file."""
    try:
        config_path = Path(__file__).parent.parent.parent / 'config' / 'ancillary_codes.json'
        return send_file(str(config_path), mimetype='application/json')
    except Exception as e:
        logger.error(f"Error serving ancillary codes configuration: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500 