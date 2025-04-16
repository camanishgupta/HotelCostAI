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
        st.info(f"Attempting to extract sales data from {os.path.basename(file_path)}")
        
        # Read the Excel file with improved error handling
        df = safe_read_excel(file_path)
        if df is None or df.empty:
            st.error(f"Could not read file or file is empty: {os.path.basename(file_path)}")
            return []
            
        # Display data preview for debugging
        st.write("Sample data preview for sales extraction:")
        st.dataframe(df.head(3))
        
        # Clean up the dataframe - remove completely empty rows and columns
        df = df.dropna(how='all').reset_index(drop=True)  # Remove empty rows
        df = df.loc[:, ~df.isna().all()].reset_index(drop=True)  # Remove empty columns
        
        # Try to determine the structure
        columns = [str(col).lower() for col in df.columns]
        st.write("Detected columns:", columns)
        
        # Define target fields and potential column matches - expanded for better matching
        field_matches = {
            'date': ['date', 'sale date', 'transaction date', 'order date', 'day', 'period', 'month', 'sale period',
                    'week', 'year', 'transaction time', 'time', 'datetime'],
            'item_name': ['item', 'product', 'name', 'description', 'item name', 'product name', 'menu item',
                         'dish', 'article', 'food item', 'merchandise', 'goods', 'service', 'sale item'],
            'quantity': ['quantity', 'qty', 'amount', 'volume', 'count', 'sold', 'units sold', 'units', 'pieces',
                        'pcs', 'number', 'num', 'unit sold', 'qty sold'],
            'revenue': ['revenue', 'sales', 'amount', 'total', 'price', 'total price', 'sales amount', 'income',
                       'sale amount', 'sale value', 'value', 'sales revenue', 'total sales', 'gross sales'],
            'cost': ['cost', 'cogs', 'cost of goods', 'expense', 'total cost', 'unit cost', 'cost price',
                    'material cost', 'production cost', 'purchase cost', 'cost amount']
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
        st.write("Column mapping for sales data:")
        for our_field, excel_col in mapping.items():
            st.write(f"- {our_field}: {excel_col}")
        
        # Special case for ABGN files - detect by filename
        filename = os.path.basename(file_path).lower()
        if 'sale' in filename and 'item' in filename and 'abgn' in filename:
            st.write("Detected ABGN Sales file format - using special extraction")
            # Try to find typical columns in ABGN sales files
            potential_item_cols = []
            potential_qty_cols = []
            potential_revenue_cols = []
            
            # Look for descriptive columns
            for i, col in enumerate(df.columns):
                col_str = str(col).lower()
                if any(term in col_str for term in ['item', 'name', 'description', 'menu', 'dish']):
                    potential_item_cols.append((i, col))
                elif any(term in col_str for term in ['quantity', 'qty', 'count', 'number']):
                    potential_qty_cols.append((i, col))
                elif any(term in col_str for term in ['total', 'amount', 'revenue', 'sales', 'price']):
                    potential_revenue_cols.append((i, col))
            
            # Use the first columns found as mapping
            if potential_item_cols:
                mapping['item_name'] = potential_item_cols[0][1]
            if potential_qty_cols:
                mapping['quantity'] = potential_qty_cols[0][1]
            if potential_revenue_cols:
                mapping['revenue'] = potential_revenue_cols[0][1]
            
            # Hard code the date for ABGN file - extract from filename
            # Example: "ABGN Sale by Items Feb-2025.xlsx" -> "Feb 2025"
            sale_date = None
            date_match = re.search(r'([a-zA-Z]{3})[- ](\d{4})', filename)
            if date_match and date_match.groups() and len(date_match.groups()) >= 2:
                try:
                    month_str = date_match.group(1)
                    year_str = date_match.group(2)
                    
                    # Map month name to number
                    month_map = {
                        'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'may': 5, 'jun': 6,
                        'jul': 7, 'aug': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12
                    }
                    month_num = month_map.get(month_str.lower(), 1)  # Default to January if not found
                    
                    # Create date and convert to ISO format
                    sale_date = datetime(int(year_str), month_num, 15).isoformat()  # Middle of the month
                    st.write(f"Extracted date from filename: {sale_date}")
                except Exception as date_err:
                    st.warning(f"Could not parse date from filename: {str(date_err)}")
                    sale_date = datetime.now().isoformat()  # Use current date as fallback
        
        # If we couldn't map critical fields, try AI mapping
        if ('item_name' not in mapping or 'quantity' not in mapping) and not ('abgn' in filename.lower()):
            st.warning("Critical fields not mapped. Attempting AI-based mapping...")
            
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
                        st.write(f"AI mapped {our_field} to {excel_col}")
        
        # Process the data using the mapping
        sales_records = []
        skipped_items = 0
        
        # Skip header rows if they exist
        start_row = 0
        for idx, row in df.iterrows():
            row_values = [str(val).lower() for val in row.values if not pd.isna(val)]
            header_keywords = ['date', 'item', 'product', 'name', 'quantity', 'qty', 'amount', 'total', 'sales']
            if any(keyword in ' '.join(row_values) for keyword in header_keywords):
                start_row = idx + 1
                break
        
        st.info(f"Starting sales data extraction from row {start_row}")
        
        # Process each row
        for idx, row in df.iloc[start_row:].iterrows():
            try:
                # Skip rows that are likely headers or completely empty
                if all(pd.isna(val) for val in row.values):
                    continue
                
                record = SalesRecord()
                has_data = False
                
                # Set date from ABGN file analysis if available
                if 'sale_date' in locals() and sale_date:
                    record.date = sale_date
                    has_data = True
                
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
                                    # Try to find year/month in string
                                    if re.search(r'(\d{4})[/\-](\d{1,2})', value):
                                        # Looks like a year-month format
                                        year_match = re.search(r'(\d{4})', value)
                                        month_match = re.search(r'[/\-](\d{1,2})', value)
                                        
                                        if year_match and month_match:
                                            year = year_match.group(1)
                                            month = month_match.group(1)
                                            value = f"{year}-{month}-15"  # Middle of month
                                        
                                    # Try different date formats
                                    for fmt in ['%Y-%m-%d', '%m/%d/%Y', '%d/%m/%Y', '%d-%m-%Y', '%Y/%m/%d']:
                                        try:
                                            parsed_date = datetime.strptime(value, fmt)
                                            value = parsed_date.isoformat()
                                            break
                                        except:
                                            pass
                                elif isinstance(value, (int, float)):
                                    # Might be an Excel date number
                                    try:
                                        value = pd.Timestamp.fromordinal(
                                            datetime(1900, 1, 1).toordinal() + int(value) - 2
                                        ).isoformat()
                                    except:
                                        pass
                                else:
                                    # Assume pandas converted it to datetime or Timestamp
                                    try:
                                        value = pd.Timestamp(value).isoformat()
                                    except:
                                        pass
                                        
                                has_data = True
                            except:
                                record.date = datetime.now().isoformat()
                        elif our_field in ['quantity', 'revenue', 'cost']:
                            try:
                                if isinstance(value, str):
                                    # Clean up the string - remove currency symbols, commas, etc.
                                    value = re.sub(r'[^\d\.\-\,]', '', value).replace(',', '')
                                value = float(value) if value else 0.0
                                has_data = True
                            except:
                                if our_field == 'quantity':
                                    record.quantity = 1  # Default
                                elif our_field == 'revenue':
                                    record.revenue = 0
                                elif our_field == 'cost':
                                    record.cost = 0
                                continue
                        else:
                            if value:
                                value = str(value).strip()
                                has_data = True
                        
                        # Set attribute
                        setattr(record, our_field, value)
                
                # Look for data in unmapped columns for item_name if missing
                if not record.item_name and has_data:
                    for col in df.columns:
                        if col not in mapping.values():
                            val = row[col]
                            if not pd.isna(val) and isinstance(val, str) and len(val.strip()) > 2:
                                record.item_name = val.strip()
                                break
                
                # Skip if no data or no item name found
                if not has_data or not record.item_name:
                    skipped_items += 1
                    continue
                
                # Set default date if missing
                if not record.date:
                    record.date = datetime.now().isoformat()
                
                # Ensure quantity is at least 1
                if record.quantity == 0:
                    record.quantity = 1
                
                # If revenue is missing but we have quantity, estimate it
                if record.revenue == 0 and record.quantity > 0:
                    # Try to find revenue in other numeric columns
                    for col in df.columns:
                        if col not in mapping.values():
                            try:
                                val = row[col]
                                if not pd.isna(val) and not isinstance(val, str):
                                    num_val = float(val)
                                    if num_val > 0 and num_val < 1000000:  # Reasonable revenue range
                                        record.revenue = num_val
                                        break
                            except:
                                continue
                    
                    # If still not found, use a default estimate
                    if record.revenue == 0:
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
                
                # Debug info for first few items
                if len(sales_records) <= 3:
                    st.write(f"Extracted sales record {len(sales_records)}: {record.item_name}, Qty: {record.quantity}, Revenue: {record.revenue}")
            
            except Exception as row_error:
                st.warning(f"Error processing sales row {idx}: {str(row_error)}")
                skipped_items += 1
                continue
        
        st.success(f"Successfully extracted {len(sales_records)} sales records. Skipped {skipped_items} rows.")
        return sales_records
    
    except Exception as e:
        st.error(f"Error extracting sales: {str(e)}")
        return []

def extract_abgn_recipe_costing(file_path):
    """
    Extract recipe data specifically from ABGN A La Carte Menu Cost format Excel files
    
    Args:
        file_path (str): Path to the ABGN Recipe Costing Excel file
        
    Returns:
        list: Extracted recipes
    """
    try:
        # Try to open the Excel file
        try:
            xl = pd.ExcelFile(file_path)
        except Exception as e:
            st.error(f"Failed to open Excel file: {str(e)}")
            return []
            
        # Get sheet names (excluding Summary and Sheet1)
        sheet_names = [name for name in xl.sheet_names if name != 'Summary' and name != 'Sheet1']
        
        # Process each sheet
        all_recipes = []
        
        for sheet_name in sheet_names:
            st.info(f"Processing sheet: {sheet_name}")
            
            try:
                # Read the sheet
                df = pd.read_excel(file_path, sheet_name=sheet_name)
                
                # Track recipe boundaries
                recipe_starts = []
                
                # Find all recipe start positions
                for i in range(len(df)):
                    row = df.iloc[i]
                    row_text = " ".join([str(x).lower() for x in row.values if pd.notna(x)])
                    
                    # Recipe usually starts with "STANDARD COST RECIPE CARD" or "NAME :"
                    if "standard cost recipe card" in row_text or (("name" in row_text) and (":" in row_text)):
                        recipe_starts.append(i)
                
                if not recipe_starts:
                    st.warning(f"No recipes found in sheet {sheet_name}")
                    continue
                    
                # Add an ending boundary
                recipe_starts.append(len(df))
                
                # Process each recipe
                for i in range(len(recipe_starts) - 1):
                    start = recipe_starts[i]
                    end = recipe_starts[i+1]
                    
                    # Extract the recipe section
                    recipe_df = df.iloc[start:end].copy()
                    
                    # Find the recipe name
                    recipe_name = ""
                    name_found = False
                    
                    # First, look for the standard name pattern in the first few rows
                    for j in range(min(10, len(recipe_df))):
                        row = recipe_df.iloc[j]
                        
                        for col_idx, cell in enumerate(row.values):
                            if pd.isna(cell):
                                continue
                                
                            cell_text = str(cell).upper()
                            
                            # Look for typical menu item name patterns
                            if "NAME" in cell_text and ":" in cell_text:
                                # Parse name from this cell (after the colon)
                                name_parts = str(cell).split(":", 1)
                                if len(name_parts) > 1 and name_parts[1].strip():
                                    recipe_name = name_parts[1].strip()
                                    name_found = True
                                    break
                                # If name isn't in this cell, check next cell
                                elif col_idx + 1 < len(row) and pd.notna(row.iloc[col_idx + 1]):
                                    potential_name = str(row.iloc[col_idx + 1]).strip()
                                    # Only use if it looks like a name (not just a number or code)
                                    if len(potential_name) > 2 and not potential_name.replace('.', '', 1).isdigit():
                                        recipe_name = potential_name
                                        name_found = True
                                        break
                            
                            # Also check for "MENU ITEM:" pattern
                            elif "MENU" in cell_text and "ITEM" in cell_text:
                                # Check if name is in this cell
                                if ":" in cell_text:
                                    name_parts = str(cell).split(":", 1)
                                    if len(name_parts) > 1:
                                        recipe_name = name_parts[1].strip()
                                        name_found = True
                                        break
                                # Check next cell for the name
                                elif col_idx + 1 < len(row) and pd.notna(row.iloc[col_idx + 1]):
                                    recipe_name = str(row.iloc[col_idx + 1]).strip()
                                    name_found = True
                                    break
                        
                        if name_found:
                            break
                    
                    # If still no name found, try looking for a header or title cell
                    if not name_found:
                        # ABGN format often has a larger title cell at the top
                        for j in range(min(7, len(recipe_df))):
                            row = recipe_df.iloc[j]
                            for cell in row.values:
                                if pd.isna(cell):
                                    continue
                                    
                                cell_text = str(cell).strip()
                                # Look for a capitalized name that isn't too long and doesn't contain special keywords
                                if (cell_text.isupper() or cell_text[0].isupper()) and 3 <= len(cell_text) <= 40:
                                    # Skip cells with administrative keywords
                                    skip_keywords = ["STANDARD", "COST", "RECIPE", "CARD", "CALCULATION"]
                                    if not any(keyword in cell_text.upper() for keyword in skip_keywords):
                                        recipe_name = cell_text
                                        name_found = True
                                        break
                            if name_found:
                                break
                    
                    # If still no name found, use a default name with index and sheet
                    if not recipe_name:
                        recipe_name = f"{sheet_name} Recipe {i+1}"
                        
                    st.write(f"Found recipe: {recipe_name}")
                    
                    # Find the ingredients table
                    ingredients_start = -1
                    for j in range(len(recipe_df)):
                        row = recipe_df.iloc[j]
                        row_text = " ".join([str(x).lower() for x in row.values if pd.notna(x)])
                        if "item code" in row_text and "ingredients" in row_text and "unit" in row_text and "qty" in row_text:
                            ingredients_start = j
                            break
                    
                    if ingredients_start < 0:
                        st.warning(f"Could not find ingredients table for recipe {recipe_name}")
                        continue
                        
                    # Find the end of ingredients (usually when Total Cost appears)
                    ingredients_end = len(recipe_df)
                    for j in range(ingredients_start + 1, len(recipe_df)):
                        row = recipe_df.iloc[j]
                        row_text = " ".join([str(x).lower() for x in row.values if pd.notna(x)])
                        if "total cost" in row_text and len(row_text) < 30:  # Short row with total cost is the summary
                            ingredients_end = j
                            break
                    
                    # Extract ingredients
                    ingredients_df = recipe_df.iloc[ingredients_start+1:ingredients_end].copy()
                    
                    # Find column positions from the header row
                    header_row = recipe_df.iloc[ingredients_start]
                    item_code_col = None
                    ingredient_name_col = None
                    unit_col = None
                    qty_col = None
                    unit_price_col = None
                    total_amount_col = None
                    
                    for col_idx, cell in enumerate(header_row.values):
                        if pd.isna(cell):
                            continue
                        
                        cell_text = str(cell).lower()
                        if "item code" in cell_text:
                            item_code_col = col_idx
                        elif "ingredients" in cell_text:
                            ingredient_name_col = col_idx
                        elif "unit" in cell_text:
                            unit_col = col_idx
                        elif "qty" in cell_text:
                            qty_col = col_idx
                        elif "at amount" in cell_text:
                            unit_price_col = col_idx
                        elif "total amount" in cell_text and "ks" in cell_text:
                            total_amount_col = col_idx
                    
                    # If columns not found, use default positions
                    if item_code_col is None:
                        item_code_col = 0
                    if ingredient_name_col is None:
                        ingredient_name_col = 1
                    if unit_col is None:
                        unit_col = 2
                    if qty_col is None:
                        qty_col = 3
                    if unit_price_col is None:
                        unit_price_col = 6
                    if total_amount_col is None:
                        total_amount_col = 7
                        
                    # Extract the ingredients
                    ingredients = []
                    
                    for j in range(len(ingredients_df)):
                        row = ingredients_df.iloc[j]
                        
                        # Skip rows with NaN in name column
                        if ingredient_name_col >= len(row) or pd.isna(row.iloc[ingredient_name_col]):
                            continue
                            
                        # Get ingredient name
                        ingredient_name = str(row.iloc[ingredient_name_col]).strip()
                        
                        # Skip if empty name
                        if not ingredient_name:
                            continue
                            
                        # Get item code if available
                        item_code = ""
                        if item_code_col < len(row) and pd.notna(row.iloc[item_code_col]):
                            item_code = str(row.iloc[item_code_col]).strip()
                            
                        # Get unit
                        unit = ""
                        if unit_col < len(row) and pd.notna(row.iloc[unit_col]):
                            unit = str(row.iloc[unit_col]).strip()
                            
                        # Get quantity
                        quantity = 0
                        if qty_col < len(row) and pd.notna(row.iloc[qty_col]):
                            try:
                                quantity = float(row.iloc[qty_col])
                            except:
                                pass
                        
                        # Get unit price
                        unit_price = 0
                        if unit_price_col < len(row) and pd.notna(row.iloc[unit_price_col]):
                            try:
                                unit_price = float(row.iloc[unit_price_col])
                            except:
                                pass
                                
                        # Get total amount
                        total_amount = 0
                        if total_amount_col < len(row) and pd.notna(row.iloc[total_amount_col]):
                            try:
                                total_amount = float(row.iloc[total_amount_col])
                            except:
                                pass
                                
                        # Check for combined fields and attempt to parse them
                        combined_field = False
                        if ingredient_name and any(c.isdigit() for c in ingredient_name[:5]):
                            st.write(f"Found combined field: {ingredient_name}")
                            combined_field = True
                            
                            # Try to parse the combined field
                            parts = ingredient_name.split()
                            if len(parts) >= 4:
                                # Format usually: "CODE NAME AMOUNT UNIT PRICE"
                                parsed_name = []
                                parsed_item_code = ""
                                parsed_unit = ""
                                parsed_quantity = 0
                                parsed_unit_price = 0
                                
                                # First part is usually item code
                                if parts[0].replace('-', '').replace('_', '').isalnum():
                                    parsed_item_code = parts[0]
                                    parts = parts[1:]
                                
                                # Last part might be price
                                try:
                                    if parts[-1].replace('.', '', 1).isdigit():
                                        parsed_unit_price = float(parts[-1])
                                        parts = parts[:-1]
                                except:
                                    pass
                                
                                # Second-to-last might be unit
                                if len(parts) >= 2 and len(parts[-1]) <= 6:
                                    parsed_unit = parts[-1]
                                    parts = parts[:-1]
                                
                                # Third-to-last might be quantity
                                if len(parts) >= 2:
                                    try:
                                        if parts[-1].replace('.', '', 1).isdigit():
                                            parsed_quantity = float(parts[-1])
                                            parts = parts[:-1]
                                    except:
                                        pass
                                
                                # What's left is the name
                                parsed_name = " ".join(parts)
                                
                                # Use parsed values if better than originals
                                if parsed_name:
                                    ingredient_name = parsed_name
                                if parsed_item_code and not item_code:
                                    item_code = parsed_item_code
                                if parsed_unit and not unit:
                                    unit = parsed_unit
                                if parsed_quantity > 0 and quantity == 0:
                                    quantity = parsed_quantity
                                if parsed_unit_price > 0 and unit_price == 0:
                                    unit_price = parsed_unit_price
                        
                        # Calculate total cost if missing but we have unit price and quantity
                        if total_amount == 0 and unit_price > 0 and quantity > 0:
                            total_amount = unit_price * quantity
                            
                        # Apply default unit if missing
                        if not unit:
                            unit = "piece"
                            
                        # Look for loss and net quantity values in the row
                        loss_qty = 0
                        net_qty = quantity  # Default to quantity if not specified
                        
                        # Try to find loss and net qty columns 
                        for i, col_val in enumerate(row):
                            if pd.isna(col_val):
                                continue
                                
                            col_header = ""
                            if i < len(header_row):
                                col_header = str(header_row.iloc[i]).lower() if pd.notna(header_row.iloc[i]) else ""
                                
                            # Check for loss column
                            if "loss" in col_header and not pd.isna(col_val):
                                try:
                                    loss_qty = float(col_val)
                                except:
                                    pass
                                    
                            # Check for net qty column
                            if "net" in col_header and "qty" in col_header and not pd.isna(col_val):
                                try:
                                    net_qty = float(col_val)
                                except:
                                    pass
                            
                        # Log for debugging
                        if combined_field:
                            st.write(f"Parsed: Name: {ingredient_name}, Code: {item_code}, Unit: {unit}, Qty: {quantity}, Loss: {loss_qty}, Net Qty: {net_qty}, Price: {unit_price}, Total: {total_amount}")
                        
                        # Add ingredient with all ABGN fields properly mapped
                        ingredients.append({
                            "item_code": item_code,
                            "name": ingredient_name,
                            "unit": unit,
                            "qty": quantity,
                            "loss": loss_qty,
                            "net_qty": net_qty,
                            "unit_cost": unit_price,
                            "total_cost": total_amount
                        })
                    
                    # Find sales price
                    sales_price = 0
                    for j in range(len(recipe_df)):
                        row = recipe_df.iloc[j]
                        row_text = " ".join([str(x).lower() for x in row.values if pd.notna(x)])
                        if "actual sales price" in row_text or "sales price" in row_text:
                            # Find the sales price value (usually in the same row, a few columns over)
                            for k in range(len(row)):
                                cell = row.iloc[k]
                                if pd.notna(cell) and isinstance(cell, (int, float)) and cell > 0:
                                    sales_price = float(cell)
                                    break
                            break
                    
                    # Find total cost and portions
                    total_cost = 0
                    portions = 1
                    
                    for j in range(len(recipe_df)):
                        row = recipe_df.iloc[j]
                        row_text = " ".join([str(x).lower() for x in row.values if pd.notna(x)])
                        
                        if "total cost" in row_text and "portion" not in row_text:
                            # Find the total cost value
                            for k in range(len(row)):
                                cell = row.iloc[k]
                                if pd.notna(cell) and isinstance(cell, (int, float)) and cell > 0:
                                    total_cost = float(cell)
                                    break
                        
                        elif "no.portion" in row_text or "number of portion" in row_text:
                            # Find the portions value
                            for k in range(len(row)):
                                cell = row.iloc[k]
                                if pd.notna(cell) and isinstance(cell, (int, float)) and cell > 0:
                                    portions = float(cell)
                                    break
                    
                    # Create the recipe
                    recipe = {
                        "name": recipe_name,
                        "category": sheet_name,
                        "yield_amount": portions,
                        "yield_unit": "serving",
                        "ingredients": ingredients,
                        "total_cost": total_cost,
                        "sales_price": sales_price,
                        "cost_percentage": (total_cost / sales_price * 100) if sales_price > 0 else 0,
                        "imported_at": datetime.now().isoformat()
                    }
                    
                    all_recipes.append(recipe)
                
            except Exception as sheet_err:
                st.error(f"Error processing sheet {sheet_name}: {str(sheet_err)}")
                continue
        
        st.success(f"Successfully extracted {len(all_recipes)} recipes from {len(sheet_names)} sheets")
        return all_recipes
        
    except Exception as e:
        st.error(f"Error extracting ABGN recipe costing data: {str(e)}")
        return []


def extract_abgn_inventory(file_path):
    """
    Extract inventory data specifically from ABGN One Line Store format Excel files
    
    Args:
        file_path (str): Path to the ABGN One Line Store Excel file
        
    Returns:
        list: Extracted inventory items
    """
    try:
        # Try different engines to handle various Excel formats
        dfs = []
        errors = []
        
        try:
            df = pd.read_excel(file_path, engine='openpyxl')
            dfs.append(df)
        except Exception as e:
            errors.append(f"openpyxl error: {str(e)}")
            
        try:
            df = pd.read_excel(file_path, engine='xlrd')
            dfs.append(df)
        except Exception as e:
            errors.append(f"xlrd error: {str(e)}")
        
        # Use the first successful DataFrame or raise an error
        if dfs:
            df = dfs[0]
        else:
            st.error(f"Failed to read Excel file: {', '.join(errors)}")
            return []
        
        # Find the header row - ABGN One Line Store format has standard header patterns
        header_row = -1
        for i in range(min(20, len(df))):
            row = df.iloc[i]
            row_text = " ".join([str(x).lower() for x in row.values if pd.notna(x)])
            if "item" in row_text and "name" in row_text and "uom" in row_text:
                header_row = i
                st.info(f"Found header row at row {i}")
                break
        
        if header_row < 0:
            # Try alternative header pattern
            for i in range(min(20, len(df))):
                row = df.iloc[i]
                row_text = " ".join([str(x).lower() for x in row.values if pd.notna(x)])
                if "item" in row_text and any(term in row_text for term in ["opb.bal", "receipts", "issues"]):
                    header_row = i
                    st.info(f"Found alternative header row at row {i}")
                    break
        
        # If still no header found, use default positions
        if header_row < 0:
            st.warning("Could not find header row in ABGN One Line Store file, using default positions")
            header_row = 1  # Common position in ABGN format
        
        # Determine column mappings based on header
        header = df.iloc[header_row]
        
        # Initialize column indices
        item_code_col = None
        item_name_col = None
        unit_col = None
        opening_balance_col = None
        closing_balance_col = None
        value_col = None
        
        # Look for column names in header
        for i, col_val in enumerate(header):
            if pd.isna(col_val):
                continue
                
            col_text = str(col_val).lower()
            
            if col_text == "item":
                item_code_col = i
            elif "name" in col_text or "description" in col_text:
                item_name_col = i
            elif "uom" in col_text or "unit" in col_text:
                unit_col = i
            elif "opb.bal" in col_text or "opening" in col_text:
                opening_balance_col = i
            elif "clb.bal" in col_text or "closing" in col_text:
                closing_balance_col = i
            elif "value" in col_text and "clb" in col_text:
                value_col = i
        
        # If columns not found, use default positions
        if item_code_col is None:
            item_code_col = 0  # Usually first column
            
        if item_name_col is None:
            item_name_col = 1  # Usually second column
            
        if unit_col is None:
            unit_col = item_name_col  # Sometimes combined with name column
            
        if opening_balance_col is None:
            opening_balance_col = 2  # Common position
            
        if closing_balance_col is None:
            closing_balance_col = -1  # Often one of the last columns
            for i in range(len(header) - 1, 2, -1):
                if "bal" in str(header.iloc[i]).lower():
                    closing_balance_col = i
                    break
            if closing_balance_col < 0:
                closing_balance_col = len(header) - 2  # Default to second-to-last column
                
        if value_col is None:
            value_col = len(header) - 1  # Usually last column
            
        st.info(f"Using columns: Item Code={item_code_col}, Name={item_name_col}, Unit={unit_col}, " +
               f"Opening={opening_balance_col}, Closing={closing_balance_col}, Value={value_col}")
        
        # Process inventory items
        inventory_items = []
        skipped_rows = 0
        group_category = "Uncategorized"
        
        for i in range(header_row + 1, len(df)):
            try:
                row = df.iloc[i]
                
                # Skip empty rows
                if all(pd.isna(val) for val in row.values):
                    skipped_rows += 1
                    continue
                
                # Check if this is a group/category header (common in ABGN format)
                first_cell = row.iloc[0] if len(row) > 0 else None
                if isinstance(first_cell, str) and any(term in first_cell.lower() for term in ["group", "total", "____"]):
                    # Update current category
                    if "total" not in first_cell.lower():
                        group_category = first_cell.strip()
                    skipped_rows += 1
                    continue
                
                # Get item code
                item_code = ""
                if item_code_col < len(row) and not pd.isna(row.iloc[item_code_col]):
                    item_code = str(row.iloc[item_code_col]).strip()
                
                # Some ABGN formats have item code on one row and name/details on next
                if "(" in item_code and ")" in item_code:
                    # This looks like an item code row with format like "20900023 (1)"
                    item_code = item_code.split("(")[0].strip()
                    # Next row may contain the item name and other details
                    if i + 1 < len(df):
                        next_row = df.iloc[i + 1]
                        
                        # If next row starts with empty cells, it's likely the details row
                        if pd.isna(next_row.iloc[0]) and not pd.isna(next_row.iloc[unit_col]):
                            # Extract unit and stock details from next row
                            unit = str(next_row.iloc[unit_col]).strip() if unit_col < len(next_row) else ""
                            
                            closing_bal = 0
                            if closing_balance_col < len(next_row) and not pd.isna(next_row.iloc[closing_balance_col]):
                                try:
                                    closing_bal = float(next_row.iloc[closing_balance_col])
                                except:
                                    pass
                            
                            value = 0
                            if value_col < len(next_row) and not pd.isna(next_row.iloc[value_col]):
                                try:
                                    value = float(next_row.iloc[value_col])
                                except:
                                    pass
                            
                            # Get item name from current row or use code if not available
                            item_name = ""
                            if item_name_col < len(row) and not pd.isna(row.iloc[item_name_col]):
                                item_name = str(row.iloc[item_name_col]).strip()
                            else:
                                item_name = item_code
                            
                            # Calculate unit price
                            unit_price = value / closing_bal if closing_bal > 0 else 0
                            
                            # Create inventory item
                            inventory_items.append({
                                "item_code": item_code,
                                "name": item_name,
                                "category": group_category,
                                "unit": unit,
                                "stock_level": closing_bal,
                                "price": unit_price,
                                "value": value,
                                "imported_at": datetime.now().isoformat()
                            })
                            
                            # Skip next row since we already processed it
                            i += 1
                            continue
                
                # Process standard row format
                # Get item name
                item_name = ""
                if item_name_col < len(row) and not pd.isna(row.iloc[item_name_col]):
                    item_name = str(row.iloc[item_name_col]).strip()
                    
                # Skip if no item code or name
                if not item_code and not item_name:
                    skipped_rows += 1
                    continue
                
                # Get unit
                unit = ""
                if unit_col < len(row) and not pd.isna(row.iloc[unit_col]):
                    unit = str(row.iloc[unit_col]).strip()
                
                # Get closing balance
                closing_bal = 0
                if closing_balance_col < len(row) and not pd.isna(row.iloc[closing_balance_col]):
                    try:
                        closing_bal = float(row.iloc[closing_balance_col])
                    except:
                        pass
                
                # Get value
                value = 0
                if value_col < len(row) and not pd.isna(row.iloc[value_col]):
                    try:
                        value = float(row.iloc[value_col])
                    except:
                        pass
                
                # Calculate unit price
                unit_price = value / closing_bal if closing_bal > 0 else 0
                
                # Create inventory item
                inventory_items.append({
                    "item_code": item_code,
                    "name": item_name if item_name else item_code,
                    "category": group_category,
                    "unit": unit,
                    "stock_level": closing_bal,
                    "price": unit_price,
                    "value": value,
                    "imported_at": datetime.now().isoformat()
                })
                
                # Debug the first few items
                if len(inventory_items) <= 5:
                    st.write(f"Item: {item_name}, Stock: {closing_bal} {unit}, Price: {unit_price}")
                
            except Exception as row_err:
                st.warning(f"Error processing row {i}: {str(row_err)}")
                skipped_rows += 1
        
        st.success(f"Extracted {len(inventory_items)} inventory items from ABGN One Line Store file. Skipped {skipped_rows} rows.")
        return inventory_items
        
    except Exception as e:
        st.error(f"Error extracting ABGN inventory data: {str(e)}")
        return []


def extract_abgn_sales(file_path):
    """
    Extract sales data specifically from ABGN Sales format Excel files
    
    Args:
        file_path (str): Path to the ABGN Sales Excel file
        
    Returns:
        list: Extracted sales records
    """
    try:
        # Try different engines to handle various Excel formats
        dfs = []
        errors = []
        
        try:
            df = pd.read_excel(file_path, engine='openpyxl')
            dfs.append(df)
        except Exception as e:
            errors.append(f"openpyxl error: {str(e)}")
            
        try:
            df = pd.read_excel(file_path, engine='xlrd')
            dfs.append(df)
        except Exception as e:
            errors.append(f"xlrd error: {str(e)}")
        
        # Use the first successful DataFrame or raise an error
        if dfs:
            df = dfs[0]
        else:
            st.error(f"Failed to read Excel file: {', '.join(errors)}")
            return []
            
        # Extract date from filename
        filename = os.path.basename(file_path).lower()
        sale_date = datetime.now().isoformat()  # Default value if extraction fails
        
        date_match = re.search(r'([a-zA-Z]{3})[- ](\d{4})', filename)
        if date_match and date_match.groups() and len(date_match.groups()) >= 2:
            try:
                month_str = date_match.group(1)
                year_str = date_match.group(2)
                
                # Map month name to number
                month_map = {
                    'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'may': 5, 'jun': 6,
                    'jul': 7, 'aug': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12
                }
                month_num = month_map.get(month_str.lower(), 1)  # Default to January if not found
                
                # Create date and convert to ISO format
                sale_date = datetime(int(year_str), month_num, 15).isoformat()  # Middle of month
                st.write(f"Extracted date from filename: {sale_date}")
            except Exception as date_err:
                st.warning(f"Could not parse date from filename: {str(date_err)}")
                # sale_date already has a default value
        
        # Find the header row
        header_row = -1
        for i in range(min(20, len(df))):
            row = df.iloc[i]
            row_text = " ".join([str(x).lower() for x in row.values if pd.notna(x)])
            if "item" in row_text and any(term in row_text for term in ["qty", "quantity"]) and any(term in row_text for term in ["value", "rate", "amount"]):
                header_row = i
                st.info(f"Found header row at row {i}")
                break
        
        # Determine column indices based on header row
        item_col = None
        desc_col = None
        qty_col = None 
        rate_col = None
        value_col = None
        
        if header_row >= 0:
            # Get header values
            header = df.iloc[header_row]
            
            # Look for column names
            for i, col_val in enumerate(header):
                if pd.isna(col_val):
                    continue
                    
                col_text = str(col_val).lower()
                if col_text == "item":
                    item_col = i
                elif any(term in col_text for term in ["description", "name"]):
                    desc_col = i
                elif any(term in col_text for term in ["qty", "quantity"]):
                    qty_col = i
                elif any(term in col_text for term in ["rate", "price"]):
                    rate_col = i
                elif any(term in col_text for term in ["value", "amount", "total"]):
                    value_col = i
        
        # If columns not found, use default positions
        if item_col is None:
            # In ABGN Sale format, first column is often item code or item
            item_col = 0
            
        if desc_col is None and len(df.columns) > 1:
            # Second column is often description
            desc_col = 1
            
        if qty_col is None and len(df.columns) > 2:
            # Third column is often quantity
            qty_col = 2
            
        if rate_col is None and len(df.columns) > 3:
            # Fourth column is often rate
            rate_col = 3
            
        if value_col is None and len(df.columns) > 4:
            # Fifth column is often value/total
            value_col = 4
        
        # Start processing from row after header
        start_row = header_row + 1 if header_row >= 0 else 0
        st.info(f"Processing data from row {start_row}")
        st.info(f"Using columns: Item={item_col}, Desc={desc_col}, Qty={qty_col}, Rate={rate_col}, Value={value_col}")
        
        # Process all rows
        sales_records = []
        skipped_rows = 0
        
        for i in range(start_row, len(df)):
            try:
                row = df.iloc[i]
                
                # Skip empty rows
                if all(pd.isna(val) for val in row.values):
                    skipped_rows += 1
                    continue
                
                # Get item name - prefer description column if available, otherwise item column
                if desc_col is not None and desc_col < len(row) and not pd.isna(row.iloc[desc_col]):
                    item_name = str(row.iloc[desc_col])
                elif item_col is not None and item_col < len(row) and not pd.isna(row.iloc[item_col]):
                    item_name = str(row.iloc[item_col])
                else:
                    skipped_rows += 1
                    continue
                
                # Clean up item name - remove trailing dashes which are common in ABGN format
                item_name = re.sub(r'\s*-+\s*$', '', item_name).strip()
                
                # Skip total and section heading rows
                item_lower = item_name.lower()
                if any(term in item_lower for term in ["total", "group", "__________", "main dining", "item"]):
                    skipped_rows += 1
                    continue
                
                # Get quantity
                quantity = None
                if qty_col is not None and qty_col < len(row):
                    qty_val = row.iloc[qty_col]
                    if not pd.isna(qty_val) and isinstance(qty_val, (int, float)) and qty_val > 0:
                        quantity = float(qty_val)
                
                # Skip if no valid quantity
                if quantity is None or quantity <= 0:
                    skipped_rows += 1
                    continue
                
                # Get revenue - prefer value column, but calculate from rate if needed
                revenue = 0
                if value_col is not None and value_col < len(row):
                    val = row.iloc[value_col]
                    if not pd.isna(val) and (isinstance(val, (int, float)) or (isinstance(val, str) and val.replace('.', '', 1).isdigit())):
                        if isinstance(val, str):
                            revenue = float(val.replace(',', ''))
                        else:
                            revenue = float(val)
                            
                if revenue == 0 and rate_col is not None and rate_col < len(row):
                    rate_val = row.iloc[rate_col]
                    if not pd.isna(rate_val) and (isinstance(rate_val, (int, float)) or (isinstance(rate_val, str) and rate_val.replace('.', '', 1).isdigit())):
                        if isinstance(rate_val, str):
                            rate = float(rate_val.replace(',', ''))
                        else:
                            rate = float(rate_val)
                        revenue = rate * quantity
                
                # Estimate cost (30% of revenue)
                cost = revenue * 0.3
                
                # Create sales record
                sales_records.append({
                    "date": sale_date,
                    "item_name": item_name,
                    "quantity": quantity,
                    "revenue": revenue,
                    "cost": cost,
                    "profit": revenue - cost,
                    "profit_margin": ((revenue - cost) / revenue * 100) if revenue > 0 else 0,
                    "imported_at": datetime.now().isoformat()
                })
                
                # Debug the first few records
                if len(sales_records) <= 5:
                    st.write(f"Item: {item_name}, Qty: {quantity}, Revenue: {revenue}")
                
            except Exception as row_err:
                st.warning(f"Error processing row {i}: {str(row_err)}")
                skipped_rows += 1
        
        st.success(f"Extracted {len(sales_records)} sales records from ABGN Sale file. Skipped {skipped_rows} rows.")
        return sales_records
        
    except Exception as e:
        st.error(f"Error extracting ABGN sales data: {str(e)}")
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
        # Check if the directory exists
        if not os.path.exists(directory):
            st.warning(f"Directory {directory} does not exist. Will try attached_assets instead.")
            directory = "attached_assets"  # Try the attached_assets folder as fallback
            
            # If that still doesn't exist, return empty results
            if not os.path.exists(directory):
                st.error(f"Directory {directory} does not exist either.")
                results['errors'].append(f"Directory {directory} does not exist")
                return results
        
        # Get all Excel files in the directory
        files = [os.path.join(directory, f) for f in os.listdir(directory) 
                 if f.endswith('.xlsx') or f.endswith('.xls')]
                 
        st.info(f"Found {len(files)} Excel files in {directory}")
        
        if len(files) == 0:
            st.warning(f"No Excel files found in {directory}.")
            results['errors'].append(f"No Excel files found in {directory}")
            return results
        
        # Process each file
        for file_path in files:
            try:
                file_name = os.path.basename(file_path)
                st.subheader(f"Processing file: {file_name}")
                
                # First check if this is an ABGN file by name
                if 'abgn' in file_name.lower():
                    # Handle special case for ABGN files
                    if 'menu cost' in file_name.lower() or 'recipe cost' in file_name.lower() or 'a la carte' in file_name.lower():
                        st.info("Detected ABGN Recipe Costing file, attempting specialized recipe extraction...")
                        recipes = extract_abgn_recipe_costing(file_path)
                        if recipes:
                            st.success(f"Found {len(recipes)} recipes in {file_name} using specialized ABGN recipe costing extractor")
                            results['recipes'].extend(recipes)
                            continue
                        else:
                            st.warning(f"Failed to extract recipes from ABGN Recipe Costing file {file_name} using specialized extractor, trying generic extraction...")
                            recipes = extract_recipes_from_excel(file_path)
                            if recipes:
                                st.success(f"Found {len(recipes)} recipes in {file_name} using generic extraction")
                                results['recipes'].extend(recipes)
                                continue
                    
                    elif 'sale' in file_name.lower() or 'sales' in file_name.lower():
                        st.info("Detected ABGN Sales file, attempting specialized ABGN sales extraction...")
                        sales = extract_abgn_sales(file_path)
                        if sales:
                            st.success(f"Found {len(sales)} sales records in {file_name}")
                            results['sales'].extend(sales)
                            continue
                        else:
                            st.warning(f"Failed to extract sales data from ABGN Sales file {file_name} using specialized extractor, trying generic extraction...")
                            sales = extract_sales_from_excel(file_path)
                            if sales:
                                st.success(f"Found {len(sales)} sales records in {file_name} using generic extraction")
                                results['sales'].extend(sales)
                                continue
                    
                    elif 'store' in file_name.lower() or 'item receipt' in file_name.lower():
                        st.info("Detected ABGN inventory file, attempting specialized ABGN inventory extraction...")
                        inventory = extract_abgn_inventory(file_path)
                        if inventory:
                            st.success(f"Found {len(inventory)} inventory items in {file_name}")
                            results['inventory'].extend(inventory)
                            continue
                        else:
                            st.warning(f"Failed to extract inventory data from ABGN file {file_name} using specialized extractor, trying generic extraction...")
                            inventory = extract_inventory_from_excel(file_path)
                            if inventory:
                                st.success(f"Found {len(inventory)} inventory items in {file_name} using generic extraction")
                                results['inventory'].extend(inventory)
                                continue
                
                # Now try the recipe extraction, which is generally our primary focus
                st.info(f"Attempting recipe extraction for {file_name}...")
                recipes = extract_recipes_from_excel(file_path)
                if recipes:
                    st.success(f"Found {len(recipes)} recipes in {file_name}")
                    results['recipes'].extend(recipes)
                    continue
                
                # If no recipes found, try detecting and extracting other data types
                st.info(f"No recipes found. Analyzing file type for {file_name}...")
                file_type = detect_file_type(file_path)
                st.write(f"Detected file type: {file_type}")
                
                if file_type == 'inventory':
                    st.info(f"Attempting inventory extraction for {file_name}...")
                    inventory = extract_inventory_from_excel(file_path)
                    if inventory:
                        st.success(f"Found {len(inventory)} inventory items in {file_name}")
                        results['inventory'].extend(inventory)
                    else:
                        st.warning(f"No inventory data could be extracted from {file_name}")
                        results['errors'].append(f"No inventory data found in {file_path}")
                
                elif file_type == 'sales':
                    st.info(f"Attempting sales extraction for {file_name}...")
                    sales = extract_sales_from_excel(file_path)
                    if sales:
                        st.success(f"Found {len(sales)} sales records in {file_name}")
                        results['sales'].extend(sales)
                    else:
                        st.warning(f"No sales data could be extracted from {file_name}")
                        results['errors'].append(f"No sales data found in {file_path}")
                
                else:
                    # If type is unknown, try all extractors
                    st.write(f"Unknown file type. Trying all extractors for {file_name}...")
                    
                    # Try inventory extraction first
                    st.info(f"Attempting inventory extraction for {file_name}...")
                    inventory = extract_inventory_from_excel(file_path)
                    if inventory:
                        st.success(f"Found {len(inventory)} inventory items in {file_name}")
                        results['inventory'].extend(inventory)
                        continue
                    
                    # Then try sales extraction
                    st.info(f"Attempting sales extraction for {file_name}...")
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
        
        # If we found any data, add a shortcut to save it
        if results['recipes'] or results['inventory'] or results['sales']:
            st.success("Data extraction completed successfully!")
            
            # Display the data to save
            if results['recipes']:
                st.info(f"Found {len(results['recipes'])} recipes. Go to the Recipe Management tab to save them.")
                # Initialize session state if needed
                if 'recipes' not in st.session_state:
                    st.session_state.recipes = []
                # Add to session state
                st.session_state.extraction_results = {
                    'type': 'recipe',
                    'data': results['recipes']
                }
                
            if results['inventory']:
                st.info(f"Found {len(results['inventory'])} inventory items. Go to the Inventory Management tab to save them.")
                # Initialize session state if needed
                if 'inventory' not in st.session_state:
                    st.session_state.inventory = []
                # Add to session state
                st.session_state.extraction_results = {
                    'type': 'inventory',
                    'data': results['inventory']
                }
                
            if results['sales']:
                st.info(f"Found {len(results['sales'])} sales records. Go to the Sales Analysis tab to save them.")
                # Initialize session state if needed
                if 'sales' not in st.session_state:
                    st.session_state.sales = []
                # Add to session state
                st.session_state.extraction_results = {
                    'type': 'sales',
                    'data': results['sales']
                }
        else:
            st.warning("No usable data was extracted from any of the files.")
        
        return results
    except Exception as e:
        st.error(f"Error processing directory: {str(e)}")
        results['errors'].append(f"Error processing directory: {str(e)}")
        return results