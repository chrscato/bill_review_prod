from flask import Blueprint, render_template, jsonify, request, send_file
from core.services.database import DatabaseService
import json
import logging
from pathlib import Path
import config

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize services
db_service = DatabaseService()

# Create blueprint
mapping_bp = Blueprint('mapping', __name__)

@mapping_bp.route('/unmapped')
def unmapped():
    """Render the unmapped items page."""
    return render_template('mapping/unmapped.html')

@mapping_bp.route('/corrections')
def corrections():
    """Render the corrections page."""
    return render_template('mapping/corrections.html')

@mapping_bp.route('/api/corrections/files')
def list_correction_files():
    """List all files that need correction."""
    try:
        files = [f.name for f in config.FOLDERS['FAILS_FOLDER'].glob('*.json')]
        return jsonify({'files': files})
    except Exception as e:
        logger.error(f"Error listing correction files: {str(e)}")
        return jsonify({'error': str(e)}), 500

@mapping_bp.route('/api/corrections/file/<filename>')
def get_correction_file(filename):
    """Get the content of a specific correction file."""
    try:
        safe_filename = validate_filename(filename)
        file_path = config.FOLDERS['FAILS_FOLDER'] / safe_filename
        with open(file_path, 'r') as f:
            data = json.load(f)
            # Ensure numeric types for units
            if 'service_lines' in data:
                for line in data['service_lines']:
                    if 'units' in line:
                        line['units'] = int(line['units']) if str(line['units']).isdigit() else 1
            return jsonify({'data': data})
    except Exception as e:
        logger.error(f"Error loading correction file {filename}: {str(e)}")
        return jsonify({'error': str(e)}), 500

@mapping_bp.route('/api/corrections/pdf/<filename>')
def get_correction_pdf(filename):
    """Serve a PDF file for viewing."""
    try:
        safe_filename = validate_filename(filename)
        pdf_filename = Path(safe_filename).with_suffix('.pdf')
        pdf_path = config.FOLDERS['PDF_FOLDER'] / pdf_filename
        return send_file(pdf_path, mimetype='application/pdf') if pdf_path.exists() else (jsonify({'error': 'PDF not found'}), 404)
    except Exception as e:
        logger.error(f"Error serving PDF {filename}: {str(e)}")
        return jsonify({'error': str(e)}), 500

@mapping_bp.route('/api/corrections/save', methods=['POST'])
def save_correction():
    """Save changes to a correction file."""
    try:
        data = request.json
        filename = validate_filename(data['filename'])
        content = data['content']
        original_content = data['original_content']
        
        # Save processed file
        with open(config.FOLDERS['OUTPUT_FOLDER'] / filename, 'w') as f:
            json.dump(content, f, indent=2)
            
        # Archive original
        with open(config.FOLDERS['ORIGINALS_FOLDER'] / filename, 'w') as f:
            json.dump(original_content, f, indent=2)
            
        # Remove from fails folder
        (config.FOLDERS['FAILS_FOLDER'] / filename).unlink(missing_ok=True)
        
        return jsonify({'message': 'File saved successfully'})
    except Exception as e:
        logger.error(f"Error saving correction file: {str(e)}")
        return jsonify({'error': str(e)}), 500

@mapping_bp.route('/api/unmapped')
def get_unmapped_items():
    """Get all unmapped items."""
    try:
        with db_service.connect_db() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM unmapped_items 
                WHERE status = 'pending'
                ORDER BY created_at DESC
            """)
            items = cursor.fetchall()
            
            # Convert to list of dictionaries
            result = []
            for item in items:
                result.append({
                    'id': item[0],
                    'type': item[1],
                    'value': item[2],
                    'created_at': item[3].isoformat() if item[3] else None,
                    'status': item[4]
                })
            
            return jsonify(result)
    except Exception as e:
        logger.error(f"Error fetching unmapped items: {str(e)}")
        return jsonify({'error': str(e)}), 500

@mapping_bp.route('/api/unmapped/<int:item_id>', methods=['PUT'])
def update_unmapped_item(item_id):
    """Update an unmapped item."""
    try:
        data = request.get_json()
        with db_service.connect_db() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE unmapped_items 
                SET status = ?, 
                    mapped_value = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (data.get('status'), data.get('mapped_value'), item_id))
            conn.commit()
            
            return jsonify({'success': True})
    except Exception as e:
        logger.error(f"Error updating unmapped item: {str(e)}")
        return jsonify({'error': str(e)}), 500 