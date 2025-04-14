import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import statsmodels.api as sm
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error

def prepare_time_series_data(sales_data, recipe_data, inventory_data):
    """
    Prepare time series data for forecasting
    
    Args:
        sales_data (list): Sales records
        recipe_data (list): Recipe data
        inventory_data (list): Inventory data
    
    Returns:
        DataFrame: Prepared time series data
    """
    # Convert sales data to DataFrame
    sales_df = pd.DataFrame(sales_data)
    
    # Ensure date is in datetime format
    sales_df['date'] = pd.to_datetime(sales_df['date'])
    
    # Create a mapping of recipe items to ingredients
    recipe_ingredients = {}
    for recipe in recipe_data:
        recipe_name = recipe.get('name')
        if recipe_name:
            recipe_ingredients[recipe_name] = [ing.get('name') for ing in recipe.get('ingredients', [])]
    
    # Map sales to ingredient consumption
    ingredient_usage = []
    
    for _, sale in sales_df.iterrows():
        item_name = sale.get('item_name')
        quantity = sale.get('quantity', 0)
        date = sale.get('date')
        
        # Skip if item name or quantity is missing
        if not item_name or not quantity:
            continue
        
        # Find recipe for this item
        ingredients = recipe_ingredients.get(item_name, [])
        
        # If no recipe found, continue to next sale
        if not ingredients:
            continue
        
        # Add usage entry for each ingredient
        for ingredient in ingredients:
            # In a real system, we would calculate exact quantities based on the recipe
            # For simplicity, we'll just record that this ingredient was used
            ingredient_usage.append({
                'date': date,
                'ingredient': ingredient,
                'quantity_used': quantity  # This is a simplification
            })
    
    # Convert to DataFrame
    if not ingredient_usage:
        # Return empty DataFrame with expected columns
        return pd.DataFrame(columns=['date', 'ingredient', 'quantity_used'])
    
    usage_df = pd.DataFrame(ingredient_usage)
    
    # Aggregate by date and ingredient
    usage_df = usage_df.groupby(['date', 'ingredient'])['quantity_used'].sum().reset_index()
    
    return usage_df

def forecast_ingredient_demand(usage_data, forecast_days=30):
    """
    Forecast future ingredient demand
    
    Args:
        usage_data (DataFrame): Historical usage data
        forecast_days (int): Number of days to forecast
    
    Returns:
        DataFrame: Forecasted demand
    """
    if usage_data.empty:
        return pd.DataFrame(columns=['date', 'ingredient', 'forecasted_quantity'])
    
    # Get unique ingredients
    ingredients = usage_data['ingredient'].unique()
    
    # Prepare results container
    forecasts = []
    
    # Get the latest date in the data
    max_date = usage_data['date'].max()
    
    # For each ingredient, create a forecast
    for ingredient in ingredients:
        # Filter data for this ingredient
        ingredient_data = usage_data[usage_data['ingredient'] == ingredient].copy()
        
        # Need at least 14 data points for a reasonable forecast
        if len(ingredient_data) < 14:
            # For ingredients with limited data, use a simple average
            avg_usage = ingredient_data['quantity_used'].mean()
            
            # Generate forecast dates
            forecast_dates = [max_date + timedelta(days=i+1) for i in range(forecast_days)]
            
            # Create forecast entries
            for date in forecast_dates:
                forecasts.append({
                    'date': date,
                    'ingredient': ingredient,
                    'forecasted_quantity': avg_usage,
                    'method': 'average'
                })
            
            continue
        
        # Set date as index
        ingredient_data.set_index('date', inplace=True)
        
        # Resample to daily frequency, filling gaps with 0
        daily_data = ingredient_data.resample('D')['quantity_used'].sum().fillna(0)
        
        try:
            # Try to fit SARIMA model - good for time series with seasonality
            # Order and seasonal order would ideally be determined through analysis
            model = sm.tsa.statespace.SARIMAX(
                daily_data,
                order=(1, 1, 1),
                seasonal_order=(1, 1, 1, 7),  # Weekly seasonality
                enforce_stationarity=False,
                enforce_invertibility=False
            )
            
            model_fit = model.fit(disp=False)
            
            # Make prediction
            pred = model_fit.forecast(steps=forecast_days)
            
            # Create forecast entries
            for i, (date, value) in enumerate(zip(pred.index, pred.values)):
                forecasts.append({
                    'date': date,
                    'ingredient': ingredient,
                    'forecasted_quantity': max(0, value),  # Ensure non-negative
                    'method': 'sarima'
                })
                
        except Exception as e:
            # If SARIMA fails, fall back to a simpler method
            # Calculate moving average
            rolling_avg = daily_data.rolling(window=7, min_periods=1).mean()
            last_avg = rolling_avg.iloc[-1]
            
            # Generate forecast dates
            forecast_dates = [max_date + timedelta(days=i+1) for i in range(forecast_days)]
            
            # Create forecast entries
            for date in forecast_dates:
                forecasts.append({
                    'date': date,
                    'ingredient': ingredient,
                    'forecasted_quantity': last_avg,
                    'method': 'moving_average'
                })
    
    # Convert forecasts to DataFrame
    forecast_df = pd.DataFrame(forecasts)
    
    return forecast_df

def identify_sales_trends(sales_data, recipe_data):
    """
    Identify trends in sales data
    
    Args:
        sales_data (list): Sales records
        recipe_data (list): Recipe data
    
    Returns:
        dict: Identified trends
    """
    # Convert to DataFrame
    sales_df = pd.DataFrame(sales_data)
    
    # Skip if empty
    if sales_df.empty:
        return {
            "top_sellers": [],
            "growing_items": [],
            "declining_items": [],
            "weekly_patterns": {}
        }
    
    # Ensure date is in datetime format
    sales_df['date'] = pd.to_datetime(sales_df['date'])
    
    # Add week and day columns
    sales_df['week'] = sales_df['date'].dt.isocalendar().week
    sales_df['day_of_week'] = sales_df['date'].dt.dayofweek
    
    # 1. Top selling items
    top_sellers = sales_df.groupby('item_name')['quantity'].sum().sort_values(ascending=False).head(5)
    
    # 2. Growing and declining items (compare recent to earlier period)
    # Split data into recent and earlier periods
    mid_date = sales_df['date'].min() + (sales_df['date'].max() - sales_df['date'].min()) / 2
    
    recent_sales = sales_df[sales_df['date'] >= mid_date]
    earlier_sales = sales_df[sales_df['date'] < mid_date]
    
    # Calculate sales volumes for both periods
    if not recent_sales.empty and not earlier_sales.empty:
        recent_vol = recent_sales.groupby('item_name')['quantity'].sum()
        earlier_vol = earlier_sales.groupby('item_name')['quantity'].sum()
        
        # Combine and calculate growth
        combined = pd.DataFrame({'recent': recent_vol, 'earlier': earlier_vol}).fillna(0)
        combined['growth'] = (combined['recent'] - combined['earlier']) / combined['earlier'].replace(0, 1) * 100
        
        # Get top growing and declining items
        growing = combined.sort_values('growth', ascending=False).head(3)
        declining = combined.sort_values('growth', ascending=True).head(3)
        
        growing_items = [{"name": k, "growth": v} for k, v in growing['growth'].items()]
        declining_items = [{"name": k, "growth": v} for k, v in declining['growth'].items()]
    else:
        growing_items = []
        declining_items = []
    
    # 3. Weekly patterns - sales by day of week
    day_patterns = sales_df.groupby('day_of_week')['quantity'].sum()
    
    # Convert day numbers to names
    day_names = {
        0: 'Monday',
        1: 'Tuesday',
        2: 'Wednesday',
        3: 'Thursday',
        4: 'Friday',
        5: 'Saturday',
        6: 'Sunday'
    }
    
    weekly_patterns = {day_names[day]: float(count) for day, count in day_patterns.items()}
    
    # Return results
    return {
        "top_sellers": [{"name": k, "quantity": float(v)} for k, v in top_sellers.items()],
        "growing_items": growing_items,
        "declining_items": declining_items,
        "weekly_patterns": weekly_patterns
    }

def recommend_inventory_levels(inventory_data, forecast_data, lead_time_days=2, buffer_percentage=20):
    """
    Recommend inventory levels based on forecasted demand
    
    Args:
        inventory_data (list): Current inventory data
        forecast_data (DataFrame): Forecasted demand
        lead_time_days (int): Lead time for ordering in days
        buffer_percentage (int): Safety buffer percentage
    
    Returns:
        list: Recommended inventory levels
    """
    # Skip if forecast data is empty
    if forecast_data.empty:
        return []
    
    # Create inventory dictionary for lookup
    inventory_dict = {item['name']: item for item in inventory_data}
    
    # Calculate total demand during lead time + buffer period
    lead_time_demand = forecast_data.groupby('ingredient')['forecasted_quantity'].sum() / len(forecast_data['date'].unique()) * lead_time_days
    
    # Apply buffer
    safety_stock = lead_time_demand * (buffer_percentage / 100)
    recommended_stock = lead_time_demand + safety_stock
    
    # Create recommendations
    recommendations = []
    
    for ingredient, recommended in recommended_stock.items():
        # Get current stock level
        current_stock = 0
        if ingredient in inventory_dict:
            current_stock = inventory_dict[ingredient].get('stock_level', 0)
        
        # Calculate order quantity
        order_quantity = max(0, recommended - current_stock)
        
        recommendations.append({
            "ingredient": ingredient,
            "current_stock": current_stock,
            "recommended_stock": float(recommended),
            "order_quantity": float(order_quantity)
        })
    
    # Sort by order quantity (highest first)
    recommendations.sort(key=lambda x: x['order_quantity'], reverse=True)
    
    return recommendations
