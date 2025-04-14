import streamlit as st
import pandas as pd
import numpy as np
import os
import json
import io
from datetime import datetime, timedelta
from utils.openai_utils import query_ai_assistant, analyze_price_changes, generate_natural_language_report
from utils.data_processing import load_data, save_data
from utils.forecasting import identify_sales_trends, prepare_time_series_data, forecast_ingredient_demand

# Set page configuration
st.set_page_config(
    page_title="Reports and Insights",
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

if 'sales' not in st.session_state:
    if os.path.exists('data/sales.json'):
        st.session_state.sales = load_data('data/sales.json')
    else:
        st.session_state.sales = []

# Create necessary directories if they don't exist
os.makedirs('data', exist_ok=True)

# Main page header
st.title("📝 Reports and Insights")
st.markdown("AI-powered analysis and reports to optimize your hotel's cost control")

# Create tabs for different report types
tab1, tab2, tab3, tab4 = st.tabs(["AI Chat Analysis", "Cost Insights", "Menu Optimization", "Custom Reports"])

with tab1:
    st.subheader("AI Chat Analysis")
    st.write("Ask questions about your data and get AI-powered insights")
    
    # AI chat interface
    user_question = st.text_area(
        "Ask a question about your recipes, inventory, or sales:",
        placeholder="Examples:\n- Which recipes have the highest profit margin?\n- What ingredients have increased in price the most?\n- How can I optimize my menu based on sales data?",
        height=100
    )
    
    if user_question:
        with st.spinner("Analyzing your data..."):
            # Prepare context data for the AI
            context = {
                "recipes_count": len(st.session_state.recipes),
                "inventory_count": len(st.session_state.inventory),
                "sales_count": len(st.session_state.sales),
                "top_recipes": sorted(st.session_state.recipes, key=lambda x: x.get('total_cost', 0), reverse=True)[:5] if st.session_state.recipes else [],
                "top_inventory": sorted(st.session_state.inventory, key=lambda x: x.get('price', 0) * x.get('stock_level', 0), reverse=True)[:5] if st.session_state.inventory else [],
                "recent_sales": sorted(st.session_state.sales, key=lambda x: x.get('date', ''), reverse=True)[:10] if st.session_state.sales else []
            }
            
            # Add sales analysis if available
            if st.session_state.sales:
                # Find top selling items
                sales_df = pd.DataFrame(st.session_state.sales)
                if not sales_df.empty and 'item_name' in sales_df.columns and 'quantity' in sales_df.columns:
                    top_sellers = sales_df.groupby('item_name')['quantity'].sum().sort_values(ascending=False).head(5)
                    context["top_selling_items"] = [{"name": k, "quantity": int(v)} for k, v in top_sellers.items()]
            
            # Query the AI
            response = query_ai_assistant(user_question, context)
            
            # Display the response
            st.markdown("### AI Response")
            st.markdown(response)
    
    # Recent questions
    st.subheader("Suggested Questions")
    
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("What are my most expensive recipes?"):
            with st.spinner("Analyzing your data..."):
                context = {
                    "recipes": sorted(st.session_state.recipes, key=lambda x: x.get('total_cost', 0), reverse=True)[:10] if st.session_state.recipes else []
                }
                response = query_ai_assistant("What are my most expensive recipes and how can I reduce their cost?", context)
                st.markdown("### AI Response")
                st.markdown(response)
    
    with col2:
        if st.button("Which menu items have the highest profit margin?"):
            with st.spinner("Analyzing your data..."):
                # Combine recipe and sales data for profit analysis
                context = {
                    "recipes": st.session_state.recipes,
                    "sales": st.session_state.sales[:100] if len(st.session_state.sales) > 100 else st.session_state.sales
                }
                response = query_ai_assistant("Which menu items have the highest profit margin based on my recipes and sales data?", context)
                st.markdown("### AI Response")
                st.markdown(response)
    
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("What ingredients should I order soon?"):
            with st.spinner("Analyzing your data..."):
                context = {
                    "inventory": st.session_state.inventory,
                    "sales": st.session_state.sales[-100:] if len(st.session_state.sales) > 100 else st.session_state.sales,
                    "recipes": st.session_state.recipes
                }
                response = query_ai_assistant("Based on my inventory levels and recent sales, what ingredients should I order soon?", context)
                st.markdown("### AI Response")
                st.markdown(response)
    
    with col2:
        if st.button("How can I optimize my menu?"):
            with st.spinner("Analyzing your data..."):
                context = {
                    "recipes": st.session_state.recipes,
                    "sales": st.session_state.sales,
                    "inventory": st.session_state.inventory
                }
                response = query_ai_assistant("How can I optimize my menu based on sales data, ingredient costs, and profit margins?", context)
                st.markdown("### AI Response")
                st.markdown(response)

with tab2:
    st.subheader("Cost Insights")
    st.write("Analyze cost trends and identify opportunities for optimization")
    
    # Cost distribution analysis
    if not st.session_state.recipes:
        st.info("No recipe data available. Please add recipes to see cost insights.")
    else:
        # Calculate cost metrics
        total_recipe_cost = sum(recipe.get('total_cost', 0) for recipe in st.session_state.recipes)
        avg_recipe_cost = total_recipe_cost / len(st.session_state.recipes) if st.session_state.recipes else 0
        
        # Recipes by cost category
        cost_categories = {
            'Low': 0,
            'Medium': 0,
            'High': 0
        }
        
        # Define thresholds (customize based on your business)
        low_threshold = avg_recipe_cost * 0.7
        high_threshold = avg_recipe_cost * 1.3
        
        for recipe in st.session_state.recipes:
            cost = recipe.get('total_cost', 0)
            if cost < low_threshold:
                cost_categories['Low'] += 1
            elif cost > high_threshold:
                cost_categories['High'] += 1
            else:
                cost_categories['Medium'] += 1
        
        # Display cost distribution
        st.write("### Recipe Cost Distribution")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric("Average Recipe Cost", f"${avg_recipe_cost:.2f}")
        
        with col2:
            highest_cost = max(recipe.get('total_cost', 0) for recipe in st.session_state.recipes) if st.session_state.recipes else 0
            st.metric("Highest Recipe Cost", f"${highest_cost:.2f}")
        
        with col3:
            lowest_cost = min(recipe.get('total_cost', 0) for recipe in st.session_state.recipes) if st.session_state.recipes else 0
            st.metric("Lowest Recipe Cost", f"${lowest_cost:.2f}")
        
        # Create chart for cost categories
        categories_df = pd.DataFrame({
            'Category': list(cost_categories.keys()),
            'Count': list(cost_categories.values())
        })
        
        st.bar_chart(categories_df.set_index('Category'))
        
        # Ingredient cost analysis
        st.write("### Key Cost Contributors")
        
        # Extract ingredient costs across all recipes
        ingredient_costs = {}
        
        for recipe in st.session_state.recipes:
            for ingredient in recipe.get('ingredients', []):
                name = ingredient.get('name', '')
                cost = ingredient.get('cost', 0)
                
                if name not in ingredient_costs:
                    ingredient_costs[name] = 0
                
                ingredient_costs[name] += cost
        
        # Sort ingredients by total cost
        sorted_ingredients = sorted(ingredient_costs.items(), key=lambda x: x[1], reverse=True)
        
        if sorted_ingredients:
            # Display top cost contributors
            top_ingredients = sorted_ingredients[:10]
            
            ing_df = pd.DataFrame({
                'Ingredient': [ing[0] for ing in top_ingredients],
                'Total Cost': [ing[1] for ing in top_ingredients]
            })
            
            st.bar_chart(ing_df.set_index('Ingredient'))
            
            # Recommendations for cost reduction
            st.write("### Cost Reduction Opportunities")
            
            # Find ingredients with price changes
            price_changes = []
            
            for ingredient_name, _ in top_ingredients:
                # Find this ingredient in inventory
                for item in st.session_state.inventory:
                    if item.get('name', '').lower() == ingredient_name.lower():
                        # Check if it has price history
                        price_history = item.get('price_history', [])
                        if price_history:
                            current_price = item.get('price', 0)
                            old_price = price_history[-1].get('price', 0)
                            
                            if old_price > 0:
                                change_pct = ((current_price - old_price) / old_price) * 100
                                
                                price_changes.append({
                                    'name': ingredient_name,
                                    'old_price': old_price,
                                    'current_price': current_price,
                                    'change_pct': change_pct
                                })
            
            if price_changes:
                # Sort by percentage change (largest increases first)
                price_changes.sort(key=lambda x: x['change_pct'], reverse=True)
                
                st.write("#### Ingredients with Recent Price Increases")
                
                changes_df = pd.DataFrame([{
                    'Ingredient': item['name'],
                    'Old Price': f"${item['old_price']:.2f}",
                    'Current Price': f"${item['current_price']:.2f}",
                    'Change': f"{item['change_pct']:+.1f}%"
                } for item in price_changes if item['change_pct'] > 0])
                
                if not changes_df.empty:
                    st.dataframe(changes_df, hide_index=True)
                    
                    st.write("Consider finding alternative suppliers or substitute ingredients for these items.")
                else:
                    st.success("Good news! None of your major ingredients have had recent price increases.")
            
            # Recipes most affected by price changes
            if st.session_state.inventory and price_changes:
                st.write("#### Recipes Affected by Price Changes")
                
                # Use AI to analyze impact
                with st.spinner("Analyzing price change impact..."):
                    price_impact = analyze_price_changes(
                        [item for item in st.session_state.inventory if item.get('price_history', [])],
                        st.session_state.inventory,
                        st.session_state.recipes
                    )
                
                if "error" not in price_impact:
                    # Display affected recipes
                    if price_impact.get('affected_recipes'):
                        affected_df = pd.DataFrame([{
                            'Recipe': recipe.get('name', ''),
                            'Impact': f"${recipe.get('total_impact', 0):.2f}",
                            'Percent': f"{recipe.get('impact_percentage', 0):+.1f}%"
                        } for recipe in price_impact.get('affected_recipes', [])])
                        
                        st.dataframe(affected_df, hide_index=True)
                        
                        # Display recommendations
                        if price_impact.get('recommendations'):
                            st.write("#### Recommendations")
                            for recommendation in price_impact.get('recommendations', []):
                                st.write(f"• {recommendation}")
                    else:
                        st.success("None of your recipes are significantly affected by recent price changes.")
                else:
                    st.error(f"Error analyzing price impacts: {price_impact.get('error')}")
            
            # Cost trend over time
            if 'sales' in st.session_state and st.session_state.sales:
                st.write("### Cost Trend Analysis")
                
                # Convert sales data to DataFrame
                sales_df = pd.DataFrame(st.session_state.sales)
                
                if not sales_df.empty and 'date' in sales_df.columns and 'cost' in sales_df.columns:
                    # Convert date to datetime
                    sales_df['date'] = pd.to_datetime(sales_df['date'])
                    
                    # Group by month and calculate average cost
                    sales_df['month'] = sales_df['date'].dt.to_period('M')
                    monthly_cost = sales_df.groupby('month')['cost'].mean().reset_index()
                    monthly_cost['month'] = monthly_cost['month'].astype(str)
                    
                    # Create line chart
                    st.line_chart(monthly_cost.set_index('month'))
                    
                    # Calculate trend
                    if len(monthly_cost) >= 2:
                        first_month = monthly_cost['cost'].iloc[0]
                        last_month = monthly_cost['cost'].iloc[-1]
                        
                        if first_month > 0:
                            trend_pct = ((last_month - first_month) / first_month) * 100
                            
                            if trend_pct > 5:
                                st.warning(f"⚠️ Your average cost has increased by {trend_pct:.1f}% over the analyzed period.")
                            elif trend_pct < -5:
                                st.success(f"✅ Your average cost has decreased by {abs(trend_pct):.1f}% over the analyzed period.")
                            else:
                                st.info(f"Your average cost has remained relatively stable ({trend_pct:+.1f}%) over the analyzed period.")
        else:
            st.info("No ingredient cost data available. Make sure your recipes have ingredients with cost information.")

with tab3:
    st.subheader("Menu Optimization")
    st.write("AI-powered recommendations to optimize your menu for profitability and popularity")
    
    if not st.session_state.recipes or not st.session_state.sales:
        st.info("Both recipe and sales data are required for menu optimization. Please add this data first.")
    else:
        # Menu analysis sections
        col1, col2 = st.columns(2)
        
        with col1:
            st.write("### Menu Performance Matrix")
            
            # Create menu performance matrix
            # We need to categorize items by profit and popularity
            
            # Convert sales data to DataFrame
            sales_df = pd.DataFrame(st.session_state.sales)
            
            if not sales_df.empty and 'item_name' in sales_df.columns and 'quantity' in sales_df.columns:
                # Calculate total quantity sold for each item
                item_quantity = sales_df.groupby('item_name')['quantity'].sum().reset_index()
                
                # Get average quantity to determine popularity threshold
                avg_quantity = item_quantity['quantity'].mean()
                
                # Create recipe lookup
                recipe_lookup = {recipe.get('name', ''): recipe for recipe in st.session_state.recipes}
                
                # Combine sales and recipe data
                menu_items = []
                
                for _, row in item_quantity.iterrows():
                    item_name = row['item_name']
                    quantity = row['quantity']
                    
                    # Find matching recipe
                    recipe = recipe_lookup.get(item_name)
                    
                    if recipe:
                        # Calculate profit if we have revenue data
                        profit = 0
                        profit_margin = 0
                        
                        # Find revenue from sales
                        item_revenue = sales_df[sales_df['item_name'] == item_name]['revenue'].sum()
                        item_cost = recipe.get('total_cost', 0) * quantity
                        
                        if item_revenue > 0:
                            profit = item_revenue - item_cost
                            profit_margin = (profit / item_revenue) * 100
                        
                        menu_items.append({
                            'name': item_name,
                            'quantity': quantity,
                            'revenue': item_revenue,
                            'cost': item_cost,
                            'profit': profit,
                            'profit_margin': profit_margin,
                            'is_popular': quantity > avg_quantity,
                            'is_profitable': profit_margin > 20  # Adjust threshold as needed
                        })
                
                if menu_items:
                    # Create menu matrix data
                    matrix_data = {
                        'Stars': [],  # High profit, high popularity
                        'Puzzles': [],  # High profit, low popularity
                        'Workhorses': [],  # Low profit, high popularity
                        'Dogs': []  # Low profit, low popularity
                    }
                    
                    for item in menu_items:
                        if item['is_profitable'] and item['is_popular']:
                            matrix_data['Stars'].append(item)
                        elif item['is_profitable'] and not item['is_popular']:
                            matrix_data['Puzzles'].append(item)
                        elif not item['is_profitable'] and item['is_popular']:
                            matrix_data['Workhorses'].append(item)
                        else:
                            matrix_data['Dogs'].append(item)
                    
                    # Create visualization
                    import plotly.express as px
                    import plotly.graph_objects as go
                    
                    # Create matrix data for scatter plot
                    scatter_data = pd.DataFrame([{
                        'Item': item['name'],
                        'Profit Margin': item['profit_margin'],
                        'Quantity Sold': item['quantity'],
                        'Revenue': item['revenue'],
                        'Category': 'Stars' if item['is_profitable'] and item['is_popular'] else
                                  'Puzzles' if item['is_profitable'] and not item['is_popular'] else
                                  'Workhorses' if not item['is_profitable'] and item['is_popular'] else 'Dogs'
                    } for item in menu_items])
                    
                    # Create scatter plot
                    fig = px.scatter(
                        scatter_data,
                        x='Profit Margin',
                        y='Quantity Sold',
                        text='Item',
                        size='Revenue',
                        color='Category',
                        color_discrete_map={
                            'Stars': '#1E88E5',
                            'Puzzles': '#FFC107',
                            'Workhorses': '#43A047',
                            'Dogs': '#E53935'
                        }
                    )
                    
                    fig.update_traces(
                        textposition='top center',
                        marker=dict(sizemode='area', sizeref=0.1)
                    )
                    
                    # Add quadrant lines
                    fig.add_shape(
                        type='line',
                        x0=20, y0=0,
                        x1=20, y1=scatter_data['Quantity Sold'].max(),
                        line=dict(color='gray', dash='dash')
                    )
                    
                    fig.add_shape(
                        type='line',
                        x0=0, y0=avg_quantity,
                        x1=scatter_data['Profit Margin'].max(), y1=avg_quantity,
                        line=dict(color='gray', dash='dash')
                    )
                    
                    # Update layout
                    fig.update_layout(
                        title='Menu Performance Matrix',
                        xaxis_title='Profit Margin (%)',
                        yaxis_title='Quantity Sold'
                    )
                    
                    st.plotly_chart(fig, use_container_width=True)
                    
                    # Display matrix data
                    st.write("### Menu Categories")
                    
                    matrix_tab1, matrix_tab2, matrix_tab3, matrix_tab4 = st.tabs(["Stars", "Puzzles", "Workhorses", "Dogs"])
                    
                    with matrix_tab1:
                        st.write("#### Stars (High Profit, High Popularity)")
                        st.write("These items are your best performers. Promote them prominently.")
                        
                        if matrix_data['Stars']:
                            stars_df = pd.DataFrame([{
                                'Item': item['name'],
                                'Quantity': item['quantity'],
                                'Profit Margin': f"{item['profit_margin']:.1f}%"
                            } for item in matrix_data['Stars']])
                            
                            st.dataframe(stars_df, hide_index=True)
                        else:
                            st.info("No items in this category.")
                    
                    with matrix_tab2:
                        st.write("#### Puzzles (High Profit, Low Popularity)")
                        st.write("These items are profitable but need promotion to increase sales.")
                        
                        if matrix_data['Puzzles']:
                            puzzles_df = pd.DataFrame([{
                                'Item': item['name'],
                                'Quantity': item['quantity'],
                                'Profit Margin': f"{item['profit_margin']:.1f}%"
                            } for item in matrix_data['Puzzles']])
                            
                            st.dataframe(puzzles_df, hide_index=True)
                        else:
                            st.info("No items in this category.")
                    
                    with matrix_tab3:
                        st.write("#### Workhorses (Low Profit, High Popularity)")
                        st.write("These items are popular but not very profitable. Look for ways to increase margins.")
                        
                        if matrix_data['Workhorses']:
                            workhorses_df = pd.DataFrame([{
                                'Item': item['name'],
                                'Quantity': item['quantity'],
                                'Profit Margin': f"{item['profit_margin']:.1f}%"
                            } for item in matrix_data['Workhorses']])
                            
                            st.dataframe(workhorses_df, hide_index=True)
                        else:
                            st.info("No items in this category.")
                    
                    with matrix_tab4:
                        st.write("#### Dogs (Low Profit, Low Popularity)")
                        st.write("Consider removing these items from your menu or revamping them.")
                        
                        if matrix_data['Dogs']:
                            dogs_df = pd.DataFrame([{
                                'Item': item['name'],
                                'Quantity': item['quantity'],
                                'Profit Margin': f"{item['profit_margin']:.1f}%"
                            } for item in matrix_data['Dogs']])
                            
                            st.dataframe(dogs_df, hide_index=True)
                        else:
                            st.info("No items in this category.")
                else:
                    st.info("Could not find matching recipes for your sales data. Make sure recipe names match sales items.")
            else:
                st.error("Sales data does not contain the required columns (item_name, quantity).")
        
        with col2:
            st.write("### Optimization Recommendations")
            
            # Generate AI recommendations based on sales and recipe data
            generate_button = st.button("Generate AI Recommendations")
            
            if generate_button:
                with st.spinner("Analyzing menu data and generating recommendations..."):
                    # Prepare data for AI
                    context = {
                        "recipes": st.session_state.recipes,
                        "sales": st.session_state.sales,
                        "inventory": st.session_state.inventory
                    }
                    
                    # Query AI for recommendations
                    prompt = """
                    Based on the provided menu data, generate specific recommendations for:
                    1. Items to promote more (with specific promotion strategies)
                    2. Items to consider removing or revamping
                    3. Price adjustment suggestions for specific items
                    4. New menu item ideas based on popular ingredients
                    
                    Format your response with clear headings and bullet points.
                    """
                    
                    recommendations = query_ai_assistant(prompt, context)
                    
                    st.markdown(recommendations)
        
        # Seasonal trends and recommendations
        st.write("### Seasonal Analysis")
        
        # Check if we have enough data with dates
        sales_df = pd.DataFrame(st.session_state.sales)
        
        if not sales_df.empty and 'date' in sales_df.columns:
            # Convert date to datetime
            sales_df['date'] = pd.to_datetime(sales_df['date'])
            
            # Add month and season columns
            sales_df['month'] = sales_df['date'].dt.month
            
            # Define seasons
            def get_season(month):
                if month in [12, 1, 2]:
                    return 'Winter'
                elif month in [3, 4, 5]:
                    return 'Spring'
                elif month in [6, 7, 8]:
                    return 'Summer'
                else:
                    return 'Fall'
            
            sales_df['season'] = sales_df['month'].apply(get_season)
            
            # Check if we have data spanning multiple seasons
            seasons_present = sales_df['season'].nunique()
            
            if seasons_present >= 2:
                # Analyze sales by season
                seasonal_sales = sales_df.groupby(['season', 'item_name'])['quantity'].sum().reset_index()
                
                # Get the top items for each season
                top_seasonal_items = {}
                
                for season in seasonal_sales['season'].unique():
                    season_items = seasonal_sales[seasonal_sales['season'] == season].sort_values('quantity', ascending=False).head(5)
                    top_seasonal_items[season] = season_items.to_dict('records')
                
                # Display seasonal top items
                season_tabs = st.tabs(list(top_seasonal_items.keys()))
                
                for i, season in enumerate(top_seasonal_items.keys()):
                    with season_tabs[i]:
                        st.write(f"#### Top Items in {season}")
                        
                        if top_seasonal_items[season]:
                            seasonal_df = pd.DataFrame([{
                                'Item': item['item_name'],
                                'Quantity Sold': item['quantity']
                            } for item in top_seasonal_items[season]])
                            
                            st.bar_chart(seasonal_df.set_index('Item'))
                        else:
                            st.info(f"No sales data for {season}.")
                
                # Generate seasonal recommendations
                st.write("#### Seasonal Menu Recommendations")
                
                if st.button("Generate Seasonal Recommendations"):
                    with st.spinner("Analyzing seasonal data..."):
                        # Convert seasonal data to format for AI
                        seasonal_context = {
                            "seasonal_data": {
                                season: [{"item": item["item_name"], "quantity": item["quantity"]} 
                                        for item in items]
                                for season, items in top_seasonal_items.items()
                            },
                            "recipes": st.session_state.recipes,
                            "inventory": st.session_state.inventory
                        }
                        
                        seasonal_prompt = """
                        Based on the seasonal sales data provided, please generate:
                        1. Recommendations for seasonal menu adjustments
                        2. Specific items to feature in each season
                        3. Suggestions for new seasonal items based on popular ingredients
                        4. Inventory planning recommendations for upcoming seasons
                        
                        Format your response with clear headings and bullet points for each season.
                        """
                        
                        seasonal_recommendations = query_ai_assistant(seasonal_prompt, seasonal_context)
                        
                        st.markdown(seasonal_recommendations)
            else:
                st.info("Not enough seasonal data available. Continue collecting sales data across multiple seasons for seasonal analysis.")
        else:
            st.info("Sales data doesn't contain date information required for seasonal analysis.")

with tab4:
    st.subheader("Custom Reports")
    st.write("Generate detailed custom reports with AI analysis")
    
    # Report type selection
    report_type = st.selectbox(
        "Select report type:",
        [
            "Recipe Cost Analysis",
            "Inventory Valuation",
            "Sales Performance",
            "Price Change Impact",
            "Ingredient Usage",
            "Menu Profitability"
        ]
    )
    
    # Date range selection
    col1, col2 = st.columns(2)
    
    with col1:
        start_date = st.date_input("Start date", datetime.now() - timedelta(days=30))
    
    with col2:
        end_date = st.date_input("End date", datetime.now())
    
    # Additional options
    st.write("### Report Options")
    
    include_charts = st.checkbox("Include charts and visualizations", value=True)
    include_recommendations = st.checkbox("Include AI recommendations", value=True)
    
    # Report filters
    if report_type == "Recipe Cost Analysis":
        recipe_filter = st.multiselect(
            "Filter by recipe (leave empty for all):",
            [recipe.get('name', f"Recipe {i}") for i, recipe in enumerate(st.session_state.recipes)]
        )
    
    elif report_type == "Inventory Valuation":
        category_filter = st.multiselect(
            "Filter by category (leave empty for all):",
            list(set(item.get('category', 'Uncategorized') for item in st.session_state.inventory))
        )
    
    elif report_type in ["Sales Performance", "Menu Profitability"]:
        min_quantity = st.number_input("Minimum quantity sold", min_value=1, value=1)
    
    # Generate report button
    if st.button("Generate Report"):
        with st.spinner(f"Generating {report_type} report..."):
            # Prepare data based on type and filters
            report_data = {}
            
            if report_type == "Recipe Cost Analysis":
                report_data["recipes"] = st.session_state.recipes
                if recipe_filter:
                    report_data["recipes"] = [r for r in st.session_state.recipes if r.get('name', '') in recipe_filter]
                report_data["inventory"] = st.session_state.inventory
            
            elif report_type == "Inventory Valuation":
                report_data["inventory"] = st.session_state.inventory
                if category_filter:
                    report_data["inventory"] = [i for i in st.session_state.inventory if i.get('category', 'Uncategorized') in category_filter]
            
            elif report_type == "Sales Performance":
                # Filter sales by date range
                sales_df = pd.DataFrame(st.session_state.sales)
                if not sales_df.empty and 'date' in sales_df.columns:
                    sales_df['date'] = pd.to_datetime(sales_df['date'])
                    filtered_sales = sales_df[
                        (sales_df['date'].dt.date >= start_date) & 
                        (sales_df['date'].dt.date <= end_date)
                    ]
                    report_data["sales"] = filtered_sales.to_dict('records')
                    
                    # Filter by minimum quantity
                    if min_quantity > 1:
                        sales_by_item = filtered_sales.groupby('item_name')['quantity'].sum().reset_index()
                        items_to_include = sales_by_item[sales_by_item['quantity'] >= min_quantity]['item_name'].tolist()
                        report_data["sales"] = [s for s in report_data["sales"] if s.get('item_name', '') in items_to_include]
                else:
                    report_data["sales"] = st.session_state.sales
            
            elif report_type == "Price Change Impact":
                report_data["previous_inventory"] = [item for item in st.session_state.inventory if item.get('price_history', [])]
                report_data["current_inventory"] = st.session_state.inventory
                report_data["recipes"] = st.session_state.recipes
            
            elif report_type == "Ingredient Usage":
                # Combine sales and recipe data
                report_data["sales"] = st.session_state.sales
                report_data["recipes"] = st.session_state.recipes
                report_data["inventory"] = st.session_state.inventory
            
            elif report_type == "Menu Profitability":
                # Filter sales by date range
                sales_df = pd.DataFrame(st.session_state.sales)
                if not sales_df.empty and 'date' in sales_df.columns:
                    sales_df['date'] = pd.to_datetime(sales_df['date'])
                    filtered_sales = sales_df[
                        (sales_df['date'].dt.date >= start_date) & 
                        (sales_df['date'].dt.date <= end_date)
                    ]
                    report_data["sales"] = filtered_sales.to_dict('records')
                else:
                    report_data["sales"] = st.session_state.sales
                
                report_data["recipes"] = st.session_state.recipes
            
            # Add report options
            report_data["include_charts"] = include_charts
            report_data["include_recommendations"] = include_recommendations
            report_data["start_date"] = start_date.isoformat()
            report_data["end_date"] = end_date.isoformat()
            
            # Generate the report using AI
            report_content = generate_natural_language_report(report_data, report_type)
            
            # Display the report
            st.markdown("## Generated Report")
            st.markdown("---")
            st.markdown(report_content)
            st.markdown("---")
            
            # Download options
            report_text = f"# {report_type} Report\n\n" + report_content
            
            st.download_button(
                label="Download Report as Text",
                data=report_text,
                file_name=f"{report_type.lower().replace(' ', '_')}_{datetime.now().strftime('%Y%m%d')}.md",
                mime="text/markdown"
            )

    # Scheduled reports section
    st.subheader("Scheduled Reports")
    st.write("Set up regular automated reports (coming soon)")
    
    # This would be linked to a backend scheduling system in a production app
    st.info("Scheduled reports feature is coming soon. You'll be able to set up weekly or monthly reports that are automatically generated and emailed to you.")
