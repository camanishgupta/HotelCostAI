import pandas as pd
import numpy as np
import sys

try:
    file_path = 'attached_assets/ABGN-A La Carte Menu Cost ( Updating )24,25.xlsx'
    xls = pd.ExcelFile(file_path)
    print('Sheets:', xls.sheet_names)
    
    # Read the Appetizer & Salad sheet (note: it's not called 'Appetizers')
    sheet_name = 'Appetizer & Salad'
    try:
        df = pd.read_excel(xls, sheet_name=sheet_name)
        
        # Print specific cells for better understanding
        print("\nExamining specific cells:")
        
        # NAME row
        name_label_idx = None
        for i, row in df.iterrows():
            if isinstance(row.iloc[0], str) and "NAME" in row.iloc[0]:
                name_label_idx = i
                print(f"NAME label found at row {i+1}")
                break
                
        if name_label_idx is not None:
            print(f"Row {name_label_idx+1} (NAME row):")
            for j in range(min(8, df.shape[1])):
                print(f"  Column {j} ({chr(65+j)}): {df.iloc[name_label_idx, j]}")
                
            # Recipe name should be in column B (index 1)
            print(f"\nRecipe Name at B{name_label_idx+1}: {df.iloc[name_label_idx, 1]}")
            
            # Check the row with portions
            portions_idx = name_label_idx + 1
            print(f"\nRow {portions_idx+1} (COST/PORTION row):")
            for j in range(min(8, df.shape[1])):
                print(f"  Column {j} ({chr(65+j)}): {df.iloc[portions_idx, j]}")
                
            # Next row should have the portion number
            portions_data_idx = portions_idx + 1
            print(f"\nRow {portions_data_idx+1} (Portion data row):")
            for j in range(min(8, df.shape[1])):
                print(f"  Column {j} ({chr(65+j)}): {df.iloc[portions_data_idx, j]}")
                
            # Look at specific cells:
            print(f"\nPortion at D{portions_data_idx+1}: {df.iloc[portions_data_idx, 3]}")
            print(f"Sales Price at G{portions_data_idx+1}: {df.iloc[portions_data_idx, 6]}")
            
            # Find ingredients table
            ingredients_start = None
            for i in range(name_label_idx, df.shape[0]):
                if isinstance(df.iloc[i, 0], str) and "Item Code" in df.iloc[i, 0]:
                    ingredients_start = i
                    break
                    
            if ingredients_start:
                print(f"\nIngredients table starts at row {ingredients_start+1}")
                
                # Calculate total cost from ingredients
                total_cost = 0
                for i in range(ingredients_start + 1, df.shape[0]):
                    if pd.isna(df.iloc[i, 0]) and pd.isna(df.iloc[i, 1]):
                        print(f"Ingredient table ends at row {i+1}")
                        break
                        
                    # Total cost is in column H (index 7)
                    if isinstance(df.iloc[i, 7], (int, float, np.number)) and not pd.isna(df.iloc[i, 7]):
                        total_cost += df.iloc[i, 7]
                        
                print(f"Calculated total cost from ingredients: {total_cost}")
        
        # First recipe section
        print('\nFirst Recipe Details:')
        # Find the location where "STANDARD COST RECIPE CARD" appears
        for i, row in df.iterrows():
            if isinstance(row.iloc[0], str) and "STANDARD COST RECIPE CARD" in row.iloc[0]:
                print(f"Standard Recipe Card found at row: {i}")
                
                # Name should be 2 rows down, column B
                name_row = i + 2
                name_col = 1  # Column B
                if name_row < df.shape[0]:
                    recipe_name = df.iloc[name_row, name_col]
                    print(f"Recipe Name (B{name_row+1}): {recipe_name}")
                
                # Look for portion info (D6, etc.)
                # In ABGN format, portions are typically near row with "COST/PORTION"
                for j in range(i+1, min(i+10, df.shape[0])):
                    if isinstance(df.iloc[j, 0], (int, float, np.number)):
                        # This is likely the row with portion number
                        cost_portion_row = j
                        portion_col = 3  # Column D
                        if portion_col < df.shape[1]:
                            portions = df.iloc[cost_portion_row, portion_col]
                            print(f"Portions (D{cost_portion_row+1}): {portions}")
                            
                            # Also get sales price from the same row
                            if 6 < df.shape[1]:  # Column G
                                sales_price = df.iloc[cost_portion_row+1, 6]
                                print(f"Sales Price (G{cost_portion_row+2}): {sales_price}")
                                
                                # Get cost percentage
                                if 7 < df.shape[1]:  # Column H
                                    cost_pct = df.iloc[cost_portion_row+1, 7]
                                    print(f"Cost Percentage (H{cost_portion_row+2}): {cost_pct}")
                        break
                
                # Find ingredient table start
                ingredient_start = None
                for j in range(i+1, min(i+15, df.shape[0])):
                    if isinstance(df.iloc[j, 0], str) and "Item Code" in df.iloc[j, 0]:
                        ingredient_start = j + 1
                        print(f"Ingredients start at row: {ingredient_start}")
                        break
                
                # Find ingredient table end and calculate total cost
                if ingredient_start:
                    ingredient_end = None
                    ingredients_total = 0
                    for j in range(ingredient_start, df.shape[0]):
                        # Check if we've reached a row with "Total" or blank rows
                        if pd.isna(df.iloc[j, 0]) and pd.isna(df.iloc[j, 1]):
                            total_row = j
                            print(f"End of ingredients at row: {j}")
                            
                            # Check for total in this row
                            if j < df.shape[0] and 7 < df.shape[1] and isinstance(df.iloc[j, 7], (int, float, np.number)):
                                table_total = df.iloc[j, 7]
                                print(f"Table Total Amount: {table_total}")
                            break
                            
                        # Sum up the total amount column (column H / index 7)
                        if 7 < df.shape[1] and isinstance(df.iloc[j, 7], (int, float, np.number)):
                            ingredients_total += df.iloc[j, 7]
                    
                    print(f"Calculated Sum of Ingredients: {ingredients_total}")
                
                break  # Found first recipe section
        
        # Find the second recipe section
        print('\nSecond Recipe Details:')
        found_first = False
        for i, row in df.iterrows():
            if isinstance(row.iloc[0], str) and "STANDARD COST RECIPE CARD" in row.iloc[0]:
                if found_first:
                    print(f"Second Standard Recipe Card found at row: {i}")
                    
                    # Name should be 2 rows down, column B
                    name_row = i + 2
                    name_col = 1  # Column B
                    if name_row < df.shape[0]:
                        recipe_name = df.iloc[name_row, name_col]
                        print(f"Recipe Name (B{name_row+1}): {recipe_name}")
                    
                    # Look for portion info
                    for j in range(i+1, min(i+10, df.shape[0])):
                        if isinstance(df.iloc[j, 0], (int, float, np.number)):
                            # This is likely the row with portion number
                            cost_portion_row = j
                            portion_col = 3  # Column D
                            if portion_col < df.shape[1]:
                                portions = df.iloc[cost_portion_row, portion_col]
                                print(f"Portions (D{cost_portion_row+1}): {portions}")
                            break
                    break
                else:
                    found_first = True
    
    except Exception as e:
        print(f"Error reading {sheet_name} sheet: {e}")
        print(f"Traceback: {sys.exc_info()}")
    
except Exception as e:
    print(f'Error: {e}')