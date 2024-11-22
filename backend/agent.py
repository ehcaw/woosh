from typing import TypedDict, List
from langchain_groq import ChatGroq
from langchain.prompts import PromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from langgraph.graph import StateGraph, END
import sqlvalidator

class NLQueryState(TypedDict):
    natural_language_query: str
    sql_query: str
    schema_info: str
    is_valid: bool
    is_safe: bool
    error_message: str
    suggested_fix: str

# Initialize Groq LLM
llm = ChatGroq(
    temperature=0,
    model_name="mixtral-8x7b-32768",
    api_key="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"
)

# Natural Language to SQL Conversion
nl_to_sql_prompt = PromptTemplate(
    template="""<|start_of_turn|>system
You are an expert at converting natural language queries to SQL.
Given the following schema information:
{schema_info}

Convert this natural language query to SQL:
{query}

Follow these rules:
1. Always include appropriate LIMIT clauses
2. Use column names from the schema
3. Include proper sorting (ORDER BY) when relevant
4. Return a JSON with:
   - sql_query: the SQL query
   - confidence: high/medium/low
   - explanation: brief explanation of the conversion

Make the query efficient and safe.<|end_of_turn|>
<|start_of_turn|>assistant""",
    input_variables=["query", "schema_info"]
)

nl_to_sql_chain = nl_to_sql_prompt | llm | JsonOutputParser()

# Schema Detection (simplified example - in practice, you'd connect to your database)
sample_schema = """
CREATE TABLE dogs (
    id INTEGER PRIMARY KEY,
    name VARCHAR(100),
    breed VARCHAR(100),
    age INTEGER,
    weight FLOAT,
    rating FLOAT,
    adoption_date DATE,
    is_available BOOLEAN
);
"""

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

# Safety validation prompt
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

safety_chain = safety_prompt | llm | JsonOutputParser()

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
    
    # Add nodes
    workflow.add_node("convert_nl_to_sql", convert_nl_to_sql_node)
    workflow.add_node("safety_check", safety_check_node)
    
    # Add edges
    workflow.add_edge("convert_nl_to_sql", "safety_check")
    
    # Set entry point
    workflow.set_entry_point("convert_nl_to_sql")
    
    # Conditional exit
    def should_exit(state):
        if not state["is_safe"]:
            return "error"
        return "success"
    
    workflow.add_conditional_edges(
        "safety_check",
        should_exit,
        {
            "error": END,
            "success": END
        }
    )
    
    return workflow.compile()

# Example usage function
def process_natural_language_query(natural_language_query: str, schema_info: str = sample_schema):
    app = build_nl_to_sql_graph()
    
    initial_state = {
        "natural_language_query": natural_language_query,
        "sql_query": "",
        "schema_info": schema_info,
        "is_valid": False,
        "is_safe": False,
        "error_message": "",
        "suggested_fix": ""
    }
    
    return app.invoke(initial_state)

# Usage example with error handling
def get_sql_query(natural_language_query: str):
    try:
        result = process_natural_language_query(natural_language_query)
        
        if result["is_safe"]:
            print("✅ Generated SQL Query:")
            print(result["sql_query"])
            return result["sql_query"]
        else:
            print("⚠️ Safety concerns detected:")
            print(result["error_message"])
            print("\nSuggested fix:")
            print(result["suggested_fix"])
            return result["suggested_fix"]
            
    except Exception as e:
        print(f"Error processing query: {str(e)}")
        return None

# Example usage
if __name__ == "__main__":
    queries = [
        "Get top 5 dogs with highest rating",
        "Show me the top 5 heaviest dogs that are available for adoption",
        "Find the 5 oldest dogs of breed 'Golden Retriever'"
    ]
    
    for query in queries:
        print(f"\nProcessing: '{query}'")
        sql = get_sql_query(query)