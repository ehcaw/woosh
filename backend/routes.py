from flask import jsonify, request
from sqlalchemy import inspect
from functools import wraps
from .database.config import get_db_connection
from .langchain_setup import get_compiled_graph, NLQueryState

def requires_db_config(db_config):
    """Decorator factory to check if database is configured"""
    def decorator(f):
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
    return decorator

def get_schema_from_db(config):
    """Fetch the database schema information"""
    with get_db_connection(config) as connection:
        inspector = inspect(connection)
        schema = {}
        for table_name in inspector.get_table_names():
            columns = inspector.get_columns(table_name)
            schema[table_name] = [column['name'] for column in columns]
        return schema

def execute_sql_query(query, config):
    with get_db_connection(config) as connection:
        result = connection.execute(query)
        return [dict(row) for row in result]

def register_routes(app, db_config, llm):
    @app.route('/health', methods=['GET'])
    @requires_db_config(db_config)
    def health_check():
        try:
            config = db_config.load_config()
            with get_db_connection(config) as connection:
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
            with get_db_connection(test_config) as connection:
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
    @requires_db_config(db_config)
    def get_schema():
        try:
            config = db_config.load_config()
            schema = get_schema_from_db(config)
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
    @requires_db_config(db_config)
    def convert_to_sql():
        data = request.get_json()
        
        if not data or 'query' not in data:
            return jsonify({
                'error': 'Missing query in request body',
                'status': 'error'
            }), 400
        
        try:
            config = db_config.load_config()
            schema = get_schema_from_db(config)
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
                    query_results = execute_sql_query(result['sql_query'], config)
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