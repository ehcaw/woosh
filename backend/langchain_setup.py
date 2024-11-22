from langchain_groq import ChatGroq
from langchain.prompts import PromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from langgraph.graph import StateGraph, END
from typing import TypedDict
import os
from functools import lru_cache

class NLQueryState(TypedDict):
    natural_language_query: str
    sql_query: str
    schema_info: str
    is_valid: bool
    is_safe: bool
    error_message: str
    suggested_fix: str

def init_llm():
    return ChatGroq(
        temperature=0,
        model_name="mixtral-8x7b-32768",
        api_key=os.getenv('GROQ_API_KEY')
    )

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

def setup_chains(llm):
    return (
        nl_to_sql_prompt | llm | JsonOutputParser(),
        safety_prompt | llm | JsonOutputParser()
    )

def convert_nl_to_sql_node(state: NLQueryState):
    nl_to_sql_chain, _ = setup_chains(init_llm())
    result = nl_to_sql_chain.invoke({
        "query": state["natural_language_query"],
        "schema_info": state["schema_info"]
    })
    return {
        **state,
        "sql_query": result["sql_query"]
    }

def safety_check_node(state: NLQueryState):
    _, safety_chain = setup_chains(init_llm())
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