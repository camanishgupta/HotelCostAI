import streamlit as st
import pandas as pd
import numpy as np
import os
import json
import io
from datetime import datetime
from utils.data_processing import process_excel_upload, generate_column_mapping_ui, load_data, save_data
from models.inventory import detect_price_changes, InventoryItem

# Set page configuration
st.set_page_config(
    page_title="Inventory Management",
    page_icon="📦",
    layout="wide"
)

# Initialize session state variables if they don't exist
if 'inventory' not in st.session_state:
    if os.path.exists('data/inventory.json'):
        st.session_state.inventory = load_data('data/inventory.json')
    else:
        st.session_state.inventory = []

if 'column_mappings' not in st.session_state:
    if os.path.exists('data/column_mappings.json'):
        st.session_state.column_mappings = load_data('data/column_mappings.json')
    else:
        st.session_state.column_mappings = {}

if 'previous_inventory' not in st.session_state:
    st.session_state.previous_inventory = []

if 'edit_inventory_index' not in st.session_state:
    st.session_state.edit_inventory_index = -1

if 'new_inventory_item' not in st.session_state:
    st.session_state.new_inventory_item = InventoryItem().to_dict()

# Create necessary directories if they don't exist
os.makedirs('data', exist_ok=True)

# Helper function to save inventory
def save_inventory():
    save_data(st.session_state.inventory, 'data/inventory.json')

# Helper function to save column mappings
def save_column_mappings():
    save_data(st.session_state.column_mappings, 'data/column_mappings.json')

# Helper function to clear inventory form
def clear_inventory_form():
    st.session_state.new_inventory_item = InventoryItem().to_dict()
    st.session_state.edit_inventory_index = -1

# Main page header
st.title("📦 Inventory Management")
st.markdown("Manage your inventory items, track prices, and monitor stock levels")

# Create tabs for different inventory functions
tab1, tab2, tab3, tab4 = st.tabs(["Inventory List", "Add & Edit Items", "Import Data", "Price Changes"])

with tab1:
    st.subheader("Current Inventory")
    
    # Search and filter
    col1, col2 = st.columns([3, 1])
    with col1:
        search_term = st.text_input("Search inventory", key="inventory_search")
    with col2:
        category_filter = st.selectbox(
            "Filter by category",
            ["All Categories"] + sorted(list(set(item.get('category', 'Uncategorized') for item in st.session_state.inventory)))
        )
    
    # Apply filters
    filtered_inventory = st.session_state.inventory
    if search_term:
        filtered_inventory = [
            item for item in filtered_inventory 
            if search_term.lower() in item.get('name', '').lower() or 
               search_term.lower() in item.get('item_code', '').lower()
        ]
    
    if category_filter != "All Categories":
        filtered_inventory = [
            item for item in filtered_inventory 
            if item.get('category', 'Uncategorized') == category_filter
        ]
    
    # Display inventory data
    if not filtered_inventory:
        st.info("No inventory items found. Add items or import inventory data.")
    else:
        # Convert to DataFrame for display
        inventory_df = pd.DataFrame(filtered_inventory)
        
        # Select columns to display - only use columns that exist in the DataFrame
        all_display_columns = ['item_code', 'name', 'category', 'price', 'unit', 'stock_level', 'supplier', 'updated_at']
        available_columns = [col for col in all_display_columns if col in inventory_df.columns]
        display_df = inventory_df[available_columns].copy()
        
        # Add missing columns with default values
        for col in all_display_columns:
            if col not in available_columns:
                if col in ['price', 'stock_level']:
                    display_df[col] = 0.0
                else:
                    display_df[col] = ""
        
        # Format columns safely - handle missing values
        if 'price' in display_df.columns:
            display_df['price'] = display_df['price'].apply(lambda x: f"${float(x):.2f}" if pd.notna(x) else "$0.00")
        
        if 'updated_at' in display_df.columns:
            try:
                display_df['updated_at'] = pd.to_datetime(display_df['updated_at'], errors='coerce').dt.strftime('%Y-%m-%d')
                # Replace NaT values
                display_df['updated_at'] = display_df['updated_at'].fillna("")
            except:
                display_df['updated_at'] = ""
        
        # Create mapping from original column names to display names
        column_name_map = {
            'item_code': 'Item Code',
            'name': 'Name',
            'category': 'Category',
            'price': 'Price',
            'unit': 'Unit',
            'stock_level': 'Stock Level',
            'supplier': 'Supplier',
            'updated_at': 'Last Updated'
        }
        
        # Rename columns using the mapping
        display_columns = []
        for col in display_df.columns:
            display_columns.append(column_name_map.get(col, col))
        
        display_df.columns = display_columns
        
        # Add edit buttons
        st.dataframe(
            display_df,
            hide_index=True,
            column_config={
                "Item Code": st.column_config.TextColumn("Item Code"),
                "Name": st.column_config.TextColumn("Name"),
                "Category": st.column_config.TextColumn("Category"),
                "Price": st.column_config.TextColumn("Price"),
                "Unit": st.column_config.TextColumn("Unit"),
                "Stock Level": st.column_config.NumberColumn("Stock Level", format="%.2f"),
                "Supplier": st.column_config.TextColumn("Supplier"),
                "Last Updated": st.column_config.DateColumn("Last Updated")
            }
        )
        
        # Inventory summary metrics
        st.subheader("Inventory Summary")
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Total Items", len(filtered_inventory))
        
        with col2:
            total_value = sum(item.get('price', 0) * item.get('stock_level', 0) for item in filtered_inventory)
            st.metric("Total Value", f"${total_value:.2f}")
        
        with col3:
            avg_price = sum(item.get('price', 0) for item in filtered_inventory) / len(filtered_inventory) if filtered_inventory else 0
            st.metric("Average Price", f"${avg_price:.2f}")
        
        with col4:
            low_stock_count = sum(1 for item in filtered_inventory if item.get('stock_level', 0) < 5)
            st.metric("Low Stock Items", low_stock_count)
        
        # Low stock items alert
        if low_stock_count > 0:
            with st.expander("View Low Stock Items"):
                low_stock_items = [item for item in filtered_inventory if item.get('stock_level', 0) < 5]
                low_stock_df = pd.DataFrame([{
                    'Item Code': item.get('item_code', ''),
                    'Name': item.get('name', ''),
                    'Current Stock': item.get('stock_level', 0),
                    'Unit': item.get('unit', ''),
                    'Supplier': item.get('supplier', '')
                } for item in low_stock_items])
                
                st.dataframe(low_stock_df, hide_index=True)

with tab2:
    st.subheader("Add or Edit Inventory Item")
    
    form_col1, form_col2 = st.columns([2, 1])
    
    with form_col1:
        # Item details form
        item_code = st.text_input(
            "Item Code",
            value=st.session_state.new_inventory_item.get('item_code', '')
        )
        
        item_name = st.text_input(
            "Item Name",
            value=st.session_state.new_inventory_item.get('name', '')
        )
        
        # Get unique categories from existing inventory
        existing_categories = sorted(list(set(item.get('category', '') for item in st.session_state.inventory)))
        
        # Allow selecting existing category or entering new one
        category_input = st.selectbox(
            "Category",
            ["Select or enter new..."] + existing_categories,
            index=0 if st.session_state.new_inventory_item.get('category', '') not in existing_categories else 
                existing_categories.index(st.session_state.new_inventory_item.get('category', '')) + 1
        )
        
        if category_input == "Select or enter new...":
            category = st.text_input("Enter New Category", value=st.session_state.new_inventory_item.get('category', ''))
        else:
            category = category_input
        
        # Price and unit information
        price_unit_col1, price_unit_col2 = st.columns(2)
        
        with price_unit_col1:
            price = st.number_input(
                "Price per Unit ($)",
                min_value=0.0,
                value=float(st.session_state.new_inventory_item.get('price', 0.0)),
                step=0.01,
                format="%.2f"
            )
        
        with price_unit_col2:
            # Common units
            common_units = ["Select or enter...", "kg", "g", "L", "ml", "each", "pcs", "box", "carton"]
            
            unit_select = st.selectbox(
                "Unit of Measure",
                common_units,
                index=common_units.index(st.session_state.new_inventory_item.get('unit', '')) if 
                      st.session_state.new_inventory_item.get('unit', '') in common_units else 0
            )
            
            if unit_select == "Select or enter...":
                unit = st.text_input("Enter Unit", value=st.session_state.new_inventory_item.get('unit', ''))
            else:
                unit = unit_select
        
        # Supplier and stock information
        supplier_stock_col1, supplier_stock_col2 = st.columns(2)
        
        with supplier_stock_col1:
            # Get unique suppliers from existing inventory
            existing_suppliers = sorted(list(set(item.get('supplier', '') for item in st.session_state.inventory)))
            
            supplier_select = st.selectbox(
                "Supplier",
                ["Select or enter new..."] + existing_suppliers,
                index=0 if st.session_state.new_inventory_item.get('supplier', '') not in existing_suppliers else 
                    existing_suppliers.index(st.session_state.new_inventory_item.get('supplier', '')) + 1
            )
            
            if supplier_select == "Select or enter new...":
                supplier = st.text_input("Enter New Supplier", value=st.session_state.new_inventory_item.get('supplier', ''))
            else:
                supplier = supplier_select
        
        with supplier_stock_col2:
            stock_level = st.number_input(
                "Current Stock Level",
                min_value=0.0,
                value=float(st.session_state.new_inventory_item.get('stock_level', 0.0)),
                step=1.0
            )
    
    with form_col2:
        # Display current vs new price if editing
        if st.session_state.edit_inventory_index >= 0:
            st.subheader("Price History")
            
            old_item = st.session_state.inventory[st.session_state.edit_inventory_index]
            old_price = old_item.get('price', 0.0)
            
            price_diff = price - old_price
            price_diff_pct = (price_diff / old_price * 100) if old_price > 0 else 0
            
            col1, col2 = st.columns(2)
            with col1:
                st.metric("Previous Price", f"${old_price:.2f}")
            with col2:
                st.metric("New Price", f"${price:.2f}", f"{price_diff_pct:+.1f}%")
            
            # Price history if available
            price_history = old_item.get('price_history', [])
            if price_history:
                hist_df = pd.DataFrame(price_history)
                hist_df['date'] = pd.to_datetime(hist_df['date']).dt.strftime('%Y-%m-%d')
                hist_df.columns = ['Price', 'Date']
                hist_df['Price'] = hist_df['Price'].apply(lambda x: f"${x:.2f}")
                
                st.dataframe(hist_df, hide_index=True)
            else:
                st.info("No price history available for this item.")
        
        # Item value calculation
        st.subheader("Item Value")
        total_value = price * stock_level
        st.metric("Total Value", f"${total_value:.2f}")
        
        # Recipes using this item
        st.subheader("Used In Recipes")
        
        # Find recipes using this ingredient
        if 'recipes' in st.session_state and item_name:
            used_in = []
            for recipe in st.session_state.recipes:
                for ingredient in recipe.get('ingredients', []):
                    if ingredient.get('name', '').lower() == item_name.lower():
                        used_in.append(recipe.get('name', 'Unnamed Recipe'))
                        break
            
            if used_in:
                for recipe_name in used_in:
                    st.write(f"• {recipe_name}")
            else:
                st.info("Not used in any recipes.")
        else:
            st.info("Not used in any recipes.")
    
    # Save/update button
    col1, col2 = st.columns([1, 1])
    with col1:
        if st.button("Clear Form"):
            clear_inventory_form()
            st.rerun()
    
    with col2:
        # Update item from form
        st.session_state.new_inventory_item['item_code'] = item_code
        st.session_state.new_inventory_item['name'] = item_name
        st.session_state.new_inventory_item['category'] = category
        st.session_state.new_inventory_item['price'] = price
        st.session_state.new_inventory_item['unit'] = unit
        st.session_state.new_inventory_item['supplier'] = supplier
        st.session_state.new_inventory_item['stock_level'] = stock_level
        st.session_state.new_inventory_item['updated_at'] = datetime.now().isoformat()
        
        if st.button("Save Item"):
            if not item_code:
                st.error("Item code is required!")
            elif not item_name:
                st.error("Item name is required!")
            elif not unit:
                st.error("Unit of measure is required!")
            else:
                if st.session_state.edit_inventory_index >= 0:
                    # Check if price has changed
                    old_item = st.session_state.inventory[st.session_state.edit_inventory_index]
                    old_price = old_item.get('price', 0.0)
                    
                    if price != old_price:
                        # Add old price to history
                        if 'price_history' not in st.session_state.new_inventory_item:
                            st.session_state.new_inventory_item['price_history'] = []
                        
                        st.session_state.new_inventory_item['price_history'].append({
                            "price": old_price,
                            "date": datetime.now().isoformat()
                        })
                    
                    # Update existing item
                    st.session_state.inventory[st.session_state.edit_inventory_index] = st.session_state.new_inventory_item
                    st.success(f"Item '{item_name}' updated!")
                else:
                    # Initialize price history for new items
                    st.session_state.new_inventory_item['price_history'] = []
                    
                    # Add created_at timestamp for new items
                    st.session_state.new_inventory_item['created_at'] = datetime.now().isoformat()
                    
                    # Add new item
                    st.session_state.inventory.append(st.session_state.new_inventory_item)
                    st.success(f"Item '{item_name}' added!")
                
                # Save inventory to file
                save_inventory()
                
                # Clear the form for a new item
                clear_inventory_form()
                st.rerun()
    
    # Edit or delete existing items
    st.subheader("Quick Edit")
    
    if not st.session_state.inventory:
        st.info("No inventory items to edit.")
    else:
        # Create a list of items for selection
        item_options = [f"{item.get('item_code', '')} - {item.get('name', '')}" for item in st.session_state.inventory]
        selected_item = st.selectbox("Select item to edit or delete", ["Select an item..."] + item_options)
        
        if selected_item != "Select an item...":
            # Get the index of the selected item
            item_index = item_options.index(selected_item) - 1  # Adjust for "Select an item..." entry
            
            col1, col2 = st.columns(2)
            with col1:
                if st.button("Edit Selected"):
                    st.session_state.edit_inventory_index = item_index
                    st.session_state.new_inventory_item = st.session_state.inventory[item_index].copy()
                    st.rerun()
            
            with col2:
                if st.button("Delete Selected"):
                    if st.session_state.inventory:
                        st.session_state.inventory.pop(item_index)
                        save_inventory()
                        st.success(f"Item '{selected_item}' deleted!")
                        st.rerun()

with tab3:
    st.subheader("Import Inventory Data")
    st.write("Upload Excel files with inventory data to update your system")
    
    # File uploader
    uploaded_file = st.file_uploader("Upload inventory data", type=['xlsx'])
    
    if uploaded_file:
        # Preview the data
        df = pd.read_excel(uploaded_file)
        st.write("Preview of uploaded data:")
        st.dataframe(df.head())
        
        # Column mapping
        st.subheader("Map Columns")
        with st.form("column_mapping_form"):
            # Get mapping from UI
            mapping = generate_column_mapping_ui(df, 'inventory')
            
            # Save mapping option
            mapping_name = st.text_input("Save this mapping as (optional):")
            
            # Import options
            import_option = st.radio(
                "Import option:",
                ["Add new items only", "Update existing items only", "Add new and update existing"]
            )
            
            # Submit button
            submitted = st.form_submit_button("Import Data")
            
            if submitted:
                # Save mapping if a name was provided
                if mapping_name:
                    st.session_state.column_mappings[mapping_name] = mapping
                    save_column_mappings()
                
                # Process the upload
                with st.spinner("Processing data..."):
                    # Store previous inventory for price change detection
                    st.session_state.previous_inventory = st.session_state.inventory.copy()
                    
                    # Process the upload
                    result = process_excel_upload(uploaded_file, 'inventory', mapping)
                    
                    if result['status'] == 'success':
                        # Get the processed data
                        new_items = result['data']
                        
                        # Handle based on import option
                        if import_option == "Add new items only":
                            # Only add items with item codes that don't exist yet
                            existing_codes = [item.get('item_code', '') for item in st.session_state.inventory]
                            items_to_add = [item for item in new_items if item.get('item_code', '') not in existing_codes]
                            
                            st.session_state.inventory.extend(items_to_add)
                            st.success(f"Added {len(items_to_add)} new items to inventory.")
                            
                        elif import_option == "Update existing items only":
                            # Only update existing items
                            existing_codes = [item.get('item_code', '') for item in st.session_state.inventory]
                            updated_count = 0
                            
                            for new_item in new_items:
                                item_code = new_item.get('item_code', '')
                                if item_code in existing_codes:
                                    # Find the item index
                                    item_index = next((i for i, item in enumerate(st.session_state.inventory) 
                                                    if item.get('item_code', '') == item_code), -1)
                                    
                                    if item_index >= 0:
                                        # Get the old item for price history
                                        old_item = st.session_state.inventory[item_index]
                                        old_price = old_item.get('price', 0.0)
                                        new_price = new_item.get('price', 0.0)
                                        
                                        # Update price history if price changed
                                        if old_price != new_price:
                                            if 'price_history' not in new_item:
                                                new_item['price_history'] = old_item.get('price_history', [])
                                            
                                            new_item['price_history'].append({
                                                "price": old_price,
                                                "date": datetime.now().isoformat()
                                            })
                                        else:
                                            # Keep existing price history
                                            new_item['price_history'] = old_item.get('price_history', [])
                                        
                                        # Keep created_at from original item
                                        new_item['created_at'] = old_item.get('created_at', datetime.now().isoformat())
                                        
                                        # Update the item
                                        st.session_state.inventory[item_index] = new_item
                                        updated_count += 1
                            
                            st.success(f"Updated {updated_count} existing items.")
                            
                        else:  # "Add new and update existing"
                            # Update existing items and add new ones
                            existing_codes = [item.get('item_code', '') for item in st.session_state.inventory]
                            updated_count = 0
                            added_count = 0
                            
                            for new_item in new_items:
                                item_code = new_item.get('item_code', '')
                                
                                if item_code in existing_codes:
                                    # Update existing item
                                    item_index = next((i for i, item in enumerate(st.session_state.inventory) 
                                                    if item.get('item_code', '') == item_code), -1)
                                    
                                    if item_index >= 0:
                                        # Get the old item for price history
                                        old_item = st.session_state.inventory[item_index]
                                        old_price = old_item.get('price', 0.0)
                                        new_price = new_item.get('price', 0.0)
                                        
                                        # Update price history if price changed
                                        if old_price != new_price:
                                            if 'price_history' not in new_item:
                                                new_item['price_history'] = old_item.get('price_history', [])
                                            
                                            new_item['price_history'].append({
                                                "price": old_price,
                                                "date": datetime.now().isoformat()
                                            })
                                        else:
                                            # Keep existing price history
                                            new_item['price_history'] = old_item.get('price_history', [])
                                        
                                        # Keep created_at from original item
                                        new_item['created_at'] = old_item.get('created_at', datetime.now().isoformat())
                                        
                                        # Update the item
                                        st.session_state.inventory[item_index] = new_item
                                        updated_count += 1
                                else:
                                    # Add new item
                                    new_item['price_history'] = []
                                    new_item['created_at'] = datetime.now().isoformat()
                                    st.session_state.inventory.append(new_item)
                                    added_count += 1
                            
                            st.success(f"Added {added_count} new items and updated {updated_count} existing items.")
                        
                        # Save the updated inventory
                        save_inventory()
                        
                        # Redirect to price changes tab if there were updates
                        if import_option != "Add new items only" and st.session_state.previous_inventory:
                            st.rerun()
                    else:
                        st.error(f"Error processing data: {result['message']}")
                    
                    # Reset uploaded file
                    uploaded_file = None
        
        # Show saved mappings if available
        if st.session_state.column_mappings:
            st.subheader("Saved Column Mappings")
            
            mapping_options = list(st.session_state.column_mappings.keys())
            selected_mapping = st.selectbox("Load a saved mapping:", ["Select a mapping..."] + mapping_options)
            
            if selected_mapping != "Select a mapping..." and st.button("Load Selected Mapping"):
                mapping = st.session_state.column_mappings[selected_mapping]
                st.success(f"Loaded mapping '{selected_mapping}'")
                st.rerun()

with tab4:
    st.subheader("Price Change Analysis")
    
    # Option to manually select date ranges or compare with previous import
    analysis_option = st.radio(
        "Analysis option:",
        ["Compare with previous import", "Compare specific date ranges"]
    )
    
    if analysis_option == "Compare with previous import":
        # Use the previous inventory stored during import
        if not st.session_state.previous_inventory:
            st.info("No previous import data available for comparison. Please import new inventory data first.")
        else:
            # Detect price changes
            price_changes = detect_price_changes(st.session_state.previous_inventory, st.session_state.inventory)
            
            if not price_changes:
                st.success("No significant price changes detected in the recent import.")
            else:
                st.warning(f"Found {len(price_changes)} significant price changes!")
                
                # Convert to DataFrame for display
                changes_df = pd.DataFrame(price_changes)
                
                # Format for display
                display_changes = changes_df.copy()
                display_changes['old_price'] = display_changes['old_price'].apply(lambda x: f"${x:.2f}")
                display_changes['new_price'] = display_changes['new_price'].apply(lambda x: f"${x:.2f}")
                display_changes['percentage_change'] = display_changes['percentage_change'].apply(lambda x: f"{x:+.1f}%")
                
                # Rename columns
                display_changes.columns = ['Item Code', 'Name', 'Old Price', 'New Price', 'Change', 'Unit']
                
                # Display the changes
                st.dataframe(display_changes, hide_index=True)
                
                # Impact analysis
                st.subheader("Impact Analysis")
                st.write("Analyzing the impact of these price changes on your recipes...")
                
                # Check which recipes are affected by the price changes
                if 'recipes' in st.session_state and st.session_state.recipes:
                    affected_recipes = []
                    
                    for recipe in st.session_state.recipes:
                        recipe_name = recipe.get('name', 'Unnamed Recipe')
                        ingredients = recipe.get('ingredients', [])
                        
                        # Check if any ingredients in this recipe had price changes
                        recipe_affected = False
                        total_impact = 0
                        affected_ingredients = []
                        
                        for ingredient in ingredients:
                            ing_name = ingredient.get('name', '')
                            
                            # Find if this ingredient had a price change
                            for change in price_changes:
                                if change['name'].lower() == ing_name.lower():
                                    recipe_affected = True
                                    
                                    # Calculate impact on this ingredient
                                    old_cost = float(ingredient.get('amount', 0)) * change['old_price']
                                    new_cost = float(ingredient.get('amount', 0)) * change['new_price']
                                    impact = new_cost - old_cost
                                    total_impact += impact
                                    
                                    affected_ingredients.append({
                                        'name': ing_name,
                                        'impact': impact,
                                        'percentage_change': change['percentage_change']
                                    })
                        
                        if recipe_affected:
                            affected_recipes.append({
                                'name': recipe_name,
                                'total_impact': total_impact,
                                'impact_percentage': (total_impact / recipe.get('total_cost', 1)) * 100 if recipe.get('total_cost', 0) > 0 else 0,
                                'affected_ingredients': affected_ingredients
                            })
                    
                    if affected_recipes:
                        # Sort by impact percentage
                        affected_recipes.sort(key=lambda x: abs(x['impact_percentage']), reverse=True)
                        
                        st.write(f"Found {len(affected_recipes)} affected recipes.")
                        
                        # Display affected recipes
                        impact_df = pd.DataFrame([{
                            'Recipe': recipe['name'],
                            'Cost Impact': f"${recipe['total_impact']:.2f}",
                            'Impact %': f"{recipe['impact_percentage']:+.1f}%",
                            'Affected Ingredients': len(recipe['affected_ingredients'])
                        } for recipe in affected_recipes])
                        
                        st.dataframe(impact_df, hide_index=True)
                        
                        # Detailed impact for selected recipe
                        selected_recipe = st.selectbox(
                            "View detailed impact for:",
                            [recipe['name'] for recipe in affected_recipes]
                        )
                        
                        # Find the selected recipe
                        selected_data = next((r for r in affected_recipes if r['name'] == selected_recipe), None)
                        
                        if selected_data:
                            st.write(f"### Impact Details for {selected_recipe}")
                            
                            # Show impact metrics
                            col1, col2 = st.columns(2)
                            with col1:
                                st.metric("Total Cost Impact", f"${selected_data['total_impact']:.2f}")
                            with col2:
                                st.metric("Percentage Impact", f"{selected_data['impact_percentage']:+.1f}%")
                            
                            # Show affected ingredients
                            ing_impact_df = pd.DataFrame([{
                                'Ingredient': ing['name'],
                                'Cost Impact': f"${ing['impact']:.2f}",
                                'Price Change': f"{ing['percentage_change']:+.1f}%"
                            } for ing in selected_data['affected_ingredients']])
                            
                            st.dataframe(ing_impact_df, hide_index=True)
                            
                            # Recommendations
                            st.subheader("Recommendations")
                            
                            if selected_data['impact_percentage'] > 5:
                                st.warning("""
                                The price changes have a significant impact on this recipe's cost.
                                Consider the following actions:
                                - Adjust menu prices to maintain profit margins
                                - Look for alternative suppliers for the affected ingredients
                                - Consider reformulating the recipe to use less expensive ingredients
                                """)
                            elif selected_data['impact_percentage'] > 2:
                                st.info("""
                                The price changes have a moderate impact on this recipe's cost.
                                Consider monitoring these ingredients closely and look for alternatives
                                if prices continue to increase.
                                """)
                            else:
                                st.success("""
                                The price changes have a minimal impact on this recipe's cost.
                                No immediate action is required, but continue to monitor prices.
                                """)
                    else:
                        st.success("No recipes are affected by these price changes.")
                else:
                    st.info("No recipes found in the system to analyze impact.")
    
    else:  # Compare specific date ranges
        st.info("To compare specific date ranges, use the import function to load inventory data from different dates.")
