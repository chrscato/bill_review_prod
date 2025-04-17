import sys
from pathlib import Path

# Add the project root to the Python path
project_root = Path(__file__).parent.parent.absolute()
sys.path.append(str(project_root))

from flask import Flask, render_template, jsonify, request, send_from_directory, send_file, abort, redirect, url_for
from pathlib import Path
import json
from typing import List, Dict
import logging
from datetime import datetime
from core.services.database import DatabaseService
from core.services.hcfa import HCFAService
from contextlib import contextmanager
from core.config.settings import settings
from flask_cors import CORS
import os
from core.services.normalizer import normalize_hcfa_format
from web.routes import (
    portal_bp, rate_bp, ota_bp, mapping_bp, failure_bp,
    dashboard_bp, escalation_bp, processing_bp, config_bp
)
from werkzeug.middleware.proxy_fix import ProxyFix

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
app.register_blueprint(portal_bp, url_prefix='/portal')
app.register_blueprint(rate_bp, url_prefix='/api/rates')
app.register_blueprint(ota_bp, url_prefix='/api/otas')
app.register_blueprint(mapping_bp, url_prefix='/mapping')
app.register_blueprint(failure_bp, url_prefix='/api/failures')
app.register_blueprint(dashboard_bp, url_prefix='/dashboard')
app.register_blueprint(escalation_bp, url_prefix='/api/escalations')
app.register_blueprint(processing_bp, url_prefix='/processing')
app.register_blueprint(config_bp, url_prefix='/config')

# Configure paths
app.config['JSON_PATH'] = r"C:\Users\ChristopherCato\OneDrive - clarity-dx.com\Documents\Bill_Review_INTERNAL\scripts\VAILIDATION\data\extracts\valid\mapped\staging"
app.config['SUCCESS_PATH'] = r"C:\Users\ChristopherCato\OneDrive - clarity-dx.com\Documents\Bill_Review_INTERNAL\scripts\VAILIDATION\data\extracts\valid\mapped\staging\success"
app.config['FAILS_PATH'] = r"C:\Users\ChristopherCato\OneDrive - clarity-dx.com\Documents\Bill_Review_INTERNAL\scripts\VAILIDATION\data\extracts\valid\mapped\staging\fails"
app.config['ESCALATE_PATH'] = r"C:\Users\ChristopherCato\OneDrive - clarity-dx.com\Documents\Bill_Review_INTERNAL\scripts\VAILIDATION\data\extracts\valid\mapped\staging\escalations"
app.config['PDF_PATH'] = r"C:\Users\ChristopherCato\OneDrive - clarity-dx.com\Documents\Bill_Review_INTERNAL\scripts\VAILIDATION\data\extracts\valid\mapped\staging\pdfs"

# Process instructions configuration
PROCESS_INSTRUCTIONS = {
    'unauthorized': {
        'title': 'Unauthorized Services',
        'steps': [
            'Review the service lines in the HCFA file',
            'Compare with the order details',
            'Identify any unauthorized services',
            'Update the HCFA file with correct services',
            'Resolve the failure'
        ]
    },
    'non-global': {
        'title': 'Non-Global Bills',
        'steps': [
            'Check for TC or 26 modifiers',
            'Verify if the service is global or component',
            'Update the HCFA file accordingly',
            'Resolve the failure'
        ]
    },
    'rate': {
        'title': 'Rate Corrections',
        'steps': [
            'Review the rate in the HCFA file',
            'Check the provider network status',
            'Verify the correct rate for the service',
            'Update the HCFA file with the correct rate',
            'Resolve the failure'
        ]
    },
    'ota': {
        'title': 'OTA Review',
        'steps': [
            'Review the OTA details',
            'Verify the service codes',
            'Update the HCFA file if needed',
            'Resolve the failure'
        ]
    }
}

app.config['PROCESS_INSTRUCTIONS'] = PROCESS_INSTRUCTIONS

# Helper functions
@contextmanager
def get_db_connection():
    """Context manager for database connections."""
    try:
        conn = db_service.get_connection()
        yield conn
    finally:
        if conn:
            conn.close()

def get_failed_files():
    """Get all failed files from the fails directory."""
    try:
        fails_path = Path(app.config['FAILS_PATH'])
        if not fails_path.exists():
            logger.error(f"Fails directory not found: {fails_path}")
            return []
            
        failed_files = []
        for file_path in fails_path.glob('*.json'):
            try:
                with open(file_path, 'r') as f:
                    data = json.load(f)
                    data['filename'] = file_path.name
                    failed_files.append(data)
            except Exception as e:
                logger.warning(f"Error reading file {file_path}: {str(e)}")
                continue
                
        return failed_files
    except Exception as e:
        logger.error(f"Error getting failed files: {str(e)}")
        return []

# Root routes
@app.route('/')
def index():
    """Redirect to the portal home page."""
    return redirect(url_for('portal.portal_home'))

@app.route('/instructions')
def instructions():
    """Render the instructions page."""
    return render_template('instructions.html')

@app.route('/instructions/<process>')
def process_detail(process):
    """Render specific process instructions."""
    if process not in PROCESS_INSTRUCTIONS:
        abort(404)
    
    return render_template('process_detail.html', 
                         process_title=PROCESS_INSTRUCTIONS[process]['title'],
                         steps=PROCESS_INSTRUCTIONS[process]['steps'])

if __name__ == '__main__':
    app.run(debug=True, port=8080) 