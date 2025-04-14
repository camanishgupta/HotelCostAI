from datetime import datetime
import json
import os
import pandas as pd

class InventoryItem:
    """
    Class representing an inventory item in the system
    """
    def __init__(self, item_code="", name="", category="", price=0.0, unit="", supplier="", stock_level=0.0):
        self.item_code = item_code
        self.name = name
        self.category = category
        self.price = price
        self.unit = unit
        self.supplier = supplier
        self.stock_level = stock_level
        self.price_history = []
        self.created_at = datetime.now().isoformat()
        self.updated_at = datetime.now().isoformat()
    
    def update_price(self, new_price, date=None):
        """
        Update the price of the inventory item
        
        Args:
            new_price (float): New price
            date (str, optional): Date of the price change
        """
        # Store the old price in history
        if self.price != new_price:
            self.price_history.append({
                "price": self.price,
                "date": date or datetime.now().isoformat()
            })
            
            self.price = new_price
            self.updated_at = datetime.now().isoformat()
    
    def update_stock(self, new_stock_level, date=None):
        """
        Update the stock level of the inventory item
        
        Args:
            new_stock_level (float): New stock level
            date (str, optional): Date of the stock update
        """
        self.stock_level = new_stock_level
        self.updated_at = date or datetime.now().isoformat()
    
    def add_stock(self, amount, date=None):
        """
        Add stock to the inventory item
        
        Args:
            amount (float): Amount to add
            date (str, optional): Date of the stock addition
        """
        self.stock_level += amount
        self.updated_at = date or datetime.now().isoformat()
    
    def remove_stock(self, amount, date=None):
        """
        Remove stock from the inventory item
        
        Args:
            amount (float): Amount to remove
            date (str, optional): Date of the stock removal
        
        Returns:
            bool: True if successful, False if not enough stock
        """
        if amount <= self.stock_level:
            self.stock_level -= amount
            self.updated_at = date or datetime.now().isoformat()
            return True
        return False
    
    def calculate_value(self):
        """
        Calculate the total value of this inventory item
        
        Returns:
            float: Total value
        """
        return self.price * self.stock_level
    
    def price_change_percentage(self):
        """
        Calculate the percentage change from the previous price
        
        Returns:
            float: Percentage change
        """
        if not self.price_history:
            return 0
        
        previous_price = self.price_history[-1]["price"]
        
        if previous_price == 0:
            return 0
            
        return ((self.price - previous_price) / previous_price) * 100
    
    def to_dict(self):
        """
        Convert the inventory item to a dictionary
        
        Returns:
            dict: Inventory item as a dictionary
        """
        return {
            "item_code": self.item_code,
            "name": self.name,
            "category": self.category,
            "price": self.price,
            "unit": self.unit,
            "supplier": self.supplier,
            "stock_level": self.stock_level,
            "price_history": self.price_history,
            "created_at": self.created_at,
            "updated_at": self.updated_at
        }
    
    @classmethod
    def from_dict(cls, data):
        """
        Create an inventory item from a dictionary
        
        Args:
            data (dict): Inventory item data
        
        Returns:
            InventoryItem: New inventory item instance
        """
        item = cls(
            item_code=data.get("item_code", ""),
            name=data.get("name", ""),
            category=data.get("category", ""),
            price=data.get("price", 0.0),
            unit=data.get("unit", ""),
            supplier=data.get("supplier", ""),
            stock_level=data.get("stock_level", 0.0)
        )
        
        item.price_history = data.get("price_history", [])
        item.created_at = data.get("created_at", datetime.now().isoformat())
        item.updated_at = data.get("updated_at", datetime.now().isoformat())
        
        return item

def detect_price_changes(old_inventory, new_inventory, threshold_percentage=5):
    """
    Detect significant price changes between old and new inventory
    
    Args:
        old_inventory (list): Old inventory data
        new_inventory (list): New inventory data
        threshold_percentage (float): Minimum percentage change to report
    
    Returns:
        list: Items with significant price changes
    """
    # Convert to dictionaries for easier lookup
    old_dict = {item["item_code"]: item for item in old_inventory}
    
    changes = []
    
    for new_item in new_inventory:
        item_code = new_item["item_code"]
        
        if item_code in old_dict:
            old_price = old_dict[item_code]["price"]
            new_price = new_item["price"]
            
            # Skip if prices are the same
            if old_price == new_price:
                continue
            
            # Calculate percentage change
            if old_price > 0:
                percentage_change = ((new_price - old_price) / old_price) * 100
            else:
                percentage_change = 0 if new_price == 0 else 100
            
            # Only include significant changes
            if abs(percentage_change) >= threshold_percentage:
                changes.append({
                    "item_code": item_code,
                    "name": new_item["name"],
                    "old_price": old_price,
                    "new_price": new_price,
                    "percentage_change": percentage_change,
                    "unit": new_item["unit"]
                })
    
    # Sort by absolute percentage change, highest first
    changes.sort(key=lambda x: abs(x["percentage_change"]), reverse=True)
    
    return changes
