"""
Improved ABGN Recipe Extractor

This script extracts recipes from ABGN format Excel files more comprehensively by:
1. Using the Summary sheet to identify all expected recipes
2. Using multiple detection methods to find recipe sections
3. Cross-referencing found recipes with expected recipes
"""

import pandas as pd
import streamlit as st
from datetime import datetime
import os
import re
import sys

def extract_all_recipes(file_path):
    """
    Extract all recipes from ABGN format Excel file using multiple detection methods
    
    Args:
        file_path (str): Path to the ABGN Excel file
        
    Returns:
        list: Extracted recipes
    """
    try:
        st.info(f"Starting comprehensive recipe extraction from {file_path}")
        
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
        
        # Step 1: Load the Excel file and get all sheets
        xls = pd.ExcelFile(file_path)
        sheet_names = xls.sheet_names
        
        # Remove common non-recipe sheets
        sheet_names = [s for s in sheet_names if s.lower() not in ['summary', 'sheet1', 'index', 'toc', 'contents']]
        
        if not sheet_names:
            st.warning("No valid sheets found in the file")
            return []
        
        # Step 2: Load the Summary sheet to get expected recipes
        expected_recipes = {}
        recipes_by_category = {}
        
        try:
            summary_df = pd.read_excel(file_path, sheet_name='Summary')
            
            # Look for food items in the Summary sheet
            for i in range(5, len(summary_df)):
                try:
                    row = summary_df.iloc[i]
                    if pd.notna(row.iloc[0]) and pd.notna(row.iloc[1]) and pd.notna(row.iloc[5]):
                        item_num = row.iloc[0]
                        menu_item = str(row.iloc[1]).strip()
                        menu_type = str(row.iloc[5]).strip()
                        category = str(row.iloc[6]).strip() if pd.notna(row.iloc[6]) else ""
                        
                        if isinstance(menu_type, str) and menu_type.upper() == 'FOOD':
                            expected_recipes[menu_item] = {
                                'category': category,
                                'found': False
                            }
                            
                            # Group by category for easier lookup
                            if category not in recipes_by_category:
                                recipes_by_category[category] = []
                            recipes_by_category[category].append(menu_item)
                except Exception as e:
                    continue
            
            st.info(f"Found {len(expected_recipes)} expected recipes in Summary sheet")
            
            # Print categories and counts
            for category, items in recipes_by_category.items():
                st.info(f"Category '{category}': {len(items)} items")
                
        except Exception as e:
            st.warning(f"Could not load Summary sheet: {str(e)}")
        
        # Step 3: Process each sheet to find recipes
        all_recipes = []
        found_recipe_names = set()  # Track found recipe names to avoid duplicates
        
        for sheet_idx, sheet_name in enumerate(sheet_names):
            try:
                st.info(f"Processing sheet {sheet_idx+1}/{len(sheet_names)}: {sheet_name}")
                
                # Load sheet data
                df = pd.read_excel(file_path, sheet_name=sheet_name)
                
                # Skip empty sheets
                if df.empty:
                    st.warning(f"Sheet {sheet_name} is empty")
                    continue
                
                # Find all potential recipe sections using multiple methods
                # Method 1: Standard Recipe Card markers
                standard_markers = []
                for i in range(len(df)):
                    row_text = " ".join([str(x) for x in df.iloc[i] if pd.notna(x)])
                    if "STANDARD COST RECIPE CARD" in row_text or "STANDARD RECIPE CARD" in row_text:
                        standard_markers.append(i)
                
                # Method 2: NAME markers not preceded by standard markers
                name_markers = []
                for i in range(len(df)):
                    if pd.notna(df.iloc[i, 0]) and str(df.iloc[i, 0]).strip() == 'NAME':
                        # Check if this NAME is near a standard marker
                        is_part_of_standard = False
                        for sm in standard_markers:
                            if i > sm and i - sm < 5:  # NAME typically within 5 rows of standard marker
                                is_part_of_standard = True
                                break
                        
                        if not is_part_of_standard:
                            name_markers.append(max(0, i-2))  # Start 2 rows before NAME
                
                # Method 3: Search for recipe names from Summary in this sheet
                recipe_name_markers = []
                
                # Focus on recipes in categories related to this sheet
                relevant_categories = []
                for category in recipes_by_category:
                    if category.lower() in sheet_name.lower() or sheet_name.lower() in category.lower():
                        relevant_categories.append(category)
                
                # If no direct match, consider all categories
                if not relevant_categories:
                    relevant_categories = list(recipes_by_category.keys())
                
                # Look for recipe names from these categories in the sheet
                for category in relevant_categories:
                    for recipe_name in recipes_by_category[category]:
                        if expected_recipes[recipe_name]['found']:
                            continue  # Skip recipes we've already found
                        
                        # Search for this recipe name in the sheet
                        for i in range(len(df)):
                            # Skip rows near existing markers
                            if any(abs(i - m) < 5 for m in standard_markers + name_markers):
                                continue
                                
                            # Check each cell in the first few columns
                            for j in range(min(5, df.shape[1])):
                                if pd.notna(df.iloc[i, j]) and recipe_name.lower() == str(df.iloc[i, j]).strip().lower():
                                    recipe_name_markers.append(i)
                                    expected_recipes[recipe_name]['found'] = True
                                    st.info(f"Found recipe '{recipe_name}' at row {i+1}")
                                    break
                            
                            if expected_recipes[recipe_name]['found']:
                                break
                
                # Combine all markers and remove duplicates
                all_markers = []
                all_markers.extend(standard_markers)
                all_markers.extend(name_markers)
                all_markers.extend(recipe_name_markers)
                recipe_markers = sorted(list(set(all_markers)))
                
                if not recipe_markers:
                    st.warning(f"No recipe markers found in sheet {sheet_name}")
                    continue
                
                st.info(f"Found {len(recipe_markers)} recipe markers in sheet {sheet_name} " + 
                        f"({len(standard_markers)} standard, {len(name_markers)} name, " + 
                        f"{len(recipe_name_markers)} from summary)")
                
                # Process each recipe section
                for i, start_idx in enumerate(recipe_markers):
                    try:
                        # Define the end of this recipe section
                        end_idx = recipe_markers[i+1] if i+1 < len(recipe_markers) else len(df)
                        
                        # Make sure sections don't overlap unreasonably
                        if end_idx - start_idx > 50:  # Typical recipe is 20-40 rows
                            end_idx = min(start_idx + 50, end_idx)
                        
                        # Extract just this recipe's rows
                        recipe_df = df.iloc[start_idx:end_idx].copy().reset_index(drop=True)
                        
                        # Step 1: Find the recipe name using multiple methods
                        recipe_name = ""
                        
                        # Method 1: Look for NAME row followed by recipe name in column B
                        name_row_idx = None
                        for j in range(min(10, len(recipe_df))):
                            if pd.notna(recipe_df.iloc[j, 0]) and str(recipe_df.iloc[j, 0]).strip() == 'NAME':
                                name_row_idx = j
                                break
                        
                        if name_row_idx is not None and recipe_df.shape[1] > 1:
                            if pd.notna(recipe_df.iloc[name_row_idx, 1]):
                                recipe_name = str(recipe_df.iloc[name_row_idx, 1]).strip()
                                st.info(f"Found recipe name '{recipe_name}' in NAME row")
                        
                        # Method 2: Look for recipe name in row following STANDARD RECIPE CARD
                        if not recipe_name:
                            for j in range(min(5, len(recipe_df))):
                                row_text = " ".join([str(x) for x in recipe_df.iloc[j] if pd.notna(x)])
                                if "STANDARD COST RECIPE CARD" in row_text or "STANDARD RECIPE CARD" in row_text:
                                    if j+1 < len(recipe_df) and recipe_df.shape[1] > 1:
                                        if pd.notna(recipe_df.iloc[j+1, 1]):
                                            potential_name = str(recipe_df.iloc[j+1, 1]).strip()
                                            if potential_name and not potential_name.isdigit():
                                                recipe_name = potential_name
                                                st.info(f"Found recipe name '{recipe_name}' after STANDARD RECIPE CARD")
                                    break
                        
                        # Method 3: Cross-reference with expected recipes by proximity
                        if not recipe_name:
                            for j in range(min(10, len(recipe_df))):
                                for k in range(min(5, recipe_df.shape[1])):
                                    if pd.notna(recipe_df.iloc[j, k]):
                                        cell_value = str(recipe_df.iloc[j, k]).strip()
                                        if cell_value in expected_recipes:
                                            recipe_name = cell_value
                                            st.info(f"Found recipe name '{recipe_name}' by exact match with expected recipe")
                                            break
                                if recipe_name:
                                    break
                        
                        # Method 4: Check if any cell matches a summary recipe with minor differences
                        if not recipe_name:
                            for expected_name in expected_recipes:
                                for j in range(min(10, len(recipe_df))):
                                    for k in range(min(5, recipe_df.shape[1])):
                                        if pd.notna(recipe_df.iloc[j, k]):
                                            cell_value = str(recipe_df.iloc[j, k]).strip()
                                            # Check for high similarity (e.g., ignore whitespace, case)
                                            if (cell_value.lower().replace(" ", "") == 
                                                expected_name.lower().replace(" ", "")):
                                                recipe_name = expected_name  # Use the official name
                                                st.info(f"Found recipe name '{recipe_name}' by fuzzy match with expected recipe")
                                                break
                                    if recipe_name:
                                        break
                                if recipe_name:
                                    break
                        
                        # If still no name, try using sheet name + index
                        if not recipe_name:
                            recipe_name = f"{sheet_name} Recipe {i+1}"
                            st.warning(f"Could not find recipe name, using default: {recipe_name}")
                        
                        # Skip if this recipe name has already been processed
                        if recipe_name in found_recipe_names:
                            st.info(f"Skipping duplicate recipe: {recipe_name}")
                            continue
                        
                        found_recipe_names.add(recipe_name)
                        
                        # Mark as found in expected recipes
                        for expected_name in expected_recipes:
                            if (recipe_name.lower().replace(" ", "") == 
                                expected_name.lower().replace(" ", "")):
                                expected_recipes[expected_name]['found'] = True
                                # Use the official name from summary
                                recipe_name = expected_name
                                break
                        
                        # Step 2: Find the ingredient table header
                        header_row_idx = -1
                        for j in range(len(recipe_df)):
                            row_values = [str(x).lower() for x in recipe_df.iloc[j] if pd.notna(x)]
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
                        
                        # Step 3: Map columns to expected fields
                        header_row = recipe_df.iloc[header_row_idx]
                        column_mapping = {}
                        
                        for field, possible_names in ABGN_COLUMNS.items():
                            for col_idx, header_cell in enumerate(header_row):
                                if pd.notna(header_cell):
                                    header_text = str(header_cell).lower().strip()
                                    if any(possible_name in header_text for possible_name in possible_names):
                                        column_mapping[field] = col_idx
                                        break
                        
                        # Check if we found essential columns
                        if 'name' not in column_mapping:
                            st.warning(f"Could not find ingredient name column for recipe: {recipe_name}")
                            continue
                        
                        # Step 4: Find the end of the ingredient table
                        ingredients_end_idx = len(recipe_df)
                        for j in range(header_row_idx + 1, len(recipe_df)):
                            row_values = [str(x).lower() for x in recipe_df.iloc[j] if pd.notna(x)]
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
                            if all(not pd.notna(x) for x in row):
                                continue
                            
                            # Initialize ingredient data
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
                            
                            # Extract data from each column
                            for field, col_idx in column_mapping.items():
                                if col_idx < len(row) and pd.notna(row.iloc[col_idx]):
                                    cell_value = row.iloc[col_idx]
                                    
                                    # Process based on field type
                                    if field in ['item_code', 'name', 'unit']:
                                        # Text fields
                                        ingredient_data[field] = str(cell_value).strip()
                                    else:
                                        # Numeric fields
                                        try:
                                            if isinstance(cell_value, (int, float)):
                                                ingredient_data[field] = float(cell_value)
                                            else:
                                                # Try to extract numbers from text
                                                clean_value = ''.join(c for c in str(cell_value) 
                                                                    if c.isdigit() or c == '.')
                                                if clean_value:
                                                    ingredient_data[field] = float(clean_value)
                                        except (ValueError, TypeError):
                                            pass
                            
                            # Skip rows without a name
                            if not ingredient_data['name']:
                                continue
                            
                            # Set default unit if missing
                            if not ingredient_data['unit']:
                                ingredient_data['unit'] = 'piece'
                            
                            # Calculate net_qty using the formula: qty + (loss% * qty)
                            if ingredient_data['qty'] > 0:
                                if ingredient_data['loss'] > 0:
                                    if ingredient_data['loss'] < 1:  # Likely a percentage
                                        ingredient_data['net_qty'] = ingredient_data['qty'] + (ingredient_data['loss'] * ingredient_data['qty'])
                                    else:  # Absolute value
                                        ingredient_data['net_qty'] = ingredient_data['qty'] + ingredient_data['loss']
                                else:
                                    ingredient_data['net_qty'] = ingredient_data['qty']
                            
                            # Calculate total_cost if missing
                            if ingredient_data['total_cost'] == 0 and ingredient_data['unit_cost'] > 0:
                                qty_to_use = ingredient_data['net_qty'] if ingredient_data['net_qty'] > 0 else ingredient_data['qty']
                                if qty_to_use > 0:
                                    ingredient_data['total_cost'] = ingredient_data['unit_cost'] * qty_to_use
                            
                            # Add to ingredients list
                            ingredients.append(ingredient_data)
                        
                        # Step 6: Find additional recipe info (sales price, portions)
                        sales_price = 0
                        portions = 1
                        
                        # Calculate total cost from ingredients
                        total_cost = sum(ingredient['total_cost'] for ingredient in ingredients)
                        
                        # Look for COST/PORTION row and extract portions from row after
                        cost_portion_row_idx = None
                        for j in range(len(recipe_df)):
                            row_text = " ".join([str(x).lower() for x in recipe_df.iloc[j] if pd.notna(x)])
                            if "cost/portion" in row_text:
                                cost_portion_row_idx = j
                                break
                        
                        if cost_portion_row_idx is not None:
                            # Portions typically in column D (index 3) of row after COST/PORTION
                            portion_row_idx = cost_portion_row_idx + 1
                            if portion_row_idx < len(recipe_df) and 3 < recipe_df.shape[1]:
                                try:
                                    cell_value = recipe_df.iloc[portion_row_idx, 3]
                                    if pd.notna(cell_value) and (isinstance(cell_value, (int, float)) or
                                               (isinstance(cell_value, str) and cell_value.replace('.', '', 1).isdigit())):
                                        portions = float(cell_value)
                                except Exception:
                                    pass
                            
                            # Sales price typically in column G (index 6) of same row
                            if portion_row_idx < len(recipe_df) and 6 < recipe_df.shape[1]:
                                try:
                                    cell_value = recipe_df.iloc[portion_row_idx, 6]
                                    if pd.notna(cell_value) and (isinstance(cell_value, (int, float)) or
                                               (isinstance(cell_value, str) and cell_value.replace('.', '', 1).isdigit())):
                                        sales_price = float(cell_value)
                                except Exception:
                                    pass
                        
                        # If we couldn't find portions or sales price, look throughout the section
                        if portions == 1 or sales_price == 0:
                            for j in range(len(recipe_df)):
                                row_text = " ".join([str(x).lower() for x in recipe_df.iloc[j] if pd.notna(x)])
                                
                                if portions == 1 and ("portion" in row_text or "yield" in row_text or "no.portion" in row_text):
                                    for k, cell in enumerate(recipe_df.iloc[j]):
                                        if pd.notna(cell) and isinstance(cell, (int, float)) and cell > 0:
                                            portions = float(cell)
                                            break
                                
                                if sales_price == 0 and ("sales price" in row_text or "selling price" in row_text):
                                    for k, cell in enumerate(recipe_df.iloc[j]):
                                        if pd.notna(cell) and isinstance(cell, (int, float)) and cell > 0:
                                            sales_price = float(cell)
                                            break
                        
                        # Make sure we have valid values
                        if portions <= 0:
                            portions = 1
                        
                        # Create the recipe object
                        category = ""
                        for expected_name, data in expected_recipes.items():
                            if expected_name.lower() == recipe_name.lower():
                                category = data['category']
                                break
                        
                        if not category:
                            category = sheet_name
                        
                        recipe = {
                            "name": recipe_name,
                            "category": category,
                            "yield_amount": portions,
                            "yield_unit": "serving",
                            "ingredients": ingredients,
                            "total_cost": total_cost,
                            "sales_price": sales_price,
                            "cost_percentage": (total_cost / sales_price * 100) if sales_price > 0 else 0,
                            "imported_at": datetime.now().isoformat()
                        }
                        
                        # Add to recipes list
                        all_recipes.append(recipe)
                        st.success(f"Successfully extracted recipe: {recipe_name} with {len(ingredients)} ingredients")
                        
                    except Exception as recipe_err:
                        st.error(f"Error processing recipe at index {i} in sheet {sheet_name}: {str(recipe_err)}")
                
            except Exception as sheet_err:
                st.error(f"Error processing sheet {sheet_name}: {str(sheet_err)}")
        
        # Report on coverage of expected recipes
        found_count = sum(1 for r in expected_recipes.values() if r['found'])
        st.info(f"Found {found_count} out of {len(expected_recipes)} expected recipes ({found_count/len(expected_recipes)*100:.1f}%)")
        
        # Report missing recipes
        missing_recipes = [name for name, data in expected_recipes.items() if not data['found']]
        if missing_recipes:
            st.warning(f"Missing {len(missing_recipes)} recipes: {', '.join(missing_recipes[:10])}" + 
                      ("..." if len(missing_recipes) > 10 else ""))
        
        return all_recipes
        
    except Exception as e:
        st.error(f"Error in recipe extraction: {str(e)}")
        import traceback
        st.error(traceback.format_exc())
        return []

if __name__ == "__main__":
    if len(sys.argv) > 1:
        file_path = sys.argv[1]
        print(f"Extracting recipes from {file_path}")
        recipes = extract_all_recipes(file_path)
        print(f"Extracted {len(recipes)} recipes")
    else:
        print("Usage: python improved_recipe_extractor.py <file_path>")