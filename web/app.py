from flask import Flask, render_template, jsonify, request
from pathlib import Path
import json
from typing import List, Dict
import logging
from datetime import datetime

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here'  # Change this in production

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_failed_files() -> List[Dict]:
    """Get all failed validation files with their details."""
    fails_dir = Path(r"C:\Users\ChristopherCato\OneDrive - clarity-dx.com\Documents\Bill_Review_INTERNAL\scripts\VAILIDATION\data\extracts\valid\mapped\staging\fails")
    failed_files = []
    
    try:
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
        failed_files = get_failed_files()
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
    fails_dir = Path(r"C:\Users\ChristopherCato\OneDrive - clarity-dx.com\Documents\Bill_Review_INTERNAL\scripts\VAILIDATION\data\extracts\valid\mapped\staging\fails")
    file_path = fails_dir / filename
    
    try:
        if not file_path.exists():
            return jsonify({
                'status': 'error',
                'message': 'File not found'
            }), 404
            
        with open(file_path, 'r') as f:
            data = json.load(f)
            return jsonify({
                'status': 'success',
                'data': data
            })
    except Exception as e:
        logger.error(f"Error reading file {filename}: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

if __name__ == '__main__':
    app.run(debug=True) 