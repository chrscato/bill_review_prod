from flask import Flask
from flask_cors import CORS
from .routes.portal_routes import portal_bp
from .routes.mapping_routes import mapping_bp
from .config import DEBUG

def create_app():
    app = Flask(__name__)
    CORS(app)
    
    # Add CSP headers
    @app.after_request
    def add_security_headers(response):
        response.headers['Content-Security-Policy'] = "default-src 'self' 'unsafe-inline' 'unsafe-eval' https:;"
        return response
    
    # Register blueprints
    app.register_blueprint(portal_bp)
    app.register_blueprint(mapping_bp)
    
    return app

app = create_app()

if __name__ == '__main__':
    app.run(debug=DEBUG, port=8080) 
