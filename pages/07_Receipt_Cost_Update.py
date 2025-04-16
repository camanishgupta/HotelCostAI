import streamlit as st
import pandas as pd
import numpy as np
import os
import json
import io
import tempfile
import time
from datetime import datetime
from utils.data_processing import load_data, save_data
from utils.price_updater import process_receipt_data, update_recipe_costs, display_price_update_summary
from utils.receipt_processor import process_abgn_receipt, process_generic_receipt, preview_receipt_columns

# Set page configuration
st.set_page_config(
    page_title="Recipe Cost Updater",
    page_icon="💰",
    layout="wide"
)

# Initialize session state variables if they don't exist
if 'recipes' not in st.session_state:
    if os.path.exists('data/recipes.json'):
        # Load recipes and ensure they're properly parsed
        recipes_data = load_data('data/recipes.json')
        
        # Process recipe data to ensure proper format
        processed_recipes = []
        if isinstance(recipes_data, list):
            for recipe in recipes_data:
                if isinstance(recipe, dict):
                    processed_recipes.append(recipe)
                elif isinstance(recipe, str):
                    try:
                        # Try to parse as JSON if it's a string
                        recipe_dict = json.loads(recipe)
                        processed_recipes.append(recipe_dict)
                    except:
                        # Skip invalid recipes
                        continue
        
        st.session_state.recipes = processed_recipes if processed_recipes else []
    else:
        st.session_state.recipes = []

if 'inventory' not in st.session_state:
    if os.path.exists('data/inventory.json'):
        # Load inventory and ensure it's properly parsed
        inventory_data = load_data('data/inventory.json')
        
        # Process inventory data to ensure proper format
        processed_inventory = []
        if isinstance(inventory_data, list):
            for item in inventory_data:
                if isinstance(item, dict):
                    processed_inventory.append(item)
                elif isinstance(item, str):
                    try:
                        # Try to parse as JSON if it's a string
                        item_dict = json.loads(item)
                        processed_inventory.append(item_dict)
                    except:
                        # Skip invalid items
                        continue
        
        st.session_state.inventory = processed_inventory if processed_inventory else []
    else:
        st.session_state.inventory = []

if 'update_results' not in st.session_state:
    st.session_state.update_results = None

# Function to save recipes to file
def save_recipes():
    save_data(st.session_state.recipes, 'data/recipes.json')

def save_inventory():
    save_data(st.session_state.inventory, 'data/inventory.json')

# Main page header
st.title("💰 Recipe Cost Updater")
st.markdown("""
This tool helps you update recipe costs based on inventory receipt data. Upload new receipt data, 
match items with ingredients in your recipes, and update costs automatically.
""")

# Create tabs for different update methods
tab1, tab2, tab3 = st.tabs(["Upload Receipt Data", "Manual Price Update", "Update History"])

with tab1:
    st.subheader("Update Costs from Receipt Data")
    st.write("Upload inventory receipt Excel files to update recipe costs")
    
    # File uploader for receipt data
    uploaded_file = st.file_uploader("Upload Receipt Excel File", type=['xlsx', 'xls'])
    
    if uploaded_file:
        # Selecting a processing method
        process_method = st.radio(
            "Receipt Processing Method",
            ["Automatic ABGN Receipt Detection", "Manual Column Selection"],
            index=0,
            help="Automatic detection will attempt to identify columns in ABGN receipt format. Manual selection allows you to specify columns."
        )
        
        # Save uploaded file to temp file for processing
        with tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx') as tmp_file:
            tmp_file.write(uploaded_file.getvalue())
            temp_path = tmp_file.name
            
        if process_method == "Automatic ABGN Receipt Detection":
            st.write("Using specialized ABGN receipt processor...")
            
            # Add a selection for sheet if needed
            try:
                # Display a spinner while processing the file
                with st.spinner("Analyzing ABGN receipt file format..."):
                    # This might take a moment for large files
                    preview_info = preview_receipt_columns(temp_path)
                
                if "error" in preview_info:
                    st.error(f"Error previewing file: {preview_info['error']}")
                    
                    # Provide more detailed error guidance
                    st.error("""
                    The file could not be analyzed properly. This could be due to:
                    1. File format issues
                    2. Unexpected column structures
                    3. Protected or corrupted Excel file
                    
                    Please check if this is a valid ABGN receipt file with price data.
                    """)
                else:
                    # Show file details
                    st.success(f"Successfully analyzed receipt file")
                    
                    # Display available sheets if more than one
                    available_sheets = preview_info.get("available_sheets", [])
                    selected_sheet = None
                    
                    if len(available_sheets) > 1:
                        st.info(f"Found {len(available_sheets)} sheets in this file")
                        selected_sheet = st.selectbox(
                            "Select Sheet to Process",
                            ["Process All Sheets"] + available_sheets
                        )
                        
                        if selected_sheet == "Process All Sheets":
                            selected_sheet = None
                    
                    # Show detected mappings
                    st.subheader("Detected Column Mappings")
                    col_mappings = preview_info.get("column_mappings", {})
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        st.write("Item Code: ", col_mappings.get("item_code", "Not detected"))
                        st.write("Name: ", col_mappings.get("name", "Not detected"))
                        st.write("Unit: ", col_mappings.get("unit", "Not detected"))
                    
                    with col2:
                        st.write("Unit Price: ", col_mappings.get("unit_price", "Not detected"))
                        st.write("Quantity: ", col_mappings.get("quantity", "Not detected"))
                        st.write("Date: ", col_mappings.get("date", "Not detected"))
                    
                    # Show sample data
                    st.subheader("Sample Data")
                    sample_data = preview_info.get("sample_data", [])
                    if sample_data:
                        st.dataframe(pd.DataFrame(sample_data))
                    
                    # Match threshold configuration
                    st.subheader("Matching Configuration")
                    match_threshold = st.slider(
                        "Matching Threshold", 
                        min_value=0.1, 
                        max_value=1.0, 
                        value=0.7, 
                        step=0.05,
                        help="Minimum similarity score (0-1) required to match receipt items to inventory items"
                    )
                    
                    # Process button
                    if st.button("Process Receipt and Update Costs"):
                        if not st.session_state.recipes or not st.session_state.inventory:
                            st.error("You need both recipes and inventory data to update costs.")
                        else:
                            with st.spinner("Processing receipt data..."):
                                # Process the receipt file
                                receipt_items = process_abgn_receipt(temp_path, selected_sheet)
                                
                                if not receipt_items:
                                    st.error("Could not extract any valid receipt items from the file.")
                                else:
                                    st.success(f"Successfully extracted {len(receipt_items)} items from the receipt.")
                                    
                                    # Display extracted items
                                    receipt_df = pd.DataFrame(receipt_items).fillna('')
                                    st.dataframe(receipt_df)
                                    
                                    # Update recipe costs
                                    with st.spinner("Updating recipe costs..."):
                                        updated_recipes, update_summary = update_recipe_costs(
                                            st.session_state.recipes, 
                                            st.session_state.inventory,
                                            receipt_items,
                                            match_threshold=match_threshold
                                        )
                                        
                                        # Store update results
                                        st.session_state.update_results = update_summary
                                        
                                        # Update recipes in session state
                                        st.session_state.recipes = updated_recipes
                                        
                                        # Save recipes to file
                                        save_recipes()
                                        
                                        # Display update summary
                                        display_price_update_summary(update_summary)
                                        
                                        # Add update to history
                                        if 'update_history' not in st.session_state:
                                            st.session_state.update_history = []
                                        
                                        st.session_state.update_history.append({
                                            'date': datetime.now().isoformat(),
                                            'file_name': uploaded_file.name,
                                            'recipes_updated': update_summary.get('recipes_updated', 0),
                                            'ingredients_updated': update_summary.get('ingredients_updated', 0),
                                            'overall_change_percent': update_summary.get('overall_change_percent', 0)
                                        })
                                        
                                        st.success("Recipe costs updated successfully!")
            except Exception as e:
                st.error(f"Error processing receipt file: {str(e)}")
                import traceback
                st.error(traceback.format_exc())
        
        else:  # Manual Column Selection
            # Read the Excel file
            try:
                df = pd.read_excel(temp_path)
                st.write("Preview of uploaded data:")
                st.dataframe(df.head())
                
                # Column mapping
                st.subheader("Map Receipt Columns")
                
                # Detect possible columns
                possible_code_cols = [col for col in df.columns if 'code' in str(col).lower() or 'item' in str(col).lower() or 'id' in str(col).lower()]
                possible_name_cols = [col for col in df.columns if 'name' in str(col).lower() or 'desc' in str(col).lower() or 'item' in str(col).lower()]
                possible_unit_cols = [col for col in df.columns if 'unit' in str(col).lower() or 'uom' in str(col).lower() or 'measure' in str(col).lower()]
                possible_price_cols = [col for col in df.columns if 'price' in str(col).lower() or 'cost' in str(col).lower() or 'rate' in str(col).lower() or 'amount' in str(col).lower()]
                
                # Default indices for selectboxes
                code_idx = next((df.columns.get_loc(col) for col in possible_code_cols if col in df.columns), 0) if possible_code_cols else 0
                name_idx = next((df.columns.get_loc(col) for col in possible_name_cols if col in df.columns), 0) if possible_name_cols else 0
                unit_idx = next((df.columns.get_loc(col) for col in possible_unit_cols if col in df.columns), 0) if possible_unit_cols else 0
                price_idx = next((df.columns.get_loc(col) for col in possible_price_cols if col in df.columns), 0) if possible_price_cols else 0
                
                # Column selection
                col1, col2 = st.columns(2)
                
                with col1:
                    item_code_col = st.selectbox("Item Code Column", ["None"] + list(df.columns), index=code_idx+1 if code_idx >= 0 else 0)
                    name_col = st.selectbox("Item Name Column", ["None"] + list(df.columns), index=name_idx+1 if name_idx >= 0 else 0)
                
                with col2:
                    unit_col = st.selectbox("Unit Column", ["None"] + list(df.columns), index=unit_idx+1 if unit_idx >= 0 else 0)
                    unit_price_col = st.selectbox("Unit Price Column", ["None"] + list(df.columns), index=price_idx+1 if price_idx >= 0 else 0)
                
                # Convert "None" to None
                item_code_col = None if item_code_col == "None" else item_code_col
                name_col = None if name_col == "None" else name_col
                unit_col = None if unit_col == "None" else unit_col
                unit_price_col = None if unit_price_col == "None" else unit_price_col
                
                # Match threshold configuration
                st.subheader("Matching Configuration")
                match_threshold = st.slider(
                    "Matching Threshold", 
                    min_value=0.1, 
                    max_value=1.0, 
                    value=0.7, 
                    step=0.05,
                    help="Minimum similarity score (0-1) required to match receipt items to inventory items"
                )
                
                # Update button
                if st.button("Update Recipe Costs"):
                    if not st.session_state.recipes:
                        st.error("You need recipe data to update costs.")
                    elif not name_col and not item_code_col:
                        st.error("You must select at least an item code or name column.")
                    elif not unit_price_col:
                        st.error("You must select a unit price column.")
                    else:
                        with st.spinner("Updating recipe costs..."):
                            # Process receipt data
                            receipt_items = process_receipt_data(df, item_code_col, name_col, unit_col, unit_price_col)
                            
                            if not receipt_items:
                                st.error("Could not extract any valid receipt items from the uploaded file.")
                            else:
                                # Update recipe costs
                                updated_recipes, update_summary = update_recipe_costs(
                                    st.session_state.recipes, 
                                    st.session_state.inventory,
                                    receipt_items,
                                    match_threshold=match_threshold
                                )
                                
                                # Store update results in session state
                                st.session_state.update_results = update_summary
                                
                                # Update recipes in session state
                                st.session_state.recipes = updated_recipes
                                
                                # Save recipes to file
                                save_recipes()
                                
                                # Display update summary
                                display_price_update_summary(update_summary)
                                
                                # Add update to history
                                if 'update_history' not in st.session_state:
                                    st.session_state.update_history = []
                                
                                st.session_state.update_history.append({
                                    'date': datetime.now().isoformat(),
                                    'file_name': uploaded_file.name,
                                    'recipes_updated': update_summary.get('recipes_updated', 0),
                                    'ingredients_updated': update_summary.get('ingredients_updated', 0),
                                    'overall_change_percent': update_summary.get('overall_change_percent', 0)
                                })
                                
                                st.success("Recipe costs updated successfully!")
            except Exception as e:
                st.error(f"Error reading Excel file: {str(e)}")
                import traceback
                st.error(traceback.format_exc())

with tab2:
    st.subheader("Manual Price Update")
    st.write("Manually update inventory prices and recalculate recipe costs")
    
    # Display current inventory items
    if not st.session_state.inventory:
        st.info("No inventory items found. Add items in the Inventory Management page.")
    else:
        # Make sure inventory is a list of dictionaries not strings
        inventory_data = []
        for item in st.session_state.inventory:
            if isinstance(item, dict):
                inventory_data.append(item)
            elif isinstance(item, str):
                # Try to handle case where data might be serialized improperly
                try:
                    import json
                    item_dict = json.loads(item)
                    inventory_data.append(item_dict)
                except:
                    # If can't parse as JSON, skip this item
                    continue
        
        # Get unique categories for filtering from valid inventory data
        categories = []
        if inventory_data:
            categories = sorted(list(set(item.get('category', '') for item in inventory_data if isinstance(item, dict))))
        
        selected_category = st.selectbox("Filter by Category", ["All Categories"] + categories)
        
        # Filter inventory based on selected category
        filtered_inventory = inventory_data
        if selected_category != "All Categories":
            filtered_inventory = [item for item in inventory_data if item.get('category', '') == selected_category]
        
        # Search filter
        search_query = st.text_input("Search Items", "")
        if search_query:
            filtered_inventory = [item for item in filtered_inventory if 
                                 search_query.lower() in str(item.get('name', '')).lower() or 
                                 search_query.lower() in str(item.get('item_code', '')).lower()]
        
        # Display inventory with editable prices
        inventory_for_display = []
        for i, item in enumerate(filtered_inventory):
            inventory_for_display.append({
                'index': i,
                'item_code': item.get('item_code', ''),
                'name': item.get('name', ''),
                'category': item.get('category', ''),
                'unit': item.get('unit', ''),
                'price': item.get('price', 0.0),
                'supplier': item.get('supplier', '')
            })
        
        # Convert to DataFrame for display
        if inventory_for_display:
            inventory_df = pd.DataFrame(inventory_for_display)
            
            # Create a price editor using Streamlit's form
            with st.form("price_editor_form"):
                st.write("Edit inventory prices:")
                
                # Create a mapping from index to new price
                price_updates = {}
                
                for i, row in inventory_df.iterrows():
                    col1, col2, col3, col4 = st.columns([3, 1, 2, 3])
                    
                    with col1:
                        st.text(f"{row['item_code']} - {row['name']}")
                    
                    with col2:
                        st.text(row['unit'])
                    
                    with col3:
                        # Custom key to avoid duplication
                        new_price = st.number_input(
                            f"Price {i}",
                            min_value=0.0,
                            value=float(row['price']),
                            step=0.01,
                            format="%.2f",
                            label_visibility="collapsed",
                            key=f"price_{row['item_code']}_{i}"
                        )
                        
                        # Check if price has changed
                        if new_price != row['price']:
                            price_updates[row['index']] = new_price
                    
                    with col4:
                        st.text(row['supplier'])
                
                # Submit button
                submitted = st.form_submit_button("Update Prices")
                
                if submitted:
                    if not price_updates:
                        st.info("No price changes were made.")
                    else:
                        # Update inventory prices
                        for index, new_price in price_updates.items():
                            original_index = filtered_inventory[index].get('item_code', '')
                            
                            # Find the actual index in the full inventory
                            for i, item in enumerate(st.session_state.inventory):
                                if item.get('item_code', '') == original_index:
                                    # Check if price has changed
                                    old_price = item.get('price', 0.0)
                                    
                                    # Update the price
                                    st.session_state.inventory[i]['price'] = new_price
                                    
                                    # Add to price history
                                    if 'price_history' not in st.session_state.inventory[i]:
                                        st.session_state.inventory[i]['price_history'] = []
                                    
                                    st.session_state.inventory[i]['price_history'].append({
                                        "price": old_price,
                                        "date": datetime.now().isoformat()
                                    })
                                    
                                    # Update timestamp
                                    st.session_state.inventory[i]['updated_at'] = datetime.now().isoformat()
                        
                        # Save inventory changes
                        save_inventory()
                        
                        # Update recipe costs
                        with st.spinner("Updating recipe costs..."):
                            # Convert inventory items to receipt format for the update function
                            receipt_items = []
                            for index, new_price in price_updates.items():
                                item = filtered_inventory[index]
                                receipt_items.append({
                                    'item_code': item.get('item_code', ''),
                                    'name': item.get('name', ''),
                                    'unit': item.get('unit', ''),
                                    'unit_cost': new_price
                                })
                            
                            # Update recipe costs
                            updated_recipes, update_summary = update_recipe_costs(
                                st.session_state.recipes, 
                                st.session_state.inventory,
                                receipt_items
                            )
                            
                            # Store update results in session state
                            st.session_state.update_results = update_summary
                            
                            # Update recipes in session state
                            st.session_state.recipes = updated_recipes
                            
                            # Save recipes to file
                            save_recipes()
                            
                            # Display update summary
                            display_price_update_summary(update_summary)
                            
                            # Add update to history
                            if 'update_history' not in st.session_state:
                                st.session_state.update_history = []
                            
                            st.session_state.update_history.append({
                                'date': datetime.now().isoformat(),
                                'file_name': 'Manual Update',
                                'recipes_updated': update_summary.get('recipes_updated', 0),
                                'ingredients_updated': update_summary.get('ingredients_updated', 0),
                                'overall_change_percent': update_summary.get('overall_change_percent', 0)
                            })
                            
                            st.success(f"Updated {len(price_updates)} inventory prices and recalculated recipe costs!")

with tab3:
    st.subheader("Update History")
    
    if 'update_history' not in st.session_state or not st.session_state.update_history:
        st.info("No update history available yet.")
    else:
        # Convert history to DataFrame
        history_df = pd.DataFrame(st.session_state.update_history)
        
        # Format for display
        formatted_df = history_df.copy()
        formatted_df['date'] = pd.to_datetime(formatted_df['date']).dt.strftime('%Y-%m-%d %H:%M')
        formatted_df['overall_change_percent'] = formatted_df['overall_change_percent'].apply(lambda x: f"{x:.2f}%")
        
        # Rename columns
        formatted_df.columns = ['Date', 'Source', 'Recipes Updated', 'Ingredients Updated', 'Cost Change']
        
        # Display the history
        st.dataframe(formatted_df, hide_index=True)
        
        # Option to clear history
        if st.button("Clear Update History"):
            st.session_state.update_history = []
            st.success("Update history cleared.")
            st.rerun()
    
    # Display most recent update details
    if st.session_state.update_results:
        with st.expander("Most Recent Update Details", expanded=True):
            display_price_update_summary(st.session_state.update_results)