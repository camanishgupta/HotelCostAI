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
from utils.excel_extraction import safe_read_excel, detect_file_type, extract_recipes_from_excel, extract_inventory_from_excel, extract_sales_from_excel
from utils.abgn_extractor import extract_recipe_costing, extract_inventory, extract_sales

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

# Function to process files in a directory
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
        st.info(f"Processing directory: {directory}")
        
        # Get list of Excel files
        excel_files = []
        for root, dirs, files in os.walk(directory):
            for file in files:
                if file.endswith('.xlsx') or file.endswith('.xls'):
                    excel_files.append(os.path.join(root, file))
        
        st.write(f"Found {len(excel_files)} Excel files.")
        
        # Process each file
        for file_path in excel_files:
            try:
                st.write(f"Processing file: {os.path.basename(file_path)}")
                
                # Try to detect file type
                file_type = detect_file_type(file_path)
                
                # Check if this is a known ABGN format
                file_name = os.path.basename(file_path).lower()
                is_abgn_recipe = any(term in file_name for term in ['a la carte', 'menu cost', 'recipe']) and 'abgn' in file_name
                is_abgn_inventory = 'one line store' in file_name and 'abgn' in file_name
                is_abgn_sales = 'sale' in file_name and 'item' in file_name and 'abgn' in file_name
                
                # Specialized handling based on file types
                if is_abgn_recipe:
                    # Use specialized ABGN recipe extractor
                    st.write("Detected ABGN Recipe format - using specialized extractor")
                    extracted_data = extract_recipe_costing(file_path)
                    if extracted_data:
                        results['recipes'].extend(extracted_data)
                        st.success(f"Extracted {len(extracted_data)} recipes with specialized ABGN extractor")
                        
                elif is_abgn_inventory:
                    # Use specialized ABGN inventory extractor
                    st.write("Detected ABGN Inventory format - using specialized extractor")
                    extracted_data = extract_inventory(file_path)
                    if extracted_data:
                        results['inventory'].extend(extracted_data)
                        st.success(f"Extracted {len(extracted_data)} inventory items with specialized ABGN extractor")
                        
                elif is_abgn_sales:
                    # Use specialized ABGN sales extractor
                    st.write("Detected ABGN Sales format - using specialized extractor")
                    extracted_data = extract_sales(file_path)
                    if extracted_data:
                        results['sales'].extend(extracted_data)
                        st.success(f"Extracted {len(extracted_data)} sales records with specialized ABGN extractor")
                
                # If not specialized format, use standard extractors
                elif file_type == 'recipe':
                    # Try ABGN extractor first, then fall back to standard
                    try:
                        st.write("Trying specialized ABGN recipe extractor first")
                        extracted_data = extract_recipe_costing(file_path)
                        if extracted_data and len(extracted_data) > 0:
                            results['recipes'].extend(extracted_data)
                            st.success(f"Extracted {len(extracted_data)} recipes with ABGN extractor")
                        else:
                            st.write("No recipes found with ABGN extractor, trying standard extractor")
                            extracted_data = extract_recipes_from_excel(file_path)
                            if extracted_data:
                                results['recipes'].extend(extracted_data)
                                st.success(f"Extracted {len(extracted_data)} recipes with standard extractor")
                    except Exception as e:
                        st.warning(f"ABGN extractor failed, using standard: {str(e)}")
                        extracted_data = extract_recipes_from_excel(file_path)
                        if extracted_data:
                            results['recipes'].extend(extracted_data)
                            st.success(f"Extracted {len(extracted_data)} recipes with standard extractor")
                        
                elif file_type == 'inventory':
                    # Try ABGN extractor first, then fall back to standard
                    try:
                        st.write("Trying specialized ABGN inventory extractor first")
                        extracted_data = extract_inventory(file_path)
                        if extracted_data and len(extracted_data) > 0:
                            results['inventory'].extend(extracted_data)
                            st.success(f"Extracted {len(extracted_data)} inventory items with ABGN extractor")
                        else:
                            st.write("No inventory items found with ABGN extractor, trying standard extractor")
                            extracted_data = extract_inventory_from_excel(file_path)
                            if extracted_data:
                                results['inventory'].extend(extracted_data)
                                st.success(f"Extracted {len(extracted_data)} inventory items with standard extractor")
                    except Exception as e:
                        st.warning(f"ABGN extractor failed, using standard: {str(e)}")
                        extracted_data = extract_inventory_from_excel(file_path)
                        if extracted_data:
                            results['inventory'].extend(extracted_data)
                            st.success(f"Extracted {len(extracted_data)} inventory items with standard extractor")
                        
                elif file_type == 'sales':
                    # Try ABGN extractor first, then fall back to standard
                    try:
                        st.write("Trying specialized ABGN sales extractor first")
                        extracted_data = extract_sales(file_path)
                        if extracted_data and len(extracted_data) > 0:
                            results['sales'].extend(extracted_data)
                            st.success(f"Extracted {len(extracted_data)} sales records with ABGN extractor")
                        else:
                            st.write("No sales records found with ABGN extractor, trying standard extractor")
                            extracted_data = extract_sales_from_excel(file_path)
                            if extracted_data:
                                results['sales'].extend(extracted_data)
                                st.success(f"Extracted {len(extracted_data)} sales records with standard extractor")
                    except Exception as e:
                        st.warning(f"ABGN extractor failed, using standard: {str(e)}")
                        extracted_data = extract_sales_from_excel(file_path)
                        if extracted_data:
                            results['sales'].extend(extracted_data)
                            st.success(f"Extracted {len(extracted_data)} sales records with standard extractor")
                        
                else:
                    # For unknown types, try all extractors in order:
                    # 1. First try ABGN extractors (better at handling complex Excel formats)
                    # 2. Then fall back to standard extractors
                    st.write(f"Unknown file type for {file_name}, trying all extractors")
                    
                    # Try recipe extractors
                    try:
                        extracted_recipes = extract_recipe_costing(file_path)
                        if extracted_recipes and len(extracted_recipes) > 0:
                            results['recipes'].extend(extracted_recipes)
                            st.success(f"Found {len(extracted_recipes)} recipes with ABGN extractor")
                        else:
                            try:
                                extracted_recipes = extract_recipes_from_excel(file_path)
                                if extracted_recipes:
                                    results['recipes'].extend(extracted_recipes)
                                    st.success(f"Found {len(extracted_recipes)} recipes with standard extractor")
                            except Exception as standard_recipe_err:
                                pass  # Silently fail standard extractor if specialized already failed
                    except Exception as recipe_err:
                        try:
                            extracted_recipes = extract_recipes_from_excel(file_path)
                            if extracted_recipes:
                                results['recipes'].extend(extracted_recipes)
                                st.success(f"Found {len(extracted_recipes)} recipes with standard extractor")
                        except Exception as both_recipe_err:
                            results['errors'].append(f"Error extracting recipes from {file_name}: {str(both_recipe_err)}")
                    
                    # Try inventory extractors
                    try:
                        extracted_inventory = extract_inventory(file_path)
                        if extracted_inventory and len(extracted_inventory) > 0:
                            results['inventory'].extend(extracted_inventory)
                            st.success(f"Found {len(extracted_inventory)} inventory items with ABGN extractor")
                        else:
                            try:
                                extracted_inventory = extract_inventory_from_excel(file_path)
                                if extracted_inventory:
                                    results['inventory'].extend(extracted_inventory)
                                    st.success(f"Found {len(extracted_inventory)} inventory items with standard extractor")
                            except Exception as standard_inv_err:
                                pass  # Silently fail standard extractor if specialized already failed
                    except Exception as inv_err:
                        try:
                            extracted_inventory = extract_inventory_from_excel(file_path)
                            if extracted_inventory:
                                results['inventory'].extend(extracted_inventory)
                                st.success(f"Found {len(extracted_inventory)} inventory items with standard extractor")
                        except Exception as both_inv_err:
                            results['errors'].append(f"Error extracting inventory from {file_name}: {str(both_inv_err)}")
                    
                    # Try sales extractors
                    try:
                        extracted_sales = extract_sales(file_path)
                        if extracted_sales and len(extracted_sales) > 0:
                            results['sales'].extend(extracted_sales)
                            st.success(f"Found {len(extracted_sales)} sales records with ABGN extractor")
                        else:
                            try:
                                extracted_sales = extract_sales_from_excel(file_path)
                                if extracted_sales:
                                    results['sales'].extend(extracted_sales)
                                    st.success(f"Found {len(extracted_sales)} sales records with standard extractor")
                            except Exception as standard_sales_err:
                                pass  # Silently fail standard extractor if specialized already failed
                    except Exception as sales_err:
                        try:
                            extracted_sales = extract_sales_from_excel(file_path)
                            if extracted_sales:
                                results['sales'].extend(extracted_sales)
                                st.success(f"Found {len(extracted_sales)} sales records with standard extractor")
                        except Exception as both_sales_err:
                            results['errors'].append(f"Error extracting sales from {file_name}: {str(both_sales_err)}")
                
            except Exception as file_err:
                error_msg = f"Error processing file {os.path.basename(file_path)}: {str(file_err)}"
                st.error(error_msg)
                results['errors'].append(error_msg)
        
        # Final summary
        st.success(f"Successfully processed {len(excel_files)} files")
        st.write(f"Found {len(results['recipes'])} recipes, {len(results['inventory'])} inventory items, and {len(results['sales'])} sales records")
        if results['errors']:
            st.warning(f"Encountered {len(results['errors'])} errors during processing")
        
        return results
        
    except Exception as e:
        error_msg = f"Error processing directory: {str(e)}"
        st.error(error_msg)
        results['errors'].append(error_msg)
        return results

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
        
        # Add option to use ABGN extractors
        use_abgn = st.checkbox("Use specialized ABGN extractors", value=True)
        
        if st.button("Extract Data"):
            with st.spinner("Extracting data..."):
                # Determine which extractor to use
                extraction_type = selected_type if selected_type != "auto-detect" else file_type
                
                if extraction_type == "recipe":
                    if use_abgn:
                        st.info("Using specialized ABGN recipe extractor")
                        try:
                            st.session_state.extraction_results = {
                                'type': 'recipe',
                                'data': extract_recipe_costing(file_path)
                            }
                        except Exception as e:
                            st.warning(f"ABGN extractor failed, using standard: {str(e)}")
                            st.session_state.extraction_results = {
                                'type': 'recipe',
                                'data': extract_recipes_from_excel(file_path)
                            }
                    else:
                        st.session_state.extraction_results = {
                            'type': 'recipe',
                            'data': extract_recipes_from_excel(file_path)
                        }
                elif extraction_type == "inventory":
                    if use_abgn:
                        st.info("Using specialized ABGN inventory extractor")
                        try:
                            st.session_state.extraction_results = {
                                'type': 'inventory',
                                'data': extract_inventory(file_path)
                            }
                        except Exception as e:
                            st.warning(f"ABGN extractor failed, using standard: {str(e)}")
                            st.session_state.extraction_results = {
                                'type': 'inventory',
                                'data': extract_inventory_from_excel(file_path)
                            }
                    else:
                        st.session_state.extraction_results = {
                            'type': 'inventory',
                            'data': extract_inventory_from_excel(file_path)
                        }
                elif extraction_type == "sales":
                    if use_abgn:
                        st.info("Using specialized ABGN sales extractor")
                        try:
                            st.session_state.extraction_results = {
                                'type': 'sales',
                                'data': extract_sales(file_path)
                            }
                        except Exception as e:
                            st.warning(f"ABGN extractor failed, using standard: {str(e)}")
                            st.session_state.extraction_results = {
                                'type': 'sales',
                                'data': extract_sales_from_excel(file_path)
                            }
                    else:
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
                                # Display each ingredient with all available fields
                                ingredient_text = f"- "
                                if 'item_code' in ing and ing['item_code']:
                                    ingredient_text += f"[{ing['item_code']}] "
                                
                                ingredient_text += f"{ing.get('name', '')}"
                                
                                if 'qty' in ing and ing['qty']:
                                    ingredient_text += f", {ing['qty']}"
                                elif 'amount' in ing and ing['amount']:
                                    ingredient_text += f", {ing['amount']}"
                                    
                                if 'unit' in ing and ing['unit']:
                                    ingredient_text += f" {ing['unit']}"
                                    
                                if 'loss' in ing and ing['loss']:
                                    ingredient_text += f", Loss: {ing['loss']}"
                                    
                                if 'net_qty' in ing and ing['net_qty']:
                                    ingredient_text += f", Net: {ing['net_qty']}"
                                    
                                if 'unit_cost' in ing and ing['unit_cost']:
                                    ingredient_text += f", Unit Cost: {ing['unit_cost']}"
                                    
                                if 'total_cost' in ing and ing['total_cost']:
                                    ingredient_text += f", Total: {ing['total_cost']}"
                                    
                                st.write(ingredient_text)
                            
                            st.write("**Preparation Steps:**")
                            for i, step in enumerate(recipe.get('preparation_steps', [])):
                                st.write(f"{i+1}. {step}")
                    
                    # Option to save
                    if st.button("Save Extracted Recipes"):
                        if results['recipes']:
                            # Determine import mode
                            import_mode = st.radio(
                                "Recipe import mode:",
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
                            st.warning("No recipes were found to save.")
                else:
                    st.info("No recipes were extracted.")
            
            with result_tab2:
                st.write(f"### Extracted Inventory Items: {len(results['inventory'])}")
                if results['inventory']:
                    # Convert to DataFrame for display
                    inventory_df = pd.DataFrame(results['inventory'])
                    
                    # Select columns to display - be more flexible with column names
                    available_columns = inventory_df.columns.tolist()
                    
                    # Define priority of columns to display
                    priority_columns = ['item_code', 'name', 'category', 'price', 'unit', 'stock_level', 'supplier']
                    
                    # Use available columns that are in the priority list
                    display_columns = [col for col in priority_columns if col in available_columns]
                    
                    # Add any remaining columns
                    display_columns.extend([col for col in available_columns if col not in display_columns])
                    
                    # Create display DataFrame
                    display_df = inventory_df[display_columns].copy()
                    
                    # Display preview
                    st.dataframe(display_df.head(10))
                    
                    # Option to save
                    if st.button("Save Extracted Inventory"):
                        if results['inventory']:
                            # Determine import mode
                            import_mode = st.radio(
                                "Inventory import mode:",
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
                            st.warning("No inventory items were found to save.")
                else:
                    st.info("No inventory items were extracted.")
            
            with result_tab3:
                st.write(f"### Extracted Sales Records: {len(results['sales'])}")
                if results['sales']:
                    # Convert to DataFrame for display
                    sales_df = pd.DataFrame(results['sales'])
                    
                    # Select columns to display - be more flexible with column names
                    available_columns = sales_df.columns.tolist()
                    
                    # Define priority of columns to display
                    priority_columns = ['date', 'item_name', 'item_code', 'quantity', 'revenue', 'cost', 'profit']
                    
                    # Use available columns that are in the priority list
                    display_columns = [col for col in priority_columns if col in available_columns]
                    
                    # Add any remaining columns
                    display_columns.extend([col for col in available_columns if col not in display_columns])
                    
                    # Create display DataFrame
                    display_df = sales_df[display_columns].copy() 
                    
                    # Display preview
                    st.dataframe(display_df.head(10))
                    
                    # Option to save
                    if st.button("Save Extracted Sales"):
                        if results['sales']:
                            # Determine import mode
                            import_mode = st.radio(
                                "Sales import mode:",
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
                            st.warning("No sales records were found to save.")
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
                                # Display each ingredient with all available fields
                                ingredient_text = f"- "
                                if 'item_code' in ing and ing['item_code']:
                                    ingredient_text += f"[{ing['item_code']}] "
                                
                                ingredient_text += f"{ing.get('name', '')}"
                                
                                if 'qty' in ing and ing['qty']:
                                    ingredient_text += f", {ing['qty']}"
                                elif 'amount' in ing and ing['amount']:
                                    ingredient_text += f", {ing['amount']}"
                                    
                                if 'unit' in ing and ing['unit']:
                                    ingredient_text += f" {ing['unit']}"
                                    
                                if 'loss' in ing and ing['loss']:
                                    ingredient_text += f", Loss: {ing['loss']}"
                                    
                                if 'net_qty' in ing and ing['net_qty']:
                                    ingredient_text += f", Net: {ing['net_qty']}"
                                    
                                if 'unit_cost' in ing and ing['unit_cost']:
                                    ingredient_text += f", Unit Cost: {ing['unit_cost']}"
                                    
                                if 'total_cost' in ing and ing['total_cost']:
                                    ingredient_text += f", Total: {ing['total_cost']}"
                                    
                                st.write(ingredient_text)
                            
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
                        if st.button("Save Recipes"):
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
                    
                    # Select columns to display - be more flexible with column names
                    available_columns = inventory_df.columns.tolist()
                    
                    # Define priority of columns to display
                    priority_columns = ['item_code', 'name', 'category', 'price', 'unit', 'stock_level', 'supplier']
                    
                    # Use available columns that are in the priority list
                    display_columns = [col for col in priority_columns if col in available_columns]
                    
                    # Add any remaining columns
                    display_columns.extend([col for col in available_columns if col not in display_columns])
                    
                    # Create display DataFrame
                    display_df = inventory_df[display_columns].copy()
                    
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
                        if st.button("Save Inventory"):
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
                    
                    # Select columns to display - be more flexible with column names
                    available_columns = sales_df.columns.tolist()
                    
                    # Define priority of columns to display
                    priority_columns = ['date', 'item_name', 'item_code', 'quantity', 'revenue', 'cost', 'profit']
                    
                    # Use available columns that are in the priority list
                    display_columns = [col for col in priority_columns if col in available_columns]
                    
                    # Add any remaining columns
                    display_columns.extend([col for col in available_columns if col not in display_columns])
                    
                    # Create display DataFrame
                    display_df = sales_df[display_columns].copy()
                    
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
                        if st.button("Save Sales"):
                            if import_mode == "Add to existing sales":
                                st.session_state.sales.extend(data)
                            else:
                                st.session_state.sales = data
                            
                            save_sales()
                            st.success(f"Saved {len(data)} sales records!")
                else:
                    st.info("No sales records were extracted.")
    else:
        st.info("No extraction results yet. Upload and process files to see results here.")