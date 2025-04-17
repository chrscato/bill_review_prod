from flask import Blueprint, render_template

# Create blueprint
portal_bp = Blueprint('portal', __name__, url_prefix='/portal')

@portal_bp.route('/')
def portal_home():
    """Render the portal home page."""
    return render_template('portal_home.html')

@portal_bp.route('/mapping')
def mapping_home():
    """Render the mapping home page."""
    return render_template('mapping_home.html') 