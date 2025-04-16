"""
Excel Extraction Module

Specialized functions to extract recipe, inventory, and sales data from various Excel formats
"""

import os
import re
from datetime import datetime
import pandas as pd
import streamlit as st

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
        # Try different engines to handle various Excel formats
        engines = ['openpyxl', 'xlrd']
        
        for engine in engines:
            try:
                if isinstance(sheet_name, (int, str)):
                    return pd.read_excel(file_path, sheet_name=sheet_name, engine=engine)
                else:
                    # If sheet_name is a list, dict or None, handle differently
                    return pd.read_excel(file_path, sheet_name=sheet_name, engine=engine)
            except Exception as e:
                last_error = str(e)
                continue
                
        # If we get here, none of the engines worked
        st.error(f"Failed to read Excel file: {last_error}")
        return None
    except Exception as e:
        st.error(f"Error reading Excel file: {str(e)}")
        return None


def detect_file_type(file_path):
    """
    Determine what type of data a file contains
    
    Args:
        file_path (str): Path to the file
        
    Returns:
        str: Type of data ('recipe', 'inventory', 'sales', 'unknown')
    """
    try:
        # Check filename for clues
        filename = os.path.basename(file_path).lower()
        
        # Recipe file indicators
        if any(term in filename for term in ['recipe', 'menu', 'dish', 'food', 'cost sheet']):
            return "recipe"
            
        # Inventory file indicators
        if any(term in filename for term in ['inventory', 'stock', 'item', 'ingredient', 'store', 'items']):
            return "inventory"
            
        # Sales file indicators
        if any(term in filename for term in ['sale', 'sales', 'revenue', 'income']):
            return "sales"
            
        # If filename doesn't help, check file contents
        df = safe_read_excel(file_path)
        if df is None:
            return "unknown"
            
        # Convert the first few rows to lowercase string for pattern matching
        content = ""
        for i in range(min(10, len(df))):
            row = df.iloc[i]
            content += " ".join([str(x).lower() for x in row if pd.notna(x)]) + " "
        
        # Recipe patterns
        if any(term in content for term in ['recipe', 'ingredient', 'portion', 'yield', 'preparation']):
            return "recipe"
            
        # Inventory patterns
        if any(term in content for term in ['inventory', 'stock', 'quantity', 'on hand', 'par level']):
            return "inventory"
            
        # Sales patterns
        if any(term in content for term in ['sales', 'revenue', 'guest count', 'covers', 'transactions']):
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
        # Get all sheets in the Excel file
        try:
            excel = pd.ExcelFile(file_path)
            sheet_names = excel.sheet_names
        except Exception as e:
            st.error(f"Cannot read sheets from {file_path}: {str(e)}")
            return []
            
        # Check if we have multiple sheets
        recipes = []
        
        if len(sheet_names) > 1:
            st.info(f"Found {len(sheet_names)} sheets in the Excel file")
            
            # Process each sheet
            for sheet in sheet_names:
                try:
                    df = safe_read_excel(file_path, sheet_name=sheet)
                    if df is None or df.empty:
                        continue
                        
                    # Check if this sheet contains a complete recipe
                    sheet_recipes = []
                    
                    # Try to find recipe header rows
                    for i in range(min(20, len(df))):
                        row_text = " ".join([str(x).lower() for x in df.iloc[i] if pd.notna(x)])
                        if ("recipe" in row_text or "dish" in row_text) and (
                            "name" in row_text or "title" in row_text or ":" in row_text):
                            # Possible recipe start
                            recipe = extract_single_recipe(df, start_row=i)
                            if recipe and recipe.get('name') and recipe.get('ingredients'):
                                recipe['source_sheet'] = sheet
                                sheet_recipes.append(recipe)
                    
                    # If no recipe headers found, treat entire sheet as one recipe
                    if not sheet_recipes:
                        recipe = extract_single_recipe(df)
                        if recipe and recipe.get('ingredients'):
                            if not recipe.get('name'):
                                recipe['name'] = sheet  # Use sheet name as recipe name
                            recipe['source_sheet'] = sheet
                            sheet_recipes.append(recipe)
                    
                    recipes.extend(sheet_recipes)
                except Exception as sheet_err:
                    st.warning(f"Error processing sheet {sheet}: {str(sheet_err)}")
        else:
            # Just one sheet
            df = safe_read_excel(file_path)
            if df is None or df.empty:
                return []
                
            # Try to find multiple recipes in the sheet
            sheet_recipes = []
            
            # Look for recipe header rows
            for i in range(len(df)):
                row_text = " ".join([str(x).lower() for x in df.iloc[i] if pd.notna(x)])
                if ("recipe" in row_text or "dish" in row_text) and (
                    "name" in row_text or "title" in row_text or ":" in row_text):
                    # Possible recipe start
                    recipe = extract_single_recipe(df, start_row=i)
                    if recipe and recipe.get('name') and recipe.get('ingredients'):
                        sheet_recipes.append(recipe)
            
            # If no recipe headers found, treat entire sheet as one recipe
            if not sheet_recipes:
                recipe = extract_single_recipe(df)
                if recipe and recipe.get('ingredients'):
                    sheet_recipes.append(recipe)
            
            recipes.extend(sheet_recipes)
        
        # Post-process all recipes
        for recipe in recipes:
            # Add default values for missing fields
            if 'source' not in recipe:
                recipe['source'] = os.path.basename(file_path)
            if 'date_added' not in recipe:
                recipe['date_added'] = datetime.now().isoformat()
            if 'yield' not in recipe:
                recipe['yield'] = {"quantity": 1, "unit": "serving"}
            if 'total_cost' not in recipe:
                # Calculate from ingredients if possible
                total = sum(ing.get('total_cost', 0) for ing in recipe.get('ingredients', []))
                recipe['total_cost'] = total if total > 0 else 0
        
        st.success(f"Extracted {len(recipes)} recipes from {file_path}")
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
        recipe = {
            'name': '',
            'description': '',
            'ingredients': [],
            'instructions': '',
            'yield': {'quantity': 1, 'unit': 'serving'},
            'total_cost': 0,
            'cost_per_serving': 0
        }
        
        # First, try to find the recipe name
        for i in range(start_row, min(start_row + 10, len(df))):
            row = df.iloc[i]
            
            # Check each cell in the row
            for j, cell in enumerate(row):
                if pd.isna(cell):
                    continue
                    
                cell_text = str(cell).strip()
                
                # Look for recipe name patterns
                if "recipe" in cell_text.lower() and ":" in cell_text:
                    parts = cell_text.split(":", 1)
                    recipe_name = parts[1].strip() if len(parts) > 1 else ""
                    if recipe_name:
                        recipe['name'] = recipe_name
                        break
                
                # Look for name/title in header cell
                for keyword in ["name", "title", "dish"]:
                    if keyword in cell_text.lower() and ":" in cell_text:
                        parts = cell_text.split(":", 1)
                        recipe_name = parts[1].strip() if len(parts) > 1 else ""
                        if recipe_name:
                            recipe['name'] = recipe_name
                            break
                        # Check next cell for the name
                        elif j+1 < len(row) and pd.notna(row[j+1]):
                            next_cell = str(row[j+1]).strip()
                            if next_cell and not any(k in next_cell.lower() for k in ["recipe", "method", "cost"]):
                                recipe['name'] = next_cell
                                break
        
        # If still no name found, look for capitalized text in first few rows
        if not recipe['name']:
            for i in range(start_row, min(start_row + 5, len(df))):
                row = df.iloc[i]
                for cell in row:
                    if pd.isna(cell):
                        continue
                    cell_text = str(cell).strip()
                    # Look for a capitalized name that isn't too long
                    if cell_text.upper() == cell_text and 3 <= len(cell_text) <= 50:
                        recipe['name'] = cell_text
                        break
                    # Or first letter capitalized
                    elif cell_text and cell_text[0].isupper() and 3 <= len(cell_text) <= 50:
                        recipe['name'] = cell_text
                        break
                if recipe['name']:
                    break
        
        # Try to find a description
        # Usually a paragraph near the recipe name
        for i in range(start_row, min(start_row + 15, len(df))):
            row = df.iloc[i]
            for cell in row:
                if pd.isna(cell):
                    continue
                cell_text = str(cell).strip()
                # Look for a longer text that might be a description
                if len(cell_text.split()) > 5 and len(cell_text) > 30:
                    if "ingredient" not in cell_text.lower() and "instruction" not in cell_text.lower():
                        recipe['description'] = cell_text
                        break
            if recipe['description']:
                break
        
        # Now find ingredients section
        # Ingredients are usually in a structured format with amounts and units
        ingredient_start_row = -1
        ingredient_end_row = -1
        
        # Look for ingredient header
        for i in range(start_row, min(start_row + 30, len(df))):
            row = df.iloc[i]
            row_text = " ".join([str(x).lower() for x in row if pd.notna(x)])
            
            if "ingredient" in row_text and any(term in row_text for term in ["amount", "quantity", "qty"]):
                ingredient_start_row = i + 1  # Start from the next row
                break
                
        # If ingredient header not found, look for patterns in the data
        if ingredient_start_row < 0:
            ingredient_candidates = []
            
            for i in range(start_row, min(start_row + 50, len(df))):
                row = df.iloc[i]
                row_text = " ".join([str(x).lower() for x in row if pd.notna(x)])
                
                # Skip empty rows
                if not row_text.strip():
                    continue
                
                # Ingredient row usually has a number followed by a unit and name
                if re.search(r'\d+\s*(?:g|kg|ml|l|cup|tbsp|tsp|oz|lb|piece|slice)', row_text):
                    ingredient_candidates.append(i)
            
            # If we have several consecutive rows, this might be the ingredients section
            if len(ingredient_candidates) >= 2:
                if ingredient_candidates[-1] - ingredient_candidates[0] <= len(ingredient_candidates) + 3:
                    # Consecutive or nearly consecutive rows, this is likely the ingredients list
                    ingredient_start_row = ingredient_candidates[0]
                    
        # Now find the end of the ingredients section
        if ingredient_start_row >= 0:
            # Usually ends when we hit "instructions" or "method" or a blank row followed by paragraph
            for i in range(ingredient_start_row, len(df)):
                row = df.iloc[i]
                row_text = " ".join([str(x).lower() for x in row if pd.notna(x)])
                
                if not row_text.strip():
                    # Could be the end, check next non-empty row
                    for j in range(i + 1, min(i + 5, len(df))):
                        if j >= len(df):
                            break
                        next_row = df.iloc[j]
                        next_text = " ".join([str(x).lower() for x in next_row if pd.notna(x)])
                        if next_text.strip():
                            if any(term in next_text for term in ["instruction", "method", "preparation", "step"]):
                                ingredient_end_row = i
                                break
                            elif len(next_text.split()) > 5:  # Looks like a paragraph
                                ingredient_end_row = i
                                break
                    if ingredient_end_row >= 0:
                        break
                
                if any(term in row_text for term in ["instruction", "method", "preparation", "step"]):
                    ingredient_end_row = i
                    break
                    
            # If still no end found, just process a reasonable number of rows
            if ingredient_end_row < 0:
                ingredient_end_row = min(ingredient_start_row + 30, len(df))
                
            # Process ingredients rows
            for i in range(ingredient_start_row, ingredient_end_row):
                row = df.iloc[i]
                
                # Skip empty rows
                row_text = " ".join([str(x) for x in row if pd.notna(x)])
                if not row_text.strip():
                    continue
                    
                # Different formats for ingredients
                # 1. Structured columns: Amount | Unit | Ingredient | Cost
                # 2. Combined text: "100g flour"
                
                # Check if this is a structured row
                amount = None
                unit = None
                name = None
                cost = None
                
                # Try to identify columns by header or content
                if i == ingredient_start_row and any(
                    term in str(x).lower() for x in row if pd.notna(x)
                    for term in ["amount", "quantity", "ingredient", "cost"]):
                    # This is a header row, skip it
                    continue
                
                # Look for structured columns
                for j, cell in enumerate(row):
                    if pd.isna(cell):
                        continue
                        
                    cell_text = str(cell).strip()
                    
                    # Is this cell a quantity?
                    if amount is None and re.match(r'^\d+\.?\d*$', cell_text):
                        amount = float(cell_text)
                        continue
                        
                    # Is this cell a unit?
                    if unit is None and cell_text in [
                        "g", "kg", "ml", "l", "cup", "tbsp", "tsp", "oz", "lb", 
                        "piece", "slice", "clove", "pinch", "sheet", "stalk"
                    ]:
                        unit = cell_text
                        continue
                        
                    # Is this cell a cost?
                    if cost is None and re.match(r'^\$?\d+\.?\d*$', cell_text.replace(',', '')):
                        cost = float(cell_text.replace('$', '').replace(',', ''))
                        continue
                        
                    # If not any of the above, might be the ingredient name
                    if name is None and len(cell_text) > 0:
                        name = cell_text
                
                # If we don't have a structured row, try to parse combined format
                if name is None or amount is None:
                    # Try parsing the whole row as a single ingredient
                    full_text = " ".join([str(x) for x in row if pd.notna(x)])
                    parsed = parse_ingredient_row(full_text)
                    
                    amount = parsed.get('amount')
                    unit = parsed.get('unit')
                    name = parsed.get('name')
                
                # If we have an ingredient name, add it
                if name:
                    ingredient = {
                        'name': name,
                        'amount': amount or 0,
                        'unit': unit or '',
                        'cost': cost or 0,
                        'total_cost': cost or 0
                    }
                    
                    # If we have amount and cost, calculate total_cost
                    if amount and cost:
                        ingredient['total_cost'] = amount * cost
                        
                    recipe['ingredients'].append(ingredient)
        
        # Find instructions section
        instruction_start_row = -1
        
        # Look for instructions header
        for i in range(start_row, min(start_row + 50, len(df))):
            row = df.iloc[i]
            row_text = " ".join([str(x).lower() for x in row if pd.notna(x)])
            
            if any(term in row_text for term in ["instruction", "method", "preparation", "step"]):
                instruction_start_row = i + 1  # Start from the next row
                break
        
        # Extract instructions if found
        if instruction_start_row >= 0:
            instruction_text = []
            
            for i in range(instruction_start_row, len(df)):
                row = df.iloc[i]
                
                # Check if we've reached the end of instructions (e.g., Notes, Nutrition, etc.)
                row_text = " ".join([str(x).lower() for x in row if pd.notna(x)])
                if row_text and any(term in row_text for term in ["note:", "nutrition:", "chef tip:", "serving suggestion:"]):
                    break
                    
                # Add non-empty cells to instructions
                for cell in row:
                    if pd.notna(cell) and str(cell).strip():
                        instruction_text.append(str(cell).strip())
            
            recipe['instructions'] = "\n".join(instruction_text)
        
        # Look for yield/serving information
        for i in range(start_row, min(start_row + 30, len(df))):
            row = df.iloc[i]
            for cell in row:
                if pd.isna(cell):
                    continue
                    
                cell_text = str(cell).lower()
                
                if "yield" in cell_text or "portion" in cell_text or "serving" in cell_text:
                    # Try to extract quantity and unit
                    match = re.search(r'(\d+\.?\d*)\s*([a-zA-Z]+)', cell_text)
                    if match:
                        recipe['yield'] = {
                            'quantity': float(match.group(1)),
                            'unit': match.group(2)
                        }
                        break
                    
                    # Check next cell if current cell just has the keyword
                    j = list(row).index(cell)
                    if j + 1 < len(row) and pd.notna(row[j+1]):
                        next_cell = str(row[j+1]).lower()
                        match = re.search(r'(\d+\.?\d*)\s*([a-zA-Z]+)', next_cell)
                        if match:
                            recipe['yield'] = {
                                'quantity': float(match.group(1)),
                                'unit': match.group(2)
                            }
                            break
        
        # Calculate total cost and cost per serving
        ingredient_cost = sum(ing.get('total_cost', 0) for ing in recipe['ingredients'])
        recipe['total_cost'] = ingredient_cost
        
        if recipe['yield']['quantity'] > 0:
            recipe['cost_per_serving'] = recipe['total_cost'] / recipe['yield']['quantity']
        
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
        result = {'name': '', 'amount': None, 'unit': ''}
        
        # Common units to look for
        units = [
            'g', 'kg', 'mg', 
            'ml', 'l', 'cl', 
            'cup', 'cups',
            'tbsp', 'tsp', 
            'oz', 'lb', 
            'piece', 'pieces', 
            'slice', 'slices',
            'pinch', 'pinches',
            'clove', 'cloves',
            'bunch', 'bunches',
            'stalk', 'stalks',
            'sheet', 'sheets',
            'drop', 'drops'
        ]
        
        # Pattern to match numeric amount followed by unit
        # e.g., "100g", "2 cups", "1.5 tbsp"
        pattern = r'(\d+\.?\d*)\s*([a-zA-Z]+)'
        match = re.search(pattern, row_str)
        
        if match:
            amount_str = match.group(1)
            unit_candidate = match.group(2).lower()
            
            # Check if the unit is valid
            unit = unit_candidate
            for valid_unit in units:
                if unit_candidate.startswith(valid_unit):
                    unit = valid_unit
                    break
            
            # Extract the remaining text as the ingredient name
            name = row_str[match.end():].strip()
            
            # If name starts with "of", remove it
            if name.lower().startswith('of '):
                name = name[3:].strip()
            
            result['amount'] = float(amount_str)
            result['unit'] = unit
            result['name'] = name
        else:
            # No amount/unit found, treat the whole string as the name
            result['name'] = row_str.strip()
        
        return result
        
    except Exception as e:
        st.error(f"Error parsing ingredient row: {str(e)}")
        return {'name': row_str, 'amount': None, 'unit': ''}


def extract_inventory_from_excel(file_path):
    """
    Extract inventory information from an Excel file
    
    Args:
        file_path (str): Path to the Excel file
        
    Returns:
        list: Extracted inventory items
    """
    try:
        df = safe_read_excel(file_path)
        if df is None or df.empty:
            return []
            
        # First, try to identify the header row
        header_row = -1
        for i in range(min(10, len(df))):
            row = df.iloc[i]
            row_text = " ".join([str(x).lower() for x in row if pd.notna(x)])
            
            # Look for common inventory column headers
            if sum(1 for term in ["item", "name", "quantity", "stock", "cost", "price", "unit"] if term in row_text) >= 2:
                header_row = i
                break
                
        # If no header row found, make a guess based on data structure
        if header_row < 0:
            # Look for a row with a good number of non-empty cells that might be headers
            for i in range(min(5, len(df))):
                non_empty = sum(1 for x in df.iloc[i] if pd.notna(x))
                if non_empty >= 3:
                    header_row = i
                    break
            
            # If still not found, assume the first row is the header
            if header_row < 0:
                header_row = 0
                
        # Extract column headers
        headers = [str(x).lower() if pd.notna(x) else "" for x in df.iloc[header_row]]
        
        # Try to identify which columns contain what data
        item_code_col = -1
        name_col = -1
        category_col = -1
        quantity_col = -1
        unit_col = -1
        cost_col = -1
        price_col = -1
        value_col = -1
        location_col = -1
        
        for i, header in enumerate(headers):
            # Item code/SKU
            if any(term in header for term in ["code", "sku", "item id", "product id"]):
                item_code_col = i
                
            # Item name/description
            elif any(term in header for term in ["name", "description", "item", "product"]) and "code" not in header:
                name_col = i
                
            # Category/group
            elif any(term in header for term in ["category", "group", "type", "department"]):
                category_col = i
                
            # Quantity/stock level
            elif any(term in header for term in ["quantity", "stock", "on hand", "level", "count", "inventory"]):
                quantity_col = i
                
            # Unit of measure
            elif any(term in header for term in ["unit", "uom", "measure"]):
                unit_col = i
                
            # Cost price
            elif any(term in header for term in ["cost", "purchase price"]):
                cost_col = i
                
            # Selling price
            elif any(term in header for term in ["price", "selling price", "retail price"]):
                price_col = i
                
            # Total value
            elif any(term in header for term in ["value", "total", "extended cost"]):
                value_col = i
                
            # Storage location
            elif any(term in header for term in ["location", "storage", "bin", "warehouse"]):
                location_col = i
        
        # If name column not found, make a best guess
        if name_col < 0:
            # Second column is often the name
            if len(headers) > 1:
                name_col = 1
                
        # Extract inventory items
        inventory_items = []
        start_row = header_row + 1
        
        for i in range(start_row, len(df)):
            try:
                row = df.iloc[i]
                
                # Skip empty rows
                if all(pd.isna(x) for x in row):
                    continue
                    
                # Skip rows that look like category headers or summaries
                row_text = " ".join([str(x).lower() for x in row if pd.notna(x)])
                if any(term in row_text for term in ["total", "summary", "subtotal", "group total"]):
                    continue
                
                # Get name (required)
                name = ""
                if name_col >= 0 and name_col < len(row) and pd.notna(row[name_col]):
                    name = str(row[name_col]).strip()
                else:
                    # If no name column found, look for any non-empty cell
                    for j, cell in enumerate(row):
                        if pd.notna(cell) and isinstance(cell, str) and j != item_code_col:
                            name = str(cell).strip()
                            break
                
                # Skip if no valid name
                if not name:
                    continue
                
                # Get item code
                item_code = ""
                if item_code_col >= 0 and item_code_col < len(row) and pd.notna(row[item_code_col]):
                    item_code = str(row[item_code_col]).strip()
                
                # Get category
                category = "Uncategorized"
                if category_col >= 0 and category_col < len(row) and pd.notna(row[category_col]):
                    category = str(row[category_col]).strip()
                
                # Get unit
                unit = ""
                if unit_col >= 0 and unit_col < len(row) and pd.notna(row[unit_col]):
                    unit = str(row[unit_col]).strip()
                
                # Get quantity
                quantity = 0
                if quantity_col >= 0 and quantity_col < len(row) and pd.notna(row[quantity_col]):
                    try:
                        quantity = float(row[quantity_col])
                    except:
                        pass
                
                # Get cost
                cost = 0
                if cost_col >= 0 and cost_col < len(row) and pd.notna(row[cost_col]):
                    try:
                        cost_text = str(row[cost_col]).replace('$', '').replace(',', '')
                        cost = float(cost_text)
                    except:
                        pass
                
                # Get price
                price = 0
                if price_col >= 0 and price_col < len(row) and pd.notna(row[price_col]):
                    try:
                        price_text = str(row[price_col]).replace('$', '').replace(',', '')
                        price = float(price_text)
                    except:
                        pass
                
                # Get value
                value = 0
                if value_col >= 0 and value_col < len(row) and pd.notna(row[value_col]):
                    try:
                        value_text = str(row[value_col]).replace('$', '').replace(',', '')
                        value = float(value_text)
                    except:
                        pass
                # Calculate value if not directly provided
                elif quantity > 0 and cost > 0:
                    value = quantity * cost
                
                # Get location
                location = ""
                if location_col >= 0 and location_col < len(row) and pd.notna(row[location_col]):
                    location = str(row[location_col]).strip()
                
                # Create inventory item
                item = {
                    "item_code": item_code,
                    "name": name,
                    "category": category,
                    "unit": unit,
                    "stock_level": quantity,
                    "cost": cost,
                    "price": price,
                    "value": value,
                    "location": location,
                    "imported_at": datetime.now().isoformat()
                }
                
                inventory_items.append(item)
            except Exception as row_err:
                st.warning(f"Error processing row {i}: {str(row_err)}")
        
        st.success(f"Extracted {len(inventory_items)} inventory items from {file_path}")
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
        df = safe_read_excel(file_path)
        if df is None or df.empty:
            return []
            
        # Try to extract date from filename
        filename = os.path.basename(file_path).lower()
        sale_date = datetime.now().strftime("%Y-%m-%d")  # Default to today
        
        # Look for date patterns in filename
        date_match = re.search(r'(\d{4}[\-_]\d{1,2}[\-_]\d{1,2})', filename)
        if date_match:
            try:
                date_str = date_match.group(1).replace('_', '-')
                sale_date = datetime.strptime(date_str, "%Y-%m-%d").strftime("%Y-%m-%d")
            except:
                pass
        
        # Also try month/year format like "Jan 2023" or "01-2023"
        month_match = re.search(r'(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[\-_\s](\d{4})', filename, re.IGNORECASE)
        if month_match:
            try:
                month_str = month_match.group(1).lower()
                year_str = month_match.group(2)
                
                month_map = {
                    'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'may': 5, 'jun': 6,
                    'jul': 7, 'aug': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12
                }
                
                month_num = month_map.get(month_str, 1)
                sale_date = f"{year_str}-{month_num:02d}-15"  # Use middle of month
            except:
                pass
                
        # Find the header row
        header_row = -1
        for i in range(min(15, len(df))):
            row_text = " ".join([str(x).lower() for x in df.iloc[i] if pd.notna(x)])
            
            # Look for key sales columns
            if sum(1 for term in ["item", "product", "qty", "quantity", "sales", "revenue", "price", "amount"] if term in row_text) >= 3:
                header_row = i
                break
                
        # If no header found, use first row
        if header_row < 0:
            header_row = 0
            
        # Get headers
        headers = [str(x).lower() if pd.notna(x) else "" for x in df.iloc[header_row]]
        
        # Find important columns
        date_col = -1
        item_col = -1
        quantity_col = -1
        price_col = -1
        revenue_col = -1
        
        for i, header in enumerate(headers):
            # Date column
            if any(term in header for term in ["date", "day", "time"]):
                date_col = i
                
            # Item/product column
            elif any(term in header for term in ["item", "product", "dish", "menu", "name", "description"]):
                item_col = i
                
            # Quantity column
            elif any(term in header for term in ["qty", "quantity", "count", "sold", "volume"]):
                quantity_col = i
                
            # Price column
            elif any(term in header for term in ["price", "rate", "unit price"]):
                price_col = i
                
            # Revenue/sales column
            elif any(term in header for term in ["revenue", "sales", "amount", "total", "value"]):
                revenue_col = i
        
        # If item column not found, make a best guess
        if item_col < 0:
            # Often in first or second column
            for col in [1, 0, 2]:
                if col < len(headers) and col not in [date_col, quantity_col, price_col, revenue_col]:
                    item_col = col
                    break
        
        # Extract sales data
        sales_records = []
        start_row = header_row + 1
        
        for i in range(start_row, len(df)):
            try:
                row = df.iloc[i]
                
                # Skip empty rows
                if all(pd.isna(x) for x in row):
                    continue
                    
                # Skip rows that look like summaries
                row_text = " ".join([str(x).lower() for x in row if pd.notna(x)])
                if any(term in row_text for term in ["total", "summary", "subtotal", "grand total"]):
                    continue
                
                # Get item name (required)
                item_name = ""
                if item_col >= 0 and item_col < len(row) and pd.notna(row[item_col]):
                    item_name = str(row[item_col]).strip()
                else:
                    # If no item column found, look for any string cell
                    for j, cell in enumerate(row):
                        if pd.notna(cell) and isinstance(cell, str) and len(str(cell).strip()) > 1:
                            item_name = str(cell).strip()
                            break
                
                # Skip if no valid item name
                if not item_name:
                    continue
                
                # Get date
                record_date = sale_date
                if date_col >= 0 and date_col < len(row) and pd.notna(row[date_col]):
                    try:
                        date_value = row[date_col]
                        if isinstance(date_value, datetime):
                            record_date = date_value.strftime("%Y-%m-%d")
                        elif isinstance(date_value, str):
                            # Try different date formats
                            for fmt in ["%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y", "%d-%m-%Y", "%m-%d-%Y"]:
                                try:
                                    record_date = datetime.strptime(date_value, fmt).strftime("%Y-%m-%d")
                                    break
                                except:
                                    pass
                    except:
                        pass
                
                # Get quantity
                quantity = 0
                if quantity_col >= 0 and quantity_col < len(row) and pd.notna(row[quantity_col]):
                    try:
                        quantity = float(row[quantity_col])
                    except:
                        pass
                
                # Get price
                price = 0
                if price_col >= 0 and price_col < len(row) and pd.notna(row[price_col]):
                    try:
                        price_text = str(row[price_col]).replace('$', '').replace(',', '')
                        price = float(price_text)
                    except:
                        pass
                
                # Get revenue
                revenue = 0
                if revenue_col >= 0 and revenue_col < len(row) and pd.notna(row[revenue_col]):
                    try:
                        revenue_text = str(row[revenue_col]).replace('$', '').replace(',', '')
                        revenue = float(revenue_text)
                    except:
                        pass
                # Calculate revenue if not directly provided
                elif quantity > 0 and price > 0:
                    revenue = quantity * price
                
                # Estimate cost (30% of revenue as a default)
                cost = revenue * 0.3
                
                # Create sales record
                record = {
                    "date": record_date,
                    "item_name": item_name,
                    "quantity": quantity,
                    "unit_price": price,
                    "revenue": revenue,
                    "cost": cost,
                    "profit": revenue - cost,
                    "profit_margin": ((revenue - cost) / revenue * 100) if revenue > 0 else 0,
                    "imported_at": datetime.now().isoformat()
                }
                
                sales_records.append(record)
            except Exception as row_err:
                st.warning(f"Error processing row {i}: {str(row_err)}")
        
        st.success(f"Extracted {len(sales_records)} sales records from {file_path}")
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
                        # Now using the function from abgn_extractor module
                        from utils.abgn_extractor import extract_recipe_costing
                        recipes = extract_recipe_costing(file_path)
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
                        # Now using the function from abgn_extractor module
                        from utils.abgn_extractor import extract_sales
                        sales = extract_sales(file_path)
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
                        # Now using the function from abgn_extractor module
                        from utils.abgn_extractor import extract_inventory
                        inventory = extract_inventory(file_path)
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