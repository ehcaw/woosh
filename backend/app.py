from flask import Flask, request, jsonify
from typing import TypedDict, List
from langchain_groq import ChatGroq
from langchain.prompts import PromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from langgraph.graph import StateGraph, END
import sqlvalidator
from functools import lru_cache
import os
import mysql.connector
from mysql.connector import Error
import sqlalchemy
from sqlalchemy import create_engine, inspect
from contextlib import contextmanager

app = Flask(__name__)

class NLQueryState(TypedDict):
    natural_language_query: str
    sql_query: str
    schema_info: str
    is_valid: bool
    is_safe: bool
    error_message: str
    suggested_fix: str

# Database connection management
def get_db_url():
    """Construct database URL from environment variables"""
    return f"mysql+mysqlconnector://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}@{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}"

@contextmanager
def get_db_connection():
    """Context manager for database connections"""
    engine = create_engine(get_db_url())
    try:
        connection = engine.connect()
        yield connection
    finally:
        connection.close()
        engine.dispose()

def get_schema_from_db():
    """Fetch and format schema information from the database"""
    try:
        with get_db_connection() as connection:
            inspector = inspect(connection)
            schema_info = []
            
            # Get all tables
            for table_name in inspector.get_table_names():
                columns = inspector.get_columns(table_name)
                
                # Format CREATE TABLE statement
                column_definitions = []
                for column in columns:
                    nullable_str = "NULL" if column['nullable'] else "NOT NULL"
                    default = f"DEFAULT {column['default']}" if column['default'] is not None else ""
                    column_definitions.append(
                        f"    {column['name']} {column['type']} {nullable_str} {default}".strip()
                    )
                
                # Get primary key information
                pk_constraint = inspector.get_pk_constraint(table_name)
                if pk_constraint and pk_constraint['constrained_columns']:
                    pk_cols = pk_constraint['constrained_columns']
                    column_definitions.append(f"    PRIMARY KEY ({', '.join(pk_cols)})")
                
                # Get foreign key information
                for fk in inspector.get_foreign_keys(table_name):
                    referred_table = fk['referred_table']
                    constrained_cols = fk['constrained_columns']
                    referred_cols = fk['referred_columns']
                    column_definitions.append(
                        f"    FOREIGN KEY ({', '.join(constrained_cols)}) REFERENCES {referred_table}({', '.join(referred_cols)})"
                    )
                
                create_table = f"CREATE TABLE {table_name} (\n"
                create_table += ",\n".join(column_definitions)
                create_table += "\n);"
                
                schema_info.append(create_table)
            
            return "\n\n".join(schema_info)
            
    except Exception as e:
        print(f"Error fetching schema: {str(e)}")
        return None

def execute_sql_query(query):
    """Execute SQL query and return results"""
    try:
        with get_db_connection() as connection:
            result = connection.execute(sqlalchemy.text(query))
            return [dict(row) for row in result]
    except Exception as e:
        raise Exception(f"Error executing query: {str(e)}")

# Initialize Groq LLM
llm = ChatGroq(
    temperature=0,
    model_name="mixtral-8x7b-32768",
    api_key=os.getenv('GROQ_API_KEY')
)

# Prompts
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

# Chain definitions
nl_to_sql_chain = nl_to_sql_prompt | llm | JsonOutputParser()
safety_chain = safety_prompt | llm | JsonOutputParser()

# Node functions
def convert_nl_to_sql_node(state: NLQueryState):
    """Convert natural language to SQL"""
    result = nl_to_sql_chain.invoke({
        "query": state["natural_language_query"],
        "schema_info": state["schema_info"]
    })
    return {
        **state,
        "sql_query": result["sql_query"]
    }

def safety_check_node(state: NLQueryState):
    """Validate query safety"""
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
def health_check():
    """Health check endpoint"""
    try:
        # Test database connection
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

@app.route('/api/v1/schema', methods=['GET'])
def get_schema():
    """Get database schema"""
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
def convert_to_sql():
    """Convert natural language to SQL and execute"""
    data = request.get_json()
    
    if not data or 'query' not in data:
        return jsonify({
            'error': 'Missing query in request body',
            'status': 'error'
        }), 400
    
    try:
        # Get schema
        schema = get_schema_from_db()
        if not schema:
            return jsonify({
                'error': 'Failed to fetch database schema',
                'status': 'error'
            }), 500
        
        # Get compiled graph
        app = get_compiled_graph()
        
        # Process the query
        initial_state = {
            "natural_language_query": data['query'],
            "sql_query": "",
            "schema_info": schema,
            "is_valid": False,
            "is_safe": False,
            "error_message": "",
            "suggested_fix": ""
        }
        
        result = app.invoke(initial_state)
        
        # Execute the query if requested and safe
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
        
        # Prepare response
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