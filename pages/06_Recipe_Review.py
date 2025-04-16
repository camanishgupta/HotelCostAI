import streamlit as st
import pandas as pd
import json
import os
import sys
from datetime import datetime

# Add the root directory to sys.path to import modules from other directories
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from utils.data_processing import load_data, save_data
from models.recipe import Recipe

# Constants
RECIPES_FILE = "data/recipes.json"

st.set_page_config(page_title="Recipe Review", page_icon="📋", layout="wide")

st.title("Recipe Review Dashboard")

# Load existing recipes
recipes_data = load_data(RECIPES_FILE) if os.path.exists(RECIPES_FILE) else []

# Make sure recipes are in the correct format (list of dictionaries)
recipes = []

# Handle the case where the data might be a dictionary with 'data' field
if isinstance(recipes_data, dict) and 'data' in recipes_data:
    recipes_data = recipes_data['data']

for recipe in recipes_data:
    # Handle case when a recipe is a string instead of a dictionary
    if isinstance(recipe, str):
        try:
            # Try to parse it as JSON
            recipe_dict = json.loads(recipe)
            recipes.append(recipe_dict)
        except:
            # If not valid JSON, create a basic recipe entry
            recipes.append({"name": recipe, "category": "Uncategorized"})
    else:
        # Already a dictionary or other object
        recipes.append(recipe)

# Display the total number of recipes loaded
st.sidebar.info(f"Total Recipes Loaded: {len(recipes)}")

# Initialize session state
if "filtered_recipes" not in st.session_state:
    st.session_state.filtered_recipes = recipes

if "search_query" not in st.session_state:
    st.session_state.search_query = ""
    
if "selected_category" not in st.session_state:
    st.session_state.selected_category = "All Categories"

def update_filters():
    """Update filtered recipes based on search query and category selection"""
    filtered = recipes
    
    # Filter by search query
    if st.session_state.search_query:
        query = st.session_state.search_query.lower()
        filtered = [r for r in filtered if isinstance(r, dict) and 
                   query in str(r.get('name', '')).lower()]
    
    # Filter by category
    if st.session_state.selected_category != "All Categories":
        filtered = [r for r in filtered if isinstance(r, dict) and 
                   r.get('category', '') == st.session_state.selected_category]
    
    st.session_state.filtered_recipes = filtered

# Create sidebar for filters
with st.sidebar:
    st.header("Recipe Filters")
    
    # Search box
    search_query = st.text_input("Search Recipes", key="search_box", 
                                on_change=update_filters, value=st.session_state.search_query)
    st.session_state.search_query = search_query
    
    # Extract categories safely
    recipe_categories = set()
    for r in recipes:
        if isinstance(r, dict) and r.get('category'):
            recipe_categories.add(r.get('category', ''))
    
    # Category filter
    categories = ["All Categories"] + sorted(list(recipe_categories))
    selected_category = st.selectbox("Filter by Category", categories, 
                                    key="category_selector", on_change=update_filters,
                                    index=categories.index(st.session_state.selected_category) 
                                    if st.session_state.selected_category in categories else 0)
    st.session_state.selected_category = selected_category
    
    # Update button
    if st.button("Apply Filters"):
        update_filters()
    
    # Reset filters
    if st.button("Reset Filters"):
        st.session_state.search_query = ""
        st.session_state.selected_category = "All Categories"
        update_filters()
    
    # Total recipes info
    st.write(f"Total Recipes: {len(recipes)}")
    st.write(f"Filtered Recipes: {len(st.session_state.filtered_recipes)}")

# Main content area
col1, col2 = st.columns([1, 2])

# Recipe list in left column
with col1:
    st.subheader("Recipe List")
    
    # Create recipe selection
    if not st.session_state.filtered_recipes:
        st.info("No recipes found. Add recipes from the Recipe Management page.")
    else:
        # Group recipes by category
        recipes_by_category = {}
        for recipe in st.session_state.filtered_recipes:
            category = recipe.get('category', 'Uncategorized')
            if category not in recipes_by_category:
                recipes_by_category[category] = []
            recipes_by_category[category].append(recipe)
        
        # Display recipes by category
        for category, category_recipes in recipes_by_category.items():
            with st.expander(f"{category} ({len(category_recipes)})", expanded=True):
                for i, recipe in enumerate(category_recipes):
                    recipe_id = recipe.get('id', i)
                    recipe_name = recipe.get('name', f"Recipe {i+1}")
                    recipe_cost = recipe.get('total_cost', 0)
                    recipe_sales_price = recipe.get('sales_price', 0)
                    cost_percentage = recipe.get('cost_percentage', 0)
                    
                    # Create a clickable recipe item
                    # Use a unique key combining category, index, and recipe ID
                    unique_key = f"recipe_{category}_{i}_{recipe_id}"
                    
                    recipe_button = st.button(
                        f"{recipe_name} - Cost: ${recipe_cost:.2f}, Sales: ${recipe_sales_price:.2f}, Cost %: {cost_percentage:.1f}%",
                        key=unique_key
                    )
                    
                    if recipe_button:
                        st.session_state.selected_recipe = recipe

# Recipe details in right column
with col2:
    st.subheader("Recipe Details")
    
    if "selected_recipe" in st.session_state and st.session_state.selected_recipe:
        recipe = st.session_state.selected_recipe
        
        # Recipe header with key details and editable fields
        st.markdown(f"## {recipe.get('name', 'Unnamed Recipe')}")
        
        # Editable details
        with st.form(key="recipe_details_form"):
            col1, col2 = st.columns(2)
            
            with col1:
                # Make name editable
                recipe_name = st.text_input("Recipe Name", value=recipe.get('name', 'Unnamed Recipe'))
                
                # Make category editable
                recipe_category = st.text_input("Category", value=recipe.get('category', 'Uncategorized'))
                
                # Make yield amount editable
                recipe_yield = st.number_input(
                    "Yield Amount", 
                    min_value=0.1, 
                    value=float(recipe.get('yield_amount', 1)),
                    step=0.1
                )
            
            with col2:
                # Make sales price editable
                recipe_sales_price = st.number_input(
                    "Sales Price", 
                    min_value=0.0, 
                    value=float(recipe.get('sales_price', 0)),
                    step=10.0,
                    format="%.2f"
                )
                
                # Calculate total cost from ingredients
                total_cost = sum(ingredient.get('total_cost', 0) for ingredient in recipe.get('ingredients', []))
                
                # Display total cost and cost percentage
                st.metric("Total Cost", f"${total_cost:.2f}")
                
                cost_percentage = 0
                if recipe_sales_price > 0:
                    cost_percentage = (total_cost / recipe_sales_price) * 100
                
                st.metric("Cost Percentage", f"{cost_percentage:.1f}%")
            
            # Submit button for recipe details
            if st.form_submit_button("Update Recipe Details"):
                # Update recipe with new values
                recipe['name'] = recipe_name
                recipe['category'] = recipe_category
                recipe['yield_amount'] = recipe_yield
                recipe['sales_price'] = recipe_sales_price
                recipe['total_cost'] = total_cost
                recipe['cost_percentage'] = cost_percentage
                
                # Save updated recipe to session state
                st.session_state.selected_recipe = recipe
                
                # Refresh to show updated values
                st.success("Recipe details updated successfully!")
                st.rerun()
        
        # Ingredients table
        st.subheader("Ingredients")
        
        ingredients = recipe.get('ingredients', [])
        if ingredients:
            try:
                # Make sure ingredients are in the correct format
                formatted_ingredients = []
                for ing in ingredients:
                    if isinstance(ing, dict):
                        formatted_ingredients.append(ing)
                    elif isinstance(ing, str):
                        # Try to convert string to dict
                        try:
                            ing_dict = json.loads(ing)
                            formatted_ingredients.append(ing_dict)
                        except:
                            formatted_ingredients.append({"name": ing, "amount": 0, "unit": "", "unit_cost": 0, "total_cost": 0})
                    else:
                        # Skip invalid types
                        continue
                        
                # Create a DataFrame for display
                ingredients_df = pd.DataFrame(formatted_ingredients)
                
                # Ensure required columns exist
                for col in ['name', 'amount', 'unit', 'unit_cost', 'total_cost']:
                    if col not in ingredients_df.columns:
                        ingredients_df[col] = ''
                
                # Format columns for display - include all ABGN columns
                display_df = ingredients_df.copy()
                
                # Check for each possible column and include it if it exists
                columns_to_display = []
                column_mapping = {}
                
                if 'item_code' in display_df.columns:
                    columns_to_display.append('item_code')
                    column_mapping['item_code'] = 'Item Code'
                
                columns_to_display.append('name')
                column_mapping['name'] = 'Ingredient'
                
                if 'unit' in display_df.columns:
                    columns_to_display.append('unit')
                    column_mapping['unit'] = 'Unit'
                
                # Handle different naming conventions for quantity
                if 'qty' in display_df.columns:
                    columns_to_display.append('qty')
                    column_mapping['qty'] = 'QTY'
                elif 'amount' in display_df.columns:
                    columns_to_display.append('amount')
                    column_mapping['amount'] = 'QTY'
                
                # Add loss column if present
                if 'loss' in display_df.columns:
                    columns_to_display.append('loss')
                    column_mapping['loss'] = 'Loss'
                
                # Add net_qty column if present
                if 'net_qty' in display_df.columns:
                    columns_to_display.append('net_qty')
                    column_mapping['net_qty'] = 'Net Qty'
                
                # Add pricing columns
                if 'unit_cost' in display_df.columns:
                    columns_to_display.append('unit_cost')
                    column_mapping['unit_cost'] = 'AT AMOUNT'
                
                if 'total_cost' in display_df.columns:
                    columns_to_display.append('total_cost')
                    column_mapping['total_cost'] = 'TOTAL AMOUNT KS'
                
                # Ensure we have at least basic columns if none of the standard ones are found
                if not columns_to_display:
                    columns_to_display = list(display_df.columns)
                    column_mapping = {col: col.capitalize() for col in columns_to_display}
                
                # Select only columns that actually exist in the DataFrame
                available_columns = [col for col in columns_to_display if col in display_df.columns]
                display_df = display_df[available_columns]
                
                # Rename columns to match ABGN format
                new_column_names = [column_mapping.get(col, col.capitalize()) for col in available_columns]
                display_df.columns = new_column_names
                
                # Format numeric columns - match both original and ABGN column names
                price_columns = ['Unit Cost', 'Total Cost', 'AT AMOUNT', 'TOTAL AMOUNT KS']
                for col in price_columns:
                    if col in display_df.columns:
                        display_df[col] = display_df[col].apply(
                            lambda x: f"{float(x):,.2f}" if pd.notnull(x) and x != '' and str(x).replace('.', '', 1).isdigit() else '')
                            
                # Format quantity columns
                qty_columns = ['QTY', 'Amount', 'Loss', 'Net Qty']
                for col in qty_columns:
                    if col in display_df.columns:
                        display_df[col] = display_df[col].apply(
                            lambda x: f"{float(x):.3f}" if pd.notnull(x) and x != '' and str(x).replace('.', '', 1).isdigit() else '')
                
                # Display ingredients table
                st.dataframe(display_df, use_container_width=True, height=400)
                
                # Add option to edit ingredients
                with st.expander("Edit Ingredients"):
                    # Select which ingredient to edit
                    ingredient_names = [ing.get('name', f"Ingredient {i+1}") for i, ing in enumerate(formatted_ingredients)]
                    selected_ingredient_idx = st.selectbox(
                        "Select ingredient to edit", 
                        range(len(ingredient_names)),
                        format_func=lambda i: ingredient_names[i]
                    )
                    
                    # Create a form to edit the selected ingredient
                    selected_ingredient = formatted_ingredients[selected_ingredient_idx]
                    with st.form(key=f"edit_ingredient_form_{selected_ingredient_idx}"):
                        # Basic ingredient info
                        ing_name = st.text_input("Ingredient Name", value=selected_ingredient.get('name', ''))
                        ing_code = st.text_input("Item Code", value=selected_ingredient.get('item_code', ''))
                        ing_unit = st.text_input("Unit", value=selected_ingredient.get('unit', ''))
                        
                        # Quantities
                        col1, col2 = st.columns(2)
                        with col1:
                            # Use qty or amount based on what's available
                            qty_field = 'qty' if 'qty' in selected_ingredient else 'amount'
                            ing_qty = st.number_input(
                                "Quantity", 
                                min_value=0.0, 
                                value=float(selected_ingredient.get(qty_field, 0)),
                                step=0.01,
                                format="%.3f"
                            )
                            
                            ing_loss = st.number_input(
                                "Loss %", 
                                min_value=0.0, 
                                max_value=1.0,
                                value=float(selected_ingredient.get('loss', 0)),
                                step=0.01,
                                format="%.2f",
                                help="Loss as a decimal: 0.05 = 5%"
                            )
                        
                        with col2:
                            # Net Qty is calculated
                            net_qty = ing_qty + (ing_loss * ing_qty)
                            st.text_input("Net Quantity (calculated)", value=f"{net_qty:.3f}", disabled=True)
                            
                            ing_unit_cost = st.number_input(
                                "Unit Cost", 
                                min_value=0.0, 
                                value=float(selected_ingredient.get('unit_cost', 0)),
                                step=10.0,
                                format="%.2f"
                            )
                            
                            # Total cost is calculated
                            total_cost = net_qty * ing_unit_cost
                            st.text_input("Total Cost (calculated)", value=f"{total_cost:.2f}", disabled=True)
                        
                        # Submit button
                        if st.form_submit_button("Update Ingredient"):
                            # Update the ingredient in the list
                            selected_ingredient['name'] = ing_name
                            selected_ingredient['item_code'] = ing_code
                            selected_ingredient['unit'] = ing_unit
                            selected_ingredient[qty_field] = ing_qty
                            selected_ingredient['loss'] = ing_loss
                            selected_ingredient['net_qty'] = net_qty
                            selected_ingredient['unit_cost'] = ing_unit_cost
                            selected_ingredient['total_cost'] = total_cost
                            
                            # Update the ingredient in the recipe
                            recipe['ingredients'][selected_ingredient_idx] = selected_ingredient
                            
                            # Recalculate recipe total cost
                            recipe['total_cost'] = sum(ing.get('total_cost', 0) for ing in recipe['ingredients'])
                            
                            # Recalculate cost percentage
                            if recipe['sales_price'] > 0:
                                recipe['cost_percentage'] = (recipe['total_cost'] / recipe['sales_price']) * 100
                            
                            # Update session state
                            st.session_state.selected_recipe = recipe
                            
                            # Display success message
                            st.success(f"Ingredient '{ing_name}' updated successfully!")
                            
                            # Reload the page to show updated values
                            st.rerun()
                
                # Button to save all changes to the recipes data file
                if st.button("Save All Changes"):
                    # Get existing recipes
                    recipes_data = load_data(RECIPES_FILE)
                    
                    # Find and update the current recipe
                    updated = False
                    for i, r in enumerate(recipes_data):
                        if isinstance(r, dict) and r.get('name') == recipe.get('name'):
                            recipes_data[i] = recipe
                            updated = True
                            break
                    
                    # If not found, append it
                    if not updated:
                        recipes_data.append(recipe)
                        
                    # Save back to file
                    if save_data(recipes_data, RECIPES_FILE):
                        st.success("All changes saved successfully!")
                    else:
                        st.error("Failed to save changes. Please try again.")
                
                # Summary metrics
                total_ingredients = len(formatted_ingredients)
                
                # Safely find highest cost ingredient
                if formatted_ingredients:
                    try:
                        highest_cost_ingredient = max(
                            formatted_ingredients, 
                            key=lambda x: float(x.get('total_cost', 0)) 
                                if x.get('total_cost') and str(x.get('total_cost')).replace('.', '', 1).isdigit() 
                                else 0
                        )
                        highest_cost_name = highest_cost_ingredient.get('name', 'Unknown')
                        highest_cost_value = highest_cost_ingredient.get('total_cost', 0)
                    except Exception as e:
                        st.warning(f"Could not determine highest cost ingredient: {str(e)}")
                        highest_cost_name = "Unknown"
                        highest_cost_value = 0
                else:
                    highest_cost_name = "Unknown"
                    highest_cost_value = 0
            except Exception as e:
                st.error(f"Error displaying ingredients: {str(e)}")
                st.write("Raw ingredients data:")
                st.write(ingredients)
                total_ingredients = len(ingredients)
                highest_cost_name = "Unknown"
                highest_cost_value = 0
            
            st.markdown(f"**Total Ingredients:** {total_ingredients}")
            st.markdown(f"**Highest Cost Ingredient:** {highest_cost_name} (${highest_cost_value:.2f})")
        else:
            st.info("No ingredients found for this recipe.")
            
        # Recipe actions
        st.subheader("Actions")
        
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("Edit Recipe", key="edit_recipe"):
                # Set up session state for edit in Recipe Management page
                st.session_state.recipe_to_edit = recipe
                st.switch_page("pages/01_Recipe_Management.py")
        
        with col2:
            if st.button("Print Recipe", key="print_recipe"):
                # Create a printer-friendly view
                st.info("Printing functionality to be implemented.")
                
    else:
        st.info("Select a recipe from the list to view details.")