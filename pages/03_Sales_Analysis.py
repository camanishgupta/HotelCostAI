import streamlit as st
import pandas as pd
import numpy as np
import os
import json
import io
from datetime import datetime, timedelta
from utils.data_processing import process_excel_upload, generate_column_mapping_ui, load_data, save_data
from utils.forecasting import identify_sales_trends, prepare_time_series_data, forecast_ingredient_demand
from models.sales import analyze_sales, calculate_ingredient_consumption, SalesRecord

# Set page configuration
st.set_page_config(
    page_title="Sales Analysis",
    page_icon="📊",
    layout="wide"
)

# Initialize session state variables if they don't exist
if 'sales' not in st.session_state:
    if os.path.exists('data/sales.json'):
        st.session_state.sales = load_data('data/sales.json')
    else:
        st.session_state.sales = []

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

if 'column_mappings' not in st.session_state:
    if os.path.exists('data/column_mappings.json'):
        st.session_state.column_mappings = load_data('data/column_mappings.json')
    else:
        st.session_state.column_mappings = {}

# Create necessary directories if they don't exist
os.makedirs('data', exist_ok=True)

# Helper function to save sales data
def save_sales():
    save_data(st.session_state.sales, 'data/sales.json')

# Helper function to save column mappings
def save_column_mappings():
    save_data(st.session_state.column_mappings, 'data/column_mappings.json')

# Main page header
st.title("📊 Sales Analysis")
st.markdown("Analyze sales data, track popular items, and forecast future demand")

# Create tabs for different sales analysis functions
tab1, tab2, tab3, tab4 = st.tabs(["Sales Dashboard", "Import Sales Data", "Consumption Analysis", "Demand Forecasting"])

with tab1:
    st.subheader("Sales Overview")
    
    # Period selection for analysis
    analysis_period = st.selectbox(
        "Analysis period:",
        ["Last 7 days", "Last 30 days", "Last 90 days", "Year to date", "All time"]
    )
    
    # Map selection to days for analysis
    period_days = {
        "Last 7 days": 7,
        "Last 30 days": 30,
        "Last 90 days": 90,
        "Year to date": (datetime.now() - datetime(datetime.now().year, 1, 1)).days,
        "All time": 10000  # Large enough to cover all data
    }
    
    # Perform sales analysis
    sales_analysis = analyze_sales(st.session_state.sales, period_days[analysis_period])
    
    # Display key metrics
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Total Revenue", f"${sales_analysis['total_revenue']:.2f}")
    
    with col2:
        st.metric("Total Profit", f"${sales_analysis['total_profit']:.2f}")
    
    with col3:
        st.metric("Profit Margin", f"{sales_analysis['avg_profit_margin']:.1f}%")
    
    with col4:
        # Calculate average daily revenue with safeguards against division by zero
        try:
            if 'sales' in st.session_state and st.session_state.sales:
                # Get unique dates in the sales data
                unique_dates = set()
                for s in st.session_state.sales:
                    if s.get('date'):
                        try:
                            date_obj = pd.to_datetime(s.get('date')).date()
                            unique_dates.add(date_obj)
                        except:
                            pass
                
                # Calculate days for the average
                num_days = min(period_days[analysis_period], len(unique_dates)) if unique_dates else 1
                
                # Make sure we don't divide by zero
                if num_days > 0 and sales_analysis['total_revenue'] > 0:
                    avg_daily = sales_analysis['total_revenue'] / num_days
                    st.metric("Avg. Daily Revenue", f"${avg_daily:.2f}")
                else:
                    st.metric("Avg. Daily Revenue", "$0.00")
            else:
                st.metric("Avg. Daily Revenue", "$0.00")
        except Exception as e:
            st.metric("Avg. Daily Revenue", "$0.00")
            st.warning(f"Could not calculate average daily revenue: {e}")
    
    # Display sales over time
    st.subheader("Sales Trend")
    
    if st.session_state.sales:
        # Convert sales data to DataFrame
        sales_df = pd.DataFrame(st.session_state.sales)
        
        # Convert date to datetime
        sales_df['date'] = pd.to_datetime(sales_df['date'])
        
        # Filter for the selected period
        cutoff_date = datetime.now() - timedelta(days=period_days[analysis_period])
        filtered_sales = sales_df[sales_df['date'] >= cutoff_date].copy()
        
        if not filtered_sales.empty:
            # Group by date and sum revenue
            daily_sales = filtered_sales.groupby(filtered_sales['date'].dt.date)['revenue'].sum().reset_index()
            daily_sales.columns = ['date', 'revenue']
            
            # Create line chart
            st.line_chart(daily_sales.set_index('date'))
            
            # Top items visualization
            st.subheader("Top Performing Items")
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.write("#### Top Items by Revenue")
                
                if sales_analysis['top_items_by_revenue']:
                    # Create chart data
                    revenue_data = pd.DataFrame({
                        'Item': [item['name'] for item in sales_analysis['top_items_by_revenue']],
                        'Revenue': [item['revenue'] for item in sales_analysis['top_items_by_revenue']]
                    })
                    
                    st.bar_chart(revenue_data.set_index('Item'))
                else:
                    st.info("No revenue data available for the selected period.")
            
            with col2:
                st.write("#### Top Items by Quantity")
                
                if sales_analysis['top_items_by_quantity']:
                    # Create chart data
                    quantity_data = pd.DataFrame({
                        'Item': [item['name'] for item in sales_analysis['top_items_by_quantity']],
                        'Quantity': [item['quantity'] for item in sales_analysis['top_items_by_quantity']]
                    })
                    
                    st.bar_chart(quantity_data.set_index('Item'))
                else:
                    st.info("No quantity data available for the selected period.")
            
            # Profit analysis
            st.subheader("Profit Analysis")
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.write("#### Top Profitable Items")
                
                if sales_analysis['top_items_by_profit']:
                    # Create chart data
                    profit_data = pd.DataFrame({
                        'Item': [item['name'] for item in sales_analysis['top_items_by_profit']],
                        'Profit': [item['profit'] for item in sales_analysis['top_items_by_profit']]
                    })
                    
                    st.bar_chart(profit_data.set_index('Item'))
                else:
                    st.info("No profit data available for the selected period.")
            
            with col2:
                st.write("#### Profit vs. Revenue")
                
                # Create scatter plot data for top items
                if sales_analysis['top_items_by_revenue']:
                    # Combine revenue and profit data
                    scatter_data = {}
                    
                    for item in sales_analysis['top_items_by_revenue']:
                        item_name = item['name']
                        scatter_data[item_name] = {'revenue': item['revenue']}
                    
                    for item in sales_analysis['top_items_by_profit']:
                        item_name = item['name']
                        if item_name in scatter_data:
                            scatter_data[item_name]['profit'] = item['profit']
                    
                    # Convert to DataFrame
                    scatter_df = pd.DataFrame([
                        {'Item': k, 'Revenue': v.get('revenue', 0), 'Profit': v.get('profit', 0)}
                        for k, v in scatter_data.items()
                    ])
                    
                    # Create a custom scatter plot
                    import plotly.express as px
                    
                    fig = px.scatter(
                        scatter_df,
                        x='Revenue',
                        y='Profit',
                        size='Revenue',
                        text='Item',
                        color='Profit',
                        color_continuous_scale='RdYlGn',
                    )
                    
                    fig.update_traces(
                        textposition='top center',
                        marker=dict(sizemode='area', sizeref=0.1)
                    )
                    
                    st.plotly_chart(fig, use_container_width=True)
                else:
                    st.info("No data available for the selected period.")
        else:
            st.info(f"No sales data available for the selected period ({analysis_period}).")
    else:
        st.info("No sales data available. Import your sales data to see analysis.")

with tab2:
    st.subheader("Import Sales Data")
    st.write("Upload Excel files with sales data to update your system")
    
    # File uploader
    uploaded_file = st.file_uploader("Upload sales data", type=['xlsx'])
    
    if uploaded_file:
        # Preview the data
        df = pd.read_excel(uploaded_file)
        st.write("Preview of uploaded data:")
        st.dataframe(df.head())
        
        # Column mapping
        st.subheader("Map Columns")
        with st.form("sales_mapping_form"):
            # Get mapping from UI
            mapping = generate_column_mapping_ui(df, 'sales')
            
            # Save mapping option
            mapping_name = st.text_input("Save this mapping as (optional):")
            
            # Import options
            import_option = st.radio(
                "Import option:",
                ["Add to existing sales data", "Replace all sales data"]
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
                    result = process_excel_upload(uploaded_file, 'sales', mapping)
                    
                    if result['status'] == 'success':
                        # Get the processed data
                        new_sales = result['data']
                        
                        # Handle based on import option
                        if import_option == "Add to existing sales data":
                            st.session_state.sales.extend(new_sales)
                            st.success(f"Added {len(new_sales)} new sales records.")
                        else:  # "Replace all sales data"
                            st.session_state.sales = new_sales
                            st.success(f"Replaced sales data with {len(new_sales)} records.")
                        
                        # Save the updated sales data
                        save_sales()
                        
                        # Redirect to dashboard
                        st.rerun()
                    else:
                        st.error(f"Error processing data: {result['message']}")
        
        # Show saved mappings if available
        if st.session_state.column_mappings:
            st.subheader("Saved Column Mappings")
            
            mapping_options = list(st.session_state.column_mappings.keys())
            selected_mapping = st.selectbox("Load a saved mapping:", ["Select a mapping..."] + mapping_options)
            
            if selected_mapping != "Select a mapping..." and st.button("Load Selected Mapping"):
                mapping = st.session_state.column_mappings[selected_mapping]
                st.success(f"Loaded mapping '{selected_mapping}'")
                st.rerun()

with tab3:
    st.subheader("Ingredient Consumption Analysis")
    st.write("Analyze how ingredients are being used based on sales data")
    
    if not st.session_state.sales:
        st.info("No sales data available. Import sales data to analyze ingredient consumption.")
    elif not st.session_state.recipes:
        st.info("No recipes found. Add recipes to analyze ingredient consumption.")
    else:
        # Calculate ingredient consumption
        consumption_data = calculate_ingredient_consumption(st.session_state.sales, st.session_state.recipes)
        
        if not consumption_data:
            st.info("No ingredient consumption data available. Make sure your sales data includes items that match your recipes.")
        else:
            # Display consumption overview
            st.write(f"Analyzed consumption for {len(consumption_data)} ingredients based on sales data.")
            
            # Display top consumed ingredients
            st.subheader("Top Consumed Ingredients")
            
            # Convert to DataFrame for charting
            consumption_df = pd.DataFrame([{
                'Ingredient': item['name'],
                'Total Amount': item['total_amount'],
                'Unit': item['unit'],
                'Used In': len(item['used_in'])
            } for item in consumption_data[:10]])
            
            # Create chart
            chart_data = consumption_df[['Ingredient', 'Total Amount']].set_index('Ingredient')
            st.bar_chart(chart_data)
            
            # Display detailed consumption table
            st.subheader("Detailed Consumption")
            
            consumption_table = pd.DataFrame([{
                'Ingredient': item['name'],
                'Total Amount': f"{item['total_amount']:.2f} {item['unit']}",
                'Used In': ', '.join(item['used_in'][:3]) + (f" +{len(item['used_in'])-3} more" if len(item['used_in']) > 3 else "")
            } for item in consumption_data])
            
            st.dataframe(consumption_table, hide_index=True)
            
            # Inventory reconciliation
            st.subheader("Inventory Reconciliation")
            st.write("Compare expected consumption based on sales with actual inventory levels")
            
            if not st.session_state.inventory:
                st.info("No inventory data available. Add inventory data to compare with consumption.")
            else:
                # Create a mapping of inventory items to their stock levels
                inventory_dict = {item.get('name', ''): item for item in st.session_state.inventory}
                
                # Compare consumption with inventory
                comparison_data = []
                
                for item in consumption_data:
                    ing_name = item['name']
                    consumed_amount = item['total_amount']
                    unit = item['unit']
                    
                    # Find in inventory
                    inv_item = inventory_dict.get(ing_name)
                    
                    if inv_item:
                        current_stock = inv_item.get('stock_level', 0)
                        inv_unit = inv_item.get('unit', '')
                        
                        # Check if units match
                        unit_match = unit.lower() == inv_unit.lower()
                        
                        comparison_data.append({
                            'Ingredient': ing_name,
                            'Consumed': consumed_amount,
                            'Unit': unit,
                            'Current Stock': current_stock,
                            'Inventory Unit': inv_unit,
                            'Units Match': unit_match,
                            'Days Until Depletion': current_stock / (consumed_amount / 30) if consumed_amount > 0 and unit_match else None
                        })
                
                if comparison_data:
                    # Convert to DataFrame
                    comparison_df = pd.DataFrame(comparison_data)
                    
                    # Format for display
                    display_df = comparison_df.copy()
                    display_df['Consumed'] = display_df['Consumed'].apply(lambda x: f"{x:.2f}")
                    display_df['Current Stock'] = display_df['Current Stock'].apply(lambda x: f"{x:.2f}")
                    display_df['Days Until Depletion'] = display_df['Days Until Depletion'].apply(
                        lambda x: f"{x:.0f} days" if pd.notna(x) else "N/A"
                    )
                    
                    # Highlight items with low days until depletion
                    def highlight_low_stock(val):
                        try:
                            days = float(val.split()[0])
                            if days < 7:
                                return 'background-color: #FFCCCC'
                            elif days < 14:
                                return 'background-color: #FFFFCC'
                            else:
                                return ''
                        except:
                            return ''
                    
                    # Display styled DataFrame
                    st.dataframe(
                        display_df,
                        hide_index=True,
                        column_config={
                            "Units Match": st.column_config.CheckboxColumn("Units Match", help="Whether the units in recipes match inventory"),
                            "Days Until Depletion": st.column_config.TextColumn("Days Until Depletion", help="Based on recent consumption rate")
                        }
                    )
                    
                    # Display warnings for items running low
                    low_stock_items = comparison_df[comparison_df['Days Until Depletion'] < 7].dropna(subset=['Days Until Depletion'])
                    
                    if not low_stock_items.empty:
                        st.warning("⚠️ The following items are running low and should be restocked soon:")
                        
                        for _, row in low_stock_items.iterrows():
                            st.write(f"• {row['Ingredient']}: {row['Current Stock']} {row['Inventory Unit']} remaining (approx. {row['Days Until Depletion']:.0f} days left)")
                else:
                    st.info("No matching ingredients found between consumption data and inventory.")

with tab4:
    st.subheader("Demand Forecasting")
    st.write("Forecast future ingredient demand based on historical sales data")
    
    if not st.session_state.sales or not st.session_state.recipes:
        st.info("Both sales data and recipes are required for demand forecasting. Please import your data first.")
    else:
        # Prepare time series data for forecasting
        time_series_data = prepare_time_series_data(
            st.session_state.sales, 
            st.session_state.recipes,
            st.session_state.inventory
        )
        
        if time_series_data.empty:
            st.info("Not enough sales data available for forecasting. Please make sure your sales data includes items that match your recipes.")
        else:
            # Display forecasting options
            forecast_days = st.slider("Forecast horizon (days)", min_value=7, max_value=90, value=30, step=1)
            
            # Generate forecast
            with st.spinner("Generating forecast..."):
                forecast_data = forecast_ingredient_demand(time_series_data, forecast_days)
            
            if forecast_data.empty:
                st.error("Failed to generate forecast. Please try again or check your data.")
            else:
                st.success(f"Generated {forecast_days}-day forecast for {len(forecast_data['ingredient'].unique())} ingredients")
                
                # Display forecast
                st.subheader("Ingredient Demand Forecast")
                
                # Convert dates to string for display
                forecast_display = forecast_data.copy()
                forecast_display['date'] = forecast_display['date'].dt.strftime('%Y-%m-%d')
                
                # Group by ingredient and calculate average daily demand
                avg_demand = forecast_display.groupby('ingredient')['forecasted_quantity'].mean().reset_index()
                avg_demand.columns = ['Ingredient', 'Average Daily Demand']
                
                # Sort by average demand (highest first)
                avg_demand = avg_demand.sort_values('Average Daily Demand', ascending=False)
                
                # Create chart
                st.bar_chart(avg_demand.set_index('Ingredient'))
                
                # Select ingredient for detailed forecast
                selected_ingredient = st.selectbox(
                    "Select ingredient for detailed forecast:",
                    avg_demand['Ingredient'].tolist()
                )
                
                # Filter forecast for selected ingredient
                ingredient_forecast = forecast_display[forecast_display['ingredient'] == selected_ingredient].copy()
                
                # Prepare for visualization
                ingredient_forecast['Forecasted Quantity'] = ingredient_forecast['forecasted_quantity']
                
                # Create a line chart
                st.line_chart(ingredient_forecast.set_index('date')['Forecasted Quantity'])
                
                # Find the method used for this forecast
                forecast_method = ingredient_forecast['method'].iloc[0] if not ingredient_forecast.empty else "unknown"
                st.write(f"Forecast method: {forecast_method}")
                
                # Identify sales trends
                st.subheader("Sales Trends Analysis")
                
                with st.spinner("Analyzing sales trends..."):
                    trends = identify_sales_trends(st.session_state.sales, st.session_state.recipes)
                
                if trends['top_sellers']:
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.write("#### Top Selling Items")
                        
                        top_sellers_df = pd.DataFrame([{
                            'Item': item['name'],
                            'Quantity': item['quantity']
                        } for item in trends['top_sellers']])
                        
                        st.dataframe(top_sellers_df, hide_index=True)
                    
                    with col2:
                        st.write("#### Growth Trend")
                        
                        growth_df = pd.DataFrame()
                        
                        if trends['growing_items']:
                            growing_df = pd.DataFrame([{
                                'Item': item['name'],
                                'Growth %': f"{item['growth']:.1f}%"
                            } for item in trends['growing_items']])
                            
                            growing_df['Trend'] = 'Growing'
                            growth_df = pd.concat([growth_df, growing_df])
                        
                        if trends['declining_items']:
                            declining_df = pd.DataFrame([{
                                'Item': item['name'],
                                'Growth %': f"{item['growth']:.1f}%"
                            } for item in trends['declining_items']])
                            
                            declining_df['Trend'] = 'Declining'
                            growth_df = pd.concat([growth_df, declining_df])
                        
                        if not growth_df.empty:
                            st.dataframe(growth_df, hide_index=True)
                        else:
                            st.info("Not enough historical data to identify growth trends.")
                    
                    # Weekly sales pattern
                    if trends['weekly_patterns']:
                        st.write("#### Weekly Sales Pattern")
                        
                        weekly_df = pd.DataFrame({
                            'Day': list(trends['weekly_patterns'].keys()),
                            'Sales': list(trends['weekly_patterns'].values())
                        })
                        
                        # Ensure correct order of days
                        day_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
                        weekly_df['Day'] = pd.Categorical(weekly_df['Day'], categories=day_order, ordered=True)
                        weekly_df = weekly_df.sort_values('Day')
                        
                        st.bar_chart(weekly_df.set_index('Day'))
                        
                        # Identify busiest and slowest days
                        if not weekly_df.empty:
                            busiest_day = weekly_df.loc[weekly_df['Sales'].idxmax()]['Day']
                            slowest_day = weekly_df.loc[weekly_df['Sales'].idxmin()]['Day']
                            
                            st.info(f"Your busiest day is {busiest_day} and your slowest day is {slowest_day}.")
                else:
                    st.info("Not enough sales data to identify trends.")
                
                # Generate ordering recommendations
                from utils.forecasting import recommend_inventory_levels
                
                st.subheader("Inventory Ordering Recommendations")
                
                if not st.session_state.inventory:
                    st.info("Please add inventory data to get ordering recommendations.")
                else:
                    with st.spinner("Generating recommendations..."):
                        recommendations = recommend_inventory_levels(
                            st.session_state.inventory,
                            forecast_data,
                            lead_time_days=2,
                            buffer_percentage=20
                        )
                    
                    if recommendations:
                        # Display recommendations
                        recom_df = pd.DataFrame([{
                            'Ingredient': item['ingredient'],
                            'Current Stock': item['current_stock'],
                            'Recommended Stock': f"{item['recommended_stock']:.2f}",
                            'Order Quantity': f"{item['order_quantity']:.2f}"
                        } for item in recommendations])
                        
                        st.dataframe(recom_df, hide_index=True)
                        
                        # Download recommendations as CSV
                        csv = recom_df.to_csv(index=False)
                        st.download_button(
                            label="Download Ordering Recommendations",
                            data=csv,
                            file_name="ordering_recommendations.csv",
                            mime="text/csv"
                        )
                    else:
                        st.info("No ordering recommendations available.")
