import re
import os
from flask import Flask
from web.app import app  # Import the app directly

# Configure Flask for URL generation
app.config['SERVER_NAME'] = 'localhost:8080'
app.config['APPLICATION_ROOT'] = '/'
app.config['PREFERRED_URL_SCHEME'] = 'http'

# Map your route functions to their new blueprint locations
URL_MAPPINGS = {
    # Portal routes
    'portal_home': 'portal.portal_home',  # /portal/
    'mapping_home': 'portal.mapping_home',  # /portal/mapping
    
    # Processing routes
    'processing_home': 'processing.processing_home',
    'unauthorized_services': 'processing.unauthorized_services',
    'non_global_bills': 'processing.non_global_bills',
    'rate_corrections': 'processing.rate_corrections',
    'ota_review': 'processing.ota_review',
    
    # Escalation routes
    'escalations': 'escalations.get_escalations',  # Changed from processing.escalations
    
    # Dashboard routes
    'dashboard': 'dashboard.dashboard',
    
    # Static files (built-in Flask route)
    'static': 'static'
}

# Search pattern for finding url_for references in templates
URL_FOR_PATTERN = r"url_for\(['\"](\w+)['\"]"

def update_template_urls(template_dir):
    """
    Scan all template files and update url_for references
    according to the URL_MAPPINGS dictionary
    """
    fixed_count = 0
    file_count = 0
    
    for root, _, files in os.walk(template_dir):
        for file in files:
            if not file.endswith('.html'):
                continue
                
            file_path = os.path.join(root, file)
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Find all url_for references
            matches = re.findall(URL_FOR_PATTERN, content)
            has_changes = False
            
            # Replace each match with the new blueprint format
            for match in matches:
                if match in URL_MAPPINGS:
                    new_ref = URL_MAPPINGS[match]
                    old_pattern = f"url_for('{match}')"
                    new_pattern = f"url_for('{new_ref}')"
                    
                    # Also handle double quote version
                    alt_old_pattern = f'url_for("{match}")'
                    alt_new_pattern = f'url_for("{new_ref}")'
                    
                    if old_pattern in content or alt_old_pattern in content:
                        content = content.replace(old_pattern, new_pattern)
                        content = content.replace(alt_old_pattern, alt_new_pattern)
                        has_changes = True
                        fixed_count += 1
            
            # Save the file if changes were made
            if has_changes:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                file_count += 1
                print(f"Updated {file_path}")
    
    print(f"Updated {fixed_count} references in {file_count} files")

def find_unmapped_url_for_calls(template_dir):
    """Find all url_for calls that aren't in our mapping dictionary"""
    unmapped = set()
    
    for root, _, files in os.walk(template_dir):
        for file in files:
            if not file.endswith('.html'):
                continue
                
            file_path = os.path.join(root, file)
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Find all url_for references
            matches = re.findall(URL_FOR_PATTERN, content)
            
            for match in matches:
                if match not in URL_MAPPINGS:
                    unmapped.add(match)
                    print(f"Unmapped route: '{match}' in {file_path}")
    
    return unmapped

def verify_blueprint_routes(app):
    """Verify that all mapped routes exist in the application"""
    missing = []
    
    with app.app_context():
        for original, mapped in URL_MAPPINGS.items():
            try:
                # Try to build a URL for this endpoint
                if mapped == 'static':
                    # Skip static route verification as it requires filename
                    continue
                app.url_for(mapped)
            except Exception as e:
                missing.append((original, mapped))
                print(f"Missing blueprint route: '{mapped}' (was '{original}') - Error: {str(e)}")
    
    return missing

if __name__ == "__main__":
    # Set the template directory
    TEMPLATE_DIR = "web/templates"
    
    # First, find any unmapped routes
    print("\nChecking for unmapped routes...")
    unmapped = find_unmapped_url_for_calls(TEMPLATE_DIR)
    if unmapped:
        print("\nFound unmapped routes. Please add these to URL_MAPPINGS:")
        for route in unmapped:
            print(f"    '{route}': 'blueprint.{route}',")
    
    # Verify all blueprint routes exist
    print("\nVerifying blueprint routes...")
    missing = verify_blueprint_routes(app)
    if missing:
        print("\nSome routes are missing. Please ensure these blueprints are registered:")
        for original, mapped in missing:
            print(f"    {mapped}")
    
    # Update the templates
    print("\nUpdating template files...")
    update_template_urls(TEMPLATE_DIR) 