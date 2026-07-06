# File: api/app.py


from flask import Flask
from flask_cors import CORS
from dotenv import load_dotenv
import os
load_dotenv(override=True)
from db.database import init_db
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def create_app():
    app = Flask(__name__, 
                template_folder='../ui/templates',
                static_folder='../ui/static')
    
    # Configuration
    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')
    app.config['JSON_SORT_KEYS'] = False
    
    # Enable CORS
    CORS(app)
    
    # Initialize database
    init_db()
    
    # Register blueprints
    from api.routes import api_bp
    app.register_blueprint(api_bp)
    
    return app

if __name__ == '__main__':
    app = create_app()
    port = int(os.getenv('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)
