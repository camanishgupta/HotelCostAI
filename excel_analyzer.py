"""
Excel Analyzer Module for ABGN Hotel Cost Control

This module provides functions to analyze ABGN format Excel files and extract:
1. Recipes and costings
2. Inventory data 
3. Sales data

It uses comprehensive extraction techniques for handling complex and inconsistent Excel files.
"""

import pandas as pd
import streamlit as st
from datetime import datetime
import os
import re
import json

from improved_recipe_extractor import extract_all_recipes

def analyze_recipe_file(file_path):
    """
    Analyze a recipe costing Excel file and extract all recipes
    
    Args:
        file_path (str): Path to the Excel file
        
    Returns:
        dict: Analysis results including extracted recipes
    """
    try:
        st.info(f"Starting analysis of recipe file: {file_path}")
        
        # Use the comprehensive extraction function
        recipes = extract_all_recipes(file_path)
        
        # Prepare results
        results = {
            "file_path": file_path,
            "file_name": os.path.basename(file_path),
            "analysis_date": datetime.now().isoformat(),
            "recipe_count": len(recipes),
            "recipes": recipes
        }
        
        # Get summary of recipes by category
        categories = {}
        for recipe in recipes:
            category = recipe.get("category", "Unknown")
            if category not in categories:
                categories[category] = 0
            categories[category] += 1
        
        results["categories"] = categories
        
        # Calculate statistics
        if recipes:
            total_cost = sum(recipe.get("total_cost", 0) for recipe in recipes)
            avg_cost = total_cost / len(recipes) if recipes else 0
            max_cost = max(recipe.get("total_cost", 0) for recipe in recipes)
            min_cost = min(recipe.get("total_cost", 0) for recipe in recipes)
            
            total_sales_price = sum(recipe.get("sales_price", 0) for recipe in recipes)
            avg_sales_price = total_sales_price / len(recipes) if recipes else 0
            
            avg_cost_percentage = sum(recipe.get("cost_percentage", 0) for recipe in recipes) / len(recipes) if recipes else 0
            
            results["statistics"] = {
                "total_cost": total_cost,
                "avg_cost": avg_cost,
                "max_cost": max_cost,
                "min_cost": min_cost,
                "total_sales_price": total_sales_price,
                "avg_sales_price": avg_sales_price,
                "avg_cost_percentage": avg_cost_percentage
            }
        
        return results
    
    except Exception as e:
        st.error(f"Error analyzing recipe file: {str(e)}")
        import traceback
        st.error(traceback.format_exc())
        return {"error": str(e)}

def analyze_inventory_file(file_path):
    """
    Analyze an inventory Excel file and extract all inventory items
    
    Args:
        file_path (str): Path to the Excel file
        
    Returns:
        dict: Analysis results including extracted inventory items
    """
    try:
        st.info(f"Starting analysis of inventory file: {file_path}")
        
        # For now, just use the basic extraction function from abgn_extractor
        # Later we can enhance this with more comprehensive extraction
        from utils.abgn_extractor import extract_inventory
        inventory_items = extract_inventory(file_path)
        
        # Prepare results
        results = {
            "file_path": file_path,
            "file_name": os.path.basename(file_path),
            "analysis_date": datetime.now().isoformat(),
            "item_count": len(inventory_items),
            "inventory_items": inventory_items
        }
        
        # Get summary of items by category
        categories = {}
        for item in inventory_items:
            category = item.get("category", "Unknown")
            if category not in categories:
                categories[category] = 0
            categories[category] += 1
        
        results["categories"] = categories
        
        return results
    
    except Exception as e:
        st.error(f"Error analyzing inventory file: {str(e)}")
        import traceback
        st.error(traceback.format_exc())
        return {"error": str(e)}

def analyze_sales_file(file_path):
    """
    Analyze a sales Excel file and extract all sales records
    
    Args:
        file_path (str): Path to the Excel file
        
    Returns:
        dict: Analysis results including extracted sales records
    """
    try:
        st.info(f"Starting analysis of sales file: {file_path}")
        
        # For now, just use the basic extraction function from abgn_extractor
        # Later we can enhance this with more comprehensive extraction
        from utils.abgn_extractor import extract_sales
        sales_records = extract_sales(file_path)
        
        # Prepare results
        results = {
            "file_path": file_path,
            "file_name": os.path.basename(file_path),
            "analysis_date": datetime.now().isoformat(),
            "record_count": len(sales_records),
            "sales_records": sales_records
        }
        
        # Calculate statistics if there are records
        if sales_records:
            total_quantity = sum(record.get("quantity", 0) for record in sales_records)
            total_revenue = sum(record.get("revenue", 0) for record in sales_records)
            total_cost = sum(record.get("cost", 0) for record in sales_records)
            
            # Get unique dates
            dates = set()
            for record in sales_records:
                if "date" in record and record["date"]:
                    dates.add(record["date"])
            
            # Get unique items
            items = set()
            for record in sales_records:
                if "item_name" in record and record["item_name"]:
                    items.add(record["item_name"])
            
            results["statistics"] = {
                "total_quantity": total_quantity,
                "total_revenue": total_revenue,
                "total_cost": total_cost,
                "total_profit": total_revenue - total_cost,
                "date_range": len(dates),
                "unique_items": len(items)
            }
        
        return results
    
    except Exception as e:
        st.error(f"Error analyzing sales file: {str(e)}")
        import traceback
        st.error(traceback.format_exc())
        return {"error": str(e)}

def save_analysis_results(results, output_path):
    """
    Save analysis results to a JSON file
    
    Args:
        results (dict): The analysis results to save
        output_path (str): Path to save the results
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        with open(output_path, 'w') as f:
            json.dump(results, f, indent=4)
        st.success(f"Saved analysis results to {output_path}")
        return True
    except Exception as e:
        st.error(f"Error saving analysis results: {str(e)}")
        return False

def batch_analyze_directory(directory, output_directory="data"):
    """
    Analyze all Excel files in a directory
    
    Args:
        directory (str): Directory containing Excel files
        output_directory (str): Directory to save results
        
    Returns:
        dict: Results of analyzing all files
    """
    try:
        if not os.path.exists(output_directory):
            os.makedirs(output_directory)
            
        st.info(f"Starting batch analysis of all Excel files in {directory}")
        
        # Find all Excel files
        excel_files = []
        for file in os.listdir(directory):
            if file.endswith(('.xlsx', '.xls')):
                excel_files.append(os.path.join(directory, file))
        
        if not excel_files:
            st.warning(f"No Excel files found in {directory}")
            return {"error": "No Excel files found"}
        
        st.info(f"Found {len(excel_files)} Excel files")
        
        # Analyze each file
        results = {
            "directory": directory,
            "analysis_date": datetime.now().isoformat(),
            "file_count": len(excel_files),
            "recipes": [],
            "inventory": [],
            "sales": []
        }
        
        for file_path in excel_files:
            try:
                file_name = os.path.basename(file_path)
                st.info(f"Analyzing {file_name}")
                
                # Try to detect file type
                file_type = "unknown"
                if "recipe" in file_name.lower() or "menu" in file_name.lower() or "cost" in file_name.lower():
                    file_type = "recipe"
                elif "inventory" in file_name.lower() or "store" in file_name.lower() or "stock" in file_name.lower():
                    file_type = "inventory"
                elif "sales" in file_name.lower() or "revenue" in file_name.lower():
                    file_type = "sales"
                
                # Ask user to confirm file type if unsure
                if file_type == "unknown":
                    st.warning(f"Could not automatically determine file type for {file_name}")
                    # In a real app, we would ask the user to confirm the type
                    # For now, we'll just skip this file
                    continue
                
                # Analyze based on file type
                if file_type == "recipe":
                    result = analyze_recipe_file(file_path)
                    if "error" not in result:
                        results["recipes"].append(result)
                        output_path = os.path.join(output_directory, f"{file_name.split('.')[0]}_recipes.json")
                        save_analysis_results(result, output_path)
                
                elif file_type == "inventory":
                    result = analyze_inventory_file(file_path)
                    if "error" not in result:
                        results["inventory"].append(result)
                        output_path = os.path.join(output_directory, f"{file_name.split('.')[0]}_inventory.json")
                        save_analysis_results(result, output_path)
                
                elif file_type == "sales":
                    result = analyze_sales_file(file_path)
                    if "error" not in result:
                        results["sales"].append(result)
                        output_path = os.path.join(output_directory, f"{file_name.split('.')[0]}_sales.json")
                        save_analysis_results(result, output_path)
            
            except Exception as e:
                st.error(f"Error analyzing {file_name}: {str(e)}")
        
        # Save summary of all results
        summary_path = os.path.join(output_directory, "batch_analysis_summary.json")
        save_analysis_results(results, summary_path)
        
        return results
    
    except Exception as e:
        st.error(f"Error in batch analysis: {str(e)}")
        import traceback
        st.error(traceback.format_exc())
        return {"error": str(e)}

if __name__ == "__main__":
    # This will only run when the script is executed directly
    st.title("Excel Analyzer for ABGN Hotel Cost Control")
    
    st.write("This tool helps analyze ABGN format Excel files for hotel cost control")
    
    # File upload section
    uploaded_file = st.file_uploader("Upload an Excel file", type=["xlsx", "xls"])
    
    if uploaded_file:
        # Save the uploaded file
        file_path = os.path.join("uploaded_files", uploaded_file.name)
        if not os.path.exists("uploaded_files"):
            os.makedirs("uploaded_files")
        
        with open(file_path, "wb") as f:
            f.write(uploaded_file.getbuffer())
        
        st.success(f"File uploaded successfully: {uploaded_file.name}")
        
        # Analyze the file
        file_type = st.selectbox("What type of data is in this file?", 
                                ["Recipe Cost", "Inventory", "Sales"])
        
        if st.button("Analyze File"):
            if file_type == "Recipe Cost":
                results = analyze_recipe_file(file_path)
                if "error" not in results:
                    st.success(f"Successfully extracted {results['recipe_count']} recipes")
                    st.write("Categories:", results["categories"])
                    if "statistics" in results:
                        st.write("Statistics:", results["statistics"])
                    
                    # Show a sample of the recipes
                    if results["recipes"]:
                        st.write("Sample recipe:")
                        st.json(results["recipes"][0])
            
            elif file_type == "Inventory":
                results = analyze_inventory_file(file_path)
                if "error" not in results:
                    st.success(f"Successfully extracted {results['item_count']} inventory items")
                    st.write("Categories:", results["categories"])
                    
                    # Show a sample of the inventory items
                    if results["inventory_items"]:
                        st.write("Sample inventory item:")
                        st.json(results["inventory_items"][0])
            
            elif file_type == "Sales":
                results = analyze_sales_file(file_path)
                if "error" not in results:
                    st.success(f"Successfully extracted {results['record_count']} sales records")
                    if "statistics" in results:
                        st.write("Statistics:", results["statistics"])
                    
                    # Show a sample of the sales records
                    if results["sales_records"]:
                        st.write("Sample sales record:")
                        st.json(results["sales_records"][0])