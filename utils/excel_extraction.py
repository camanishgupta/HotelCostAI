import pandas as pd
import os
import json
import re
import streamlit as st
from datetime import datetime
from utils.openai_utils import extract_recipe_from_document, map_columns_with_ai
from models.recipe import Recipe
from models.inventory import InventoryItem
from models.sales import SalesRecord

def safe_read_excel(file_path, sheet_name=0):
    """
    Safely read Excel files that might have encoding issues
    
    Args:
        file_path (str): Path to the Excel file
        sheet_name (int or str): Sheet to read
        
    Returns:
        DataFrame: The Excel data as a DataFrame
    """
    try:
        # First try normal read
        return pd.read_excel(file_path, sheet_name=sheet_name)
    except:
        # If that fails, try with xlrd engine for xls files
        try:
            return pd.read_excel(file_path, sheet_name=sheet_name, engine='xlrd')
        except:
            # If that fails too, try with openpyxl engine for xlsx files
            try:
                return pd.read_excel(file_path, sheet_name=sheet_name, engine='openpyxl')
            except Exception as e:
                st.error(f"Failed to read Excel file: {str(e)}")
                return None

def detect_file_type(file_path):
    """
    Determine what type of data a file contains
    
    Args:
        file_path (str): Path to the file
        
    Returns:
        str: Type of data ('recipe', 'inventory', 'sales', 'unknown')
    """
    # Sample the file to determine content
    try:
        df = safe_read_excel(file_path)
        if df is None:
            return "unknown"
            
        # Convert columns to string
        columns = [str(col).lower() for col in df.columns]
        
        # Look for signals of each type
        # Recipe signals
        recipe_signals = ['recipe', 'ingredient', 'dish', 'menu', 'yield', 'portion']
        # Inventory signals
        inventory_signals = ['inventory', 'stock', 'item', 'price', 'supplier', 'unit', 'quantity', 'store']
        # Sales signals
        sales_signals = ['sale', 'revenue', 'sold', 'quantity', 'transaction', 'income', 'date']
        
        # Count signals
        recipe_count = sum(1 for signal in recipe_signals if any(signal in col for col in columns))
        inventory_count = sum(1 for signal in inventory_signals if any(signal in col for col in columns))
        sales_count = sum(1 for signal in sales_signals if any(signal in col for col in columns))
        
        # Determine type based on highest signal count
        max_count = max(recipe_count, inventory_count, sales_count)
        
        if max_count == 0:
            # Check filename as fallback
            filename = os.path.basename(file_path).lower()
            if any(signal in filename for signal in recipe_signals):
                return "recipe"
            if any(signal in filename for signal in inventory_signals):
                return "inventory"
            if any(signal in filename for signal in sales_signals):
                return "sales"
            return "unknown"
            
        if recipe_count == max_count:
            return "recipe"
        if inventory_count == max_count:
            return "inventory"
        if sales_count == max_count:
            return "sales"
            
        return "unknown"
    except Exception as e:
        st.error(f"Error detecting file type: {str(e)}")
        return "unknown"

def extract_recipes_from_excel(file_path):
    """
    Extract recipe information from an Excel file
    
    Args:
        file_path (str): Path to the Excel file
        
    Returns:
        list: Extracted recipes
    """
    try:
        # Read the Excel file
        df = safe_read_excel(file_path)
        if df is None:
            return []
            
        # Get sheet names in case we need to look at multiple sheets
        try:
            excel_file = pd.ExcelFile(file_path)
            sheets = excel_file.sheet_names
        except:
            sheets = [0]  # Just use the first sheet if we can't get names
        
        recipes = []
        
        # Process each sheet
        for sheet in sheets:
            try:
                sheet_df = safe_read_excel(file_path, sheet_name=sheet)
                if sheet_df is None or sheet_df.empty:
                    continue
                    
                # For each potential recipe table in the sheet
                # This is a bit complex as recipe formats vary widely
                # We'll try a few approaches
                
                # Approach 1: Look for structured tables with clear recipe headers
                for i in range(len(sheet_df)):
                    row = sheet_df.iloc[i]
                    # Look for rows that might indicate a recipe start
                    if any(str(val).lower().strip() in ['recipe', 'dish', 'item', 'menu item'] 
                           for val in row.values if isinstance(val, str)):
                        # Extract this potential recipe and add to our list
                        recipe_data = extract_single_recipe(sheet_df, start_row=i)
                        if recipe_data:
                            recipes.append(recipe_data)
                
                # Approach 2: If we didn't find structured recipes, try using AI extraction
                if not recipes:
                    # Convert to bytes for AI processing
                    buffer = pd.ExcelWriter('temp.xlsx', engine='xlsxwriter')
                    sheet_df.to_excel(buffer)
                    buffer.save()
                    with open('temp.xlsx', 'rb') as f:
                        file_bytes = f.read()
                    
                    # Use AI to extract recipes
                    extracted = extract_recipe_from_document(file_bytes, 'excel')
                    if not isinstance(extracted, dict) or "error" in extracted:
                        continue
                        
                    recipes.append(extracted)
                    
                    # Clean up temp file
                    if os.path.exists('temp.xlsx'):
                        os.remove('temp.xlsx')
                        
            except Exception as e:
                st.warning(f"Error processing sheet {sheet}: {str(e)}")
                continue
        
        return recipes
    except Exception as e:
        st.error(f"Error extracting recipes: {str(e)}")
        return []

def extract_single_recipe(df, start_row=0):
    """
    Extract a single recipe from a dataframe starting at a particular row
    
    Args:
        df (DataFrame): The dataframe containing recipe data
        start_row (int): Row index to start extraction from
        
    Returns:
        dict: Extracted recipe data
    """
    try:
        # Look for recipe name
        recipe_name = None
        for i in range(start_row, min(start_row + 5, len(df))):
            row = df.iloc[i]
            for val in row.values:
                if isinstance(val, str) and len(val.strip()) > 0:
                    # If this isn't a header row descriptor
                    if val.lower() not in ['recipe', 'dish', 'item', 'menu item', 'name']:
                        recipe_name = val.strip()
                        break
            if recipe_name:
                break
                
        if not recipe_name:
            recipe_name = f"Unnamed Recipe {start_row}"
            
        # Look for yield information
        yield_amount = 1
        yield_unit = "serving"
        for i in range(start_row, min(start_row + 10, len(df))):
            row = df.iloc[i]
            row_str = ' '.join(str(val) for val in row.values if not pd.isna(val))
            if 'yield' in row_str.lower() or 'portion' in row_str.lower() or 'serves' in row_str.lower():
                # Extract numbers
                numbers = re.findall(r'\d+\.?\d*', row_str)
                if numbers:
                    try:
                        yield_amount = float(numbers[0])
                    except:
                        pass
                
                # Extract unit
                for unit in ['portion', 'serving', 'person', 'people', 'pax', 'plate']:
                    if unit in row_str.lower():
                        yield_unit = unit
                        break
                
        # Extract ingredients
        ingredients = []
        ingredient_started = False
        for i in range(start_row, len(df)):
            row = df.iloc[i]
            row_str = ' '.join(str(val) for val in row.values if not pd.isna(val))
            
            # Look for ingredients section start
            if not ingredient_started:
                if 'ingredient' in row_str.lower():
                    ingredient_started = True
                    continue
            
            # If we've started ingredients section, extract ingredients
            if ingredient_started:
                # Check if this row looks like an ingredient entry
                # Typically ingredients have a quantity, unit, and name
                if len(row_str.strip()) > 0 and not any(header in row_str.lower() for header in 
                                                       ['preparation', 'method', 'instruction', 'direction', 'step']):
                    # Try to parse as ingredient
                    ing_data = parse_ingredient_row(row_str)
                    if ing_data:
                        ingredients.append(ing_data)
                # Check if we've reached the end of ingredients section
                elif any(header in row_str.lower() for header in 
                       ['preparation', 'method', 'instruction', 'direction', 'step']):
                    break
        
        # If we didn't find explicit ingredients section, try a more general approach
        if not ingredients:
            for i in range(start_row, len(df)):
                row = df.iloc[i]
                # Look for rows that resemble ingredients (have numbers followed by units)
                row_str = ' '.join(str(val) for val in row.values if not pd.isna(val))
                if re.search(r'\d+\.?\d*\s*(g|kg|ml|l|tbsp|tsp|cup|oz|lb|piece|pcs)', row_str.lower()):
                    ing_data = parse_ingredient_row(row_str)
                    if ing_data:
                        ingredients.append(ing_data)
        
        # Create recipe object
        recipe = {
            "name": recipe_name,
            "ingredients": ingredients,
            "yield_amount": yield_amount,
            "yield_unit": yield_unit,
            "preparation_steps": [],
            "created_at": datetime.now().isoformat()
        }
        
        return recipe
    except Exception as e:
        st.error(f"Error extracting single recipe: {str(e)}")
        return None

def parse_ingredient_row(row_str):
    """
    Parse an ingredient row into name, amount, and unit
    
    Args:
        row_str (str): String representing an ingredient row
        
    Returns:
        dict: Ingredient data with name, amount, and unit
    """
    try:
        # Look for a number followed by a unit
        match = re.search(r'(\d+\.?\d*)\s*(g|kg|ml|l|tbsp|tsp|cup|oz|lb|piece|pcs|whole|clove|slice|bunch)', 
                          row_str.lower())
        
        if match:
            amount = float(match.group(1))
            unit = match.group(2)
            
            # Extract name - usually everything after the quantity and unit
            name_part = row_str[match.end():].strip()
            # If no text after unit, use everything before as name
            if not name_part:
                name_part = row_str[:match.start()].strip()
            
            # Clean up name
            name = re.sub(r'^\W+|\W+$', '', name_part)  # Remove leading/trailing non-word chars
            
            return {
                "name": name,
                "amount": amount,
                "unit": unit,
                "cost": 0.0  # We don't have cost info from the Excel usually
            }
        
        # If no match for standard format, try other patterns
        # Check for just a number at the start
        match = re.search(r'^(\d+\.?\d*)\s+(.+)$', row_str.strip())
        if match:
            amount = float(match.group(1))
            # Assume the unit is included in the text
            rest = match.group(2)
            
            # Try to extract unit from the text
            unit_match = re.search(r'^(g|kg|ml|l|tbsp|tsp|cup|oz|lb|piece|pcs|whole|clove|slice|bunch)\s+(.+)$', 
                                  rest.lower())
            
            if unit_match:
                unit = unit_match.group(1)
                name = unit_match.group(2)
            else:
                # Default to "piece" if no unit found
                unit = "piece"
                name = rest
                
            return {
                "name": name,
                "amount": amount,
                "unit": unit,
                "cost": 0.0
            }
        
        # If still no match but the string has reasonable length, assume it's an ingredient with default values
        if len(row_str.strip()) > 3 and not any(x in row_str.lower() for x in ['step', 'method', 'note']):
            return {
                "name": row_str.strip(),
                "amount": 1.0,
                "unit": "piece",
                "cost": 0.0
            }
            
        return None
    except:
        return None

def extract_inventory_from_excel(file_path):
    """
    Extract inventory information from an Excel file
    
    Args:
        file_path (str): Path to the Excel file
        
    Returns:
        list: Extracted inventory items
    """
    try:
        # Read the Excel file
        df = safe_read_excel(file_path)
        if df is None or df.empty:
            return []
            
        # Try to determine the structure
        columns = [str(col).lower() for col in df.columns]
        
        # Define target fields and potential column matches
        field_matches = {
            'item_code': ['item code', 'code', 'sku', 'id', 'item id', 'product code', 'product id'],
            'name': ['name', 'item name', 'product name', 'description', 'item description'],
            'category': ['category', 'group', 'department', 'type', 'item type', 'item group'],
            'price': ['price', 'cost', 'unit price', 'unit cost', 'price per unit', 'rate'],
            'unit': ['unit', 'uom', 'measure', 'unit of measure', 'unit of measurement'],
            'supplier': ['supplier', 'vendor', 'source', 'manufacturer'],
            'stock_level': ['stock', 'quantity', 'on hand', 'level', 'balance', 'inventory', 'qty', 'stock level']
        }
        
        # Create mapping of our fields to Excel columns
        mapping = {}
        for our_field, possible_matches in field_matches.items():
            for i, col in enumerate(columns):
                if any(match in col for match in possible_matches):
                    mapping[our_field] = df.columns[i]
                    break
        
        # If we couldn't map critical fields, try AI mapping
        if 'name' not in mapping or ('price' not in mapping and 'stock_level' not in mapping):
            # Convert to dict for AI processing
            sample_data = df.head(5).to_dict()
            target_schema = {
                'item_code': 'Item code or SKU',
                'name': 'Item name',
                'category': 'Category',
                'price': 'Price per unit',
                'unit': 'Unit of measure',
                'supplier': 'Supplier name',
                'stock_level': 'Current stock level'
            }
            
            ai_mapping = map_columns_with_ai(sample_data, target_schema)
            if "error" not in ai_mapping:
                # Convert AI mapping to our format
                for our_field, excel_col in ai_mapping.items():
                    if excel_col is not None:
                        mapping[our_field] = excel_col
        
        # Process the data using the mapping
        inventory_items = []
        
        for _, row in df.iterrows():
            item = InventoryItem()
            
            # Extract mapped fields
            for our_field, excel_col in mapping.items():
                if excel_col in row:
                    value = row[excel_col]
                    
                    # Handle NaN
                    if pd.isna(value):
                        continue
                    
                    # Convert to appropriate type
                    if our_field in ['price', 'stock_level']:
                        try:
                            value = float(value)
                        except:
                            continue
                    else:
                        value = str(value)
                    
                    # Set attribute
                    setattr(item, our_field, value)
            
            # Skip if no name or both price and stock are missing
            if not item.name or (item.price == 0 and item.stock_level == 0):
                continue
                
            # Generate item code if missing
            if not item.item_code:
                item.item_code = f"ITEM{len(inventory_items) + 1}"
                
            # Set default category if missing
            if not item.category:
                item.category = "Uncategorized"
                
            # Set default unit if missing
            if not item.unit:
                item.unit = "each"
                
            # Set timestamp
            item.created_at = datetime.now().isoformat()
            item.updated_at = datetime.now().isoformat()
            
            # Add to list
            inventory_items.append(item.to_dict())
        
        return inventory_items
    except Exception as e:
        st.error(f"Error extracting inventory: {str(e)}")
        return []

def extract_sales_from_excel(file_path):
    """
    Extract sales information from an Excel file
    
    Args:
        file_path (str): Path to the Excel file
        
    Returns:
        list: Extracted sales records
    """
    try:
        # Read the Excel file
        df = safe_read_excel(file_path)
        if df is None or df.empty:
            return []
            
        # Try to determine the structure
        columns = [str(col).lower() for col in df.columns]
        
        # Define target fields and potential column matches
        field_matches = {
            'date': ['date', 'sale date', 'transaction date', 'order date', 'day'],
            'item_name': ['item', 'product', 'name', 'description', 'item name', 'product name'],
            'quantity': ['quantity', 'qty', 'amount', 'volume', 'count', 'sold', 'units sold'],
            'revenue': ['revenue', 'sales', 'amount', 'total', 'price', 'total price', 'sales amount', 'income'],
            'cost': ['cost', 'cogs', 'cost of goods', 'expense', 'total cost']
        }
        
        # Create mapping of our fields to Excel columns
        mapping = {}
        for our_field, possible_matches in field_matches.items():
            for i, col in enumerate(columns):
                if any(match in col for match in possible_matches):
                    mapping[our_field] = df.columns[i]
                    break
        
        # If we couldn't map critical fields, try AI mapping
        if 'item_name' not in mapping or 'quantity' not in mapping:
            # Convert to dict for AI processing
            sample_data = df.head(5).to_dict()
            target_schema = {
                'date': 'Sale date',
                'item_name': 'Item name',
                'quantity': 'Quantity sold',
                'revenue': 'Revenue amount',
                'cost': 'Cost amount'
            }
            
            ai_mapping = map_columns_with_ai(sample_data, target_schema)
            if "error" not in ai_mapping:
                # Convert AI mapping to our format
                for our_field, excel_col in ai_mapping.items():
                    if excel_col is not None:
                        mapping[our_field] = excel_col
        
        # Process the data using the mapping
        sales_records = []
        
        for _, row in df.iterrows():
            record = SalesRecord()
            
            # Extract mapped fields
            for our_field, excel_col in mapping.items():
                if excel_col in row:
                    value = row[excel_col]
                    
                    # Handle NaN
                    if pd.isna(value):
                        continue
                    
                    # Convert to appropriate type
                    if our_field == 'date':
                        try:
                            if isinstance(value, str):
                                # Try different date formats
                                for fmt in ['%Y-%m-%d', '%m/%d/%Y', '%d/%m/%Y', '%d-%m-%Y', '%Y/%m/%d']:
                                    try:
                                        value = datetime.strptime(value, fmt).isoformat()
                                        break
                                    except:
                                        pass
                            else:
                                # Assume pandas converted it to datetime or Timestamp
                                value = pd.Timestamp(value).isoformat()
                        except:
                            value = datetime.now().isoformat()
                    elif our_field in ['quantity', 'revenue', 'cost']:
                        try:
                            value = float(value)
                        except:
                            continue
                    else:
                        value = str(value)
                    
                    # Set attribute
                    setattr(record, our_field, value)
            
            # Skip if no item name or quantity
            if not record.item_name or record.quantity == 0:
                continue
                
            # If revenue is missing but we have quantity, estimate it
            if record.revenue == 0 and record.quantity > 0:
                # Assume a default revenue per item
                record.revenue = record.quantity * 10.0
                
            # If cost is missing but we have revenue, estimate it
            if record.cost == 0 and record.revenue > 0:
                # Assume a standard profit margin of 70%
                record.cost = record.revenue * 0.3
                
            # Recalculate profit fields
            record.profit = record.revenue - record.cost
            record.profit_margin = (record.profit / record.revenue) * 100 if record.revenue > 0 else 0
            
            # Set timestamp
            record.imported_at = datetime.now().isoformat()
            
            # Add to list
            sales_records.append(record.to_dict())
        
        return sales_records
    except Exception as e:
        st.error(f"Error extracting sales: {str(e)}")
        return []

def batch_process_directory(directory):
    """
    Process all Excel files in a directory
    
    Args:
        directory (str): Directory path
        
    Returns:
        dict: Results of processing
    """
    results = {
        'recipes': [],
        'inventory': [],
        'sales': [],
        'errors': []
    }
    
    try:
        # Get all Excel files in the directory
        files = [os.path.join(directory, f) for f in os.listdir(directory) 
                 if f.endswith('.xlsx') or f.endswith('.xls')]
                 
        for file_path in files:
            try:
                # Detect file type
                file_type = detect_file_type(file_path)
                
                # Process based on type
                if file_type == 'recipe':
                    recipes = extract_recipes_from_excel(file_path)
                    results['recipes'].extend(recipes)
                elif file_type == 'inventory':
                    inventory = extract_inventory_from_excel(file_path)
                    results['inventory'].extend(inventory)
                elif file_type == 'sales':
                    sales = extract_sales_from_excel(file_path)
                    results['sales'].extend(sales)
                else:
                    # If type is unknown, try all extractors
                    recipes = extract_recipes_from_excel(file_path)
                    if recipes:
                        results['recipes'].extend(recipes)
                        continue
                        
                    inventory = extract_inventory_from_excel(file_path)
                    if inventory:
                        results['inventory'].extend(inventory)
                        continue
                        
                    sales = extract_sales_from_excel(file_path)
                    if sales:
                        results['sales'].extend(sales)
                        continue
                        
                    results['errors'].append(f"Could not determine data type for {file_path}")
            except Exception as e:
                results['errors'].append(f"Error processing {file_path}: {str(e)}")
        
        return results
    except Exception as e:
        results['errors'].append(f"Error processing directory: {str(e)}")
        return results