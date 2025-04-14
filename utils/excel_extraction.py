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
        # Try different engines and handle various issues
        engines = ['openpyxl', 'xlrd']
        
        for engine in engines:
            try:
                # For xlsx files, openpyxl is preferred
                if file_path.endswith('.xlsx') and engine == 'openpyxl':
                    return pd.read_excel(file_path, sheet_name=sheet_name, engine=engine)
                
                # For xls files, xlrd is preferred
                if file_path.endswith('.xls') and engine == 'xlrd':
                    return pd.read_excel(file_path, sheet_name=sheet_name, engine=engine)
                
                # Try anyway as fallback
                try:
                    return pd.read_excel(file_path, sheet_name=sheet_name, engine=engine)
                except:
                    pass
            except Exception as specific_error:
                st.warning(f"Error with engine {engine}: {str(specific_error)}")
                continue
        
        # If all engines fail, try a binary read approach
        st.warning("Trying binary approach for difficult Excel file...")
        
        # Use a direct binary approach for stubborn files
        import tempfile
        import shutil
        
        # Create a temporary copy of the file
        with tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx') as tmp:
            shutil.copy2(file_path, tmp.name)
            tmp_path = tmp.name
        
        try:
            # Try with default engine
            df = pd.read_excel(tmp_path, sheet_name=sheet_name)
            os.unlink(tmp_path)  # Clean up
            return df
        except:
            # Cleanup temp file
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
            
            st.error(f"All methods failed to read Excel file: {os.path.basename(file_path)}")
            return None
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
                
                st.info(f"Processing sheet {sheet}")
                    
                # For each potential recipe table in the sheet
                # This is a bit complex as recipe formats vary widely
                # We'll try a few approaches
                
                # Approach 1: Look for structured tables with clear recipe headers
                recipe_found = False
                for i in range(len(sheet_df)):
                    row = sheet_df.iloc[i]
                    # Look for rows that might indicate a recipe start
                    recipe_indicators = ['recipe', 'dish', 'item', 'menu item', 'set menu', 'menu set']
                    row_values = [str(val).lower().strip() for val in row.values if isinstance(val, str)]
                    
                    if any(indicator in ' '.join(row_values) for indicator in recipe_indicators):
                        # Extract this potential recipe and add to our list
                        recipe_data = extract_single_recipe(sheet_df, start_row=i)
                        if recipe_data:
                            recipes.append(recipe_data)
                            recipe_found = True
                
                # Approach 2: If we didn't find structured recipes, try a more general approach
                if not recipe_found:
                    # Look for clusters of text that might be recipes
                    i = 0
                    while i < len(sheet_df):
                        # Skip empty rows
                        if sheet_df.iloc[i].isnull().all():
                            i += 1
                            continue
                        
                        # Check if this row looks like it might be the start of a recipe
                        row_text = ' '.join([str(val) for val in sheet_df.iloc[i].values if not pd.isna(val)])
                        if len(row_text.strip()) > 3 and not row_text.strip().isdigit():
                            # This might be a recipe name or header
                            recipe_data = extract_single_recipe(sheet_df, start_row=i)
                            if recipe_data and recipe_data.get('name') and recipe_data.get('ingredients'):
                                recipes.append(recipe_data)
                                # Skip ahead a bit to avoid extracting the same recipe again
                                i += 10
                            else:
                                i += 1
                        else:
                            i += 1
                
                # Approach 3: If we still didn't find any recipes, try using AI extraction
                if not recipe_found and not recipes:
                    try:
                        # Create a temporary file
                        import tempfile
                        with tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False) as tmp:
                            # Write the data to the temp file using openpyxl
                            with pd.ExcelWriter(tmp.name, engine='openpyxl') as writer:
                                sheet_df.to_excel(writer, index=False)
                            
                            # Re-open the temp file to read its contents
                            with open(tmp.name, 'rb') as f:
                                file_bytes = f.read()
                            
                            # Use AI to extract recipes
                            extracted = extract_recipe_from_document(file_bytes, 'excel')
                            if isinstance(extracted, dict) and "error" not in extracted:
                                recipes.append(extracted)
                                
                            # Clean up the temp file
                            os.unlink(tmp.name)
                    except Exception as e:
                        st.warning(f"Error using AI extraction: {str(e)}")
                        
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
        st.info(f"Attempting to extract inventory data from {os.path.basename(file_path)}")
        
        # Read the Excel file with improved error handling
        df = safe_read_excel(file_path)
        if df is None or df.empty:
            st.error(f"Could not read file or file is empty: {os.path.basename(file_path)}")
            return []
            
        # Display data preview for debugging
        st.write("Sample data preview:")
        st.dataframe(df.head(3))
        
        # Clean up the dataframe - remove completely empty rows and columns
        df = df.dropna(how='all').reset_index(drop=True)  # Remove empty rows
        df = df.loc[:, ~df.isna().all()].reset_index(drop=True)  # Remove empty columns
        
        # Try to determine the structure
        columns = [str(col).lower() for col in df.columns]
        st.write("Detected columns:", columns)
        
        # Define target fields and potential column matches - expanded for better matching
        field_matches = {
            'item_code': ['item code', 'code', 'sku', 'id', 'item id', 'product code', 'product id', 'item no', 'item number',
                         'article number', 'art no', '#', 'no', 'no.', 'number'],
            'name': ['name', 'item name', 'product name', 'description', 'item description', 'product', 'item',
                    'goods', 'title', 'product description'],
            'category': ['category', 'group', 'department', 'type', 'item type', 'item group', 'class', 'classification',
                        'product group', 'product category', 'product type'],
            'price': ['price', 'cost', 'unit price', 'unit cost', 'price per unit', 'rate', 'amount', 'value',
                     'unit value', 'cost price', 'purchase price', 'buying price'],
            'unit': ['unit', 'uom', 'measure', 'unit of measure', 'unit of measurement', 'measurement unit', 'selling unit',
                    'purchase unit', 'inventory unit'],
            'supplier': ['supplier', 'vendor', 'source', 'manufacturer', 'supply', 'provider', 'distributor', 'brand'],
            'stock_level': ['stock', 'quantity', 'on hand', 'level', 'balance', 'inventory', 'qty', 'stock level',
                           'current stock', 'available', 'on-hand', 'count', 'qty on hand']
        }
        
        # Create mapping of our fields to Excel columns - enhanced for better matching
        mapping = {}
        mapped_columns = []
        
        # First pass - exact matches
        for our_field, possible_matches in field_matches.items():
            for i, col in enumerate(columns):
                if col in possible_matches:
                    mapping[our_field] = df.columns[i]
                    mapped_columns.append(col)
                    break
        
        # Second pass - partial matches if we didn't find exact matches
        for our_field, possible_matches in field_matches.items():
            if our_field in mapping:
                continue  # Skip if already mapped
                
            for i, col in enumerate(columns):
                if col in mapped_columns:
                    continue  # Skip if column already mapped
                    
                if any(match in col for match in possible_matches):
                    mapping[our_field] = df.columns[i]
                    mapped_columns.append(col)
                    break
        
        # Display the mapping for debugging
        st.write("Column mapping:")
        for our_field, excel_col in mapping.items():
            st.write(f"- {our_field}: {excel_col}")
        
        # If we couldn't map critical fields, try AI mapping
        if 'name' not in mapping or ('price' not in mapping and 'stock_level' not in mapping):
            st.warning("Critical fields not mapped. Attempting AI-based mapping...")
            
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
                        st.write(f"AI mapped {our_field} to {excel_col}")
        
        # Process the data using the mapping
        inventory_items = []
        skipped_items = 0
        
        # Skip header rows if they exist
        start_row = 0
        for idx, row in df.iterrows():
            row_values = [str(val).lower() for val in row.values if not pd.isna(val)]
            header_keywords = ['item', 'product', 'code', 'name', 'description', 'price', 'quantity']
            if any(keyword in ' '.join(row_values) for keyword in header_keywords):
                start_row = idx + 1
                break
        
        st.info(f"Starting data extraction from row {start_row}")
        
        # Process each row
        for idx, row in df.iloc[start_row:].iterrows():
            try:
                # Skip rows that are likely headers or completely empty
                if all(pd.isna(val) for val in row.values):
                    continue
                
                item = InventoryItem()
                has_data = False
                
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
                                if isinstance(value, str):
                                    # Clean up the string - remove currency symbols, commas, etc.
                                    value = re.sub(r'[^\d\.\-\,]', '', value).replace(',', '')
                                value = float(value) if value else 0.0
                                has_data = True
                            except:
                                continue
                        else:
                            value = str(value).strip()
                            if value:  # Only set if not empty
                                has_data = True
                        
                        # Set attribute
                        setattr(item, our_field, value)
                
                # Look for data in unmapped columns for name if missing
                if not item.name and has_data:
                    for col in df.columns:
                        if col not in mapping.values():
                            val = row[col]
                            if not pd.isna(val) and isinstance(val, str) and len(val.strip()) > 2:
                                item.name = val.strip()
                                break
                
                # Skip if no name or no meaningful data
                if not item.name or not has_data:
                    skipped_items += 1
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
                
                # Debug info for first few items
                if len(inventory_items) <= 3:
                    st.write(f"Extracted item {len(inventory_items)}: {item.name}")
            
            except Exception as row_error:
                st.warning(f"Error processing row {idx}: {str(row_error)}")
                skipped_items += 1
                continue
        
        st.success(f"Successfully extracted {len(inventory_items)} inventory items. Skipped {skipped_items} rows.")
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
                 
        st.info(f"Found {len(files)} Excel files in {directory}")
        
        for file_path in files:
            try:
                file_name = os.path.basename(file_path)
                st.write(f"Processing file: {file_name}")
                
                # First try to extract recipes, which is our primary focus
                recipes = extract_recipes_from_excel(file_path)
                if recipes:
                    st.success(f"Found {len(recipes)} recipes in {file_name}")
                    results['recipes'].extend(recipes)
                    continue
                
                # If no recipes found, try detecting and extracting other data types
                file_type = detect_file_type(file_path)
                st.write(f"Detected file type: {file_type}")
                
                if file_type == 'inventory':
                    inventory = extract_inventory_from_excel(file_path)
                    if inventory:
                        st.success(f"Found {len(inventory)} inventory items in {file_name}")
                        results['inventory'].extend(inventory)
                    else:
                        st.warning(f"No inventory data could be extracted from {file_name}")
                        results['errors'].append(f"No inventory data found in {file_path}")
                
                elif file_type == 'sales':
                    sales = extract_sales_from_excel(file_path)
                    if sales:
                        st.success(f"Found {len(sales)} sales records in {file_name}")
                        results['sales'].extend(sales)
                    else:
                        st.warning(f"No sales data could be extracted from {file_name}")
                        results['errors'].append(f"No sales data found in {file_path}")
                
                else:
                    # If type is unknown, try all extractors
                    st.write("Trying all extractors for unknown file type...")
                    
                    inventory = extract_inventory_from_excel(file_path)
                    if inventory:
                        st.success(f"Found {len(inventory)} inventory items in {file_name}")
                        results['inventory'].extend(inventory)
                        continue
                    
                    sales = extract_sales_from_excel(file_path)
                    if sales:
                        st.success(f"Found {len(sales)} sales records in {file_name}")
                        results['sales'].extend(sales)
                        continue
                    
                    st.warning(f"Could not extract any useful data from {file_name}")
                    results['errors'].append(f"Could not determine data type for {file_path}")
            except Exception as e:
                st.error(f"Error processing {os.path.basename(file_path)}: {str(e)}")
                results['errors'].append(f"Error processing {file_path}: {str(e)}")
        
        # Summary of extraction
        st.subheader("Extraction Summary")
        st.write(f"Recipes extracted: {len(results['recipes'])}")
        st.write(f"Inventory items extracted: {len(results['inventory'])}")
        st.write(f"Sales records extracted: {len(results['sales'])}")
        st.write(f"Errors encountered: {len(results['errors'])}")
        
        return results
    except Exception as e:
        st.error(f"Error processing directory: {str(e)}")
        results['errors'].append(f"Error processing directory: {str(e)}")
        return results