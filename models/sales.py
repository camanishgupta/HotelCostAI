from datetime import datetime, timedelta
import json
import os
import pandas as pd
import numpy as np

class SalesRecord:
    """
    Class representing a sales record in the system
    """
    def __init__(self, date=None, item_name="", quantity=0, revenue=0.0, cost=0.0):
        self.date = date or datetime.now().isoformat()
        self.item_name = item_name
        self.quantity = quantity
        self.revenue = revenue
        self.cost = cost
        self.profit = revenue - cost
        self.profit_margin = (self.profit / revenue) * 100 if revenue > 0 else 0
        self.imported_at = datetime.now().isoformat()
    
    def to_dict(self):
        """
        Convert the sales record to a dictionary
        
        Returns:
            dict: Sales record as a dictionary
        """
        return {
            "date": self.date,
            "item_name": self.item_name,
            "quantity": self.quantity,
            "revenue": self.revenue,
            "cost": self.cost,
            "profit": self.profit,
            "profit_margin": self.profit_margin,
            "imported_at": self.imported_at
        }
    
    @classmethod
    def from_dict(cls, data):
        """
        Create a sales record from a dictionary
        
        Args:
            data (dict): Sales record data
        
        Returns:
            SalesRecord: New sales record instance
        """
        record = cls(
            date=data.get("date", datetime.now().isoformat()),
            item_name=data.get("item_name", ""),
            quantity=data.get("quantity", 0),
            revenue=data.get("revenue", 0.0),
            cost=data.get("cost", 0.0)
        )
        
        record.profit = data.get("profit", record.profit)
        record.profit_margin = data.get("profit_margin", record.profit_margin)
        record.imported_at = data.get("imported_at", datetime.now().isoformat())
        
        return record

def analyze_sales(sales_data, period_days=30):
    """
    Analyze sales data for insights
    
    Args:
        sales_data (list): Sales records
        period_days (int): Analysis period in days
    
    Returns:
        dict: Sales analysis results
    """
    # Convert to DataFrame
    df = pd.DataFrame(sales_data)
    
    # Handle empty dataframe
    if df.empty:
        return {
            "total_revenue": 0,
            "total_profit": 0,
            "average_profit_margin": 0,
            "top_items_by_quantity": [],
            "top_items_by_revenue": [],
            "top_items_by_profit": []
        }
    
    # Ensure date is in datetime format
    df['date'] = pd.to_datetime(df['date'])
    
    # Filter to the analysis period
    cutoff_date = datetime.now() - timedelta(days=period_days)
    recent_df = df[df['date'] >= cutoff_date]
    
    # If no recent data, use all data
    if recent_df.empty:
        recent_df = df
    
    # Calculate totals
    total_revenue = recent_df['revenue'].sum()
    total_profit = recent_df['profit'].sum()
    
    # Calculate average profit margin (weighted by revenue)
    if total_revenue > 0:
        average_profit_margin = (total_profit / total_revenue) * 100
    else:
        average_profit_margin = 0
    
    # Get top items by different metrics
    top_by_quantity = recent_df.groupby('item_name')['quantity'].sum().sort_values(ascending=False).head(5)
    top_by_revenue = recent_df.groupby('item_name')['revenue'].sum().sort_values(ascending=False).head(5)
    top_by_profit = recent_df.groupby('item_name')['profit'].sum().sort_values(ascending=False).head(5)
    
    # Convert to lists of dictionaries
    top_quantity_list = [{"name": item, "quantity": float(qty)} for item, qty in top_by_quantity.items()]
    top_revenue_list = [{"name": item, "revenue": float(rev)} for item, rev in top_by_revenue.items()]
    top_profit_list = [{"name": item, "profit": float(prf)} for item, prf in top_by_profit.items()]
    
    return {
        "total_revenue": float(total_revenue),
        "total_profit": float(total_profit),
        "average_profit_margin": float(average_profit_margin),
        "top_items_by_quantity": top_quantity_list,
        "top_items_by_revenue": top_revenue_list,
        "top_items_by_profit": top_profit_list
    }

def calculate_ingredient_consumption(sales_data, recipes):
    """
    Calculate the consumption of ingredients based on sales
    
    Args:
        sales_data (list): Sales records
        recipes (list): Recipe data
    
    Returns:
        dict: Ingredient consumption data
    """
    # Create a lookup dictionary for recipes
    recipe_dict = {recipe["name"]: recipe for recipe in recipes}
    
    # Initialize ingredient consumption
    consumption = {}
    
    # Process each sales record
    for record in sales_data:
        item_name = record.get("item_name", "")
        quantity = record.get("quantity", 0)
        
        # Skip if item is not found in recipes
        if item_name not in recipe_dict:
            continue
        
        recipe = recipe_dict[item_name]
        ingredients = recipe.get("ingredients", [])
        
        # Process each ingredient
        for ingredient in ingredients:
            ing_name = ingredient.get("name", "")
            ing_amount = float(ingredient.get("amount", 0))
            ing_unit = ingredient.get("unit", "")
            
            # Calculate consumption for this sale
            ing_consumption = ing_amount * quantity
            
            # Add to total consumption
            if ing_name not in consumption:
                consumption[ing_name] = {
                    "name": ing_name,
                    "total_amount": 0,
                    "unit": ing_unit,
                    "used_in": []
                }
            
            consumption[ing_name]["total_amount"] += ing_consumption
            
            # Track which recipes use this ingredient
            if item_name not in consumption[ing_name]["used_in"]:
                consumption[ing_name]["used_in"].append(item_name)
    
    # Convert to list and sort by consumption amount
    result = list(consumption.values())
    result.sort(key=lambda x: x["total_amount"], reverse=True)
    
    return result
