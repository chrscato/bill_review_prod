from .portal_routes import portal_bp
from .dashboard_routes import dashboard_bp
from .mapping_routes import mapping_bp
from .failure_routes import failure_bp
from .rate_routes import rate_bp
from .ota_routes import ota_bp
from .escalation_routes import escalation_bp
from .processing_routes import processing_bp
from .config_routes import config_bp
from .order_routes import order_bp

__all__ = [
    'portal_bp',
    'dashboard_bp',
    'mapping_bp',
    'failure_bp',
    'rate_bp',
    'ota_bp',
    'escalation_bp',
    'processing_bp',
    'config_bp',
    'order_bp'
] 