import streamlit as st
import pandas as pd
import os
import json
from datetime import datetime
from utils.data_processing import load_data, save_data, process_excel_upload, calculate_recipe_cost
from models.recipe import Recipe

# Set page configuration
st.set_page_config(
    page_title="Recipe Management",
    page_icon="📝",
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

# Helper function to save recipes
def save_recipes():
    save_data(st.session_state.recipes, 'data/recipes.json')

# Helper function to clear recipe form
def clear_recipe_form():
    st.session_state.new_recipe_name = ""
    st.session_state.new_recipe_yield_amount = 1
    st.session_state.new_recipe_yield_unit = "serving"
    st.session_state.new_recipe_ingredients = []
    st.session_state.new_recipe_preparation_steps = []

# Initialize recipe form state if needed
if 'new_recipe_name' not in st.session_state:
    st.session_state.new_recipe_name = ""
if 'new_recipe_yield_amount' not in st.session_state:
    st.session_state.new_recipe_yield_amount = 1
if 'new_recipe_yield_unit' not in st.session_state:
    st.session_state.new_recipe_yield_unit = "serving"
if 'new_recipe_ingredients' not in st.session_state:
    st.session_state.new_recipe_ingredients = []
if 'new_recipe_preparation_steps' not in st.session_state:
    st.session_state.new_recipe_preparation_steps = []

# Page title
st.title("📝 Recipe Management")
st.markdown("Create, edit, and manage your recipes")

# Create tabs for different sections
tab1, tab2, tab3 = st.tabs(["Recipe List", "Add Recipe", "Import Recipes"])

with tab1:
    st.subheader("Recipe List")
    
    # Filter and sort options
    col1, col2 = st.columns(2)
    
    with col1:
        search_term = st.text_input("Search recipes", "")
    
    with col2:
        sort_by = st.selectbox(
            "Sort by",
            ["Name (A-Z)", "Name (Z-A)", "Cost (Low to High)", "Cost (High to Low)"]
        )
    
    # Apply filters and sorting
    filtered_recipes = st.session_state.recipes.copy()
    
    # Search filter
    if search_term:
        filtered_recipes = [
            recipe for recipe in filtered_recipes
            if search_term.lower() in recipe.get("name", "").lower()
        ]
    
    # Sorting
    if sort_by == "Name (A-Z)":
        filtered_recipes.sort(key=lambda x: x.get("name", "").lower())
    elif sort_by == "Name (Z-A)":
        filtered_recipes.sort(key=lambda x: x.get("name", "").lower(), reverse=True)
    elif sort_by == "Cost (Low to High)":
        filtered_recipes.sort(key=lambda x: x.get("total_cost", 0))
    elif sort_by == "Cost (High to Low)":
        filtered_recipes.sort(key=lambda x: x.get("total_cost", 0), reverse=True)
    
    # Display recipes
    if filtered_recipes:
        for i, recipe in enumerate(filtered_recipes):
            with st.expander(f"{recipe.get('name', 'Unnamed Recipe')} - ${recipe.get('total_cost', 0):.2f}"):
                col1, col2 = st.columns([3, 1])
                
                with col1:
                    st.markdown(f"**Yield:** {recipe.get('yield_amount', 1)} {recipe.get('yield_unit', 'serving')}")
                    st.markdown(f"**Cost per {recipe.get('yield_unit', 'serving')}:** ${recipe.get('cost_per_unit', 0):.2f}")
                    
                    st.subheader("Ingredients")
                    ingredient_data = []
                    
                    for ingredient in recipe.get("ingredients", []):
                        ingredient_data.append({
                            "Name": ingredient.get("name", ""),
                            "Amount": ingredient.get("amount", 0),
                            "Unit": ingredient.get("unit", ""),
                            "Cost": f"${ingredient.get('cost', 0):.2f}"
                        })
                    
                    if ingredient_data:
                        st.table(pd.DataFrame(ingredient_data))
                    else:
                        st.info("No ingredients specified.")
                    
                    st.subheader("Preparation Steps")
                    for j, step in enumerate(recipe.get("preparation_steps", [])):
                        st.markdown(f"{j+1}. {step}")
                    
                    if not recipe.get("preparation_steps", []):
                        st.info("No preparation steps specified.")
                
                with col2:
                    # Actions
                    if st.button("Delete Recipe", key=f"delete_{i}"):
                        st.session_state.recipes.remove(recipe)
                        save_recipes()
                        st.success("Recipe deleted!")
                        st.rerun()
                    
                    # Scale recipe
                    new_yield = st.number_input(
                        "Scale recipe to yield:",
                        min_value=1,
                        value=recipe.get("yield_amount", 1),
                        key=f"scale_{i}"
                    )
                    
                    if st.button("Scale Recipe", key=f"scale_btn_{i}"):
                        # Create Recipe object
                        recipe_obj = Recipe.from_dict(recipe)
                        
                        # Scale recipe
                        scaled_recipe = recipe_obj.scale_recipe(new_yield)
                        
                        # Display scaled recipe
                        st.subheader("Scaled Recipe")
                        st.markdown(f"**New Yield:** {scaled_recipe.yield_amount} {scaled_recipe.yield_unit}")
                        st.markdown(f"**New Cost:** ${scaled_recipe.total_cost:.2f}")
                        
                        ingredient_data = []
                        for ingredient in scaled_recipe.ingredients:
                            ingredient_data.append({
                                "Name": ingredient.get("name", ""),
                                "Amount": ingredient.get("amount", 0),
                                "Unit": ingredient.get("unit", ""),
                                "Cost": f"${ingredient.get('cost', 0):.2f}"
                            })
                        
                        if ingredient_data:
                            st.table(pd.DataFrame(ingredient_data))
    else:
        st.info("No recipes found. Add some recipes to get started!")

with tab2:
    st.subheader("Add New Recipe")
    
    # Recipe form
    recipe_name = st.text_input("Recipe Name", st.session_state.new_recipe_name)
    
    col1, col2 = st.columns(2)
    
    with col1:
        yield_amount = st.number_input("Yield Amount", min_value=1, value=st.session_state.new_recipe_yield_amount)
    
    with col2:
        yield_unit = st.text_input("Yield Unit", st.session_state.new_recipe_yield_unit)
    
    # Ingredients section
    st.subheader("Ingredients")
    
    # Display current ingredients
    if st.session_state.new_recipe_ingredients:
        ingredient_data = []
        for i, ingredient in enumerate(st.session_state.new_recipe_ingredients):
            ingredient_data.append({
                "Name": ingredient.get("name", ""),
                "Amount": ingredient.get("amount", 0),
                "Unit": ingredient.get("unit", ""),
                "Cost": ingredient.get("cost", 0)
            })
        
        st.table(pd.DataFrame(ingredient_data))
    
    # Add ingredient form
    with st.form("add_ingredient_form"):
        st.subheader("Add Ingredient")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            new_ingredient_name = st.text_input("Ingredient Name")
        
        with col2:
            new_ingredient_amount = st.number_input("Amount", min_value=0.0, step=0.1, value=1.0)
        
        with col3:
            new_ingredient_unit = st.selectbox(
                "Unit",
                ["g", "kg", "ml", "L", "tbsp", "tsp", "cup", "oz", "lb", "pcs", "each", "slice", "whole"]
            )
        
        # Try to find this ingredient in inventory for cost
        new_ingredient_cost = 0.0
        matched_ingredient = None
        
        for item in st.session_state.inventory:
            if item.get("name", "").lower() == new_ingredient_name.lower():
                matched_ingredient = item
                new_ingredient_cost = item.get("price", 0.0) * new_ingredient_amount
                break
        
        if matched_ingredient:
            st.success(f"Found {new_ingredient_name} in inventory at ${matched_ingredient.get('price', 0.0):.2f} per {matched_ingredient.get('unit', 'unit')}")
            st.info(f"Estimated cost: ${new_ingredient_cost:.2f}")
        
        add_ingredient = st.form_submit_button("Add Ingredient")
        
        if add_ingredient and new_ingredient_name:
            st.session_state.new_recipe_ingredients.append({
                "name": new_ingredient_name,
                "amount": new_ingredient_amount,
                "unit": new_ingredient_unit,
                "cost": new_ingredient_cost
            })
            st.rerun()
    
    # Preparation steps
    st.subheader("Preparation Steps")
    
    # Display current steps
    for i, step in enumerate(st.session_state.new_recipe_preparation_steps):
        st.text_area(f"Step {i+1}", step, key=f"step_{i}", disabled=True)
    
    # Add step form
    with st.form("add_step_form"):
        new_step = st.text_area("New Step")
        add_step = st.form_submit_button("Add Step")
        
        if add_step and new_step:
            st.session_state.new_recipe_preparation_steps.append(new_step)
            st.rerun()
    
    # Save recipe
    if st.button("Save Recipe"):
        if not recipe_name:
            st.error("Recipe name is required!")
        elif not st.session_state.new_recipe_ingredients:
            st.error("At least one ingredient is required!")
        else:
            # Create recipe dictionary
            recipe = {
                "name": recipe_name,
                "yield_amount": yield_amount,
                "yield_unit": yield_unit,
                "ingredients": st.session_state.new_recipe_ingredients,
                "preparation_steps": st.session_state.new_recipe_preparation_steps,
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat()
            }
            
            # Calculate recipe cost
            recipe_obj = Recipe.from_dict(recipe)
            recipe_obj.calculate_cost()
            recipe = recipe_obj.to_dict()
            
            # Add recipe to session state
            st.session_state.recipes.append(recipe)
            
            # Save recipes
            save_recipes()
            
            # Clear form
            clear_recipe_form()
            
            st.success("Recipe saved successfully!")
            st.rerun()
    
    if st.button("Clear Form"):
        clear_recipe_form()
        st.rerun()

with tab3:
    st.subheader("Import Recipes from Excel")
    
    # File uploader
    uploaded_file = st.file_uploader("Upload Excel file", type=["xlsx", "xls"])
    
    if uploaded_file:
        # Preview file
        try:
            df = pd.read_excel(uploaded_file)
            st.write("File Preview:")
            st.dataframe(df.head())
            
            # Map columns
            st.subheader("Map Columns")
            st.write("Map columns from your Excel file to our recipe fields:")
            
            # Get available columns
            columns = list(df.columns)
            none_option = "None"
            columns.insert(0, none_option)
            
            # Column mapping
            name_col = st.selectbox("Recipe Name column", columns, index=next((i for i, col in enumerate(columns) if "name" in str(col).lower()), 0))
            yield_amount_col = st.selectbox("Yield Amount column", columns, index=next((i for i, col in enumerate(columns) if "yield" in str(col).lower() or "amount" in str(col).lower()), 0))
            yield_unit_col = st.selectbox("Yield Unit column", columns, index=next((i for i, col in enumerate(columns) if "unit" in str(col).lower() or "portion" in str(col).lower() or "serving" in str(col).lower()), 0))
            ingredients_col = st.selectbox("Ingredients column", columns, index=next((i for i, col in enumerate(columns) if "ingredient" in str(col).lower()), 0))
            steps_col = st.selectbox("Preparation Steps column", columns, index=next((i for i, col in enumerate(columns) if "step" in str(col).lower() or "preparation" in str(col).lower() or "instruction" in str(col).lower() or "method" in str(col).lower()), 0))
            
            column_mapping = {}
            if name_col != none_option:
                column_mapping["name"] = name_col
            if yield_amount_col != none_option:
                column_mapping["yield_amount"] = yield_amount_col
            if yield_unit_col != none_option:
                column_mapping["yield_unit"] = yield_unit_col
            if ingredients_col != none_option:
                column_mapping["ingredients"] = ingredients_col
            if steps_col != none_option:
                column_mapping["preparation_steps"] = steps_col
            
            # Import button
            if st.button("Import Recipes"):
                with st.spinner("Processing..."):
                    # Process the file
                    result = process_excel_upload(uploaded_file, "recipe", column_mapping)
                    
                    if "error" in result:
                        st.error(f"Error processing file: {result['error']}")
                    elif "data" in result:
                        # Determine import mode
                        import_mode = st.radio(
                            "Import mode",
                            ["Add to existing recipes", "Replace all recipes"]
                        )
                        
                        if import_mode == "Add to existing recipes":
                            st.session_state.recipes.extend(result["data"])
                        else:
                            st.session_state.recipes = result["data"]
                        
                        # Calculate recipe costs
                        for i, recipe in enumerate(st.session_state.recipes):
                            # Create a Recipe object
                            recipe_obj = Recipe.from_dict(recipe)
                            # Calculate costs
                            recipe_obj.calculate_cost()
                            # Replace recipe with updated version
                            st.session_state.recipes[i] = recipe_obj.to_dict()
                        
                        # Save recipes
                        save_recipes()
                        
                        st.success(f"Successfully imported {len(result['data'])} recipes!")
                        st.rerun()
        except Exception as e:
            st.error(f"Error reading file: {str(e)}")
    else:
        st.info("Upload an Excel file containing recipe data")
    
    # Link to data extraction
    st.markdown("---")
    st.markdown("Need more advanced data extraction? Go to the [Data Extraction](/Data_Extraction) page.")