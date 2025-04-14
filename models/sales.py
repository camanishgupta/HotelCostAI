from datetime import datetime

class SalesRecord:
    """
    Class representing a sales record in the system
    """
    def __init__(self, date=None, item_name="", quantity=0, revenue=0.0, cost=0.0):
        self.date = date if date else datetime.now().isoformat()
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
        record.imported_at = data.get("imported_at", record.imported_at)
        
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
    today = datetime.now()
    
    # Filter for the analysis period
    filtered_sales = []
    for record in sales_data:
        try:
            # Parse the date
            record_date = datetime.fromisoformat(record.get("date", ""))
            days_ago = (today - record_date).days
            
            if days_ago <= period_days:
                filtered_sales.append(record)
        except:
            continue
    
    # Calculate total metrics
    total_revenue = sum(record.get("revenue", 0) for record in filtered_sales)
    total_cost = sum(record.get("cost", 0) for record in filtered_sales)
    total_profit = sum(record.get("profit", 0) for record in filtered_sales)
    total_quantity = sum(record.get("quantity", 0) for record in filtered_sales)
    
    # Calculate average profit margin
    avg_profit_margin = 0
    if total_revenue > 0:
        avg_profit_margin = (total_profit / total_revenue) * 100
    
    # Group sales by item
    item_sales = {}
    for record in filtered_sales:
        item_name = record.get("item_name", "")
        
        if item_name not in item_sales:
            item_sales[item_name] = {
                "quantity": 0,
                "revenue": 0,
                "cost": 0,
                "profit": 0
            }
        
        item_sales[item_name]["quantity"] += record.get("quantity", 0)
        item_sales[item_name]["revenue"] += record.get("revenue", 0)
        item_sales[item_name]["cost"] += record.get("cost", 0)
        item_sales[item_name]["profit"] += record.get("profit", 0)
    
    # Calculate profit margin for each item
    for item_name, data in item_sales.items():
        if data["revenue"] > 0:
            data["profit_margin"] = (data["profit"] / data["revenue"]) * 100
        else:
            data["profit_margin"] = 0
    
    # Sort items by profit
    top_profit_items = sorted(
        [(item, data["profit"]) for item, data in item_sales.items()],
        key=lambda x: x[1],
        reverse=True
    )
    
    # Sort items by quantity
    top_quantity_items = sorted(
        [(item, data["quantity"]) for item, data in item_sales.items()],
        key=lambda x: x[1],
        reverse=True
    )
    
    # Sort items by profit margin
    top_margin_items = sorted(
        [(item, data["profit_margin"]) for item, data in item_sales.items()],
        key=lambda x: x[1],
        reverse=True
    )
    
    # Group sales by date
    daily_sales = {}
    for record in filtered_sales:
        try:
            # Parse the date
            record_date = datetime.fromisoformat(record.get("date", ""))
            date_str = record_date.strftime("%Y-%m-%d")
            
            if date_str not in daily_sales:
                daily_sales[date_str] = {
                    "revenue": 0,
                    "cost": 0,
                    "profit": 0,
                    "quantity": 0
                }
            
            daily_sales[date_str]["revenue"] += record.get("revenue", 0)
            daily_sales[date_str]["cost"] += record.get("cost", 0)
            daily_sales[date_str]["profit"] += record.get("profit", 0)
            daily_sales[date_str]["quantity"] += record.get("quantity", 0)
        except:
            continue
    
    # Sort daily sales by date
    sorted_daily_sales = {k: daily_sales[k] for k in sorted(daily_sales.keys())}
    
    # Return the analysis results
    return {
        "period_days": period_days,
        "total_records": len(filtered_sales),
        "total_revenue": total_revenue,
        "total_cost": total_cost,
        "total_profit": total_profit,
        "total_quantity": total_quantity,
        "avg_profit_margin": avg_profit_margin,
        "item_sales": item_sales,
        "top_profit_items": top_profit_items[:10],  # Top 10
        "top_quantity_items": top_quantity_items[:10],  # Top 10
        "top_margin_items": top_margin_items[:10],  # Top 10
        "daily_sales": sorted_daily_sales
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
    # Create a dictionary of recipes by name for quick lookup
    recipe_dict = {recipe.get("name", "").lower(): recipe for recipe in recipes}
    
    # Initialize ingredient consumption tracker
    ingredient_consumption = {}
    
    # Process each sales record
    for record in sales_data:
        item_name = record.get("item_name", "").lower()
        quantity = record.get("quantity", 0)
        
        # Skip if quantity is 0
        if quantity == 0:
            continue
        
        # Check if we have a recipe for this item
        if item_name in recipe_dict:
            recipe = recipe_dict[item_name]
            ingredients = recipe.get("ingredients", [])
            yield_amount = recipe.get("yield_amount", 1)
            
            # Calculate scaling factor
            scaling_factor = quantity / yield_amount if yield_amount > 0 else quantity
            
            # Calculate ingredient consumption
            for ingredient in ingredients:
                ing_name = ingredient.get("name", "")
                ing_amount = ingredient.get("amount", 0)
                ing_unit = ingredient.get("unit", "")
                
                # Skip if name or amount is missing
                if not ing_name or ing_amount == 0:
                    continue
                
                # Calculate consumption
                consumption = ing_amount * scaling_factor
                
                # Add to consumption tracker
                if ing_name not in ingredient_consumption:
                    ingredient_consumption[ing_name] = {
                        "total": 0,
                        "unit": ing_unit,
                        "recipes": {}
                    }
                
                ingredient_consumption[ing_name]["total"] += consumption
                
                # Track consumption by recipe
                if recipe.get("name", "") not in ingredient_consumption[ing_name]["recipes"]:
                    ingredient_consumption[ing_name]["recipes"][recipe.get("name", "")] = 0
                
                ingredient_consumption[ing_name]["recipes"][recipe.get("name", "")] += consumption
    
    # Sort ingredients by total consumption
    sorted_consumption = {
        k: v for k, v in sorted(
            ingredient_consumption.items(),
            key=lambda x: x[1]["total"],
            reverse=True
        )
    }
    
    return {
        "total_recipes_matched": len(set(r.get("item_name", "").lower() for r in sales_data if r.get("item_name", "").lower() in recipe_dict)),
        "total_ingredients_tracked": len(sorted_consumption),
        "consumption_data": sorted_consumption
    }