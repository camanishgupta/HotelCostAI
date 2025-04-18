from datetime import datetime

class Recipe:
    """
    Class representing a recipe in the system
    """
    def __init__(self, name="", ingredients=None, yield_amount=1, yield_unit="serving"):
        self.name = name
        self.ingredients = ingredients or []
        self.yield_amount = yield_amount
        self.yield_unit = yield_unit
        self.preparation_steps = []
        self.total_cost = 0.0
        self.cost_per_unit = 0.0
        self.created_at = datetime.now().isoformat()
        self.updated_at = datetime.now().isoformat()
        
    def add_ingredient(self, name, amount, unit, cost=0):
        """
        Add an ingredient to the recipe
        
        Args:
            name (str): Ingredient name
            amount (float): Amount of the ingredient
            unit (str): Unit of measurement
            cost (float): Cost of the ingredient
        """
        self.ingredients.append({
            "name": name,
            "amount": amount,
            "unit": unit,
            "cost": cost
        })
        self.calculate_cost()
        self.updated_at = datetime.now().isoformat()
        
    def remove_ingredient(self, index):
        """
        Remove an ingredient by index
        
        Args:
            index (int): Index of the ingredient to remove
        """
        if 0 <= index < len(self.ingredients):
            del self.ingredients[index]
            self.calculate_cost()
            self.updated_at = datetime.now().isoformat()
            
    def update_ingredient(self, index, name=None, amount=None, unit=None, cost=None):
        """
        Update an ingredient by index
        
        Args:
            index (int): Index of the ingredient to update
            name (str, optional): New name
            amount (float, optional): New amount
            unit (str, optional): New unit
            cost (float, optional): New cost
        """
        if 0 <= index < len(self.ingredients):
            if name is not None:
                self.ingredients[index]["name"] = name
            if amount is not None:
                self.ingredients[index]["amount"] = amount
            if unit is not None:
                self.ingredients[index]["unit"] = unit
            if cost is not None:
                self.ingredients[index]["cost"] = cost
                
            self.calculate_cost()
            self.updated_at = datetime.now().isoformat()
            
    def calculate_cost(self):
        """
        Calculate the total cost of the recipe
        """
        self.total_cost = sum(ingredient.get("cost", 0) for ingredient in self.ingredients)
        if self.yield_amount > 0:
            self.cost_per_unit = self.total_cost / self.yield_amount
        else:
            self.cost_per_unit = 0
            
    def scale_recipe(self, new_yield):
        """
        Scale recipe ingredients to a new yield
        
        Args:
            new_yield (float): New yield amount
        
        Returns:
            Recipe: New scaled recipe
        """
        if self.yield_amount == 0:
            return self
            
        scale_factor = new_yield / self.yield_amount
        new_recipe = Recipe(
            name=f"{self.name} ({new_yield} {self.yield_unit})",
            yield_amount=new_yield,
            yield_unit=self.yield_unit
        )
        
        for ingredient in self.ingredients:
            new_recipe.add_ingredient(
                name=ingredient["name"],
                amount=ingredient["amount"] * scale_factor,
                unit=ingredient["unit"],
                cost=ingredient["cost"] * scale_factor
            )
            
        new_recipe.preparation_steps = self.preparation_steps.copy()
        
        return new_recipe
        
    def to_dict(self):
        """
        Convert the recipe to a dictionary
        
        Returns:
            dict: Recipe as a dictionary
        """
        return {
            "name": self.name,
            "ingredients": self.ingredients,
            "yield_amount": self.yield_amount,
            "yield_unit": self.yield_unit,
            "preparation_steps": self.preparation_steps,
            "total_cost": self.total_cost,
            "cost_per_unit": self.cost_per_unit,
            "created_at": self.created_at,
            "updated_at": self.updated_at
        }
        
    @classmethod
    def from_dict(cls, data):
        """
        Create a recipe from a dictionary
        
        Args:
            data (dict): Recipe data
        
        Returns:
            Recipe: New recipe instance
        """
        recipe = cls(
            name=data.get("name", ""),
            ingredients=data.get("ingredients", []),
            yield_amount=data.get("yield_amount", 1),
            yield_unit=data.get("yield_unit", "serving")
        )
        
        recipe.preparation_steps = data.get("preparation_steps", [])
        recipe.total_cost = data.get("total_cost", 0.0)
        recipe.cost_per_unit = data.get("cost_per_unit", 0.0)
        recipe.created_at = data.get("created_at", datetime.now().isoformat())
        recipe.updated_at = data.get("updated_at", datetime.now().isoformat())
        
        return recipe