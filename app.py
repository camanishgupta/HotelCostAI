import streamlit as st
import pandas as pd
import os
import json
from datetime import datetime
from utils.openai_utils import query_ai_assistant
from utils.data_processing import load_data, save_data

# Set page configuration
st.set_page_config(
    page_title="Hotel Cost Control System",
    page_icon="🏨",
    layout="wide",
    initial_sidebar_state="expanded"
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

if 'column_mappings' not in st.session_state:
    if os.path.exists('data/column_mappings.json'):
        st.session_state.column_mappings = load_data('data/column_mappings.json')
    else:
        st.session_state.column_mappings = {}

# Create necessary directories if they don't exist
os.makedirs('data', exist_ok=True)

# Main page header
st.title("🏨 Hotel Cost Control System")
st.markdown("### AI-powered cost management for hotels and restaurants")

# Dashboard overview
col1, col2, col3 = st.columns(3)

with col1:
    st.metric(
        "Total Recipes", 
        len(st.session_state.recipes), 
        help="Total number of recipes in the system"
    )

with col2:
    st.metric(
        "Inventory Items", 
        len(st.session_state.inventory), 
        help="Number of items in inventory"
    )

with col3:
    # Calculate average cost if recipes exist
    if st.session_state.recipes:
        avg_cost = sum(recipe.get('total_cost', 0) for recipe in st.session_state.recipes) / len(st.session_state.recipes)
        st.metric("Avg Recipe Cost", f"${avg_cost:.2f}")
    else:
        st.metric("Avg Recipe Cost", "$0.00")

# Features overview
st.markdown("## Key Features")

feature_col1, feature_col2 = st.columns(2)

with feature_col1:
    st.markdown("### Recipe Management")
    st.markdown("- Interactive recipe creation with cost calculation")
    st.markdown("- AI extraction from Excel and Word documents")
    st.markdown("- Price change impact analysis")
    
    st.markdown("### Inventory Control")
    st.markdown("- Stock item tracking and management")
    st.markdown("- Ingredient consumption monitoring")
    st.markdown("- Price change alerts")

with feature_col2:
    st.markdown("### Sales Analysis")
    st.markdown("- Popular items tracking")
    st.markdown("- Menu performance insights")
    st.markdown("- Ingredient usage patterns")
    
    st.markdown("### AI-Powered Insights")
    st.markdown("- Demand forecasting for ingredients")
    st.markdown("- Natural language reporting")
    st.markdown("- Menu optimization recommendations")

# Quick access section
st.markdown("## Quick Access")
quick_action = st.selectbox(
    "I want to...",
    [
        "Select an action",
        "Create a new recipe",
        "Upload inventory data",
        "Upload sales data",
        "Get AI insights about my business",
        "Check price change impacts"
    ]
)

if quick_action == "Create a new recipe":
    st.switch_page("pages/01_Recipe_Management.py")
elif quick_action == "Upload inventory data":
    st.switch_page("pages/02_Inventory_Management.py")
elif quick_action == "Upload sales data":
    st.switch_page("pages/03_Sales_Analysis.py")
elif quick_action == "Get AI insights about my business" or quick_action == "Check price change impacts":
    st.switch_page("pages/04_Reports_and_Insights.py")

# Recent activity section
st.markdown("## Recent Activity")

# Get most recent data from each category
recent_items = []

# Add recent recipes
for recipe in st.session_state.recipes[-3:]:
    recent_items.append({
        "type": "Recipe",
        "name": recipe.get('name', 'Unnamed Recipe'),
        "date": recipe.get('created_at', 'Unknown date'),
        "details": f"Cost: ${recipe.get('total_cost', 0):.2f}"
    })

# Add recent inventory updates
for item in st.session_state.inventory[-3:]:
    recent_items.append({
        "type": "Inventory",
        "name": item.get('name', 'Unnamed Item'),
        "date": item.get('updated_at', 'Unknown date'),
        "details": f"Price: ${item.get('price', 0):.2f} per {item.get('unit', 'unit')}"
    })

# Sort by date (newest first) and take top 5
if recent_items:
    recent_df = pd.DataFrame(recent_items)
    try:
        recent_df['date'] = pd.to_datetime(recent_df['date'])
        recent_df = recent_df.sort_values('date', ascending=False).head(5)
    except:
        # If date parsing fails, just show the items as they are
        recent_df = recent_df.head(5)
    
    st.dataframe(recent_df, hide_index=True)
else:
    st.info("No recent activity found. Start by creating recipes or uploading inventory data.")

# AI chat assistant
st.markdown("## AI Assistant")
user_question = st.text_input("Ask anything about your hotel's cost management:", placeholder="E.g., 'What are my most expensive recipes?'")

if user_question:
    with st.spinner("Getting AI insights..."):
        # Prepare context from our data
        context = {
            "recipes_count": len(st.session_state.recipes),
            "inventory_count": len(st.session_state.inventory),
            "sales_count": len(st.session_state.sales),
            "recipes_sample": st.session_state.recipes[:5] if st.session_state.recipes else [],
            "inventory_sample": st.session_state.inventory[:5] if st.session_state.inventory else [],
            "sales_sample": st.session_state.sales[:5] if st.session_state.sales else []
        }
        
        response = query_ai_assistant(user_question, context)
        st.markdown(f"**Answer:**\n{response}")

# Footer
st.markdown("---")
st.markdown("© 2023 Hotel Cost Control System | Powered by AI")
