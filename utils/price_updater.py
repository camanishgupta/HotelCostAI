"""
Price Updater Module for ABGN Hotel Cost Control

This module provides functions to update recipe costs based on inventory receipt data.
It handles ingredient matching and unit conversion.
"""

import pandas as pd
import numpy as np
import streamlit as st
from datetime import datetime
import re
import math

def normalize_text(text):
    """
    Normalize text for better matching by removing special characters and making lowercase
    
    Args:
        text (str): Input text to normalize
        
    Returns:
        str: Normalized text
    """
    if not isinstance(text, str):
        return ""
    
    # Convert to lowercase
    text = text.lower()
    
    # Remove special characters
    text = re.sub(r'[^a-z0-9\s]', '', text)
    
    # Replace multiple spaces with single space
    text = re.sub(r'\s+', ' ', text)
    
    # Trim whitespace
    text = text.strip()
    
    return text

def calculate_similarity(str1, str2):
    """
    Calculate string similarity score between two strings
    
    Args:
        str1 (str): First string
        str2 (str): Second string
        
    Returns:
        float: Similarity score (0-1)
    """
    # Normalize both strings
    norm1 = normalize_text(str1)
    norm2 = normalize_text(str2)
    
    if not norm1 or not norm2:
        return 0.0
    
    # Split into words
    words1 = set(norm1.split())
    words2 = set(norm2.split())
    
    # Calculate Jaccard similarity (intersection over union)
    intersection = len(words1.intersection(words2))
    union = len(words1.union(words2))
    
    if union == 0:
        return 0.0
    
    similarity = intersection / union
    
    # Boost score if one is substring of the other
    if norm1 in norm2 or norm2 in norm1:
        similarity += 0.3
        similarity = min(similarity, 1.0)  # Cap at 1.0
    
    return similarity

def get_conversion_factor(from_unit, to_unit):
    """
    Get conversion factor between units
    
    Args:
        from_unit (str): Source unit
        to_unit (str): Target unit
        
    Returns:
        float: Conversion factor or 1.0 if no conversion needed/available
    """
    # Normalize units
    from_unit = normalize_text(from_unit) if from_unit else ""
    to_unit = normalize_text(to_unit) if to_unit else ""
    
    # If units are the same or missing, no conversion needed
    if from_unit == to_unit or not from_unit or not to_unit:
        return 1.0
    
    # Common unit conversions for weight
    weight_conversions = {
        ('kg', 'g'): 1000,
        ('g', 'kg'): 0.001,
        ('lb', 'kg'): 0.45359237,
        ('kg', 'lb'): 2.20462262,
        ('lb', 'g'): 453.59237,
        ('g', 'lb'): 0.00220462,
        ('oz', 'g'): 28.3495,
        ('g', 'oz'): 0.035274,
        ('lb', 'oz'): 16,
        ('oz', 'lb'): 0.0625
    }
    
    # Common unit conversions for volume
    volume_conversions = {
        ('l', 'ml'): 1000,
        ('ml', 'l'): 0.001,
        ('gal', 'l'): 3.78541,
        ('l', 'gal'): 0.264172,
        ('qt', 'l'): 0.946353,
        ('l', 'qt'): 1.05669,
        ('pt', 'l'): 0.473176,
        ('l', 'pt'): 2.11338,
        ('cup', 'ml'): 236.588,
        ('ml', 'cup'): 0.00423,
        ('tbsp', 'ml'): 14.7868,
        ('ml', 'tbsp'): 0.067628,
        ('tsp', 'ml'): 4.92892,
        ('ml', 'tsp'): 0.202884
    }
    
    # Handle common unit abbreviations and alternative spellings
    unit_map = {
        'kilogram': 'kg', 'kilograms': 'kg', 'kilo': 'kg', 'kilos': 'kg',
        'gram': 'g', 'grams': 'g', 'gm': 'g', 'gms': 'g', 'gr': 'g',
        'pound': 'lb', 'pounds': 'lb', 'lbs': 'lb',
        'ounce': 'oz', 'ounces': 'oz', 'ozs': 'oz',
        'liter': 'l', 'liters': 'l', 'litre': 'l', 'litres': 'l',
        'milliliter': 'ml', 'milliliters': 'ml', 'millilitre': 'ml', 'millilitres': 'ml',
        'gallon': 'gal', 'gallons': 'gal',
        'quart': 'qt', 'quarts': 'qt',
        'pint': 'pt', 'pints': 'pt',
        'tablespoon': 'tbsp', 'tablespoons': 'tbsp', 'tbsps': 'tbsp', 'tbs': 'tbsp',
        'teaspoon': 'tsp', 'teaspoons': 'tsp', 'tsps': 'tsp',
        'piece': 'pc', 'pieces': 'pc', 'pcs': 'pc',
        'each': 'ea',
        'number': 'nos', 'no': 'nos', 'num': 'nos',
        'package': 'pkg', 'packages': 'pkg', 'pack': 'pkg', 'pkt': 'pkg',
        'bottle': 'btl', 'bottles': 'btl',
        'box': 'bx', 'boxes': 'bx',
        'can': 'cn', 'cans': 'cn',
        'jar': 'jr', 'jars': 'jr',
        'portion': 'por', 'portions': 'por'
    }
    
    # Map to standard unit codes
    from_std = unit_map.get(from_unit, from_unit)
    to_std = unit_map.get(to_unit, to_unit)
    
    # Check for direct conversion
    if (from_std, to_std) in weight_conversions:
        return weight_conversions[(from_std, to_std)]
    elif (from_std, to_std) in volume_conversions:
        return volume_conversions[(from_std, to_std)]
    
    # No conversion found, return 1.0 as default
    return 1.0

def match_inventory_items(receipt_items, inventory_items, threshold=0.7):
    """
    Match receipt items to inventory items based on name similarity
    
    Args:
        receipt_items (list): List of receipt items with 'item_code' and 'name'
        inventory_items (list): List of inventory items with 'item_code' and 'name'
        threshold (float): Minimum similarity score to consider a match
        
    Returns:
        dict: Mapping of receipt item codes to inventory item codes
    """
    matches = {}
    
    # Convert any string items to dictionaries
    processed_receipt_items = []
    for item in receipt_items:
        if isinstance(item, dict):
            processed_receipt_items.append(item)
        elif isinstance(item, str):
            try:
                # Try to parse as JSON if it's a string
                import json
                item_dict = json.loads(item)
                processed_receipt_items.append(item_dict)
            except:
                # If can't parse, create a simple dict with only name
                processed_receipt_items.append({'name': item})
    
    # Same with inventory items
    processed_inventory_items = []
    for item in inventory_items:
        if isinstance(item, dict):
            processed_inventory_items.append(item)
        elif isinstance(item, str):
            try:
                # Try to parse as JSON if it's a string
                import json
                item_dict = json.loads(item)
                processed_inventory_items.append(item_dict)
            except:
                # If can't parse, create a simple dict with only name
                processed_inventory_items.append({'name': item})
    
    # Create normalized name lookup for inventory
    inventory_lookup = {}
    for item in processed_inventory_items:
        item_code = item.get('item_code', '')
        name = item.get('name', '')
        if name:
            normalized_name = normalize_text(name)
            inventory_lookup[item_code] = {
                'normalized_name': normalized_name,
                'original_name': name,
                'item': item
            }
    
    # Try direct item code matching first
    for receipt_item in processed_receipt_items:
        receipt_code = receipt_item.get('item_code', '')
        receipt_name = receipt_item.get('name', '')
        
        # If receipt code matches inventory code directly
        if receipt_code and receipt_code in inventory_lookup:
            matches[receipt_code] = receipt_code
            continue
        
        # If no direct match, try matching by name
        if receipt_name:
            best_match = None
            best_score = threshold  # Only consider matches above threshold
            
            normalized_receipt_name = normalize_text(receipt_name)
            
            for inv_code, inv_data in inventory_lookup.items():
                if not inv_data['normalized_name']:
                    continue
                
                similarity = calculate_similarity(
                    normalized_receipt_name, 
                    inv_data['normalized_name']
                )
                
                if similarity > best_score:
                    best_score = similarity
                    best_match = inv_code
            
            # If found a good match
            if best_match:
                matches[receipt_code] = best_match
    
    return matches

def update_recipe_costs(recipes, inventory_items, receipt_items, match_threshold=0.7):
    """
    Update recipe costs based on receipt data and inventory items
    
    Args:
        recipes (list): List of recipe dictionaries
        inventory_items (list): List of inventory item dictionaries
        receipt_items (list): List of receipt item dictionaries
        match_threshold (float, optional): Threshold for fuzzy matching of ingredient names (0.0-1.0)
        
    Returns:
        tuple: (updated_recipes, update_summary)
    """
    if not recipes or not inventory_items or not receipt_items:
        return recipes, {"error": "Missing required data"}
    
    # Track changes for reporting
    update_summary = {
        "recipes_updated": 0,
        "ingredients_updated": 0,
        "total_cost_before": 0,
        "total_cost_after": 0,
        "price_changes": []
    }
    
    # Match receipt items to inventory items
    item_matches = match_inventory_items(receipt_items, inventory_items, threshold=match_threshold)
    
    # Convert receipt items to processed form
    processed_receipt_items = []
    for item in receipt_items:
        if isinstance(item, dict):
            processed_receipt_items.append(item)
        elif isinstance(item, str):
            try:
                # Try to parse as JSON if it's a string
                import json
                item_dict = json.loads(item)
                processed_receipt_items.append(item_dict)
            except:
                # If can't parse, create a simple dict with only name
                processed_receipt_items.append({'name': item})
                
    # Build lookup of receipt prices by matched inventory item code
    price_lookup = {}
    for receipt_item in processed_receipt_items:
        receipt_code = receipt_item.get('item_code', '')
        
        # Skip if no code or no match found
        if not receipt_code or receipt_code not in item_matches:
            continue
        
        # Get the matched inventory code
        inventory_code = item_matches[receipt_code]
        
        # Store the new unit price and unit from receipt
        price = receipt_item.get('unit_cost', 0) or receipt_item.get('unit_price', 0)
        unit = receipt_item.get('unit', '')
        
        if price > 0:
            price_lookup[inventory_code] = {
                'price': price,
                'unit': unit
            }
    
    # Convert inventory items to processed form if not already processed
    processed_inventory_items = []
    for item in inventory_items:
        if isinstance(item, dict):
            processed_inventory_items.append(item)
        elif isinstance(item, str):
            try:
                # Try to parse as JSON if it's a string
                import json
                item_dict = json.loads(item)
                processed_inventory_items.append(item_dict)
            except:
                # If can't parse, create a simple dict with only name
                processed_inventory_items.append({'name': item})
    
    # Get ingredient details from inventory lookup
    inventory_lookup = {item.get('item_code', ''): item for item in processed_inventory_items}
    
    # Update recipe costs
    updated_recipes = []
    
    for recipe in recipes:
        original_total_cost = recipe.get('total_cost', 0)
        update_summary['total_cost_before'] += original_total_cost
        
        # Track if this recipe was modified
        recipe_modified = False
        recipe_ingredients_updated = 0
        
        # Update ingredients
        ingredients = recipe.get('ingredients', [])
        updated_ingredients = []
        
        for ingredient in ingredients:
            # Clone the ingredient to avoid modifying the original
            updated_ingredient = ingredient.copy()
            
            # Get item code (if any)
            item_code = updated_ingredient.get('item_code', '')
            
            # If item has code and it's in our price lookup
            if item_code and item_code in price_lookup:
                new_price_data = price_lookup[item_code]
                inventory_item = inventory_lookup.get(item_code, {})
                
                # Get original values
                original_unit_cost = updated_ingredient.get('unit_cost', 0)
                original_total_cost = updated_ingredient.get('total_cost', 0)
                
                # Get units for conversion
                receipt_unit = new_price_data.get('unit', '')
                ingredient_unit = updated_ingredient.get('unit', '')
                
                # Get conversion factor
                conversion_factor = get_conversion_factor(receipt_unit, ingredient_unit)
                
                # Calculate new unit cost
                new_unit_cost = new_price_data['price'] * conversion_factor
                
                # Calculate quantity to use for total cost
                qty_to_use = 0
                if 'net_qty' in updated_ingredient and updated_ingredient['net_qty'] > 0:
                    qty_to_use = updated_ingredient['net_qty']
                elif 'qty' in updated_ingredient and updated_ingredient['qty'] > 0:
                    qty_to_use = updated_ingredient['qty']
                
                # Calculate new total cost
                new_total_cost = new_unit_cost * qty_to_use if qty_to_use > 0 else 0
                
                # Update the ingredient if price changed significantly (>0.1%)
                price_change_percent = 0
                if original_unit_cost > 0:
                    price_change_percent = ((new_unit_cost - original_unit_cost) / original_unit_cost) * 100
                
                if abs(price_change_percent) > 0.1:
                    # Update the ingredient
                    updated_ingredient['unit_cost'] = new_unit_cost
                    updated_ingredient['total_cost'] = new_total_cost
                    
                    # Track change
                    update_summary['ingredients_updated'] += 1
                    recipe_ingredients_updated += 1
                    recipe_modified = True
                    
                    # Record price change
                    update_summary['price_changes'].append({
                        'recipe_name': recipe.get('name', 'Unknown'),
                        'ingredient_name': updated_ingredient.get('name', 'Unknown'),
                        'item_code': item_code,
                        'original_price': original_unit_cost,
                        'new_price': new_unit_cost,
                        'change_percent': price_change_percent
                    })
            
            updated_ingredients.append(updated_ingredient)
        
        # Update recipe with modified ingredients
        updated_recipe = recipe.copy()
        updated_recipe['ingredients'] = updated_ingredients
        
        # Recalculate total cost if ingredients were updated
        if recipe_modified:
            new_total_cost = sum(ing.get('total_cost', 0) for ing in updated_ingredients)
            updated_recipe['total_cost'] = new_total_cost
            
            # Update cost percentage if we have a sales price
            if 'sales_price' in updated_recipe and updated_recipe['sales_price'] > 0:
                updated_recipe['cost_percentage'] = (new_total_cost / updated_recipe['sales_price']) * 100
            
            update_summary['recipes_updated'] += 1
        
        updated_recipes.append(updated_recipe)
        update_summary['total_cost_after'] += updated_recipe.get('total_cost', 0)
    
    # Calculate overall changes
    if update_summary['total_cost_before'] > 0:
        update_summary['overall_change_percent'] = (
            (update_summary['total_cost_after'] - update_summary['total_cost_before']) / 
            update_summary['total_cost_before'] * 100
        )
    else:
        update_summary['overall_change_percent'] = 0
    
    return updated_recipes, update_summary

def process_receipt_data(df, item_code_col=None, name_col=None, unit_col=None, unit_price_col=None):
    """
    Process receipt data from a DataFrame into a standardized format
    
    Args:
        df (DataFrame): Receipt data
        item_code_col (str): Column name for item code
        name_col (str): Column name for item name
        unit_col (str): Column name for unit
        unit_price_col (str): Column name for unit price
        
    Returns:
        list: Standardized receipt items
    """
    # Default column mapping for ABGN format
    column_mapping = {
        'item_code': item_code_col or 'Item Code',
        'name': name_col or 'Description',
        'unit': unit_col or 'Unit',
        'unit_price': unit_price_col or 'Rate'
    }
    
    # Try to guess columns if not specified
    if not item_code_col:
        possible_code_cols = ['Code', 'Item Code', 'ItemCode', 'SKU', 'Product Code', 'ID']
        for col in possible_code_cols:
            if col in df.columns:
                column_mapping['item_code'] = col
                break
    
    if not name_col:
        possible_name_cols = ['Description', 'Item Name', 'Name', 'Product', 'Product Name', 'Item Description']
        for col in possible_name_cols:
            if col in df.columns:
                column_mapping['name'] = col
                break
    
    if not unit_col:
        possible_unit_cols = ['Unit', 'UOM', 'U/M', 'Unit of Measure', 'UofM', 'Measure']
        for col in possible_unit_cols:
            if col in df.columns:
                column_mapping['unit'] = col
                break
    
    if not unit_price_col:
        possible_price_cols = ['Rate', 'Unit Price', 'Price', 'Cost', 'Unit Cost', 'Amount', 'Rate/Amt']
        for col in possible_price_cols:
            if col in df.columns:
                column_mapping['unit_price'] = col
                break
    
    # Create standardized receipt items
    receipt_items = []
    
    for _, row in df.iterrows():
        try:
            item = {}
            
            # Extract values using the mapping
            for key, col in column_mapping.items():
                if col in df.columns:
                    item[key] = row[col]
            
            # Skip items without a name
            if 'name' not in item or not item['name']:
                continue
            
            # Ensure numeric fields are numeric
            if 'unit_price' in item:
                try:
                    item['unit_cost'] = float(item['unit_price'])
                except (ValueError, TypeError):
                    item['unit_cost'] = 0
            
            receipt_items.append(item)
            
        except Exception as e:
            st.warning(f"Error processing receipt row: {str(e)}")
    
    return receipt_items

def display_price_update_summary(summary):
    """
    Display a summary of price updates
    
    Args:
        summary (dict): Update summary data
    """
    st.subheader("Price Update Summary")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("Recipes Updated", summary.get('recipes_updated', 0))
    
    with col2:
        st.metric("Ingredients Updated", summary.get('ingredients_updated', 0))
    
    with col3:
        change_percent = summary.get('overall_change_percent', 0)
        st.metric("Overall Cost Change", f"{change_percent:.2f}%", 
                  delta=f"{change_percent:.2f}%", 
                  delta_color="inverse")
    
    # Display before/after costs
    st.write("**Cost Before:** ${:,.2f}".format(summary.get('total_cost_before', 0)))
    st.write("**Cost After:** ${:,.2f}".format(summary.get('total_cost_after', 0)))
    
    # Display price changes
    price_changes = summary.get('price_changes', [])
    if price_changes:
        st.subheader("Price Changes")
        
        # Convert to DataFrame for display
        changes_df = pd.DataFrame(price_changes)
        
        # Format DataFrame
        changes_df['original_price'] = changes_df['original_price'].apply(lambda x: f"${x:.2f}")
        changes_df['new_price'] = changes_df['new_price'].apply(lambda x: f"${x:.2f}")
        changes_df['change_percent'] = changes_df['change_percent'].apply(lambda x: f"{x:.2f}%")
        
        # Define columns to display
        display_cols = ['recipe_name', 'ingredient_name', 'item_code', 
                         'original_price', 'new_price', 'change_percent']
        
        # Rename columns for display
        display_df = changes_df[display_cols].copy()
        display_df.columns = ['Recipe', 'Ingredient', 'Item Code', 
                              'Original Price', 'New Price', 'Change']
        
        st.dataframe(display_df)
    
    if 'error' in summary:
        st.error(summary['error'])