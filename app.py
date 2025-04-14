import streamlit as st
import pandas as pd
import numpy as np
import os
import json
from datetime import datetime

# Set page configuration
st.set_page_config(
    page_title="Hotel Cost Control System",
    page_icon="🏨",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Create necessary directories if they don't exist
os.makedirs('data', exist_ok=True)
os.makedirs('data/uploaded', exist_ok=True)

# Main page header
st.title("🏨 Hotel Cost Control System")
st.markdown("""
Welcome to the AI-powered hotel cost control system. This application helps you manage recipes, 
track inventory, analyze sales, forecast demand, and generate insightful reports.

Use the sidebar navigation to access different features of the system.
""")

# Display system overview metrics
st.subheader("System Overview")

col1, col2, col3 = st.columns(3)

# Try to load data from files
try:
    if os.path.exists('data/recipes.json'):
        with open('data/recipes.json', 'r') as f:
            recipes = json.load(f)
    else:
        recipes = []
except:
    recipes = []

try:
    if os.path.exists('data/inventory.json'):
        with open('data/inventory.json', 'r') as f:
            inventory = json.load(f)
    else:
        inventory = []
except:
    inventory = []

try:
    if os.path.exists('data/sales.json'):
        with open('data/sales.json', 'r') as f:
            sales = json.load(f)
    else:
        sales = []
except:
    sales = []

# Display metrics
with col1:
    st.metric("Recipes", len(recipes))
    
with col2:
    st.metric("Inventory Items", len(inventory))
    
with col3:
    st.metric("Sales Records", len(sales))

# Recent activity
st.subheader("Recent Activity")

# Combine recent activity from all data sources
activity = []

# Add recent recipes
for recipe in recipes[-5:]:
    activity.append({
        "type": "Recipe",
        "name": recipe.get("name", "Unnamed Recipe"),
        "date": recipe.get("updated_at", ""),
        "details": f"Cost: ${recipe.get('total_cost', 0):.2f}, Yield: {recipe.get('yield_amount', 0)} {recipe.get('yield_unit', 'serving')}"
    })

# Add recent inventory updates
for item in inventory[-5:]:
    activity.append({
        "type": "Inventory",
        "name": item.get("name", "Unnamed Item"),
        "date": item.get("updated_at", ""),
        "details": f"Price: ${item.get('price', 0):.2f}, Stock: {item.get('stock_level', 0)} {item.get('unit', '')}"
    })

# Add recent sales records
for record in sales[-5:]:
    activity.append({
        "type": "Sales",
        "name": record.get("item_name", "Unnamed Item"),
        "date": record.get("date", ""),
        "details": f"Quantity: {record.get('quantity', 0)}, Revenue: ${record.get('revenue', 0):.2f}, Profit: ${record.get('profit', 0):.2f}"
    })

# Sort by date (assuming ISO format)
try:
    activity.sort(key=lambda x: x["date"], reverse=True)
except:
    pass

# Display recent activity
if activity:
    activity_df = pd.DataFrame(activity[:10])  # Show top 10 most recent
    st.dataframe(activity_df)
else:
    st.info("No recent activity to display. Start by adding recipes, inventory items, or sales records.")

# Quick actions section
st.subheader("Quick Actions")

col1, col2, col3 = st.columns(3)

with col1:
    st.markdown("### Add Recipe")
    st.markdown("Go to the Recipe Management page to create a new recipe or import from Excel")
    if st.button("Go to Recipes"):
        st.switch_page("pages/01_Recipe_Management.py")

with col2:
    st.markdown("### Update Inventory")
    st.markdown("Go to the Inventory Management page to update stock or import data")
    if st.button("Go to Inventory"):
        st.switch_page("pages/02_Inventory_Management.py")

with col3:
    st.markdown("### Import Data")
    st.markdown("Go to the Data Extraction page to extract and clean data from Excel files")
    if st.button("Go to Data Extraction"):
        st.switch_page("pages/05_Data_Extraction.py")

# Help section
st.subheader("Help & Tips")

with st.expander("Getting Started"):
    st.markdown("""
    ### Getting Started with the Hotel Cost Control System
    
    1. **Add your recipes** - Create recipes manually or import from Excel files
    2. **Set up your inventory** - Add ingredients and stock levels
    3. **Record sales** - Track sales data by item
    4. **Generate reports** - Analyze costs and sales performance
    
    Use the AI-powered features to get insights from your data and forecast future needs.
    """)

with st.expander("AI Features"):
    st.markdown("""
    ### AI-Powered Features
    
    The system includes several AI capabilities:
    
    - **Automatic data extraction** from Excel and Word files
    - **Column mapping** to match your data to the system
    - **Natural language reporting** to generate insights
    - **Price change analysis** to understand cost impacts
    - **Demand forecasting** to optimize inventory
    
    These features use OpenAI's advanced models to save you time and provide deeper insights.
    """)

# Footer
st.markdown("---")
st.markdown("© 2025 Hotel Cost Control System | Powered by AI")