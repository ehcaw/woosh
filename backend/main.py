import secrets
from flask import Flask
from dotenv import load_dotenv
import os

# Use absolute imports when running as script
try:
    from database.config import DatabaseConfig
    from langchain_setup import init_llm
    from routes import register_routes
except ImportError:
    from .database.config import DatabaseConfig
    from .langchain_setup import init_llm
    from .routes import register_routes

# Initialize Flask app
app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET_KEY', secrets.token_hex(32))

# Initialize components
db_config = DatabaseConfig()
llm = init_llm()

# Register routes
register_routes(app, db_config, llm)

# CORS configuration
@app.after_request
def after_request(response):
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
    response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE,OPTIONS')
    return response

if __name__ == '__main__':
    load_dotenv()
    
    app.run(
        debug=os.getenv('FLASK_DEBUG', 'False').lower() == 'true',
        host='0.0.0.0',
        port=int(os.getenv('PORT', 5000))
    )