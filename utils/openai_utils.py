import os
import json
import base64
import pandas as pd
import streamlit as st
from openai import OpenAI

# Initialize OpenAI client
api_key = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=api_key)

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
        # Format the prompt
        system_message = "You are an AI assistant for a hotel cost control system."
        
        if context:
            # Convert context data to a readable format
            context_str = json.dumps(context, indent=2)
            user_message = f"Context data:\n{context_str}\n\nUser question: {query}"
        else:
            user_message = query
        
        # Call the OpenAI API
        response = client.chat.completions.create(
            model="gpt-4o",  # the newest OpenAI model is "gpt-4o" which was released May 13, 2024. do not change this unless explicitly requested by the user
            messages=[
                {"role": "system", "content": system_message},
                {"role": "user", "content": user_message}
            ],
            temperature=0.3,  # Lower temperature for more factual responses
            max_tokens=1000   # Limit response length
        )
        
        # Return the AI's response
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
        # Prepare the file data
        if file_type == 'excel':
            # For Excel files, convert to CSV for easier processing
            try:
                # Create a temporary file
                with open('temp_file.xlsx', 'wb') as f:
                    f.write(file_data)
                
                # Read the Excel file
                df = pd.read_excel('temp_file.xlsx')
                
                # Convert to CSV string
                file_content = df.to_csv(index=False)
                
                # Clean up
                if os.path.exists('temp_file.xlsx'):
                    os.remove('temp_file.xlsx')
            except Exception as e:
                return {"error": f"Failed to process Excel file: {str(e)}"}
        elif file_type == 'word':
            # For Word files, we need to extract text
            try:
                # Create a temporary file
                with open('temp_file.docx', 'wb') as f:
                    f.write(file_data)
                
                # Use docx2txt to extract text
                import docx2txt
                file_content = docx2txt.process('temp_file.docx')
                
                # Clean up
                if os.path.exists('temp_file.docx'):
                    os.remove('temp_file.docx')
            except Exception as e:
                return {"error": f"Failed to process Word file: {str(e)}"}
        else:  # text file
            file_content = file_data.decode('utf-8', errors='ignore')
        
        # Call the OpenAI API
        prompt = f"""
        Extract recipe information from the following document content:
        
        {file_content[:4000]}  # Limiting content to avoid token limit
        
        Please extract and structure the following information:
        1. Recipe name
        2. Yield amount (number of servings)
        3. Yield unit (e.g., serving, portion)
        4. Ingredients list with:
           - Ingredient name
           - Amount
           - Unit of measurement
        5. Preparation steps if available
        
        Format your response as a JSON object with the following structure:
        {{
            "name": "Recipe Name",
            "yield_amount": 4,
            "yield_unit": "servings",
            "ingredients": [
                {{
                    "name": "Ingredient 1",
                    "amount": 100,
                    "unit": "g",
                    "cost": 0
                }},
                // More ingredients...
            ],
            "preparation_steps": [
                "Step 1...",
                "Step 2...",
                // More steps...
            ]
        }}
        
        If you cannot extract certain information, use empty values or reasonable defaults.
        """
        
        response = client.chat.completions.create(
            model="gpt-4o",  # the newest OpenAI model is "gpt-4o" which was released May 13, 2024. do not change this unless explicitly requested by the user
            messages=[
                {"role": "system", "content": "You are a specialized recipe extraction assistant."},
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"},
            temperature=0.3
        )
        
        # Parse the JSON response
        recipe_data = json.loads(response.choices[0].message.content)
        
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
        # Convert sample data to a more readable format
        readable_sample = {}
        for col, values in sample_data.items():
            readable_sample[str(col)] = [str(v) for v in list(values.values())[:5]]
        
        # Create a prompt for the AI
        prompt = f"""
        I need to map columns from an uploaded data file to a specific schema.
        
        Here's a sample of the uploaded data:
        {json.dumps(readable_sample, indent=2)}
        
        And here's the target schema I need to map to:
        {json.dumps(target_schema, indent=2)}
        
        For each field in the target schema, identify the most appropriate column from the uploaded data.
        If there's no good match for a field, return null for that field.
        
        Format your response as a JSON object where:
        - Keys are the target schema fields
        - Values are the corresponding column names from the uploaded data
        
        Example response:
        {{
            "target_field1": "source_column_a",
            "target_field2": "source_column_b",
            "target_field3": null
        }}
        """
        
        response = client.chat.completions.create(
            model="gpt-4o",  # the newest OpenAI model is "gpt-4o" which was released May 13, 2024. do not change this unless explicitly requested by the user
            messages=[
                {"role": "system", "content": "You are a data mapping assistant."},
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"},
            temperature=0.3
        )
        
        # Parse the JSON response
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
        # Create inventory dictionaries for easier lookup
        old_prices = {item['name']: item['price'] for item in old_inventory if 'name' in item and 'price' in item}
        new_prices = {item['name']: item['price'] for item in new_inventory if 'name' in item and 'price' in item}
        
        # Find items with price changes
        price_changes = []
        for name, new_price in new_prices.items():
            if name in old_prices:
                old_price = old_prices[name]
                if old_price != new_price:
                    percent_change = ((new_price - old_price) / old_price) * 100
                    price_changes.append({
                        'name': name,
                        'old_price': old_price,
                        'new_price': new_price,
                        'change_percent': round(percent_change, 2)
                    })
        
        # Analyze impact on recipes
        impact = []
        for recipe in recipes:
            recipe_name = recipe.get('name', 'Unnamed Recipe')
            old_cost = 0
            new_cost = 0
            ingredients_affected = []
            
            for ingredient in recipe.get('ingredients', []):
                ing_name = ingredient.get('name', '')
                ing_amount = ingredient.get('amount', 0)
                
                if ing_name in old_prices:
                    old_ingredient_cost = old_prices[ing_name] * ing_amount
                    old_cost += old_ingredient_cost
                
                if ing_name in new_prices:
                    new_ingredient_cost = new_prices[ing_name] * ing_amount
                    new_cost += new_ingredient_cost
                    
                    # Check if this ingredient had a price change
                    if ing_name in old_prices and old_prices[ing_name] != new_prices[ing_name]:
                        percent_change = ((new_prices[ing_name] - old_prices[ing_name]) / old_prices[ing_name]) * 100
                        ingredients_affected.append({
                            'name': ing_name,
                            'old_price': old_prices[ing_name],
                            'new_price': new_prices[ing_name],
                            'change_percent': round(percent_change, 2)
                        })
            
            if old_cost > 0 and ingredients_affected:
                cost_change_percent = ((new_cost - old_cost) / old_cost) * 100
                impact.append({
                    'recipe_name': recipe_name,
                    'old_cost': round(old_cost, 2),
                    'new_cost': round(new_cost, 2),
                    'cost_change_percent': round(cost_change_percent, 2),
                    'ingredients_affected': ingredients_affected
                })
        
        # Create the analysis
        analysis = {
            'price_changes': price_changes,
            'recipe_impact': impact,
            'summary': {
                'items_with_price_changes': len(price_changes),
                'recipes_affected': len(impact),
                'average_price_change_percent': round(sum(item['change_percent'] for item in price_changes) / len(price_changes), 2) if price_changes else 0,
                'average_recipe_cost_change_percent': round(sum(item['cost_change_percent'] for item in impact) / len(impact), 2) if impact else 0
            }
        }
        
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
        # Convert data to a string representation
        data_str = json.dumps(data, indent=2)
        
        # Create a prompt based on the report type
        if report_type == 'price_changes':
            prompt = f"""
            Generate a natural language report analyzing the following price change data:
            
            {data_str}
            
            Your report should cover:
            1. An executive summary of the price changes
            2. The items with the most significant price increases and decreases
            3. The impact on recipe costs
            4. Recommendations for managing costs
            
            Use a professional tone suitable for hotel management.
            """
        elif report_type == 'sales_performance':
            prompt = f"""
            Generate a natural language report analyzing the following sales performance data:
            
            {data_str}
            
            Your report should cover:
            1. An executive summary of sales performance
            2. Top performing menu items and categories
            3. Items that may need attention due to low sales or margins
            4. Seasonal trends if applicable
            5. Recommendations for menu optimization
            
            Use a professional tone suitable for hotel management.
            """
        elif report_type == 'inventory_forecast':
            prompt = f"""
            Generate a natural language report analyzing the following inventory forecast data:
            
            {data_str}
            
            Your report should cover:
            1. An executive summary of inventory needs
            2. Items that need immediate reordering
            3. Projected consumption rates
            4. Recommendations for inventory management
            5. Potential cost-saving opportunities
            
            Use a professional tone suitable for hotel management.
            """
        else:
            prompt = f"""
            Generate a natural language report analyzing the following data:
            
            {data_str}
            
            Your report should provide insights, highlight important trends, and make recommendations based on the data.
            
            Use a professional tone suitable for hotel management.
            """
        
        # Call the OpenAI API
        response = client.chat.completions.create(
            model="gpt-4o",  # the newest OpenAI model is "gpt-4o" which was released May 13, 2024. do not change this unless explicitly requested by the user
            messages=[
                {"role": "system", "content": "You are a hotel cost control analyst specializing in generating insightful reports."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.5,
            max_tokens=1500
        )
        
        # Return the report
        return response.choices[0].message.content
    except Exception as e:
        return f"Error generating report: {str(e)}"