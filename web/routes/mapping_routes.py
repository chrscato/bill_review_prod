from flask import Blueprint, render_template, jsonify, request, send_file
from core.services.database import DatabaseService
import json
import logging
from pathlib import Path
from web import config
import re
import shutil
import datetime
from io import BytesIO
import base64
from PIL import Image, ImageDraw, ImageFont

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize services
db_service = DatabaseService()

# Create blueprint
mapping_bp = Blueprint('mapping', __name__)

@mapping_bp.route('/')
def mapping_home():
    """Render the mapping home page."""
    return render_template('mapping_home.html')

def validate_filename(filename):
    """Validate and sanitize a filename."""
    # Remove any path components
    filename = Path(filename).name
    
    # Only allow alphanumeric characters, underscores, hyphens, and dots
    if not re.match(r'^[\w\-\.]+$', filename):
        raise ValueError('Invalid filename')
        
    return filename

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
        # Get files from both the fails folder and database
        files = [f.name for f in config.FOLDERS['FAILS_FOLDER'].glob('*.json')]
        
        # Get additional files from database that need correction
        conn = db_service.connect_db()
        try:
            failures = db_service.get_validation_failures(
                status='pending',
                validation_type='correction',
                conn=conn
            )
            db_files = [f"{row['order_id']}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json" 
                       for _, row in failures.iterrows()]
            files.extend(db_files)
        finally:
            conn.close()
            
        return jsonify({'files': files})
    except Exception as e:
        logger.error(f"Error listing correction files: {str(e)}")
        return jsonify({'error': str(e)}), 500

@mapping_bp.route('/api/corrections/file/<filename>')
def get_correction_file(filename):
    """Get the content of a specific JSON file."""
    try:
        safe_filename = validate_filename(filename)
        file_path = config.FOLDERS['FAILS_FOLDER'] / safe_filename
        
        # Try to get from file first
        if file_path.exists():
            with open(file_path, 'r') as f:
                data = json.load(f)
        else:
            # If not in file, try to get from database
            order_id = safe_filename.split('_')[0]
            conn = db_service.connect_db()
            try:
                data = db_service.get_full_details(order_id, conn)
            finally:
                conn.close()
        
        # Ensure numeric types for units
        if 'service_lines' in data:
            for line in data['service_lines']:
                if 'units' in line:
                    line['units'] = int(line['units']) if str(line['units']).isdigit() else 1
                    
        return jsonify({'data': data})
    except Exception as e:
        logger.error(f"Error loading file {filename}: {str(e)}")
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
    """Save corrections to the database and move the file to the output folder."""
    try:
        data = request.json
        filename = validate_filename(data['filename'])
        content = data['content']
        original_content = data['original_content']
        
        # Get order_id from filename (assuming format: order_id_timestamp.json)
        order_id = filename.split('_')[0]
        
        # Update order details in database
        success = db_service.update_order_details(order_id, content)
        if not success:
            raise Exception("Failed to update order details in database")
        
        # Save processed file
        with open(config.FOLDERS['OUTPUT_FOLDER'] / filename, 'w') as f:
            json.dump(content, f, indent=2)
            
        # Archive original
        with open(config.FOLDERS['ORIGINALS_FOLDER'] / filename, 'w') as f:
            json.dump(original_content, f, indent=2)
            
        # Remove from fails folder
        (config.FOLDERS['FAILS_FOLDER'] / filename).unlink(missing_ok=True)
        
        # Log the correction in the database
        validation_result = {
            'order_id': order_id,
            'validation_type': 'correction',
            'status': 'completed',
            'details': {
                'original': original_content,
                'corrected': content,
                'timestamp': datetime.now().isoformat()
            }
        }
        db_service.save_validation_result(validation_result)
        
        return jsonify({'message': 'File saved successfully'})
    except Exception as e:
        logger.error(f"Error saving correction: {str(e)}")
        return jsonify({'error': str(e)}), 500

@mapping_bp.route('/api/files')
def list_files():
    """List all unmapped JSON files."""
    try:
        logger.info("=== Starting list_files endpoint ===")
        logger.info(f"UNMAPPED_FOLDER path: {config.FOLDERS['UNMAPPED_FOLDER']}")
        logger.info(f"UNMAPPED_FOLDER exists: {config.FOLDERS['UNMAPPED_FOLDER'].exists()}")
        logger.info(f"UNMAPPED_FOLDER is directory: {config.FOLDERS['UNMAPPED_FOLDER'].is_dir()}")
        
        if not config.FOLDERS['UNMAPPED_FOLDER'].exists():
            logger.error("UNMAPPED_FOLDER does not exist!")
            return jsonify({'error': 'UNMAPPED_FOLDER does not exist', 'path': str(config.FOLDERS['UNMAPPED_FOLDER'])}), 500
            
        files = [f.name for f in config.FOLDERS['UNMAPPED_FOLDER'].glob('*.json')]
        logger.info(f"Found {len(files)} files: {files}")
        
        response = jsonify({'files': files})
        logger.info(f"Response: {response.get_data(as_text=True)}")
        return response
    except Exception as e:
        logger.error(f"Error in list_files: {str(e)}", exc_info=True)
        return jsonify({'error': str(e)}), 500

@mapping_bp.route('/api/file/<filename>')
def get_file(filename):
    """Get the content of a specific JSON file."""
    try:
        safe_filename = validate_filename(filename)
        file_path = config.FOLDERS['UNMAPPED_FOLDER'] / safe_filename
        with open(file_path, 'r') as f:
            data = json.load(f)
            return jsonify({'data': data})
    except Exception as e:
        logger.error(f"Error loading file {filename}: {str(e)}")
        return jsonify({'error': str(e)}), 500

@mapping_bp.route('/api/pdf/<filename>')
def get_pdf(filename):
    """Serve a PDF file for viewing."""
    try:
        safe_filename = validate_filename(filename)
        pdf_path = config.FOLDERS['PDF_FOLDER'] / safe_filename.replace('.json', '.pdf')
        if pdf_path.exists():
            return send_file(pdf_path, mimetype='application/pdf')
        else:
            return jsonify({'error': 'PDF not found'}), 404
    except Exception as e:
        logger.error(f"Error serving PDF {filename}: {str(e)}")
        return jsonify({'error': str(e)}), 500

@mapping_bp.route('/api/save', methods=['POST'])
def save_file():
    """Save changes to a file and move it to the mapped folder."""
    try:
        data = request.json
        filename = validate_filename(data['filename'])
        content = data['content']
        
        # Optional: Log the changes if needed
        changes_made = data.get('changes_made', [])
        if changes_made:
            logger.info(f"Changes made to {filename}:")
            for change in changes_made:
                logger.info(f"- {change}")
        
        # Save to the mapped folder
        with open(config.FOLDERS['MAPPED_FOLDER'] / filename, 'w') as f:
            json.dump(content, f, indent=2)
            
        # Remove from unmapped folder
        (config.FOLDERS['UNMAPPED_FOLDER'] / filename).unlink(missing_ok=True)
        
        return jsonify({'message': 'File saved successfully'})
    except Exception as e:
        logger.error(f"Error saving file {filename}: {str(e)}")
        return jsonify({'error': str(e)}), 500

@mapping_bp.route('/api/not_found', methods=['POST'])
def not_found():
    """Handle the NOT FOUND IN FILEMAKER action."""
    try:
        data = request.json
        filename = validate_filename(data.get('filename', ''))
        
        if not filename:
            return jsonify({'error': 'Filename is required'}), 400
            
        # Source file path
        source_path = config.FOLDERS['UNMAPPED_FOLDER'] / filename
        
        # Ensure the review2 folder exists
        review2_folder = config.BASE_PATH / r"scripts\VAILIDATION\data\extracts\review2"
        review2_folder.mkdir(parents=True, exist_ok=True)
        
        # Target file path
        target_path = review2_folder / filename
        
        # Move the file to the review2 folder
        if source_path.exists():
            # Read the original file content
            with open(source_path, 'r') as f:
                content = json.load(f)
                
            # Write to the target location
            with open(target_path, 'w') as f:
                json.dump(content, f, indent=2)
                
            # Remove from unmapped folder
            source_path.unlink()
            
            return jsonify({'message': 'File marked as not found and moved to review2 folder'})
        else:
            return jsonify({'error': f'Source file not found: {filename}'}), 404
            
    except Exception as e:
        logger.error(f"Error in not_found: {str(e)}")
        return jsonify({'error': str(e)}), 500

@mapping_bp.route('/api/escalate', methods=['POST'])
def escalate():
    """Handle the ESCALATE action."""
    try:
        data = request.json
        filename = validate_filename(data.get('filename', ''))
        content = data.get('content', {})
        notes = data.get('notes', '')
        
        if not filename:
            return jsonify({'error': 'Filename is required'}), 400
            
        if not notes:
            return jsonify({'error': 'Escalation notes are required'}), 400
            
        # Source file path
        source_path = config.FOLDERS['UNMAPPED_FOLDER'] / filename
        
        # Ensure the escalations folder exists
        escalations_folder = config.BASE_PATH / r"scripts\VAILIDATION\data\extracts\escalations"
        escalations_folder.mkdir(parents=True, exist_ok=True)
        
        # Target file path
        target_path = escalations_folder / filename
        
        # Move the file to the escalations folder
        if source_path.exists():
            # Add escalation metadata if not already present
            if not content.get('escalation'):
                content['escalation'] = {}
                
            # Add notes and timestamp
            content['escalation']['notes'] = notes
            content['escalation']['timestamp'] = datetime.datetime.now().isoformat()
            content['escalation']['user'] = request.environ.get('REMOTE_USER', 'unknown')
            
            # Write to the target location with escalation data
            with open(target_path, 'w') as f:
                json.dump(content, f, indent=2)
                
            # Remove from unmapped folder
            source_path.unlink()
            
            return jsonify({'message': 'File escalated successfully'})
        else:
            return jsonify({'error': f'Source file not found: {filename}'}), 404
            
    except Exception as e:
        logger.error(f"Error in escalate: {str(e)}")
        return jsonify({'error': str(e)}), 500

@mapping_bp.route('/api/debug_paths')
def debug_paths():
    """Return debug information about file paths"""
    try:
        # Check if folders exist
        unmapped_exists = config.FOLDERS['UNMAPPED_FOLDER'].exists()
        mapped_exists = config.FOLDERS['MAPPED_FOLDER'].exists()
        pdf_exists = config.FOLDERS['PDF_FOLDER'].exists()
        
        # Count files
        unmapped_files = len(list(config.FOLDERS['UNMAPPED_FOLDER'].glob('*.json')))
        mapped_files = len(list(config.FOLDERS['MAPPED_FOLDER'].glob('*.json')))
        pdf_files = len(list(config.FOLDERS['PDF_FOLDER'].glob('*.pdf')))
        
        return jsonify({
            'paths': {
                'unmapped': str(config.FOLDERS['UNMAPPED_FOLDER']),
                'mapped': str(config.FOLDERS['MAPPED_FOLDER']),
                'pdf': str(config.FOLDERS['PDF_FOLDER'])
            },
            'exists': {
                'unmapped': unmapped_exists,
                'mapped': mapped_exists,
                'pdf': pdf_exists
            },
            'file_counts': {
                'unmapped': unmapped_files,
                'mapped': mapped_files,
                'pdf': pdf_files
            }
        })
    except Exception as e:
        logger.error(f"Error in debug_paths: {str(e)}")
        return jsonify({'error': str(e)}), 500

@mapping_bp.route('/api/pdf_region/<filename>/<region>', methods=['GET'])
def get_pdf_region(filename, region):
    """Get a specific region of a PDF as an image."""
    try:
        logger.info(f"PDF region request received for file: {filename}, region: {region}")
        
        # Validate filename
        if not filename.endswith('.json'):
            return jsonify({'error': 'Invalid filename'}), 400

        # Get corresponding PDF filename
        pdf_filename = filename.replace('.json', '.pdf')
        pdf_path = config.FOLDERS['PDF_FOLDER'] / pdf_filename
        json_path = config.FOLDERS['UNMAPPED_FOLDER'] / filename

        # Check if files exist
        if not pdf_path.exists():
            logger.error(f"PDF file not found: {pdf_path}")
            return jsonify({'error': 'PDF file not found'}), 404
        if not json_path.exists():
            logger.error(f"JSON file not found: {json_path}")
            return jsonify({'error': 'JSON file not found'}), 404

        # Load JSON data to get coordinates
        with open(json_path, 'r') as f:
            data = json.load(f)

        # Get region coordinates
        if region == 'header':
            coords = data.get('header_coords', {})
        elif region == 'service_lines':
            coords = data.get('service_lines_coords', {})
        else:
            return jsonify({'error': 'Invalid region'}), 400

        if not coords:
            return jsonify({'error': 'Region coordinates not found'}), 404

        # Create a placeholder image with region information
        placeholder = Image.new('RGB', (800, 200), color='white')
        # Add some text to the placeholder
        draw = ImageDraw.Draw(placeholder)
        try:
            font = ImageFont.truetype("arial.ttf", 24)
        except:
            font = ImageFont.load_default()
        draw.text((10, 10), f"Region: {region}", fill="black", font=font)
        draw.text((10, 50), f"File: {filename}", fill="black", font=font)
        draw.text((10, 90), "PDF region extraction is not available", fill="red", font=font)
        draw.text((10, 130), "Click 'Open Full PDF' to view the entire document", fill="blue", font=font)
        
        # Convert to base64
        buffered = BytesIO()
        placeholder.save(buffered, format="PNG")
        img_str = base64.b64encode(buffered.getvalue()).decode()

        return jsonify({
            'image': f'data:image/png;base64,{img_str}'
        })

    except Exception as e:
        logger.error(f"Error in PDF region extraction: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return jsonify({'error': str(e)}), 500

@mapping_bp.route('/test')
def test():
    """Test route to verify the blueprint is working."""
    return jsonify({'status': 'ok', 'message': 'Test route is working'})

@mapping_bp.route('/api/search', methods=['POST'])
def search_patients():
    """Search for patients in the database."""
    try:
        data = request.json
        first_name = data.get('firstName', '').strip()
        last_name = data.get('lastName', '').strip()
        dos = data.get('dos', '').strip()
        months_range = int(data.get('monthsRange', 0))
        
        # Validate inputs
        if not first_name and not last_name:
            return jsonify({'error': 'Please enter at least a first or last name'}), 400
            
        # Connect to database
        conn = db_service.connect_db()
        try:
            # Build query with proper column names
            query = """
                SELECT DISTINCT 
                    o.Order_ID as order_id,
                    o.Patient_First_Name as patient_first_name,
                    o.Patient_Last_Name as patient_last_name,
                    o.PatientName as patient_name,
                    GROUP_CONCAT(DISTINCT li.DOS) as dos_list,
                    GROUP_CONCAT(DISTINCT li.CPT) as cpt_list,
                    GROUP_CONCAT(DISTINCT li.Description) as description_list
                FROM orders o
                LEFT JOIN line_items li ON o.Order_ID = li.Order_ID
                WHERE 1=1
            """
            params = []
            
            if first_name:
                query += " AND LOWER(o.Patient_First_Name) LIKE LOWER(?)"
                params.append(f"%{first_name}%")
            if last_name:
                query += " AND LOWER(o.Patient_Last_Name) LIKE LOWER(?)"
                params.append(f"%{last_name}%")
            if dos:
                query += " AND li.DOS = ?"
                params.append(dos)
            if months_range > 0:
                query += " AND li.DOS >= date('now', ?)"
                params.append(f"-{months_range} months")
                
            query += " GROUP BY o.Order_ID, o.Patient_First_Name, o.Patient_Last_Name, o.PatientName"
            query += " ORDER BY o.Patient_Last_Name, o.Patient_First_Name"
            query += " LIMIT 100"
            
            # Execute query
            cursor = conn.cursor()
            cursor.execute(query, params)
            results = cursor.fetchall()
            
            # Format results
            formatted_results = []
            for row in results:
                formatted_results.append({
                    'order_id': row['order_id'],
                    'first_name': row['patient_first_name'],
                    'last_name': row['patient_last_name'],
                    'patient_name': row['patient_name'],
                    'dos_list': row['dos_list'].split(',') if row['dos_list'] else [],
                    'cpt_list': row['cpt_list'].split(',') if row['cpt_list'] else [],
                    'description_list': row['description_list'].split(',') if row['description_list'] else []
                })
                
            return jsonify({
                'results': formatted_results,
                'count': len(formatted_results)
            })
            
        finally:
            conn.close()
            
    except Exception as e:
        logger.error(f"Error searching patients: {str(e)}")
        return jsonify({'error': str(e)}), 500

@mapping_bp.route('/api/escalations/deny', methods=['POST'])
def deny_escalation():
    """Handle the DENY action for both escalated bills and regular failures."""
    try:
        data = request.json
        filename = validate_filename(data.get('filename', ''))
        content = data.get('content', {})
        source_type = data.get('source_type', 'escalations')  # 'escalations' or 'failures'
        
        if not filename:
            return jsonify({'error': 'Filename is required'}), 400
            
        # Determine source path based on source type
        if source_type == 'escalations':
            source_path = config.BASE_PATH / r"scripts\VAILIDATION\data\extracts\escalations" / filename
        else:  # failures
            source_path = config.BASE_PATH / r"scripts\VAILIDATION\data\extracts\valid\mapped\staging" / filename
        
        # Ensure the denials folder exists
        denials_folder = config.BASE_PATH / r"scripts\VAILIDATION\data\extracts\valid\mapped\staging\denials"
        denials_folder.mkdir(parents=True, exist_ok=True)
        
        # Target file path
        target_path = denials_folder / filename
        
        # Move the file to the denials folder
        if source_path.exists():
            # Add denial metadata if not already present
            if not content.get('denial'):
                content['denial'] = {}
                
            # Add denial reason and timestamp
            content['denial']['reason'] = content.get('denial_reason', '')
            content['denial']['timestamp'] = datetime.datetime.now().isoformat()
            content['denial']['user'] = request.environ.get('REMOTE_USER', 'unknown')
            content['denial']['source'] = source_type
            
            # Write to the target location with denial data
            with open(target_path, 'w') as f:
                json.dump(content, f, indent=2)
                
            # Remove from source folder
            source_path.unlink()
            
            return jsonify({'message': 'Bill denied successfully'})
        else:
            return jsonify({'error': f'Source file not found: {filename}'}), 404
            
    except Exception as e:
        logger.error(f"Error in deny_escalation: {str(e)}")
        return jsonify({'error': str(e)}), 500 