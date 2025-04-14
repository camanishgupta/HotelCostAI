import streamlit as st
import pandas as pd
import numpy as np
import os
import json
import io
import tempfile
import shutil
from datetime import datetime
from utils.data_processing import load_data, save_data
from utils.excel_extraction import (
    safe_read_excel, detect_file_type, extract_recipes_from_excel,
    extract_inventory_from_excel, extract_sales_from_excel, batch_process_directory
)

# Set page configuration
st.set_page_config(
    page_title="Data Extraction",
    page_icon="🔄",
    layout="wide"
)

# Initialize session state variables if they don't exist
if 'recipes' not in st.session_state:
    if os.path.exists('data/recipes.json'):
        st.session_state.recipes = load_data('data/recipes.json')
    else:
        st.session_state.recipes = []

if 'inventory' not in st.session_state:
    if os.path.exists('data/inventory.json'):
        st.session_state.inventory = load_data('data/inventory.json')
    else:
        st.session_state.inventory = []

if 'sales' not in st.session_state:
    if os.path.exists('data/sales.json'):
        st.session_state.sales = load_data('data/sales.json')
    else:
        st.session_state.sales = []

if 'extraction_results' not in st.session_state:
    st.session_state.extraction_results = None

# Create necessary directories if they don't exist
os.makedirs('data', exist_ok=True)
os.makedirs('data/uploaded', exist_ok=True)

# Helper functions to save data
def save_recipes():
    save_data(st.session_state.recipes, 'data/recipes.json')

def save_inventory():
    save_data(st.session_state.inventory, 'data/inventory.json')

def save_sales():
    save_data(st.session_state.sales, 'data/sales.json')

# Main page header
st.title("🔄 Advanced Data Extraction")
st.markdown("Extract and clean data from complex Excel files")

# Create tabs for different extraction methods
tab1, tab2, tab3 = st.tabs(["Single File Extraction", "Batch Processing", "Results and Preview"])

with tab1:
    st.subheader("Extract Data from a Single File")
    st.write("Upload an Excel file to extract recipe, inventory, or sales data")
    
    # File uploader for single file
    uploaded_file = st.file_uploader("Upload Excel file", type=['xlsx', 'xls'])
    
    if uploaded_file:
        # Save the file to disk so we can use it with our extraction functions
        file_path = os.path.join('data/uploaded', uploaded_file.name)
        with open(file_path, 'wb') as f:
            f.write(uploaded_file.getbuffer())
        
        # Try to detect the file type
        file_type = detect_file_type(file_path)
        st.write(f"Detected file type: **{file_type.capitalize()}**")
        
        # Allow user to override the detected type
        selected_type = st.radio(
            "Choose data type to extract:",
            ["recipe", "inventory", "sales", "auto-detect"],
            index=3 if file_type == "unknown" else ["recipe", "inventory", "sales"].index(file_type)
        )
        
        if st.button("Extract Data"):
            with st.spinner("Extracting data..."):
                # Determine which extractor to use
                extraction_type = selected_type if selected_type != "auto-detect" else file_type
                
                if extraction_type == "recipe" or extraction_type == "unknown":
                    st.session_state.extraction_results = {
                        'type': 'recipe',
                        'data': extract_recipes_from_excel(file_path)
                    }
                elif extraction_type == "inventory":
                    st.session_state.extraction_results = {
                        'type': 'inventory',
                        'data': extract_inventory_from_excel(file_path)
                    }
                elif extraction_type == "sales":
                    st.session_state.extraction_results = {
                        'type': 'sales',
                        'data': extract_sales_from_excel(file_path)
                    }
                
                # Show a preview of the results
                if st.session_state.extraction_results and st.session_state.extraction_results['data']:
                    count = len(st.session_state.extraction_results['data'])
                    st.success(f"Successfully extracted {count} {st.session_state.extraction_results['type']} items!")
                    
                    # Switch to the results tab
                    st.rerun()
                else:
                    st.error("No data could be extracted. Try a different file type or upload a different file.")

with tab2:
    st.subheader("Batch Process Multiple Files")
    st.write("Upload a ZIP file containing multiple Excel files, or provide a folder path")
    
    col1, col2 = st.columns(2)
    
    with col1:
        # Zip file uploader
        zip_file = st.file_uploader("Upload ZIP archive", type=['zip'])
        
        if zip_file and st.button("Process ZIP Archive"):
            # Create a temporary directory for extraction
            with tempfile.TemporaryDirectory() as tmpdirname:
                # Save the zip file
                zip_path = os.path.join(tmpdirname, 'archive.zip')
                with open(zip_path, 'wb') as f:
                    f.write(zip_file.getbuffer())
                
                # Extract the zip file
                import zipfile
                with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                    zip_ref.extractall(tmpdirname)
                
                # Process the extracted files
                with st.spinner("Processing files..."):
                    results = batch_process_directory(tmpdirname)
                    
                    # Store the results
                    st.session_state.extraction_results = {
                        'type': 'batch',
                        'data': results
                    }
                    
                    # Show summary
                    st.success(f"Processed ZIP file with {len(results['recipes'])} recipes, " + 
                              f"{len(results['inventory'])} inventory items, and {len(results['sales'])} sales records.")
                    
                    # Show errors if any
                    if results['errors']:
                        st.warning(f"Encountered {len(results['errors'])} errors during processing.")
                    
                    # Switch to results tab
                    st.rerun()
    
    with col2:
        # Folder path option
        folder_path = st.text_input("Or enter a folder path on the server", "data/uploaded")
        
        if st.button("Process Folder"):
            if os.path.exists(folder_path) and os.path.isdir(folder_path):
                with st.spinner("Processing files in folder..."):
                    results = batch_process_directory(folder_path)
                    
                    # Store the results
                    st.session_state.extraction_results = {
                        'type': 'batch',
                        'data': results
                    }
                    
                    # Show summary
                    st.success(f"Processed folder with {len(results['recipes'])} recipes, " + 
                              f"{len(results['inventory'])} inventory items, and {len(results['sales'])} sales records.")
                    
                    # Show errors if any
                    if results['errors']:
                        st.warning(f"Encountered {len(results['errors'])} errors during processing.")
                    
                    # Switch to results tab
                    st.rerun()
            else:
                st.error(f"Folder path '{folder_path}' does not exist or is not a directory.")

with tab3:
    st.subheader("Extraction Results")
    
    if st.session_state.extraction_results:
        # Display based on result type
        if st.session_state.extraction_results['type'] == 'batch':
            # Batch results
            results = st.session_state.extraction_results['data']
            
            # Create tabs for different data types
            result_tab1, result_tab2, result_tab3 = st.tabs(["Recipes", "Inventory", "Sales"])
            
            with result_tab1:
                st.write(f"### Extracted Recipes: {len(results['recipes'])}")
                if results['recipes']:
                    # Display recipe preview
                    for i, recipe in enumerate(results['recipes'][:5]):  # Show first 5
                        with st.expander(f"Recipe: {recipe.get('name', 'Unnamed Recipe')}"):
                            st.write(f"**Yield:** {recipe.get('yield_amount', 1)} {recipe.get('yield_unit', 'serving')}")
                            
                            st.write("**Ingredients:**")
                            for ing in recipe.get('ingredients', []):
                                st.write(f"- {ing.get('amount', '')} {ing.get('unit', '')} {ing.get('name', '')}")
                            
                            st.write("**Preparation Steps:**")
                            for i, step in enumerate(recipe.get('preparation_steps', [])):
                                st.write(f"{i+1}. {step}")
                    
                    # Option to save
                    if st.button("Save Extracted Recipes"):
                        # Determine import mode
                        import_mode = st.radio(
                            "Import mode:",
                            ["Add to existing recipes", "Replace all recipes"],
                            key="recipe_import_mode"
                        )
                        
                        if import_mode == "Add to existing recipes":
                            st.session_state.recipes.extend(results['recipes'])
                        else:
                            st.session_state.recipes = results['recipes']
                        
                        save_recipes()
                        st.success(f"Saved {len(results['recipes'])} recipes!")
                else:
                    st.info("No recipes were extracted.")
            
            with result_tab2:
                st.write(f"### Extracted Inventory Items: {len(results['inventory'])}")
                if results['inventory']:
                    # Convert to DataFrame for display
                    inventory_df = pd.DataFrame(results['inventory'])
                    
                    # Select columns to display
                    display_columns = ['item_code', 'name', 'category', 'price', 'unit', 'stock_level', 'supplier']
                    display_df = inventory_df[display_columns].copy() if all(col in inventory_df.columns for col in display_columns) else inventory_df
                    
                    # Display preview
                    st.dataframe(display_df.head(10))
                    
                    # Option to save
                    if st.button("Save Extracted Inventory"):
                        # Determine import mode
                        import_mode = st.radio(
                            "Import mode:",
                            ["Add to existing inventory", "Replace all inventory"],
                            key="inventory_import_mode"
                        )
                        
                        if import_mode == "Add to existing inventory":
                            st.session_state.inventory.extend(results['inventory'])
                        else:
                            st.session_state.inventory = results['inventory']
                        
                        save_inventory()
                        st.success(f"Saved {len(results['inventory'])} inventory items!")
                else:
                    st.info("No inventory items were extracted.")
            
            with result_tab3:
                st.write(f"### Extracted Sales Records: {len(results['sales'])}")
                if results['sales']:
                    # Convert to DataFrame for display
                    sales_df = pd.DataFrame(results['sales'])
                    
                    # Select columns to display
                    display_columns = ['date', 'item_name', 'quantity', 'revenue', 'cost', 'profit']
                    display_df = sales_df[display_columns].copy() if all(col in sales_df.columns for col in display_columns) else sales_df
                    
                    # Display preview
                    st.dataframe(display_df.head(10))
                    
                    # Option to save
                    if st.button("Save Extracted Sales"):
                        # Determine import mode
                        import_mode = st.radio(
                            "Import mode:",
                            ["Add to existing sales", "Replace all sales"],
                            key="sales_import_mode"
                        )
                        
                        if import_mode == "Add to existing sales":
                            st.session_state.sales.extend(results['sales'])
                        else:
                            st.session_state.sales = results['sales']
                        
                        save_sales()
                        st.success(f"Saved {len(results['sales'])} sales records!")
                else:
                    st.info("No sales records were extracted.")
            
            # Errors section
            if results['errors']:
                with st.expander(f"Errors ({len(results['errors'])})"):
                    for error in results['errors']:
                        st.error(error)
                        
        else:
            # Single type results
            result_type = st.session_state.extraction_results['type']
            data = st.session_state.extraction_results['data']
            
            if result_type == 'recipe':
                st.write(f"### Extracted Recipes: {len(data)}")
                if data:
                    # Display recipe preview
                    for i, recipe in enumerate(data[:5]):  # Show first 5
                        with st.expander(f"Recipe: {recipe.get('name', 'Unnamed Recipe')}"):
                            st.write(f"**Yield:** {recipe.get('yield_amount', 1)} {recipe.get('yield_unit', 'serving')}")
                            
                            st.write("**Ingredients:**")
                            for ing in recipe.get('ingredients', []):
                                st.write(f"- {ing.get('amount', '')} {ing.get('unit', '')} {ing.get('name', '')}")
                            
                            st.write("**Preparation Steps:**")
                            for i, step in enumerate(recipe.get('preparation_steps', [])):
                                st.write(f"{i+1}. {step}")
                    
                    # Option to save
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        import_mode = st.radio(
                            "Import mode:",
                            ["Add to existing recipes", "Replace all recipes"]
                        )
                    
                    with col2:
                        if st.button("Save Extracted Recipes"):
                            if import_mode == "Add to existing recipes":
                                st.session_state.recipes.extend(data)
                            else:
                                st.session_state.recipes = data
                            
                            save_recipes()
                            st.success(f"Saved {len(data)} recipes!")
                else:
                    st.info("No recipes were extracted.")
                    
            elif result_type == 'inventory':
                st.write(f"### Extracted Inventory Items: {len(data)}")
                if data:
                    # Convert to DataFrame for display
                    inventory_df = pd.DataFrame(data)
                    
                    # Select columns to display
                    display_columns = ['item_code', 'name', 'category', 'price', 'unit', 'stock_level', 'supplier']
                    display_df = inventory_df[display_columns].copy() if all(col in inventory_df.columns for col in display_columns) else inventory_df
                    
                    # Display preview
                    st.dataframe(display_df)
                    
                    # Option to save
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        import_mode = st.radio(
                            "Import mode:",
                            ["Add to existing inventory", "Replace all inventory"]
                        )
                    
                    with col2:
                        if st.button("Save Extracted Inventory"):
                            if import_mode == "Add to existing inventory":
                                st.session_state.inventory.extend(data)
                            else:
                                st.session_state.inventory = data
                            
                            save_inventory()
                            st.success(f"Saved {len(data)} inventory items!")
                else:
                    st.info("No inventory items were extracted.")
                    
            elif result_type == 'sales':
                st.write(f"### Extracted Sales Records: {len(data)}")
                if data:
                    # Convert to DataFrame for display
                    sales_df = pd.DataFrame(data)
                    
                    # Select columns to display
                    display_columns = ['date', 'item_name', 'quantity', 'revenue', 'cost', 'profit']
                    display_df = sales_df[display_columns].copy() if all(col in sales_df.columns for col in display_columns) else sales_df
                    
                    # Display preview
                    st.dataframe(display_df)
                    
                    # Option to save
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        import_mode = st.radio(
                            "Import mode:",
                            ["Add to existing sales", "Replace all sales"]
                        )
                    
                    with col2:
                        if st.button("Save Extracted Sales"):
                            if import_mode == "Add to existing sales":
                                st.session_state.sales.extend(data)
                            else:
                                st.session_state.sales = data
                            
                            save_sales()
                            st.success(f"Saved {len(data)} sales records!")
                else:
                    st.info("No sales records were extracted.")
    else:
        st.info("No extraction results available. Use the other tabs to extract data first.")

# Data cleaning section
st.markdown("---")
st.subheader("Data Cleaning Tools")
st.write("Clean and standardize your extracted data")

cleaning_tab1, cleaning_tab2, cleaning_tab3 = st.tabs(["Recipe Cleaning", "Inventory Cleaning", "Sales Cleaning"])

with cleaning_tab1:
    st.write("### Recipe Data Cleaning")
    
    if not st.session_state.recipes:
        st.info("No recipes available to clean. Extract or add recipes first.")
    else:
        # Recipe cleaning options
        st.write("Select cleaning options:")
        
        clean_options = {
            "normalize_units": st.checkbox("Normalize units (e.g., convert g to kg where appropriate)", value=True),
            "capitalize_names": st.checkbox("Capitalize recipe and ingredient names", value=True),
            "remove_duplicates": st.checkbox("Remove duplicate recipes", value=True),
            "sort_ingredients": st.checkbox("Sort ingredients by quantity", value=True),
            "fill_missing_costs": st.checkbox("Estimate missing costs based on inventory", value=True)
        }
        
        if st.button("Clean Recipe Data"):
            with st.spinner("Cleaning recipe data..."):
                # Get a copy to work with
                cleaned_recipes = st.session_state.recipes.copy()
                
                # Normalize units
                if clean_options["normalize_units"]:
                    for recipe in cleaned_recipes:
                        for ing in recipe.get('ingredients', []):
                            unit = ing.get('unit', '').lower()
                            amount = ing.get('amount', 0)
                            
                            # Convert small weights to larger units
                            if unit == 'g' and amount >= 1000:
                                ing['unit'] = 'kg'
                                ing['amount'] = amount / 1000
                            
                            # Convert small volumes to larger units
                            elif unit == 'ml' and amount >= 1000:
                                ing['unit'] = 'L'
                                ing['amount'] = amount / 1000
                                
                            # Convert large weights to smaller units
                            elif unit == 'kg' and amount < 0.1:
                                ing['unit'] = 'g'
                                ing['amount'] = amount * 1000
                                
                            # Convert large volumes to smaller units
                            elif unit == 'L' and amount < 0.1:
                                ing['unit'] = 'ml'
                                ing['amount'] = amount * 1000
                                
                            # Standardize unit names
                            unit_mapping = {
                                'gram': 'g', 'grams': 'g', 'gr': 'g',
                                'kilogram': 'kg', 'kilograms': 'kg', 'kilo': 'kg',
                                'milliliter': 'ml', 'milliliters': 'ml', 'millilitre': 'ml',
                                'liter': 'L', 'liters': 'L', 'litre': 'L', 'litres': 'L',
                                'tablespoon': 'tbsp', 'tablespoons': 'tbsp', 'tbs': 'tbsp',
                                'teaspoon': 'tsp', 'teaspoons': 'tsp', 'ts': 'tsp',
                                'ounce': 'oz', 'ounces': 'oz',
                                'pound': 'lb', 'pounds': 'lb',
                                'piece': 'pcs', 'pieces': 'pcs', 'pc': 'pcs',
                                'ea': 'each', 'eaches': 'each'
                            }
                            
                            if unit in unit_mapping:
                                ing['unit'] = unit_mapping[unit]
                
                # Capitalize names
                if clean_options["capitalize_names"]:
                    for recipe in cleaned_recipes:
                        if 'name' in recipe:
                            recipe['name'] = recipe['name'].title()
                            
                        for ing in recipe.get('ingredients', []):
                            if 'name' in ing:
                                ing['name'] = ing['name'].title()
                
                # Remove duplicates
                if clean_options["remove_duplicates"]:
                    # Create a set of recipe names to track duplicates
                    seen_names = set()
                    unique_recipes = []
                    
                    for recipe in cleaned_recipes:
                        name = recipe.get('name', '').lower()
                        if name and name not in seen_names:
                            seen_names.add(name)
                            unique_recipes.append(recipe)
                        
                    cleaned_recipes = unique_recipes
                
                # Sort ingredients
                if clean_options["sort_ingredients"]:
                    for recipe in cleaned_recipes:
                        if 'ingredients' in recipe:
                            recipe['ingredients'] = sorted(
                                recipe['ingredients'], 
                                key=lambda x: x.get('amount', 0),
                                reverse=True
                            )
                
                # Fill missing costs
                if clean_options["fill_missing_costs"]:
                    # Create a lookup dict for inventory prices
                    inventory_prices = {}
                    for item in st.session_state.inventory:
                        inventory_prices[item.get('name', '').lower()] = item.get('price', 0)
                        
                    for recipe in cleaned_recipes:
                        recipe_cost = 0
                        for ing in recipe.get('ingredients', []):
                            ing_name = ing.get('name', '').lower()
                            ing_amount = ing.get('amount', 0)
                            
                            # Check if we have a price for this ingredient
                            if ing_name in inventory_prices:
                                ing_cost = ing_amount * inventory_prices[ing_name]
                                ing['cost'] = ing_cost
                                recipe_cost += ing_cost
                        
                        # Update recipe cost
                        recipe['total_cost'] = recipe_cost
                        yield_amount = recipe.get('yield_amount', 1)
                        if yield_amount > 0:
                            recipe['cost_per_unit'] = recipe_cost / yield_amount
                
                # Update the recipes
                st.session_state.recipes = cleaned_recipes
                save_recipes()
                
                st.success(f"Successfully cleaned {len(cleaned_recipes)} recipes!")
                
with cleaning_tab2:
    st.write("### Inventory Data Cleaning")
    
    if not st.session_state.inventory:
        st.info("No inventory available to clean. Extract or add inventory items first.")
    else:
        # Inventory cleaning options
        st.write("Select cleaning options:")
        
        clean_options = {
            "standardize_categories": st.checkbox("Standardize product categories", value=True),
            "fix_item_codes": st.checkbox("Fix or generate missing item codes", value=True),
            "normalize_units": st.checkbox("Normalize units", value=True),
            "round_prices": st.checkbox("Round prices to 2 decimal places", value=True),
            "capitalize_names": st.checkbox("Capitalize item names", value=True)
        }
        
        if st.button("Clean Inventory Data"):
            with st.spinner("Cleaning inventory data..."):
                # Get a copy to work with
                cleaned_inventory = st.session_state.inventory.copy()
                
                # Standardize categories
                if clean_options["standardize_categories"]:
                    # Create a mapping of similar categories
                    category_mapping = {
                        'veg': 'Vegetables',
                        'vegetable': 'Vegetables',
                        'vegetables': 'Vegetables',
                        'vegi': 'Vegetables',
                        'vegetabl': 'Vegetables',
                        
                        'fruit': 'Fruits',
                        'fruits': 'Fruits',
                        
                        'meat': 'Meat',
                        'meats': 'Meat',
                        
                        'seafood': 'Seafood',
                        'sea food': 'Seafood',
                        'fish': 'Seafood',
                        
                        'dairy': 'Dairy',
                        'dairy products': 'Dairy',
                        'milk': 'Dairy',
                        
                        'spice': 'Spices & Seasonings',
                        'spices': 'Spices & Seasonings',
                        'seasoning': 'Spices & Seasonings',
                        'seasonings': 'Spices & Seasonings',
                        'herb': 'Spices & Seasonings',
                        'herbs': 'Spices & Seasonings',
                        
                        'oil': 'Oils & Fats',
                        'oils': 'Oils & Fats',
                        'fat': 'Oils & Fats',
                        'fats': 'Oils & Fats',
                        
                        'grain': 'Grains & Rice',
                        'grains': 'Grains & Rice',
                        'rice': 'Grains & Rice',
                        'pasta': 'Grains & Rice',
                        
                        'baking': 'Baking Supplies',
                        'baking supplies': 'Baking Supplies',
                        'flour': 'Baking Supplies',
                        'sugar': 'Baking Supplies',
                        
                        'beverage': 'Beverages',
                        'beverages': 'Beverages',
                        'drink': 'Beverages',
                        'drinks': 'Beverages',
                        
                        'condiment': 'Condiments',
                        'condiments': 'Condiments',
                        'sauce': 'Condiments',
                        'sauces': 'Condiments'
                    }
                    
                    for item in cleaned_inventory:
                        category = item.get('category', '').lower()
                        
                        # Check if this category should be standardized
                        for pattern, standard in category_mapping.items():
                            if pattern in category:
                                item['category'] = standard
                                break
                
                # Fix item codes
                if clean_options["fix_item_codes"]:
                    # Track existing codes to avoid duplicates
                    existing_codes = set()
                    
                    for item in cleaned_inventory:
                        code = item.get('item_code', '')
                        
                        # Fix or generate item code
                        if not code or code in existing_codes:
                            # Generate a code based on the item name and category
                            name = item.get('name', '')
                            category = item.get('category', '')
                            
                            if name and category:
                                # Use first 3 chars of category and first 3 chars of name
                                prefix = category[:3].upper()
                                suffix = name[:3].upper()
                                
                                # Add a number to make it unique
                                i = 1
                                while f"{prefix}{suffix}{i:03d}" in existing_codes:
                                    i += 1
                                
                                item['item_code'] = f"{prefix}{suffix}{i:03d}"
                            else:
                                # Fallback to a generic code
                                i = 1
                                while f"ITEM{i:05d}" in existing_codes:
                                    i += 1
                                
                                item['item_code'] = f"ITEM{i:05d}"
                        
                        existing_codes.add(item['item_code'])
                
                # Normalize units
                if clean_options["normalize_units"]:
                    # Standardize unit names
                    unit_mapping = {
                        'gram': 'g', 'grams': 'g', 'gr': 'g',
                        'kilogram': 'kg', 'kilograms': 'kg', 'kilo': 'kg',
                        'milliliter': 'ml', 'milliliters': 'ml', 'millilitre': 'ml',
                        'liter': 'L', 'liters': 'L', 'litre': 'L', 'litres': 'L',
                        'tablespoon': 'tbsp', 'tablespoons': 'tbsp', 'tbs': 'tbsp',
                        'teaspoon': 'tsp', 'teaspoons': 'tsp', 'ts': 'tsp',
                        'ounce': 'oz', 'ounces': 'oz',
                        'pound': 'lb', 'pounds': 'lb',
                        'piece': 'pcs', 'pieces': 'pcs', 'pc': 'pcs',
                        'ea': 'each', 'eaches': 'each'
                    }
                    
                    for item in cleaned_inventory:
                        unit = item.get('unit', '').lower()
                        
                        # Check if this unit should be standardized
                        if unit in unit_mapping:
                            item['unit'] = unit_mapping[unit]
                
                # Round prices
                if clean_options["round_prices"]:
                    for item in cleaned_inventory:
                        price = item.get('price', 0)
                        item['price'] = round(price, 2)
                
                # Capitalize names
                if clean_options["capitalize_names"]:
                    for item in cleaned_inventory:
                        if 'name' in item:
                            item['name'] = item['name'].title()
                
                # Update the inventory
                st.session_state.inventory = cleaned_inventory
                save_inventory()
                
                st.success(f"Successfully cleaned {len(cleaned_inventory)} inventory items!")
                
with cleaning_tab3:
    st.write("### Sales Data Cleaning")
    
    if not st.session_state.sales:
        st.info("No sales data available to clean. Extract or add sales records first.")
    else:
        # Sales cleaning options
        st.write("Select cleaning options:")
        
        clean_options = {
            "fix_dates": st.checkbox("Fix invalid dates", value=True),
            "recalculate_profits": st.checkbox("Recalculate profits based on recipes", value=True),
            "remove_duplicates": st.checkbox("Remove duplicate transactions", value=True),
            "standardize_names": st.checkbox("Standardize item names to match recipes", value=True),
            "fill_missing_values": st.checkbox("Fill missing values with estimates", value=True)
        }
        
        if st.button("Clean Sales Data"):
            with st.spinner("Cleaning sales data..."):
                # Get a copy to work with
                cleaned_sales = st.session_state.sales.copy()
                
                # Fix dates
                if clean_options["fix_dates"]:
                    for record in cleaned_sales:
                        try:
                            # Try to parse the date
                            date_str = record.get('date', '')
                            parsed_date = pd.to_datetime(date_str)
                            record['date'] = parsed_date.isoformat()
                        except:
                            # If parsing fails, use current date
                            record['date'] = datetime.now().isoformat()
                
                # Recalculate profits
                if clean_options["recalculate_profits"]:
                    # Create a mapping of recipe names to costs
                    recipe_costs = {}
                    for recipe in st.session_state.recipes:
                        recipe_costs[recipe.get('name', '').lower()] = {
                            'cost': recipe.get('total_cost', 0),
                            'yield': recipe.get('yield_amount', 1)
                        }
                    
                    for record in cleaned_sales:
                        item_name = record.get('item_name', '').lower()
                        quantity = record.get('quantity', 0)
                        revenue = record.get('revenue', 0)
                        
                        # Check if we have a recipe cost for this item
                        if item_name in recipe_costs:
                            recipe_info = recipe_costs[item_name]
                            cost_per_yield = recipe_info['cost'] / recipe_info['yield']
                            record['cost'] = cost_per_yield * quantity
                        else:
                            # If no recipe, estimate cost as 30% of revenue
                            record['cost'] = revenue * 0.3
                        
                        # Recalculate profit and margin
                        record['profit'] = record['revenue'] - record['cost']
                        record['profit_margin'] = (record['profit'] / record['revenue']) * 100 if record['revenue'] > 0 else 0
                
                # Remove duplicates
                if clean_options["remove_duplicates"]:
                    # Convert to DataFrame for easier duplicate detection
                    sales_df = pd.DataFrame(cleaned_sales)
                    
                    # Drop duplicates based on date, item_name, and quantity
                    unique_sales = sales_df.drop_duplicates(subset=['date', 'item_name', 'quantity']).to_dict('records')
                    cleaned_sales = unique_sales
                
                # Standardize item names
                if clean_options["standardize_names"]:
                    # Create a set of recipe names for matching
                    recipe_names = {recipe.get('name', '').lower(): recipe.get('name') for recipe in st.session_state.recipes}
                    
                    for record in cleaned_sales:
                        item_name = record.get('item_name', '').lower()
                        
                        # Try to find a match in recipe names
                        best_match = None
                        best_score = 0
                        
                        for recipe_lower, recipe_original in recipe_names.items():
                            # Exact match
                            if item_name == recipe_lower:
                                best_match = recipe_original
                                break
                                
                            # Fuzzy match
                            # For simplicity, we're using a crude similarity measure
                            # In a real app, you might use a library like fuzzywuzzy
                            if recipe_lower in item_name or item_name in recipe_lower:
                                score = len(set(item_name) & set(recipe_lower)) / len(set(item_name) | set(recipe_lower))
                                if score > best_score and score > 0.7:  # 70% similarity threshold
                                    best_score = score
                                    best_match = recipe_original
                        
                        if best_match:
                            record['item_name'] = best_match
                
                # Fill missing values
                if clean_options["fill_missing_values"]:
                    for record in cleaned_sales:
                        # Ensure required fields have values
                        if not record.get('quantity', 0):
                            record['quantity'] = 1
                            
                        if not record.get('revenue', 0):
                            # Estimate revenue based on other records for this item
                            item_name = record.get('item_name', '')
                            similar_records = [r for r in cleaned_sales if r.get('item_name') == item_name and r.get('revenue', 0) > 0]
                            
                            if similar_records:
                                avg_revenue = sum(r.get('revenue', 0) for r in similar_records) / len(similar_records)
                                record['revenue'] = avg_revenue * record['quantity']
                            else:
                                # Default estimate
                                record['revenue'] = 10.0 * record['quantity']
                        
                        if not record.get('cost', 0):
                            # Estimate cost as 30% of revenue
                            record['cost'] = record['revenue'] * 0.3
                            
                        # Recalculate profit and margin
                        record['profit'] = record['revenue'] - record['cost']
                        record['profit_margin'] = (record['profit'] / record['revenue']) * 100 if record['revenue'] > 0 else 0
                
                # Update the sales data
                st.session_state.sales = cleaned_sales
                save_sales()
                
                st.success(f"Successfully cleaned {len(cleaned_sales)} sales records!")

# Help section
st.markdown("---")
st.subheader("Help & Instructions")

with st.expander("How to Use the Data Extraction Tools"):
    st.write("""
    ### Single File Extraction
    1. Upload an Excel file using the file uploader in the "Single File Extraction" tab.
    2. The system will try to detect the type of data (recipe, inventory, or sales).
    3. You can override the detected type if needed.
    4. Click "Extract Data" to process the file.
    5. Review the extracted data in the "Results and Preview" tab.
    6. Choose whether to add the data to your existing records or replace them.
    
    ### Batch Processing
    1. You can upload a ZIP archive containing multiple Excel files.
    2. Alternatively, you can specify a folder path on the server.
    3. The system will attempt to identify and extract all relevant data from the files.
    4. Review the results and save the data you want to keep.
    
    ### Data Cleaning
    Use the Data Cleaning tools to standardize and improve your extracted data:
    - For recipes: normalize units, capitalize names, remove duplicates, etc.
    - For inventory: standardize categories, fix item codes, normalize units, etc.
    - For sales: fix dates, recalculate profits, standardize item names, etc.
    """)

with st.expander("Common Extraction Issues"):
    st.write("""
    ### Troubleshooting Extraction Problems
    
    #### Files Not Reading Correctly
    - Some Excel files may have encoding issues. The extraction engine tries multiple approaches to handle this.
    - If a file still won't read, try saving it in a different Excel format (.xlsx or .xls).
    
    #### Incorrect Data Type Detection
    - If the system incorrectly identifies the data type (e.g., recipes identified as inventory), manually select the correct type.
    
    #### Missing or Incomplete Extraction
    - Complex files with unusual formatting may not extract perfectly.
    - Review the extracted data and use the Data Cleaning tools to fix issues.
    - For complex recipes, you may need to manually edit after extraction.
    
    #### Encoding Problems
    - If you see strange characters in extracted text, the file may have unusual encoding.
    - Try opening the file in Excel, saving it with UTF-8 encoding, and uploading again.
    """)