import streamlit as st
import pandas as pd
import numpy as np
import os
import json
import io
from datetime import datetime
from utils.openai_utils import extract_recipe_from_document
from utils.data_processing import calculate_recipe_cost, load_data, save_data
from models.recipe import Recipe

# Set page configuration
st.set_page_config(
    page_title="Recipe Management",
    page_icon="🍳",
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

if 'edit_recipe_index' not in st.session_state:
    st.session_state.edit_recipe_index = -1

if 'new_recipe' not in st.session_state:
    st.session_state.new_recipe = Recipe().to_dict()

# Create necessary directories if they don't exist
os.makedirs('data', exist_ok=True)

# Helper function to save recipes
def save_recipes():
    save_data(st.session_state.recipes, 'data/recipes.json')

# Helper function to clear recipe form
def clear_recipe_form():
    st.session_state.new_recipe = Recipe().to_dict()
    st.session_state.edit_recipe_index = -1

# Main page header
st.title("🍳 Recipe Management")
st.markdown("Create, edit, and manage your recipes with cost calculations")

# Create tabs for different recipe management functions
tab1, tab2, tab3, tab4 = st.tabs(["Recipe List", "Create & Edit", "Import Recipes", "Cost Analysis"])

with tab1:
    st.subheader("Recipe Library")
    
    # Search and filter
    search_term = st.text_input("Search recipes", key="recipe_search")
    
    filtered_recipes = st.session_state.recipes
    if search_term:
        filtered_recipes = [
            recipe for recipe in st.session_state.recipes 
            if search_term.lower() in recipe.get('name', '').lower()
        ]
    
    if not filtered_recipes:
        st.info("No recipes found. Create a new recipe or import from documents.")
    else:
        # Display recipes in a grid
        cols = st.columns(3)
        for i, recipe in enumerate(filtered_recipes):
            with cols[i % 3]:
                with st.container(border=True):
                    st.subheader(recipe.get('name', 'Unnamed Recipe'))
                    st.write(f"Yield: {recipe.get('yield_amount', 1)} {recipe.get('yield_unit', 'serving')}")
                    st.write(f"Total Cost: ${recipe.get('total_cost', 0):.2f}")
                    st.write(f"Cost per {recipe.get('yield_unit', 'serving')}: ${recipe.get('cost_per_unit', 0):.2f}")
                    
                    # Show ingredient count 
                    ingredients = recipe.get('ingredients', [])
                    st.write(f"Ingredients: {len(ingredients)}")
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        if st.button("Edit", key=f"edit_{i}"):
                            st.session_state.edit_recipe_index = i
                            st.session_state.new_recipe = recipe.copy()
                            st.switch_page("pages/01_Recipe_Management.py")
                    with col2:
                        if st.button("Delete", key=f"delete_{i}"):
                            st.session_state.recipes.pop(i)
                            save_recipes()
                            st.rerun()

with tab2:
    st.subheader("Recipe Creator")
    
    # Recipe form
    form_col1, form_col2 = st.columns([3, 2])
    
    with form_col1:
        recipe_name = st.text_input("Recipe Name", st.session_state.new_recipe.get('name', ''))
        
        # Yield information
        yield_col1, yield_col2 = st.columns(2)
        with yield_col1:
            yield_amount = st.number_input("Yield Amount", min_value=1, value=st.session_state.new_recipe.get('yield_amount', 1), step=1)
        with yield_col2:
            yield_unit = st.text_input("Yield Unit", st.session_state.new_recipe.get('yield_unit', 'serving'))
        
        # Show a dataframe for entering ingredients
        st.subheader("Ingredients")
        
        # Use inventory items as a reference for units and costs
        inventory_items = [item.get('name', '') for item in st.session_state.inventory]
        
        # Check if ingredients exist in new_recipe
        if 'ingredients' not in st.session_state.new_recipe:
            st.session_state.new_recipe['ingredients'] = []
        
        # Create a DataFrame for editing ingredients
        if st.session_state.new_recipe['ingredients']:
            ingredient_data = pd.DataFrame(st.session_state.new_recipe['ingredients'])
        else:
            ingredient_data = pd.DataFrame(columns=['name', 'amount', 'unit', 'cost'])
        
        # Create an editable dataframe
        edited_ingredients = st.data_editor(
            ingredient_data,
            key="ingredient_editor",
            num_rows="dynamic",
            column_config={
                'name': st.column_config.SelectboxColumn(
                    'Ingredient Name',
                    options=inventory_items,
                    required=True,
                ),
                'amount': st.column_config.NumberColumn(
                    'Amount',
                    min_value=0.01,
                    format="%.2f",
                    required=True,
                ),
                'unit': st.column_config.TextColumn(
                    'Unit',
                    default="g",
                    required=True,
                ),
                'cost': st.column_config.NumberColumn(
                    'Cost ($)',
                    min_value=0.0,
                    format="%.2f",
                )
            },
            hide_index=True
        )
        
        # Update the ingredients in the new_recipe
        st.session_state.new_recipe['ingredients'] = edited_ingredients.to_dict('records')
        
        # Preparation steps
        st.subheader("Preparation Steps")
        prep_steps = st.text_area(
            "Enter preparation steps (one per line)",
            value="\n".join(st.session_state.new_recipe.get('preparation_steps', [])),
            height=150
        )
        
        # Convert the preparation steps text to a list
        st.session_state.new_recipe['preparation_steps'] = [
            step.strip() for step in prep_steps.split('\n') if step.strip()
        ]
    
    with form_col2:
        st.subheader("Cost Calculation")
        
        # Calculate costs if there are ingredients
        if st.session_state.new_recipe['ingredients']:
            # Calculate cost using inventory data
            total_cost = calculate_recipe_cost(st.session_state.new_recipe, st.session_state.inventory)
            
            # Update the recipe with the calculated cost
            st.session_state.new_recipe['total_cost'] = total_cost
            
            if yield_amount > 0:
                st.session_state.new_recipe['cost_per_unit'] = total_cost / yield_amount
            else:
                st.session_state.new_recipe['cost_per_unit'] = 0
            
            # Display cost information
            st.metric("Total Recipe Cost", f"${total_cost:.2f}")
            st.metric(f"Cost per {yield_unit}", f"${st.session_state.new_recipe['cost_per_unit']:.2f}")
            
            # Display missing ingredients warning
            missing_ingredients = [
                ing['name'] for ing in st.session_state.new_recipe['ingredients'] 
                if ing.get('missing', False)
            ]
            
            if missing_ingredients:
                st.warning(f"⚠️ Missing from inventory: {', '.join(missing_ingredients)}")
                st.write("Add these items to your inventory for accurate cost calculation.")
        else:
            st.info("Add ingredients to calculate recipe cost.")
        
        # Display recipe scaling tool
        st.subheader("Recipe Scaling")
        new_yield = st.number_input(
            f"Scale recipe to (in {yield_unit})",
            min_value=1,
            value=yield_amount,
            step=1
        )
        
        if new_yield != yield_amount:
            scale_factor = new_yield / yield_amount
            st.write(f"Scale factor: {scale_factor:.2f}x")
            
            if 'total_cost' in st.session_state.new_recipe:
                new_cost = st.session_state.new_recipe['total_cost'] * scale_factor
                st.write(f"New total cost: ${new_cost:.2f}")
    
    # Save/update button
    col1, col2 = st.columns([1, 1])
    with col1:
        if st.button("Clear Form"):
            clear_recipe_form()
            st.rerun()
    
    with col2:
        # Update recipe name and yield from form
        st.session_state.new_recipe['name'] = recipe_name
        st.session_state.new_recipe['yield_amount'] = yield_amount
        st.session_state.new_recipe['yield_unit'] = yield_unit
        
        # Add timestamp
        st.session_state.new_recipe['updated_at'] = datetime.now().isoformat()
        
        if st.button("Save Recipe"):
            if not recipe_name:
                st.error("Recipe name is required!")
            elif not st.session_state.new_recipe['ingredients']:
                st.error("At least one ingredient is required!")
            else:
                if st.session_state.edit_recipe_index >= 0:
                    # Update existing recipe
                    st.session_state.recipes[st.session_state.edit_recipe_index] = st.session_state.new_recipe
                    st.success(f"Recipe '{recipe_name}' updated!")
                else:
                    # Add created_at timestamp for new recipes
                    st.session_state.new_recipe['created_at'] = datetime.now().isoformat()
                    
                    # Add new recipe
                    st.session_state.recipes.append(st.session_state.new_recipe)
                    st.success(f"Recipe '{recipe_name}' created!")
                
                # Save recipes to file
                save_recipes()
                
                # Clear the form for a new recipe
                clear_recipe_form()
                st.rerun()

with tab3:
    st.subheader("Import Recipes")
    st.write("Upload recipe documents to automatically extract recipe information using AI")
    
    # File uploader
    uploaded_file = st.file_uploader("Upload recipe document", type=['xlsx', 'docx', 'txt'])
    
    if uploaded_file:
        # Determine file type
        file_type = None
        if uploaded_file.name.endswith('.xlsx'):
            file_type = 'excel'
        elif uploaded_file.name.endswith('.docx'):
            file_type = 'word'
        elif uploaded_file.name.endswith('.txt'):
            file_type = 'text'
        
        # Show extraction button
        if st.button("Extract Recipe"):
            with st.spinner("Extracting recipe using AI..."):
                # Read file data
                file_data = uploaded_file.read()
                
                # Extract recipe using AI
                extracted_recipe = extract_recipe_from_document(file_data, file_type)
                
                if "error" in extracted_recipe:
                    st.error(f"Failed to extract recipe: {extracted_recipe['error']}")
                else:
                    # Display extracted recipe
                    st.success("Recipe extracted successfully!")
                    
                    with st.expander("Review Extracted Recipe", expanded=True):
                        st.subheader(extracted_recipe.get('name', 'Unnamed Recipe'))
                        
                        yield_amount = extracted_recipe.get('yield_amount', 1)
                        yield_unit = extracted_recipe.get('yield_unit', 'serving')
                        st.write(f"Yield: {yield_amount} {yield_unit}")
                        
                        st.subheader("Ingredients")
                        ingredients = extracted_recipe.get('ingredients', [])
                        if ingredients:
                            ingredients_df = pd.DataFrame(ingredients)
                            st.dataframe(ingredients_df)
                        else:
                            st.info("No ingredients extracted.")
                        
                        st.subheader("Preparation")
                        prep_steps = extracted_recipe.get('preparation_steps', [])
                        if prep_steps:
                            for i, step in enumerate(prep_steps, 1):
                                st.write(f"{i}. {step}")
                        else:
                            st.info("No preparation steps extracted.")
                    
                    # Calculate cost using inventory data
                    total_cost = calculate_recipe_cost(extracted_recipe, st.session_state.inventory)
                    extracted_recipe['total_cost'] = total_cost
                    
                    if yield_amount > 0:
                        extracted_recipe['cost_per_unit'] = total_cost / yield_amount
                    else:
                        extracted_recipe['cost_per_unit'] = 0
                    
                    st.metric("Calculated Total Cost", f"${total_cost:.2f}")
                    
                    # Option to save or edit
                    col1, col2 = st.columns(2)
                    with col1:
                        if st.button("Save Recipe As Is"):
                            st.session_state.recipes.append(extracted_recipe)
                            save_recipes()
                            st.success(f"Recipe '{extracted_recipe.get('name', 'Unnamed Recipe')}' saved!")
                            st.rerun()
                    
                    with col2:
                        if st.button("Edit Before Saving"):
                            st.session_state.new_recipe = extracted_recipe
                            st.session_state.edit_recipe_index = -1  # New recipe
                            st.switch_page("pages/01_Recipe_Management.py")
        
        # Batch import section
        st.subheader("Batch Import")
        st.write("For Excel files containing multiple recipes, you can import them all at once.")
        
        if uploaded_file.name.endswith('.xlsx') and st.button("Batch Import Recipes"):
            with st.spinner("Processing batch import..."):
                # Read Excel file
                df = pd.read_excel(uploaded_file)
                
                # Sample data to determine structure
                sample_data = df.head(5).to_dict()
                
                # Display preview
                st.write("Preview of imported data:")
                st.dataframe(df.head())
                
                # Ask user to confirm import
                if st.button("Confirm Batch Import"):
                    # Process each row as a separate recipe
                    # This is a simplified implementation - real batch import would use
                    # more sophisticated AI mapping and extraction
                    imported_count = 0
                    
                    for _, row in df.iterrows():
                        # Create a basic recipe from each row
                        # This is just a placeholder implementation
                        recipe = {
                            "name": row.iloc[0] if not pd.isna(row.iloc[0]) else f"Imported Recipe {imported_count+1}",
                            "ingredients": [],
                            "yield_amount": 1,
                            "yield_unit": "serving",
                            "preparation_steps": [],
                            "total_cost": 0,
                            "cost_per_unit": 0,
                            "created_at": datetime.now().isoformat(),
                            "updated_at": datetime.now().isoformat()
                        }
                        
                        st.session_state.recipes.append(recipe)
                        imported_count += 1
                    
                    if imported_count > 0:
                        save_recipes()
                        st.success(f"Imported {imported_count} recipes!")
                        st.rerun()

with tab4:
    st.subheader("Recipe Cost Analysis")
    
    if not st.session_state.recipes:
        st.info("No recipes found. Create recipes to analyze costs.")
    else:
        # Prepare data for charts
        recipe_names = [recipe.get('name', f"Recipe {i}") for i, recipe in enumerate(st.session_state.recipes)]
        recipe_costs = [recipe.get('total_cost', 0) for recipe in st.session_state.recipes]
        cost_per_unit = [recipe.get('cost_per_unit', 0) for recipe in st.session_state.recipes]
        
        # Combine data for sorting
        cost_data = list(zip(recipe_names, recipe_costs, cost_per_unit))
        
        # Sort options
        sort_option = st.radio(
            "Sort recipes by:",
            ["Total Cost (High to Low)", "Total Cost (Low to High)", "Cost per Unit (High to Low)", "Cost per Unit (Low to High)"]
        )
        
        if sort_option == "Total Cost (High to Low)":
            cost_data.sort(key=lambda x: x[1], reverse=True)
        elif sort_option == "Total Cost (Low to High)":
            cost_data.sort(key=lambda x: x[1])
        elif sort_option == "Cost per Unit (High to Low)":
            cost_data.sort(key=lambda x: x[2], reverse=True)
        else:  # "Cost per Unit (Low to High)"
            cost_data.sort(key=lambda x: x[2])
        
        # Unpack sorted data
        recipe_names, recipe_costs, cost_per_unit = zip(*cost_data)
        
        # Limit to top 10 for better visualization
        recipe_names = recipe_names[:10]
        recipe_costs = recipe_costs[:10]
        cost_per_unit = cost_per_unit[:10]
        
        # Create a DataFrame for the chart
        chart_data = pd.DataFrame({
            "Recipe": recipe_names,
            "Total Cost": recipe_costs,
            "Cost per Unit": cost_per_unit
        })
        
        # Display bar chart
        st.subheader("Recipe Cost Comparison")
        
        # Use Plotly for better interactivity
        import plotly.express as px
        
        fig = px.bar(
            chart_data,
            x="Recipe",
            y="Total Cost",
            hover_data=["Cost per Unit"],
            color="Total Cost",
            labels={"Total Cost": "Total Recipe Cost ($)"},
            height=400
        )
        
        st.plotly_chart(fig, use_container_width=True)
        
        # Cost breakdown for a selected recipe
        st.subheader("Recipe Cost Breakdown")
        
        selected_recipe = st.selectbox(
            "Select a recipe to analyze:",
            [recipe.get('name', f"Recipe {i}") for i, recipe in enumerate(st.session_state.recipes)]
        )
        
        # Find the selected recipe
        selected_recipe_data = None
        for recipe in st.session_state.recipes:
            if recipe.get('name') == selected_recipe:
                selected_recipe_data = recipe
                break
        
        if selected_recipe_data:
            # Get ingredients with costs
            ingredients = selected_recipe_data.get('ingredients', [])
            
            if ingredients:
                # Create data for pie chart
                ingredient_names = [ing.get('name', f"Ingredient {i}") for i, ing in enumerate(ingredients)]
                ingredient_costs = [ing.get('cost', 0) for ing in ingredients]
                
                # Create pie chart for cost breakdown
                breakdown_data = pd.DataFrame({
                    "Ingredient": ingredient_names,
                    "Cost": ingredient_costs
                })
                
                fig2 = px.pie(
                    breakdown_data,
                    values="Cost",
                    names="Ingredient",
                    title=f"Cost Breakdown for {selected_recipe}",
                    hover_data=["Cost"],
                    labels={"Cost": "Cost ($)"}
                )
                
                st.plotly_chart(fig2, use_container_width=True)
                
                # Display ingredient cost table
                st.subheader("Ingredient Costs")
                
                breakdown_table = pd.DataFrame({
                    "Ingredient": ingredient_names,
                    "Amount": [f"{ing.get('amount')} {ing.get('unit')}" for ing in ingredients],
                    "Cost": [f"${ing.get('cost', 0):.2f}" for ing in ingredients],
                    "% of Total": [(ing.get('cost', 0) / selected_recipe_data.get('total_cost', 1)) * 100 for ing in ingredients]
                })
                
                st.dataframe(breakdown_table, hide_index=True)
                
                # Alert for missing cost data
                missing_costs = any(ing.get('cost', 0) == 0 for ing in ingredients)
                if missing_costs:
                    st.warning("⚠️ Some ingredients are missing cost data. Add them to your inventory for accurate cost calculations.")
            else:
                st.info("This recipe has no ingredients to analyze.")
        else:
            st.error("Recipe not found!")
