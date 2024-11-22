from flask import Flask, request, jsonify, session
from typing import TypedDict, List
from langchain_groq import ChatGroq
from langchain.prompts import PromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from langgraph.graph import StateGraph, END
import sqlvalidator
from functools import lru_cache, wraps
import os
import json
from pathlib import Path
import base64
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import secrets
import mysql.connector
from mysql.connector import Error
import sqlalchemy
from sqlalchemy import create_engine, inspect
from contextlib import contextmanager

app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET_KEY', secrets.token_hex(32))

# Data Models
class NLQueryState(TypedDict):
    natural_language_query: str
    sql_query: str
    schema_info: str
    is_valid: bool
    is_safe: bool
    error_message: str
    suggested_fix: str

# Database Configuration Class
class DatabaseConfig:
    CONFIG_FILE = 'db_config.encrypted'
    
    def __init__(self):
        self.key = self._get_or_create_key()
        self.fernet = Fernet(self.key)
        
    def _get_or_create_key(self):
        key_file = Path('.env.key')
        if key_file.exists():
            return key_file.read_bytes()
        else:
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=b'static_salt',
                iterations=100000,
            )
            key = base64.urlsafe_b64encode(kdf.derive(secrets.token_bytes(32)))
            key_file.write_bytes(key)
            return key
    
    def save_config(self, config):
        encrypted_data = self.fernet.encrypt(json.dumps(config).encode())
        with open(self.CONFIG_FILE, 'wb') as f:
            f.write(encrypted_data)
    
    def load_config(self):
        try:
            if not Path(self.CONFIG_FILE).exists():
                return None
            with open(self.CONFIG_FILE, 'rb') as f:
                encrypted_data = f.read()
            decrypted_data = self.fernet.decrypt(encrypted_data)
            return json.loads(decrypted_data)
        except Exception:
            return None

# Initialize database config manager
db_config = DatabaseConfig()

# Database connection management
@contextmanager
def get_db_connection():
    """Context manager for database connections"""
    config = db_config.load_config()
    if not config:
        raise Exception("Database not configured")
    
    engine = create_engine(get_db_url())
    try:
        connection = engine.connect()
        yield connection
    finally:
        connection.close()
        engine.dispose()

def get_db_url():
    """Get database URL from stored configuration"""
    config = db_config.load_config()
    if not config:
        raise Exception("Database not configured")
    return f"mysql+mysqlconnector://{config['DB_USER']}:{config['DB_PASSWORD']}@{config['DB_HOST']}:{config['DB_PORT']}/{config['DB_NAME']}"

def requires_db_config(f):
    """Decorator to check if database is configured"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        config = db_config.load_config()
        if not config:
            return jsonify({
                'error': 'Database not configured',
                'status': 'error',
                'code': 'DB_NOT_CONFIGURED'
            }), 400
        return f(*args, **kwargs)
    return decorated_function

# Initialize Groq LLM
llm = ChatGroq(
    temperature=0,
    model_name="mixtral-8x7b-32768",
    api_key=os.getenv('GROQ_API_KEY')
)

# Prompts and Chains setup
nl_to_sql_prompt = PromptTemplate(
    template="""<|start_of_turn|>system
You are an expert at converting natural language queries to SQL.
Given the following schema information:
{schema_info}

Convert this natural language query to SQL:
{query}

Follow these rules:
1. Always include appropriate LIMIT clauses
2. Use exact column names from the schema
3. Include proper sorting (ORDER BY) when relevant
4. Return a JSON with:
   - sql_query: the SQL query
   - confidence: high/medium/low
   - explanation: brief explanation of the conversion

Make the query efficient and safe.<|end_of_turn|>
<|start_of_turn|>assistant""",
    input_variables=["query", "schema_info"]
)

safety_prompt = PromptTemplate(
    template="""<|start_of_turn|>system
Analyze this SQL query for safety and efficiency:
{query}

Consider:
1. SQL injection risks
2. Performance implications
3. Data security
4. Resource usage

Return a JSON with:
- is_safe: boolean
- concerns: list of issues
- suggested_fix: optimized safe version<|end_of_turn|>
<|start_of_turn|>assistant""",
    input_variables=["query"]
)

nl_to_sql_chain = nl_to_sql_prompt | llm | JsonOutputParser()
safety_chain = safety_prompt | llm | JsonOutputParser()

# Node functions
def convert_nl_to_sql_node(state: NLQueryState):
    result = nl_to_sql_chain.invoke({
        "query": state["natural_language_query"],
        "schema_info": state["schema_info"]
    })
    return {
        **state,
        "sql_query": result["sql_query"]
    }

def safety_check_node(state: NLQueryState):
    safety_result = safety_chain.invoke({"query": state["sql_query"]})
    return {
        **state,
        "is_safe": safety_result["is_safe"],
        "error_message": ", ".join(safety_result["concerns"]) if not safety_result["is_safe"] else "",
        "suggested_fix": safety_result["suggested_fix"] if not safety_result["is_safe"] else state["sql_query"]
    }

def build_nl_to_sql_graph():
    workflow = StateGraph(NLQueryState)
    workflow.add_node("convert_nl_to_sql", convert_nl_to_sql_node)
    workflow.add_node("safety_check", safety_check_node)
    workflow.add_edge("convert_nl_to_sql", "safety_check")
    workflow.set_entry_point("convert_nl_to_sql")
    
    def should_exit(state):
        return "error" if not state["is_safe"] else "success"
    
    workflow.add_conditional_edges(
        "safety_check",
        should_exit,
        {
            "error": END,
            "success": END
        }
    )
    
    return workflow.compile()

@lru_cache(maxsize=1)
def get_compiled_graph():
    return build_nl_to_sql_graph()

# API Routes
@app.route('/health', methods=['GET'])
@requires_db_config
def health_check():
    try:
        with get_db_connection() as connection:
            return jsonify({
                'status': 'healthy',
                'message': 'API and database connection are working',
                'database': 'connected'
            })
    except Exception as e:
        return jsonify({
            'status': 'unhealthy',
            'message': f'Database connection failed: {str(e)}',
            'database': 'disconnected'
        }), 500

@app.route('/api/v1/database/config', methods=['POST'])
def configure_database():
    data = request.get_json()
    
    required_fields = ['DB_USER', 'DB_PASSWORD', 'DB_HOST', 'DB_PORT', 'DB_NAME']
    
    if not all(field in data for field in required_fields):
        return jsonify({
            'error': 'Missing required fields',
            'required_fields': required_fields,
            'status': 'error'
        }), 400
    
    try:
        test_config = {
            'DB_USER': data['DB_USER'],
            'DB_PASSWORD': data['DB_PASSWORD'],
            'DB_HOST': data['DB_HOST'],
            'DB_PORT': data['DB_PORT'],
            'DB_NAME': data['DB_NAME']
        }
        
        # Test connection
        test_url = f"mysql+mysqlconnector://{test_config['DB_USER']}:{test_config['DB_PASSWORD']}@{test_config['DB_HOST']}:{test_config['DB_PORT']}/{test_config['DB_NAME']}"
        engine = create_engine(test_url)
        
        with engine.connect() as connection:
            pass
        
        db_config.save_config(test_config)
        
        return jsonify({
            'message': 'Database configuration saved successfully',
            'status': 'success'
        })
        
    except Exception as e:
        return jsonify({
            'error': f'Failed to connect to database: {str(e)}',
            'status': 'error'
        }), 400

@app.route('/api/v1/schema', methods=['GET'])
@requires_db_config
def get_schema():
    try:
        schema = get_schema_from_db()
        if schema:
            return jsonify({
                'schema': schema,
                'status': 'success'
            })
        else:
            return jsonify({
                'error': 'Failed to fetch schema',
                'status': 'error'
            }), 500
    except Exception as e:
        return jsonify({
            'error': str(e),
            'status': 'error'
        }), 500

@app.route('/api/v1/convert', methods=['POST'])
@requires_db_config
def convert_to_sql():
    data = request.get_json()
    
    if not data or 'query' not in data:
        return jsonify({
            'error': 'Missing query in request body',
            'status': 'error'
        }), 400
    
    try:
        schema = get_schema_from_db()
        if not schema:
            return jsonify({
                'error': 'Failed to fetch database schema',
                'status': 'error'
            }), 500
        
        graph = get_compiled_graph()
        
        initial_state = {
            "natural_language_query": data['query'],
            "sql_query": "",
            "schema_info": schema,
            "is_valid": False,
            "is_safe": False,
            "error_message": "",
            "suggested_fix": ""
        }
        
        result = graph.invoke(initial_state)
        
        execute = data.get('execute', False)
        query_results = None
        if execute and result['is_safe']:
            try:
                query_results = execute_sql_query(result['sql_query'])
            except Exception as e:
                return jsonify({
                    'error': f'Query execution failed: {str(e)}',
                    'sql_query': result['sql_query'],
                    'status': 'error'
                }), 500
        
        response = {
            'original_query': data['query'],
            'sql_query': result['sql_query'] if result['is_safe'] else result['suggested_fix'],
            'is_safe': result['is_safe'],
            'status': 'success' if result['is_safe'] else 'warning'
        }
        
        if not result['is_safe']:
            response.update({
                'warnings': result['error_message'],
                'suggested_fix': result['suggested_fix']
            })
        
        if query_results is not None:
            response['results'] = query_results
        
        return jsonify(response)
        
    except Exception as e:
        return jsonify({
            'error': str(e),
            'status': 'error'
        }), 500

# CORS configuration
@app.after_request
def after_request(response):
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
    response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE,OPTIONS')
    return response

if __name__ == '__main__':
    from dotenv import load_dotenv
    load_dotenv()
    
    app.run(
        debug=os.getenv('FLASK_DEBUG', 'False').lower() == 'true',
        host='0.0.0.0',
        port=int(os.getenv('PORT', 5000))
    )