import json
import os
import pandas as pd
import streamlit as st
from datetime import datetime

def load_data(file_path):
    """
    Load data from a JSON file
    
    Args:
        file_path (str): Path to the JSON file
    
    Returns:
        list or dict: The loaded data
    """
    try:
        if os.path.exists(file_path):
            with open(file_path, 'r') as f:
                return json.load(f)
        return []
    except Exception as e:
        st.error(f"Error loading data: {str(e)}")
        return []

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
        
        # Add timestamp to saved data if it's a dictionary
        if isinstance(data, dict) and 'metadata' not in data:
            data['metadata'] = {
                'last_updated': datetime.now().isoformat(),
                'record_count': len(data.get('data', [])) if 'data' in data else 0
            }
        elif isinstance(data, list) and data:
            # If it's a list, we'll wrap it in a dict with metadata
            data = {
                'metadata': {
                    'last_updated': datetime.now().isoformat(),
                    'record_count': len(data)
                },
                'data': data
            }
        
        with open(file_path, 'w') as f:
            json.dump(data, f, indent=2)
        
        st.success(f"Successfully saved data to {file_path}")
        return True
    except Exception as e:
        st.error(f"Error saving data: {str(e)}")
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
        # Save the file to disk temporarily
        file_path = os.path.join('data/uploaded', uploaded_file.name)
        with open(file_path, 'wb') as f:
            f.write(uploaded_file.getbuffer())
        
        # Read the file
        df = pd.read_excel(file_path)
        
        # Process the data based on type
        if data_type == 'recipe':
            processed_data = process_recipe_data(df, column_mapping)
        elif data_type == 'inventory':
            processed_data = process_inventory_data(df, column_mapping)
        elif data_type == 'sales':
            processed_data = process_sales_data(df, column_mapping)
        else:
            return {"error": "Invalid data type"}
        
        return {
            "data": processed_data,
            "status": "success",
            "message": f"Successfully processed {len(processed_data)} {data_type} items"
        }
    except Exception as e:
        return {
            "error": str(e),
            "status": "error",
            "message": f"Error processing file: {str(e)}"
        }

def process_recipe_data(df, column_mapping):
    """
    Process recipe data from a DataFrame
    
    Args:
        df (DataFrame): Recipe data
        column_mapping (dict): Column mapping
    
    Returns:
        list: Processed recipe data
    """
    if column_mapping is None:
        column_mapping = {}
    
    # Default mappings if not provided
    name_col = column_mapping.get('name', 'Name')
    yield_amount_col = column_mapping.get('yield_amount', 'Yield Amount')
    yield_unit_col = column_mapping.get('yield_unit', 'Yield Unit')
    ingredients_col = column_mapping.get('ingredients', 'Ingredients')
    
    recipes = []
    
    # Process each recipe
    for _, row in df.iterrows():
        try:
            recipe = {
                "name": str(row.get(name_col, "")),
                "yield_amount": float(row.get(yield_amount_col, 1)),
                "yield_unit": str(row.get(yield_unit_col, "serving")),
                "ingredients": [],
                "preparation_steps": [],
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat()
            }
            
            # Process ingredients if available
            ingredients_str = str(row.get(ingredients_col, ""))
            if ingredients_str:
                # Split ingredients by newline or comma
                ingredient_list = ingredients_str.split('\n') if '\n' in ingredients_str else ingredients_str.split(',')
                
                for ing_str in ingredient_list:
                    ing_str = ing_str.strip()
                    if not ing_str:
                        continue
                    
                    # Try to parse amount and unit
                    import re
                    match = re.search(r'(\d+\.?\d*)\s*([a-zA-Z]+)', ing_str)
                    
                    if match:
                        amount = float(match.group(1))
                        unit = match.group(2)
                        name = ing_str[match.end():].strip()
                        if not name:
                            name = ing_str[:match.start()].strip()
                    else:
                        # Default values if parsing fails
                        amount = 1
                        unit = "piece"
                        name = ing_str
                    
                    recipe["ingredients"].append({
                        "name": name,
                        "amount": amount,
                        "unit": unit,
                        "cost": 0
                    })
            
            recipes.append(recipe)
        except Exception as e:
            st.warning(f"Error processing recipe row: {str(e)}")
            continue
    
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
    if column_mapping is None:
        column_mapping = {}
    
    # Default mappings if not provided
    item_code_col = column_mapping.get('item_code', 'Item Code')
    name_col = column_mapping.get('name', 'Name')
    category_col = column_mapping.get('category', 'Category')
    price_col = column_mapping.get('price', 'Price')
    unit_col = column_mapping.get('unit', 'Unit')
    supplier_col = column_mapping.get('supplier', 'Supplier')
    stock_level_col = column_mapping.get('stock_level', 'Stock Level')
    
    inventory_items = []
    
    # Process each inventory item
    for _, row in df.iterrows():
        try:
            # Handle NaN values
            item_code = str(row.get(item_code_col, "")) if pd.notna(row.get(item_code_col, "")) else ""
            name = str(row.get(name_col, "")) if pd.notna(row.get(name_col, "")) else ""
            category = str(row.get(category_col, "")) if pd.notna(row.get(category_col, "")) else ""
            unit = str(row.get(unit_col, "")) if pd.notna(row.get(unit_col, "")) else ""
            supplier = str(row.get(supplier_col, "")) if pd.notna(row.get(supplier_col, "")) else ""
            
            # Convert price and stock level to float
            try:
                price = float(row.get(price_col, 0))
            except:
                price = 0
                
            try:
                stock_level = float(row.get(stock_level_col, 0))
            except:
                stock_level = 0
            
            # Skip empty rows
            if not name:
                continue
            
            # Generate item code if missing
            if not item_code:
                item_code = f"ITEM{len(inventory_items) + 1:04d}"
            
            inventory_items.append({
                "item_code": item_code,
                "name": name,
                "category": category,
                "price": price,
                "unit": unit,
                "supplier": supplier,
                "stock_level": stock_level,
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat(),
                "price_history": [],
                "stock_history": []
            })
        except Exception as e:
            st.warning(f"Error processing inventory row: {str(e)}")
            continue
    
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
    if column_mapping is None:
        column_mapping = {}
    
    # Default mappings if not provided
    date_col = column_mapping.get('date', 'Date')
    item_name_col = column_mapping.get('item_name', 'Item Name')
    quantity_col = column_mapping.get('quantity', 'Quantity')
    revenue_col = column_mapping.get('revenue', 'Revenue')
    cost_col = column_mapping.get('cost', 'Cost')
    
    sales_records = []
    
    # Process each sales record
    for _, row in df.iterrows():
        try:
            # Handle date
            try:
                date_value = row.get(date_col, datetime.now())
                if pd.isna(date_value):
                    date = datetime.now().isoformat()
                else:
                    date = pd.Timestamp(date_value).isoformat()
            except:
                date = datetime.now().isoformat()
            
            # Handle item name
            item_name = str(row.get(item_name_col, "")) if pd.notna(row.get(item_name_col, "")) else ""
            
            # Convert numeric values
            try:
                quantity = float(row.get(quantity_col, 0))
            except:
                quantity = 0
                
            try:
                revenue = float(row.get(revenue_col, 0))
            except:
                revenue = 0
                
            try:
                cost = float(row.get(cost_col, 0))
            except:
                cost = 0
            
            # Skip empty rows
            if not item_name or quantity == 0:
                continue
            
            # Calculate profit metrics
            profit = revenue - cost
            profit_margin = (profit / revenue) * 100 if revenue > 0 else 0
            
            sales_records.append({
                "date": date,
                "item_name": item_name,
                "quantity": quantity,
                "revenue": revenue,
                "cost": cost,
                "profit": profit,
                "profit_margin": profit_margin,
                "imported_at": datetime.now().isoformat()
            })
        except Exception as e:
            st.warning(f"Error processing sales row: {str(e)}")
            continue
    
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
    # Create a dictionary of inventory items for quick lookup
    inventory_dict = {item["name"].lower(): item for item in inventory}
    
    total_cost = 0
    
    # Process each ingredient
    for ingredient in recipe.get("ingredients", []):
        ingredient_name = ingredient.get("name", "").lower()
        ingredient_amount = ingredient.get("amount", 0)
        
        # Look for exact match
        if ingredient_name in inventory_dict:
            item = inventory_dict[ingredient_name]
            price = item.get("price", 0)
            ingredient_cost = price * ingredient_amount
            
            # Update ingredient cost
            ingredient["cost"] = ingredient_cost
            total_cost += ingredient_cost
        else:
            # Look for fuzzy match
            best_match = None
            best_score = 0
            
            for inv_name, item in inventory_dict.items():
                # Simple similarity score
                if ingredient_name in inv_name or inv_name in ingredient_name:
                    score = len(set(ingredient_name) & set(inv_name)) / len(set(ingredient_name) | set(inv_name))
                    if score > best_score:
                        best_score = score
                        best_match = item
            
            if best_match and best_score > 0.6:  # Threshold for fuzzy matching
                price = best_match.get("price", 0)
                ingredient_cost = price * ingredient_amount
                
                # Update ingredient cost
                ingredient["cost"] = ingredient_cost
                total_cost += ingredient_cost
    
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
    # Define system fields based on data type
    if data_type == 'recipe':
        system_fields = [
            "name",
            "yield_amount",
            "yield_unit",
            "ingredients",
            "preparation_steps"
        ]
    elif data_type == 'inventory':
        system_fields = [
            "item_code",
            "name",
            "category",
            "price",
            "unit",
            "supplier",
            "stock_level"
        ]
    elif data_type == 'sales':
        system_fields = [
            "date",
            "item_name",
            "quantity",
            "revenue",
            "cost"
        ]
    else:
        st.error("Invalid data type")
        return {}
    
    # Get Excel file columns
    file_columns = list(df.columns)
    file_columns.insert(0, "None")  # Add option for no mapping
    
    st.subheader("Map Columns")
    st.write("Map columns from your file to our system fields")
    
    # Create mapping UI
    mapping = {}
    for field in system_fields:
        # Try to find a match automatically
        default_index = 0
        for i, col in enumerate(file_columns):
            if field.lower() in str(col).lower():
                default_index = i
                break
        
        # Let user select mapping
        selected_column = st.selectbox(
            f"Map '{field}' to:",
            file_columns,
            index=default_index,
            key=f"mapping_{field}"
        )
        
        if selected_column != "None":
            mapping[field] = selected_column
    
    return mapping