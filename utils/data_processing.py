import pandas as pd
import numpy as np
import json
import os
from datetime import datetime
import streamlit as st
from io import BytesIO
from utils.openai_utils import map_columns_with_ai

def load_data(file_path):
    """
    Load data from a JSON file
    
    Args:
        file_path (str): Path to the JSON file
    
    Returns:
        list or dict: The loaded data
    """
    try:
        if not os.path.exists(file_path):
            if file_path.endswith('.json'):
                return [] if 'recipes' in file_path or 'inventory' in file_path or 'sales' in file_path else {}
        
        with open(file_path, 'r') as f:
            return json.load(f)
    except Exception as e:
        st.error(f"Error loading data from {file_path}: {str(e)}")
        return [] if 'recipes' in file_path or 'inventory' in file_path or 'sales' in file_path else {}

def save_data(data, file_path):
    """
    Save data to a JSON file
    
    Args:
        data (list or dict): The data to save
        file_path (str): Path to the JSON file
    
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # Create directory if it doesn't exist
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        
        with open(file_path, 'w') as f:
            json.dump(data, f, indent=2)
        return True
    except Exception as e:
        st.error(f"Error saving data to {file_path}: {str(e)}")
        return False

def process_excel_upload(uploaded_file, data_type, column_mapping=None):
    """
    Process an uploaded Excel file
    
    Args:
        uploaded_file (UploadedFile): The uploaded Excel file
        data_type (str): Type of data ('recipe', 'inventory', 'sales')
        column_mapping (dict, optional): Mapping of columns from file to system
    
    Returns:
        dict: Processed data and status information
    """
    try:
        # Read the Excel file
        df = pd.read_excel(uploaded_file)
        
        # If no mapping is provided, try to use a saved mapping or create a new one
        if column_mapping is None:
            # Define target schemas for different data types
            target_schemas = {
                'recipe': {
                    'name': 'Recipe name',
                    'ingredients': 'List of ingredients',
                    'yield_amount': 'Yield amount',
                    'yield_unit': 'Yield unit'
                },
                'inventory': {
                    'item_code': 'Item code or SKU',
                    'name': 'Item name',
                    'category': 'Category',
                    'price': 'Price per unit',
                    'unit': 'Unit of measure',
                    'supplier': 'Supplier name',
                    'stock_level': 'Current stock level'
                },
                'sales': {
                    'date': 'Sale date',
                    'item_name': 'Item name',
                    'quantity': 'Quantity sold',
                    'revenue': 'Revenue amount',
                    'cost': 'Cost amount'
                }
            }
            
            # Get the target schema for this data type
            schema = target_schemas.get(data_type, {})
            
            # Use AI to map columns
            sample_data = df.head(5).to_dict()
            column_mapping = map_columns_with_ai(sample_data, schema)
            
            if "error" in column_mapping:
                return {"status": "error", "message": column_mapping["error"]}
        
        # Process the data based on type
        if data_type == 'recipe':
            processed_data = process_recipe_data(df, column_mapping)
        elif data_type == 'inventory':
            processed_data = process_inventory_data(df, column_mapping)
        elif data_type == 'sales':
            processed_data = process_sales_data(df, column_mapping)
        else:
            return {"status": "error", "message": f"Unknown data type: {data_type}"}
        
        return {
            "status": "success",
            "data": processed_data,
            "mapping": column_mapping
        }
    except Exception as e:
        return {"status": "error", "message": f"Error processing file: {str(e)}"}

def process_recipe_data(df, column_mapping):
    """
    Process recipe data from a DataFrame
    
    Args:
        df (DataFrame): Recipe data
        column_mapping (dict): Column mapping
    
    Returns:
        list: Processed recipe data
    """
    recipes = []
    
    # Reverse the mapping to go from system field to file column
    rev_mapping = {v: k for k, v in column_mapping.items() if v is not None}
    
    for _, row in df.iterrows():
        recipe = {
            "name": row[rev_mapping.get('name')] if 'name' in rev_mapping else "Unnamed Recipe",
            "ingredients": [],
            "yield_amount": row[rev_mapping.get('yield_amount')] if 'yield_amount' in rev_mapping else 1,
            "yield_unit": row[rev_mapping.get('yield_unit')] if 'yield_unit' in rev_mapping else "serving",
            "created_at": datetime.now().isoformat()
        }
        
        # Process ingredients if available
        if 'ingredients' in rev_mapping:
            ingredients_str = row[rev_mapping['ingredients']]
            # Simple parsing of ingredients (in a real app, this would be more sophisticated)
            ingredients_list = ingredients_str.split(',')
            for ing in ingredients_list:
                parts = ing.strip().split()
                if len(parts) >= 2:
                    amount = parts[0]
                    unit = parts[1]
                    name = ' '.join(parts[2:])
                    recipe["ingredients"].append({
                        "name": name,
                        "amount": amount,
                        "unit": unit
                    })
        
        recipes.append(recipe)
    
    return recipes

def process_inventory_data(df, column_mapping):
    """
    Process inventory data from a DataFrame
    
    Args:
        df (DataFrame): Inventory data
        column_mapping (dict): Column mapping
    
    Returns:
        list: Processed inventory data
    """
    inventory_items = []
    
    # Reverse the mapping to go from system field to file column
    rev_mapping = {v: k for k, v in column_mapping.items() if v is not None}
    
    for _, row in df.iterrows():
        item = {
            "item_code": row[rev_mapping.get('item_code')] if 'item_code' in rev_mapping else f"ITEM{len(inventory_items)+1}",
            "name": row[rev_mapping.get('name')] if 'name' in rev_mapping else "Unnamed Item",
            "category": row[rev_mapping.get('category')] if 'category' in rev_mapping else "Uncategorized",
            "price": float(row[rev_mapping.get('price')]) if 'price' in rev_mapping else 0.0,
            "unit": row[rev_mapping.get('unit')] if 'unit' in rev_mapping else "unit",
            "supplier": row[rev_mapping.get('supplier')] if 'supplier' in rev_mapping else "Unknown",
            "stock_level": float(row[rev_mapping.get('stock_level')]) if 'stock_level' in rev_mapping else 0.0,
            "updated_at": datetime.now().isoformat()
        }
        
        inventory_items.append(item)
    
    return inventory_items

def process_sales_data(df, column_mapping):
    """
    Process sales data from a DataFrame
    
    Args:
        df (DataFrame): Sales data
        column_mapping (dict): Column mapping
    
    Returns:
        list: Processed sales data
    """
    sales_records = []
    
    # Reverse the mapping to go from system field to file column
    rev_mapping = {v: k for k, v in column_mapping.items() if v is not None}
    
    for _, row in df.iterrows():
        record = {
            "date": row[rev_mapping.get('date')].isoformat() if 'date' in rev_mapping and pd.notna(row[rev_mapping.get('date')]) else datetime.now().isoformat(),
            "item_name": row[rev_mapping.get('item_name')] if 'item_name' in rev_mapping else "Unknown Item",
            "quantity": float(row[rev_mapping.get('quantity')]) if 'quantity' in rev_mapping else 0,
            "revenue": float(row[rev_mapping.get('revenue')]) if 'revenue' in rev_mapping else 0.0,
            "cost": float(row[rev_mapping.get('cost')]) if 'cost' in rev_mapping else 0.0,
            "imported_at": datetime.now().isoformat()
        }
        
        sales_records.append(record)
    
    return sales_records

def calculate_recipe_cost(recipe, inventory):
    """
    Calculate the cost of a recipe based on inventory prices
    
    Args:
        recipe (dict): Recipe data
        inventory (list): Inventory data
    
    Returns:
        float: Total cost of the recipe
    """
    total_cost = 0.0
    
    # Create a lookup dict for inventory items
    inventory_dict = {item['name'].lower(): item for item in inventory}
    
    # Add alternative lookup by item code
    for item in inventory:
        inventory_dict[item['item_code'].lower()] = item
    
    # Calculate cost for each ingredient
    for ingredient in recipe.get('ingredients', []):
        ingredient_name = ingredient['name'].lower()
        ingredient_amount = float(ingredient['amount'])
        ingredient_unit = ingredient['unit'].lower()
        
        # Try to find the ingredient in inventory
        inventory_item = inventory_dict.get(ingredient_name)
        
        if inventory_item:
            # Check if units match
            if inventory_item['unit'].lower() == ingredient_unit:
                # Direct calculation
                ingredient_cost = ingredient_amount * float(inventory_item['price'])
            else:
                # Unit conversion would be needed here
                # For simplicity, we'll use a 1:1 conversion
                ingredient_cost = ingredient_amount * float(inventory_item['price'])
                ingredient['unit_mismatch'] = True
            
            ingredient['cost'] = ingredient_cost
            total_cost += ingredient_cost
        else:
            # Ingredient not found in inventory
            ingredient['missing'] = True
            ingredient['cost'] = 0.0
    
    return total_cost

def generate_column_mapping_ui(df, data_type):
    """
    Generate a UI for mapping columns from an uploaded file to system fields
    
    Args:
        df (DataFrame): The uploaded data
        data_type (str): Type of data ('recipe', 'inventory', 'sales')
    
    Returns:
        dict: User-selected column mapping
    """
    # Define the fields needed for each data type
    field_definitions = {
        'recipe': {
            'name': 'Recipe name',
            'ingredients': 'List of ingredients',
            'yield_amount': 'Yield amount',
            'yield_unit': 'Yield unit'
        },
        'inventory': {
            'item_code': 'Item code or SKU',
            'name': 'Item name',
            'category': 'Category',
            'price': 'Price per unit',
            'unit': 'Unit of measure',
            'supplier': 'Supplier name',
            'stock_level': 'Current stock level'
        },
        'sales': {
            'date': 'Sale date',
            'item_name': 'Item name',
            'quantity': 'Quantity sold',
            'revenue': 'Revenue amount',
            'cost': 'Cost amount'
        }
    }
    
    # Use the appropriate field set
    fields = field_definitions.get(data_type, {})
    
    st.subheader("Map Columns")
    st.markdown("Please map the columns from your file to our system fields.")
    
    # Get the column names from the DataFrame
    columns = list(df.columns)
    columns.insert(0, "-- Not mapped --")
    
    # Create the mapping
    mapping = {}
    for field, description in fields.items():
        # Try to find a good default by looking for similar column names
        default_idx = 0
        for i, col in enumerate(columns):
            if field.lower() in col.lower() or col.lower() in field.lower():
                default_idx = i
                break
        
        # Let the user select the mapping
        selected = st.selectbox(
            f"{description} ({field})",
            columns,
            index=default_idx,
            key=f"map_{field}"
        )
        
        # Add to mapping if not the "Not mapped" option
        if selected != "-- Not mapped --":
            mapping[field] = selected
        else:
            mapping[field] = None
    
    return mapping
