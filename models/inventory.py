from datetime import datetime

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
        self.created_at = datetime.now().isoformat()
        self.updated_at = datetime.now().isoformat()
        self.price_history = []
        self.stock_history = []
        
    def update_price(self, new_price, date=None):
        """
        Update the price of the inventory item
        
        Args:
            new_price (float): New price
            date (str, optional): Date of the price change
        """
        if date is None:
            date = datetime.now().isoformat()
            
        # Add to price history
        self.price_history.append({
            "old_price": self.price,
            "new_price": new_price,
            "date": date
        })
        
        # Update current price
        self.price = new_price
        self.updated_at = datetime.now().isoformat()
        
    def update_stock(self, new_stock_level, date=None):
        """
        Update the stock level of the inventory item
        
        Args:
            new_stock_level (float): New stock level
            date (str, optional): Date of the stock update
        """
        if date is None:
            date = datetime.now().isoformat()
            
        # Add to stock history
        self.stock_history.append({
            "old_level": self.stock_level,
            "new_level": new_stock_level,
            "date": date
        })
        
        # Update current stock level
        self.stock_level = new_stock_level
        self.updated_at = datetime.now().isoformat()
        
    def add_stock(self, amount, date=None):
        """
        Add stock to the inventory item
        
        Args:
            amount (float): Amount to add
            date (str, optional): Date of the stock addition
        """
        self.update_stock(self.stock_level + amount, date)
        
    def remove_stock(self, amount, date=None):
        """
        Remove stock from the inventory item
        
        Args:
            amount (float): Amount to remove
            date (str, optional): Date of the stock removal
        
        Returns:
            bool: True if successful, False if not enough stock
        """
        if amount > self.stock_level:
            return False
            
        self.update_stock(self.stock_level - amount, date)
        return True
        
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
            
        last_change = self.price_history[-1]
        old_price = last_change["old_price"]
        
        if old_price == 0:
            return 0
            
        return ((self.price - old_price) / old_price) * 100
        
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
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "price_history": self.price_history,
            "stock_history": self.stock_history
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
        
        item.created_at = data.get("created_at", datetime.now().isoformat())
        item.updated_at = data.get("updated_at", datetime.now().isoformat())
        item.price_history = data.get("price_history", [])
        item.stock_history = data.get("stock_history", [])
        
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
    changes = []
    
    # Create a dictionary of old inventory items by name for quick lookup
    old_items = {item.get("name", ""): item for item in old_inventory}
    
    # Check each item in the new inventory
    for new_item in new_inventory:
        name = new_item.get("name", "")
        new_price = new_item.get("price", 0)
        
        # Skip if name is empty or price is 0
        if not name or new_price == 0:
            continue
            
        # Check if this item exists in the old inventory
        if name in old_items:
            old_item = old_items[name]
            old_price = old_item.get("price", 0)
            
            # Skip if old price is 0
            if old_price == 0:
                continue
                
            # Calculate percentage change
            percent_change = ((new_price - old_price) / old_price) * 100
            
            # Check if change is significant
            if abs(percent_change) >= threshold_percentage:
                changes.append({
                    "name": name,
                    "old_price": old_price,
                    "new_price": new_price,
                    "percent_change": percent_change,
                    "unit": new_item.get("unit", "")
                })
    
    # Sort by absolute percentage change
    changes.sort(key=lambda x: abs(x["percent_change"]), reverse=True)
    
    return changes