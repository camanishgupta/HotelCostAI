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

st.set_page_config(page_title="Recipe Review", page_icon="📋", layout="wide")

st.title("Recipe Review Dashboard")

# Define data file paths
RECIPES_FILE = "data/recipes.json"

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
                    recipe_button = st.button(
                        f"{recipe_name} - Cost: ${recipe_cost:.2f}, Sales: ${recipe_sales_price:.2f}, Cost %: {cost_percentage:.1f}%",
                        key=f"recipe_{recipe_id}_{i}"
                    )
                    
                    if recipe_button:
                        st.session_state.selected_recipe = recipe

# Recipe details in right column
with col2:
    st.subheader("Recipe Details")
    
    if "selected_recipe" in st.session_state and st.session_state.selected_recipe:
        recipe = st.session_state.selected_recipe
        
        # Recipe header with key details
        st.markdown(f"## {recipe.get('name', 'Unnamed Recipe')}")
        st.markdown(f"**Category:** {recipe.get('category', 'Uncategorized')}")
        st.markdown(f"**Yield:** {recipe.get('yield_amount', 1)} {recipe.get('yield_unit', 'serving')}")
        
        # Cost information in columns
        cost_col1, cost_col2, cost_col3 = st.columns(3)
        
        with cost_col1:
            st.metric("Total Cost", f"${recipe.get('total_cost', 0):.2f}")
            
        with cost_col2:
            st.metric("Sales Price", f"${recipe.get('sales_price', 0):.2f}")
            
        with cost_col3:
            st.metric("Cost Percentage", f"{recipe.get('cost_percentage', 0):.1f}%")
        
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
                
                # Format columns for display
                display_df = ingredients_df.copy()
                display_df = display_df[['name', 'amount', 'unit', 'unit_cost', 'total_cost']]
                display_df.columns = ['Ingredient', 'Amount', 'Unit', 'Unit Cost', 'Total Cost']
                
                # Format numeric columns
                for col in ['Unit Cost', 'Total Cost']:
                    if col in display_df.columns:
                        display_df[col] = display_df[col].apply(
                            lambda x: f"${float(x):.2f}" if pd.notnull(x) and x != '' and str(x).replace('.', '', 1).isdigit() else '')
                
                # Display ingredients table
                st.dataframe(display_df, use_container_width=True, height=400)
                
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