"""
ABGN Format Extractor

Specialized module for extracting data from ABGN format Excel files
"""

import pandas as pd
import streamlit as st
from datetime import datetime
import os
import re

def extract_recipe_costing(file_path):
    """
    Extract recipe data specifically from ABGN A La Carte Menu Cost format Excel files
    
    Args:
        file_path (str): Path to the ABGN Recipe Costing Excel file
        
    Returns:
        list: Extracted recipes
    """
    try:
        st.info(f"Starting ABGN recipe extraction from {file_path}")
        
        # Define the expected ABGN column names for ingredients
        ABGN_COLUMNS = {
            'item_code': ['item code', 'item', 'code', 'item.code'],
            'name': ['ingredients', 'ingredient', 'description', 'item name'],
            'unit': ['unit', 'uom', 'unit of measure', 'measure'],
            'qty': ['qty', 'quantity', 'req.qty', 'required qty'],
            'loss': ['loss', 'waste', 'loss %', 'loss qty'],
            'net_qty': ['net qty', 'net quantity', 'net.qty', 'net'],
            'unit_cost': ['at amount', 'rate', 'price', 'unit price', 'amount', 'unit cost'],
            'total_cost': ['total amount ks', 'total', 'total amount', 'total cost', 'ext.amount']
        }
        
        # Try different engines to handle various Excel formats
        xls = None
        try:
            xls = pd.ExcelFile(file_path, engine='openpyxl')
            st.success("Successfully opened Excel file with openpyxl engine")
        except Exception as e1:
            st.warning(f"openpyxl engine failed: {str(e1)}")
            try:
                xls = pd.ExcelFile(file_path, engine='xlrd')
                st.success("Successfully opened Excel file with xlrd engine")
            except Exception as e2:
                st.error(f"Failed to open Excel file with both engines: {str(e1)}; {str(e2)}")
                return []
        
        # Get all sheet names
        sheet_names = xls.sheet_names
        
        if not sheet_names:
            st.warning("No sheets found in file")
            return []
            
        st.info(f"Found {len(sheet_names)} sheets: {', '.join(sheet_names)}")
        
        all_recipes = []
        
        # Process each sheet
        for sheet_idx, sheet_name in enumerate(sheet_names):
            try:
                st.info(f"Processing sheet {sheet_idx+1}/{len(sheet_names)}: {sheet_name}")
                
                # Load sheet
                df = pd.read_excel(file_path, sheet_name=sheet_name)
                
                # Skip empty sheets
                if df.empty:
                    st.warning(f"Sheet {sheet_name} is empty")
                    continue
                
                # Fix any completely blank rows (replace NaN with empty string)
                df = df.fillna('')
                
                # Find all potential recipe sections
                # ABGN recipe format typically has headers with "STANDARD RECIPE" or similar text
                recipe_markers = []
                
                for i in range(len(df)):
                    row_values = [str(x).lower() for x in df.iloc[i] if str(x).strip()]
                    row_text = " ".join(row_values)
                    
                    # Look for typical recipe header patterns
                    if any(marker in row_text for marker in [
                        "standard recipe", "recipe card", "recipe cost", "menu item",
                        "cost calculation", "food cost"
                    ]):
                        recipe_markers.append(i)
                
                # If no markers found, try to find ingredient table headers
                if not recipe_markers:
                    for i in range(len(df)):
                        row_values = [str(x).lower() for x in df.iloc[i] if str(x).strip()]
                        row_text = " ".join(row_values)
                        
                        if "item code" in row_text and "ingredients" in row_text and ("unit" in row_text or "qty" in row_text):
                            # Found an ingredient table header - go back a few rows to find recipe start
                            start_idx = max(0, i-5)
                            recipe_markers.append(start_idx)
                
                if not recipe_markers:
                    st.warning(f"No recipe markers found in sheet {sheet_name}")
                    continue
                
                st.success(f"Found {len(recipe_markers)} potential recipes in sheet {sheet_name}")
                
                # Process each recipe section
                for i, start_idx in enumerate(recipe_markers):
                    try:
                        # Determine the end of this recipe (next recipe start or end of sheet)
                        end_idx = recipe_markers[i+1] if i < len(recipe_markers)-1 else len(df)
                        
                        # Extract just this recipe's rows
                        recipe_df = df.iloc[start_idx:end_idx].copy().reset_index(drop=True)
                        
                        # Step 1: Find the recipe name
                        recipe_name = ""
                        
                        # In ABGN format, look specifically for the "NAME" row first
                        name_row_idx = None
                        for j in range(min(8, len(recipe_df))):
                            if isinstance(recipe_df.iloc[j, 0], str) and recipe_df.iloc[j, 0].strip() == "NAME":
                                name_row_idx = j
                                break
                        
                        # If NAME row found, get recipe name from column B of the same row
                        if name_row_idx is not None and recipe_df.shape[1] > 1:
                            recipe_name = str(recipe_df.iloc[name_row_idx, 1]).strip()
                            st.info(f"Found recipe name '{recipe_name}' in NAME row (B{name_row_idx+1})")
                        
                        # If still no name found, use the standard fallback strategies
                        if not recipe_name or recipe_name.lower() in ["nan", ""]:
                            # Strategy 1: Look for cells with "NAME:" or "MENU ITEM:" patterns
                            for j in range(min(10, len(recipe_df))):
                                row = recipe_df.iloc[j]
                                
                                for k, cell in enumerate(row):
                                    cell_str = str(cell).strip()
                                    cell_lower = cell_str.lower()
                                    
                                    # Check for explicit name patterns
                                    if ("name:" in cell_lower or "menu item:" in cell_lower or "item name:" in cell_lower) and ":" in cell_str:
                                        # Extract name after the colon
                                        parts = cell_str.split(":", 1)
                                        if len(parts) > 1 and parts[1].strip():
                                            recipe_name = parts[1].strip()
                                            break
                                        # If no text after colon, look at next cell
                                        elif k+1 < len(row) and str(row.iloc[k+1]).strip():
                                            next_cell = str(row.iloc[k+1]).strip()
                                            if len(next_cell) > 2:  # Ensure it's not just a number
                                                recipe_name = next_cell
                                                break
                                
                                if recipe_name:
                                    break
                            
                            # Strategy 2: Look for cells containing "Recipe Name" or similar
                            if not recipe_name:
                                for j in range(min(10, len(recipe_df))):
                                    row = recipe_df.iloc[j]
                                    
                                    for k, cell in enumerate(row):
                                        cell_str = str(cell).strip()
                                        cell_lower = cell_str.lower()
                                        
                                        if ("recipe name" in cell_lower or "recipe title" in cell_lower or "dish name" in cell_lower):
                                            # If found, check the next cell or cells in the same row for the name
                                            for l in range(k+1, len(row)):
                                                next_cell = str(row.iloc[l]).strip()
                                                if len(next_cell) > 2 and not any(ignore in next_cell.lower() for ignore in ["standard", "recipe", "card"]):
                                                    recipe_name = next_cell
                                                    break
                                            
                                            # If not found in same row, check cell below
                                            if not recipe_name and j+1 < len(recipe_df):
                                                below_cell = str(recipe_df.iloc[j+1, k]).strip()
                                                if len(below_cell) > 2 and not any(ignore in below_cell.lower() for ignore in ["standard", "recipe", "card"]):
                                                    recipe_name = below_cell
                                            
                                            break
                                    
                                    if recipe_name:
                                        break
                            
                            # Strategy 3: Look for a prominent standalone title in first few rows
                            if not recipe_name:
                                for j in range(min(10, len(recipe_df))):
                                    row = recipe_df.iloc[j]
                                    
                                    for cell in row:
                                        cell_str = str(cell).strip()
                                        # Avoid common header words and ensure reasonable length
                                        if (3 <= len(cell_str) <= 50 and 
                                            not any(ignore in cell_str.upper() for ignore in [
                                                "STANDARD RECIPE", "RECIPE CARD", "COST CALCULATION", "ITEM CODE", 
                                                "INGREDIENTS", "UNIT", "QTY", "FOOD COST", "AMOUNT"
                                            ])):
                                            # Check if it looks like a title (first letter uppercase or all caps)
                                            if (cell_str[0].isupper() or cell_str.isupper()) and not cell_str.isdigit():
                                                recipe_name = cell_str
                                                break
                                    
                                    if recipe_name:
                                        break
                        
                        # Default name if still not found
                        if not recipe_name or recipe_name.lower() in ["nan", ""]:
                            recipe_name = f"{sheet_name} Recipe {i+1}"
                        
                        st.info(f"Recipe found: {recipe_name}")
                        
                        # Step 2: Find the ingredient table header row
                        header_row_idx = -1
                        
                        for j in range(len(recipe_df)):
                            row_values = [str(x).lower() for x in recipe_df.iloc[j] if str(x).strip()]
                            row_text = " ".join(row_values)
                            
                            # Look for the ingredient table header pattern
                            if (("item code" in row_text or "code" in row_text) and 
                                ("ingredients" in row_text or "ingredient" in row_text) and 
                                ("unit" in row_text or "uom" in row_text or "qty" in row_text)):
                                header_row_idx = j
                                break
                        
                        if header_row_idx == -1:
                            st.warning(f"Could not find ingredient table header for recipe: {recipe_name}")
                            continue
                        
                        # Step 3: Map the column indices to our expected fields
                        header_row = recipe_df.iloc[header_row_idx]
                        column_mapping = {}
                        
                        # For each expected column, try to find the matching column in the header
                        for field, possible_names in ABGN_COLUMNS.items():
                            for col_idx, header_cell in enumerate(header_row):
                                header_text = str(header_cell).lower().strip()
                                if any(possible_name in header_text for possible_name in possible_names):
                                    column_mapping[field] = col_idx
                                    break
                        
                        # Check if we found the essential columns
                        if 'name' not in column_mapping:
                            st.warning(f"Could not find ingredient name column for recipe: {recipe_name}")
                            continue
                        
                        st.info(f"Found ingredient table with columns: {', '.join(column_mapping.keys())}")
                        
                        # Step 4: Find the end of the ingredient table
                        # Usually ends with a "Total Cost" row or a blank row
                        ingredients_end_idx = len(recipe_df)
                        
                        for j in range(header_row_idx + 1, len(recipe_df)):
                            row_values = [str(x).lower() for x in recipe_df.iloc[j] if str(x).strip()]
                            row_text = " ".join(row_values)
                            
                            if ((not row_values) or  # Empty row
                                ("total" in row_text and "cost" in row_text) or  # Total cost row
                                any(x in row_text for x in ["grand total", "total cost", "food cost %"])):
                                ingredients_end_idx = j
                                break
                        
                        # Step 5: Extract ingredients
                        ingredients = []
                        
                        for j in range(header_row_idx + 1, ingredients_end_idx):
                            row = recipe_df.iloc[j]
                            
                            # Skip empty rows
                            if all(not str(x).strip() for x in row):
                                continue
                            
                            # Initialize ingredient data with all fields
                            ingredient_data = {
                                'item_code': '',
                                'name': '',
                                'unit': '',
                                'qty': 0,
                                'loss': 0,
                                'net_qty': 0,
                                'unit_cost': 0,
                                'total_cost': 0
                            }
                            
                            # Read each column based on mapping
                            for field, col_idx in column_mapping.items():
                                if col_idx < len(row) and str(row.iloc[col_idx]).strip():
                                    cell_value = row.iloc[col_idx]
                                    
                                    # Process based on field type
                                    if field in ['item_code', 'name', 'unit']:
                                        # Text fields
                                        ingredient_data[field] = str(cell_value).strip()
                                    else:
                                        # Numeric fields
                                        try:
                                            # Try to convert to float
                                            if isinstance(cell_value, (int, float)):
                                                ingredient_data[field] = float(cell_value)
                                            else:
                                                # Remove any non-numeric characters except decimal point
                                                clean_value = ''.join(c for c in str(cell_value) 
                                                                  if c.isdigit() or c == '.')
                                                if clean_value:
                                                    ingredient_data[field] = float(clean_value)
                                        except (ValueError, TypeError):
                                            # Keep as 0 if conversion fails
                                            pass
                            
                            # Skip rows that don't have a name
                            if not ingredient_data['name']:
                                continue
                                
                            # Set default unit if missing
                            if not ingredient_data['unit']:
                                ingredient_data['unit'] = 'piece'
                                
                            # Calculate net_qty if missing but we have qty
                            # Formula: net_qty = qty + (loss % * qty)
                            if ingredient_data['qty'] > 0:
                                # Apply loss if available - always recalculate net_qty for consistency
                                if ingredient_data['loss'] > 0:
                                    # Loss might be a percentage or absolute value
                                    if ingredient_data['loss'] < 1:  # Likely a percentage (e.g., 0.05 for 5%)
                                        # Correct formula as requested: qty + (loss% * qty)
                                        ingredient_data['net_qty'] = ingredient_data['qty'] + (ingredient_data['loss'] * ingredient_data['qty'])
                                    else:
                                        # If loss is absolute value, add it directly
                                        ingredient_data['net_qty'] = ingredient_data['qty'] + ingredient_data['loss']
                                else:
                                    # No loss, so net quantity equals quantity
                                    ingredient_data['net_qty'] = ingredient_data['qty']
                            
                            # Calculate total_cost if missing but we have unit_cost and qty/net_qty
                            if ingredient_data['total_cost'] == 0 and ingredient_data['unit_cost'] > 0:
                                # Prefer using net_qty for calculation if available
                                qty_to_use = ingredient_data['net_qty'] if ingredient_data['net_qty'] > 0 else ingredient_data['qty']
                                if qty_to_use > 0:
                                    ingredient_data['total_cost'] = ingredient_data['unit_cost'] * qty_to_use
                            
                            # Add ingredient to list
                            ingredients.append(ingredient_data)
                        
                        # Step 6: Find additional recipe info (sales price, portions, etc.)
                        sales_price = 0
                        portions = 1
                        
                        # Calculate total cost by summing ingredients
                        total_cost = sum(ingredient['total_cost'] for ingredient in ingredients)
                        st.info(f"Calculated total cost from ingredients: {total_cost:.2f}")
                        
                        # In ABGN format, find the specific rows for portions and sales price
                        # Look for the row with "COST/PORTION" in it, which is after the NAME row
                        cost_portion_row_idx = None
                        for j in range(len(recipe_df)):
                            row_text = " ".join(str(x).lower() for x in recipe_df.iloc[j] if str(x).strip())
                            if "cost/portion" in row_text:
                                cost_portion_row_idx = j
                                break
                        
                        if cost_portion_row_idx is not None:
                            # Portions are in column D of the row after COST/PORTION
                            portion_row_idx = cost_portion_row_idx + 1
                            if portion_row_idx < len(recipe_df) and 3 < recipe_df.shape[1]:  # Column D is index 3
                                try:
                                    cell_value = recipe_df.iloc[portion_row_idx, 3]
                                    if pd.notna(cell_value) and (isinstance(cell_value, (int, float)) or 
                                                               (isinstance(cell_value, str) and cell_value.replace('.', '', 1).isdigit())):
                                        portions = float(cell_value)
                                        st.info(f"Found portions: {portions} at D{portion_row_idx+1}")
                                except Exception as e:
                                    st.warning(f"Error parsing portions: {str(e)}")
                            
                            # Sales price is typically in column G of the same row
                            if portion_row_idx < len(recipe_df) and 6 < recipe_df.shape[1]:  # Column G is index 6
                                try:
                                    cell_value = recipe_df.iloc[portion_row_idx, 6]
                                    if pd.notna(cell_value) and (isinstance(cell_value, (int, float)) or 
                                                               (isinstance(cell_value, str) and cell_value.replace('.', '', 1).isdigit())):
                                        sales_price = float(cell_value)
                                        st.info(f"Found sales price: {sales_price} at G{portion_row_idx+1}")
                                except Exception as e:
                                    st.warning(f"Error parsing sales price: {str(e)}")
                        
                        # If not found through specific positions, use general pattern matching as fallback
                        if portions == 1:
                            for j in range(len(recipe_df)):
                                row = recipe_df.iloc[j]
                                row_text = " ".join(str(x).lower() for x in row if str(x).strip())
                                
                                # Look for Portions patterns
                                if "portion" in row_text or "yield" in row_text or "no.portion" in row_text:
                                    for k, cell in enumerate(row):
                                        if isinstance(cell, (int, float)) and cell > 0:
                                            portions = float(cell)
                                            st.info(f"Found portions via pattern: {portions}")
                                            break
                        
                        # If still no sales price found, use general pattern matching
                        if sales_price == 0:
                            for j in range(len(recipe_df)):
                                row = recipe_df.iloc[j]
                                row_text = " ".join(str(x).lower() for x in row if str(x).strip())
                                
                                # Sales price patterns
                                if "sales price" in row_text or "selling price" in row_text:
                                    for k, cell in enumerate(row):
                                        if isinstance(cell, (int, float)) and cell > 0:
                                            sales_price = float(cell)
                                            st.info(f"Found sales price via pattern: {sales_price}")
                                            break
                            
                            # Look for total cost confirmation in each row
                            for j in range(len(recipe_df)):
                                row = recipe_df.iloc[j]
                                row_text = " ".join(str(x).lower() for x in row if str(x).strip())
                                
                                if "total cost" in row_text and "total cost ks" not in row_text:
                                    for k, cell in enumerate(row):
                                        if isinstance(cell, (int, float)) and cell > 0:
                                            # Only update if significantly different (sometimes the row total is more accurate)
                                            calculated_total = total_cost
                                            cell_total = float(cell)
                                            if abs(calculated_total - cell_total) / max(calculated_total, cell_total) > 0.05:
                                                total_cost = cell_total
                        
                        # Handle case where portions wasn't found
                        if portions <= 0:
                            portions = 1
                            
                        # Create the recipe object
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
                        st.success(f"Successfully extracted recipe: {recipe_name} with {len(ingredients)} ingredients")
                        
                    except Exception as recipe_err:
                        st.error(f"Error processing recipe at index {i} in sheet {sheet_name}: {str(recipe_err)}")
                
            except Exception as sheet_err:
                st.error(f"Error processing sheet {sheet_name}: {str(sheet_err)}")
        
        # Final success message
        if all_recipes:
            total_ingredients = sum(len(recipe['ingredients']) for recipe in all_recipes)
            st.success(f"Successfully extracted {len(all_recipes)} recipes with {total_ingredients} total ingredients")
        else:
            st.warning("No recipes were extracted from the file")
            
        return all_recipes
        
    except Exception as e:
        st.error(f"Error in ABGN recipe extraction: {str(e)}")
        import traceback
        st.error(traceback.format_exc())
        return []


def extract_inventory(file_path):
    """
    Extract inventory data specifically from ABGN One Line Store format Excel files
    
    Args:
        file_path (str): Path to the ABGN One Line Store Excel file
        
    Returns:
        list: Extracted inventory items
    """
    try:
        st.info(f"Starting ABGN inventory extraction from {file_path}")
        
        # Try different engines to handle various Excel formats
        df = None
        try:
            df = pd.read_excel(file_path, engine='openpyxl')
            st.success("Successfully opened Excel file with openpyxl engine")
        except Exception as e1:
            st.warning(f"openpyxl engine failed: {str(e1)}")
            try:
                df = pd.read_excel(file_path, engine='xlrd')
                st.success("Successfully opened Excel file with xlrd engine")
            except Exception as e2:
                st.error(f"Failed to open Excel file with both engines: {str(e1)}; {str(e2)}")
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
        
        # Extract header and data
        header = df.iloc[header_row]
        data_df = df.iloc[header_row+1:].copy().reset_index(drop=True)
        
        # Define expected columns
        EXPECTED_COLUMNS = {
            'item_code': ['item', 'item code', 'code', 'product code'],
            'name': ['name', 'description', 'item name', 'product name'],
            'unit': ['unit', 'uom', 'um', 'measure'],
            'stock_level': ['clb.bal', 'closing', 'closing balance', 'bal', 'stock'],
            'price': ['value', 'unit price', 'price', 'cost', 'unit cost']
        }
        
        # Map columns to our schema
        column_mapping = {}
        for field, possible_names in EXPECTED_COLUMNS.items():
            for col_idx, header_cell in enumerate(header):
                header_text = str(header_cell).lower().strip()
                if any(possible_name in header_text for possible_name in possible_names):
                    column_mapping[field] = col_idx
                    break
        
        # Check if we found the essential columns
        missing_columns = [field for field in ['item_code', 'name'] if field not in column_mapping]
        if missing_columns:
            st.warning(f"Could not find essential columns: {', '.join(missing_columns)}")
            # Use default positions
            if 'item_code' not in column_mapping:
                column_mapping['item_code'] = 0
            if 'name' not in column_mapping:
                column_mapping['name'] = 1
        
        # Extract inventory items
        inventory_items = []
        current_category = "Uncategorized"
        
        for i in range(len(data_df)):
            row = data_df.iloc[i]
            
            # Skip empty rows
            if all(pd.isna(x) or str(x).strip() == '' for x in row):
                continue
            
            # Check if this is a category header
            first_cell = str(row.iloc[0]).strip() if len(row) > 0 else ""
            if first_cell and all(pd.isna(x) or str(x).strip() == '' for x in row[1:]):
                # This is likely a category heading
                if "total" not in first_cell.lower():
                    current_category = first_cell
                continue
            
            # Extract item data
            item_data = {
                'item_code': '',
                'name': '',
                'category': current_category,
                'unit': '',
                'stock_level': 0,
                'price': 0
            }
            
            # Get values from mapped columns
            for field, col_idx in column_mapping.items():
                if col_idx < len(row) and not pd.isna(row.iloc[col_idx]):
                    cell_value = row.iloc[col_idx]
                    
                    if field in ['item_code', 'name', 'unit', 'category']:
                        # Text fields
                        item_data[field] = str(cell_value).strip()
                    else:
                        # Numeric fields
                        try:
                            if isinstance(cell_value, (int, float)):
                                item_data[field] = float(cell_value)
                            else:
                                # Try to extract numbers from text
                                clean_value = ''.join(c for c in str(cell_value) if c.isdigit() or c == '.')
                                if clean_value:
                                    item_data[field] = float(clean_value)
                        except (ValueError, TypeError):
                            pass
            
            # Skip rows without name or code
            if not item_data['name'] and not item_data['item_code']:
                continue
            
            # Set default name if missing
            if not item_data['name'] and item_data['item_code']:
                item_data['name'] = f"Item {item_data['item_code']}"
            
            # Set default unit if missing
            if not item_data['unit']:
                item_data['unit'] = 'piece'
            
            # Add to inventory list
            inventory_items.append(item_data)
        
        st.success(f"Successfully extracted {len(inventory_items)} inventory items")
        return inventory_items
        
    except Exception as e:
        st.error(f"Error extracting ABGN inventory data: {str(e)}")
        import traceback
        st.error(traceback.format_exc())
        return []


def extract_sales(file_path):
    """
    Extract sales data specifically from ABGN Sales format Excel files
    
    Args:
        file_path (str): Path to the ABGN Sales Excel file
        
    Returns:
        tuple: (all_sales, sales_by_sheet, sale_month_year)
            - all_sales: List of all extracted sales records
            - sales_by_sheet: Dictionary mapping sheet names to their sales records
            - sale_month_year: Tuple of (month, year) extracted from filename
    """
    try:
        st.info(f"Starting ABGN sales extraction from {file_path}")
        
        # Try to open the Excel file to get sheet names
        xls = None
        engine = None
        try:
            xls = pd.ExcelFile(file_path, engine='openpyxl')
            st.success("Successfully opened Excel file with openpyxl engine")
            engine = 'openpyxl'
        except Exception as e1:
            st.warning(f"openpyxl engine failed: {str(e1)}")
            try:
                xls = pd.ExcelFile(file_path, engine='xlrd')
                st.success("Successfully opened Excel file with xlrd engine")
                engine = 'xlrd'
            except Exception as e2:
                st.error(f"Failed to open Excel file with both engines: {str(e1)}; {str(e2)}")
                return [], {}, None
        
        if not xls:
            st.error("Could not open Excel file")
            return [], {}, None
            
        # Get sheet names 
        sheets = xls.sheet_names
        st.success(f"Found {len(sheets)} sheets in the sales file")
        
        # Dictionary to store sales by sheet
        sales_by_sheet = {}
        all_sales = []
        
        # Extract month and year from filename
        file_name = os.path.basename(file_path)
        sale_month_year = None
        month_name_to_num = {
            'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'may': 5, 'jun': 6,
            'jul': 7, 'aug': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12
        }
        
        # Look for month name and year pattern (like Feb-2025)
        month_pattern = re.search(r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[\'\.,-]?(\d{2,4})', 
                                 file_name, re.IGNORECASE)
        
        if month_pattern:
            month_name, year = month_pattern.groups()
            month_num = month_name_to_num.get(month_name.lower()[:3], 1)
            
            # Fix two-digit year
            if len(year) == 2:
                year = f"20{year}"
                
            sale_month_year = (month_num, int(year))
            st.success(f"Detected month/year from filename: {month_name} {year} ({month_num}/{year})")
        else:
            # Try other patterns like 02-2025
            num_pattern = re.search(r'(\d{1,2})[\/.-](\d{2,4})', file_name)
            if num_pattern:
                month_num, year = num_pattern.groups()
                month_num = int(month_num)
                
                # Fix two-digit year
                if len(year) == 2:
                    year = f"20{year}"
                    
                if 1 <= month_num <= 12:
                    sale_month_year = (month_num, int(year))
                    st.success(f"Detected month/year from filename: {month_num}/{year}")
        
        # Process each sheet to extract daily sales data
        for sheet_name in sheets:
            # Skip sheets that are clearly not sales data
            if sheet_name.lower() in ['summary', 'index', 'contents', 'toc', 'cover', 'info']:
                continue
                
            st.info(f"Processing sheet: {sheet_name}")
            
            try:
                # Read the sheet
                df = pd.read_excel(file_path, sheet_name=sheet_name, engine=engine)
                
                # Skip empty sheets
                if df.empty:
                    st.warning(f"Sheet {sheet_name} is empty, skipping")
                    continue
                
                # Remove fully empty rows and columns
                df = df.dropna(how='all').dropna(axis=1, how='all')
                
                # Try to determine if this sheet represents a specific day
                sheet_date = None
                
                # Check if sheet name is a day number (1-31)
                day_num_match = re.match(r'^(\d{1,2})$', sheet_name.strip())
                if day_num_match and sale_month_year:
                    day_num = int(day_num_match.group(1))
                    if 1 <= day_num <= 31:
                        month_num, year = sale_month_year
                        sheet_date = f"{year}-{month_num:02d}-{day_num:02d}"
                        st.info(f"Sheet {sheet_name} represents day {day_num} of {month_num}/{year}")
                
                # Or check for date format in sheet name
                if not sheet_date:
                    date_match = re.search(r'(\d{1,2})[\/.-](\d{1,2})[\/.-](\d{2,4})', sheet_name)
                    if date_match:
                        day, month, year = date_match.groups()
                        # Fix two-digit year
                        if len(year) == 2:
                            year = f"20{year}"
                        try:
                            sheet_date = f"{year}-{month.zfill(2)}-{day.zfill(2)}"
                            st.info(f"Sheet {sheet_name} has date {sheet_date}")
                        except:
                            pass
                
                # Find the sales data header row in this sheet
                header_row = None
                data_start_row = None
                
                # Scan first 20 rows to find header
                for i in range(min(20, len(df))):
                    row = df.iloc[i]
                    row_text = " ".join([str(x).lower() for x in row if pd.notna(x)])
                    
                    # Common patterns in ABGN sales headers
                    if ("item" in row_text and ("qty" in row_text or "quantity" in row_text) and 
                        any(term in row_text for term in ["sales", "revenue", "amount", "price"])):
                        header_row = i
                        data_start_row = i + 1
                        st.info(f"Found header row at row {i+1}")
                        break
                
                if header_row is None:
                    st.warning(f"Could not find header row in sheet {sheet_name}, using default position")
                    # Use a common default in ABGN files
                    header_row = 4
                    data_start_row = 5
                
                # Get the header row
                header = df.iloc[header_row]
                
                # Map columns to our expected schema
                EXPECTED_COLUMNS = {
                    'item_code': ['item code', 'code', 'product code', 'item number', 'plu'],
                    'item_name': ['item name', 'description', 'menu item', 'product name', 'menu', 'item desc'],
                    'quantity': ['qty', 'quantity', 'sales qty', 'no of cups', 'count', 'pcs', 'nos', 'pax', 'unit sold'],
                    'revenue': ['revenue', 'sales', 'amount', 'total', 'sales amount', 'ext amount', 'net sales', 'total sales'],
                    'cost': ['cost', 'food cost', 'cost amount', 'cogs', 'fc', 'cost price', 'cost %']
                }
                
                column_mapping = {}
                for field, possible_names in EXPECTED_COLUMNS.items():
                    for col_idx, col_name in enumerate(header):
                        if pd.isna(col_name):
                            continue
                        col_text = str(col_name).lower().strip()
                        if any(name in col_text for name in possible_names):
                            column_mapping[field] = col_idx
                            break
                
                # Check if we found the essential columns
                missing_columns = [field for field in ['item_name', 'quantity'] if field not in column_mapping]
                if missing_columns:
                    st.warning(f"Sheet {sheet_name} is missing essential columns: {', '.join(missing_columns)}")
                    continue
                
                # Extract sales data
                sheet_sales = []
                current_category = "Uncategorized"
                
                # Process each row of data
                for i in range(data_start_row, len(df)):
                    row = df.iloc[i]
                    
                    # Skip completely empty rows
                    if all(pd.isna(x) or str(x).strip() == '' for x in row):
                        continue
                    
                    # Check if this is a category header row
                    first_cell = str(row.iloc[0]).strip() if not pd.isna(row.iloc[0]) else ""
                    if first_cell and all(pd.isna(x) or str(x).strip() == '' for x in row[1:]):
                        # This is likely a category heading
                        if not any(keyword in first_cell.lower() for keyword in ['total', 'sum', 'grand', 'sub']):
                            current_category = first_cell
                        continue
                    
                    # Extract sales data for this row
                    sales_data = {
                        'date': sheet_date if sheet_date else (f"{sale_month_year[1]}-{sale_month_year[0]:02d}-01" if sale_month_year else None),
                        'sheet_name': sheet_name,
                        'item_code': '',
                        'item_name': '',
                        'category': current_category,
                        'quantity': 0,
                        'revenue': 0,
                        'cost': 0
                    }
                    
                    # Get values from mapped columns
                    for field, col_idx in column_mapping.items():
                        if col_idx < len(row) and not pd.isna(row.iloc[col_idx]):
                            cell_value = row.iloc[col_idx]
                            
                            if field in ['item_code', 'item_name', 'category']:
                                # Text fields
                                sales_data[field] = str(cell_value).strip()
                            else:
                                # Numeric fields
                                try:
                                    if isinstance(cell_value, (int, float)):
                                        sales_data[field] = float(cell_value)
                                    else:
                                        # Try to extract numbers from text
                                        clean_value = ''.join(c for c in str(cell_value) if c.isdigit() or c == '.' or c == '-')
                                        if clean_value:
                                            sales_data[field] = float(clean_value)
                                except (ValueError, TypeError):
                                    pass
                    
                    # Skip rows without item name or with zero quantity
                    if (not sales_data['item_name'] and not sales_data['item_code']) or sales_data['quantity'] <= 0:
                        continue
                    
                    # Skip rows that are likely totals or summaries
                    if any(keyword in sales_data['item_name'].lower() for keyword in 
                          ['total', 'sum', 'grand', 'subtotal', 'food cost', 'sales %']):
                        continue
                    
                    # Set default name if missing
                    if not sales_data['item_name'] and sales_data['item_code']:
                        sales_data['item_name'] = f"Item {sales_data['item_code']}"
                    
                    # Try to extract food cost percentage if missing cost but have revenue
                    if sales_data['cost'] == 0 and sales_data['revenue'] > 0:
                        # Look for a percentage column
                        for col_idx, cell in enumerate(row):
                            if col_idx not in column_mapping.values() and not pd.isna(cell):
                                cell_text = str(cell).lower()
                                if "%" in cell_text:
                                    try:
                                        # Extract percentage value
                                        pct_value = float(''.join(c for c in cell_text if c.isdigit() or c == '.'))
                                        if 0 < pct_value <= 100:  # Reasonable percentage range
                                            # Convert to decimal
                                            sales_data['cost'] = sales_data['revenue'] * (pct_value / 100)
                                            break
                                    except (ValueError, TypeError):
                                        pass
                    
                    # Add to sales records for this sheet
                    sheet_sales.append(sales_data)
                
                st.success(f"Extracted {len(sheet_sales)} sales records from sheet {sheet_name}")
                
                if sheet_sales:
                    sales_by_sheet[sheet_name] = sheet_sales
                    all_sales.extend(sheet_sales)
            
            except Exception as sheet_err:
                st.error(f"Error processing sheet {sheet_name}: {str(sheet_err)}")
                import traceback
                st.error(traceback.format_exc())
        
        # Summary
        total_sales = len(all_sales)
        total_sheets = len(sales_by_sheet)
        
        if total_sales > 0:
            st.success(f"Successfully extracted {total_sales} total sales records from {total_sheets} sheets")
            return all_sales, sales_by_sheet, sale_month_year
        else:
            st.warning("No sales data was extracted from the file")
            return [], {}, sale_month_year
        
    except Exception as e:
        st.error(f"Error extracting ABGN sales data: {str(e)}")
        import traceback
        st.error(traceback.format_exc())
        return [], {}, None