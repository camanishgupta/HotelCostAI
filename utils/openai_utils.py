import os
import json
import base64
import pandas as pd
from io import BytesIO
from openai import OpenAI
import streamlit as st

# the newest OpenAI model is "gpt-4o" which was released May 13, 2024.
# do not change this unless explicitly requested by the user
MODEL = "gpt-4o"
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")

client = OpenAI(api_key=OPENAI_API_KEY)

def query_ai_assistant(query, context=None):
    """
    Queries the OpenAI API with the user's question and context data
    
    Args:
        query (str): The user's question
        context (dict, optional): Data context to help the AI answer the question
    
    Returns:
        str: The AI's response
    """
    try:
        messages = [
            {"role": "system", "content": """You are an AI assistant for a hotel cost control system. 
            You help hotel and restaurant managers analyze their recipes, inventory, and sales data.
            You provide insights on cost optimization, popular menu items, and ingredient usage patterns.
            Always provide specific, actionable advice based on the data provided.
            If you don't have enough information to answer a question well, ask for the specific data you need."""}
        ]
        
        # Add context to the messages if provided
        if context:
            context_str = json.dumps(context)
            messages.append({
                "role": "system", 
                "content": f"Here is the current data context: {context_str}"
            })
        
        messages.append({"role": "user", "content": query})
        
        response = client.chat.completions.create(
            model=MODEL,
            messages=messages,
            max_tokens=800,
            temperature=0.3,
        )
        
        return response.choices[0].message.content
    except Exception as e:
        return f"Error querying AI assistant: {str(e)}"

def extract_recipe_from_document(file_data, file_type):
    """
    Extract recipe information from uploaded documents using OpenAI
    
    Args:
        file_data (bytes): The uploaded file data
        file_type (str): The type of file ('excel', 'word', or 'text')
    
    Returns:
        dict: Extracted recipe information
    """
    try:
        content = ""
        
        if file_type == 'excel':
            # Read Excel file
            df = pd.read_excel(BytesIO(file_data))
            content = df.to_string()
        elif file_type == 'word':
            # For Word files, we'll send the raw text
            # In a real implementation, you would use a library like python-docx
            content = "Word document content (raw text)"
        else:
            # Text files
            content = file_data.decode('utf-8')
        
        # Send to OpenAI API
        messages = [
            {"role": "system", "content": """You are a recipe extraction expert for a hotel cost control system.
            Extract the following information from the provided document:
            1. Recipe name
            2. List of ingredients with amounts and units
            3. Cost information if available
            4. Preparation instructions if available
            5. Portion size or yield
            
            Format your response as a JSON object with these keys:
            name, ingredients (array of objects with name, amount, unit), preparation_steps,
            yield_amount, yield_unit, and any cost information found.
            
            For each ingredient, try to normalize the units and format consistently."""},
            {"role": "user", "content": f"Extract the recipe information from this document:\n\n{content}"}
        ]
        
        response = client.chat.completions.create(
            model=MODEL,
            messages=messages,
            response_format={"type": "json_object"},
            temperature=0.2,
        )
        
        recipe_data = json.loads(response.choices[0].message.content)
        
        # Add timestamp
        recipe_data['created_at'] = pd.Timestamp.now().isoformat()
        
        return recipe_data
    except Exception as e:
        return {"error": f"Failed to extract recipe: {str(e)}"}

def map_columns_with_ai(sample_data, target_schema):
    """
    Use AI to map columns from uploaded data to the system's schema
    
    Args:
        sample_data (dict): Sample of the uploaded data
        target_schema (dict): The system's schema with required fields
    
    Returns:
        dict: Mapping of source columns to target columns
    """
    try:
        # Convert sample data and schema to string representations
        sample_str = json.dumps(sample_data, indent=2)
        schema_str = json.dumps(target_schema, indent=2)
        
        messages = [
            {"role": "system", "content": """You are a data mapping expert. Your task is to analyze a sample 
            of uploaded data and map its columns to the required schema of our system.
            Provide your response as a JSON object where keys are the target schema fields
            and values are the corresponding column names from the sample data.
            If a required field has no good match in the sample data, use null as the value."""},
            {"role": "user", "content": f"""Here is a sample of the uploaded data:
            {sample_str}
            
            And here is the target schema our system requires:
            {schema_str}
            
            Please create a mapping between the columns in the uploaded data and our target schema fields.
            """}
        ]
        
        response = client.chat.completions.create(
            model=MODEL,
            messages=messages,
            response_format={"type": "json_object"},
            temperature=0.1,
        )
        
        mapping = json.loads(response.choices[0].message.content)
        return mapping
    except Exception as e:
        return {"error": f"Failed to map columns: {str(e)}"}

def analyze_price_changes(old_inventory, new_inventory, recipes):
    """
    Analyze the impact of price changes on recipes
    
    Args:
        old_inventory (list): Previous inventory data
        new_inventory (list): Updated inventory data
        recipes (list): List of recipes
    
    Returns:
        dict: Analysis of price changes and their impact
    """
    try:
        # Convert to string representations for the AI
        old_inv_str = json.dumps(old_inventory[:10], indent=2)  # Limit to 10 items
        new_inv_str = json.dumps(new_inventory[:10], indent=2)  # Limit to 10 items
        recipes_str = json.dumps(recipes[:5], indent=2)  # Limit to 5 recipes
        
        messages = [
            {"role": "system", "content": """You are a cost analysis expert for hotels and restaurants.
            Analyze the provided inventory price changes and their impact on recipes.
            Provide insights on:
            1. Which ingredients have notable price changes (percentage and absolute)
            2. Which recipes are most affected by these changes
            3. Recommendations for menu adjustments or supplier changes
            
            Format your response as a JSON object with the following keys:
            price_changes (array of affected items), affected_recipes (array of affected recipes),
            total_impact (overall cost impact), and recommendations (array of suggestions)."""},
            {"role": "user", "content": f"""Here is the previous inventory data:
            {old_inv_str}
            
            Here is the updated inventory data:
            {new_inv_str}
            
            Here are some of the recipes that might be affected:
            {recipes_str}
            
            Please analyze the price changes and their impact on the recipes.
            """}
        ]
        
        response = client.chat.completions.create(
            model=MODEL,
            messages=messages,
            response_format={"type": "json_object"},
            temperature=0.3,
        )
        
        analysis = json.loads(response.choices[0].message.content)
        return analysis
    except Exception as e:
        return {"error": f"Failed to analyze price changes: {str(e)}"}

def generate_natural_language_report(data, report_type):
    """
    Generate a natural language report from the data
    
    Args:
        data (dict): The data to analyze
        report_type (str): The type of report to generate
    
    Returns:
        str: Natural language report
    """
    try:
        data_str = json.dumps(data, indent=2)
        
        messages = [
            {"role": "system", "content": f"""You are a data analysis expert for hotel cost control.
            Generate a detailed {report_type} report based on the provided data.
            Your report should include:
            1. Key findings and trends
            2. Areas of concern or opportunity
            3. Specific recommendations for improvement
            4. Potential cost-saving measures
            
            Use a professional tone and include specific numbers/percentages when relevant."""},
            {"role": "user", "content": f"""Here is the data to analyze for the {report_type} report:
            {data_str}
            
            Please generate a comprehensive report.
            """}
        ]
        
        response = client.chat.completions.create(
            model=MODEL,
            messages=messages,
            max_tokens=1000,
            temperature=0.4,
        )
        
        return response.choices[0].message.content
    except Exception as e:
        return f"Error generating report: {str(e)}"
