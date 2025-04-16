"""
Receipt Processor Module for ABGN Hotel Cost Control

This module provides specialized functions to process ABGN item receipt files
and extract item codes, descriptions, units, and prices.
"""

import pandas as pd
import numpy as np
import streamlit as st
from datetime import datetime
import os
import re
import io

def detect_receipt_columns(df):
    """
    Automatically detect relevant columns in a receipt dataframe
    
    Args:
        df (DataFrame): The receipt dataframe
        
    Returns:
        dict: Detected column mappings
    """
    mappings = {
        'item_code': None,
        'name': None,
        'unit': None,
        'unit_price': None,
        'quantity': None,
        'total_amount': None,
        'date': None
    }
    
    # Convert column names to lowercase for easier matching
    cols_lower = [str(col).lower() for col in df.columns]
    
    # Item Code patterns for ABGN format and general formats
    code_patterns = [
        'item code', 'code', 'sku', 'product code', 'product id', 'part', 'part no',
        'item number', 'item#', 'art#', 'article', 'art. no.', 'catalog#', 'item no',
        'abgn code', 'id', 'ref', 'reference', 'material code', 'material number'
    ]
    for pattern in code_patterns:
        for i, col in enumerate(cols_lower):
            if pattern in col:
                mappings['item_code'] = df.columns[i]
                break
        if mappings['item_code']:
            break
    
    # Item Name/Description patterns for ABGN format and general formats
    name_patterns = [
        'item name', 'description', 'desc', 'product name', 'product desc', 'particular',
        'item description', 'name', 'goods', 'article', 'material', 'particular', 'item',
        'material description', 'product', 'commodity', 'menu item', 'food item'
    ]
    for pattern in name_patterns:
        for i, col in enumerate(cols_lower):
            if pattern in col:
                mappings['name'] = df.columns[i]
                break
        if mappings['name']:
            break
    
    # Unit patterns for ABGN format and general formats
    unit_patterns = [
        'unit', 'uom', 'measure', 'u/m', 'units', 'unit of measure',
        'pack', 'packaging', 'pack size', 'pkg', 'size', 'unit size',
        'basis', 'base unit', 'pur. unit', 'packing', 'standard unit'
    ]
    for pattern in unit_patterns:
        for i, col in enumerate(cols_lower):
            if pattern in col and not 'price' in col and not 'rate' in col and not 'cost' in col:
                mappings['unit'] = df.columns[i]
                break
        if mappings['unit']:
            break
    
    # Unit Price patterns for ABGN format and general formats
    price_patterns = [
        'rate', 'unit price', 'price', 'unit rate', 'unit cost', 'at amount',
        'price/unit', 'amount', 'cost', 'rate/amt', 'rate/unit', 'unit value', 
        'basic rate', 'net rate', 'net price', 'standard price', 'unit rate',
        'effective price', 'per unit', 'nett amount'
    ]
    for pattern in price_patterns:
        for i, col in enumerate(cols_lower):
            if pattern in col:
                mappings['unit_price'] = df.columns[i]
                break
        if mappings['unit_price']:
            break
    
    # Quantity patterns for ABGN format and general formats
    qty_patterns = [
        'qty', 'quantity', 'pcs', 'nos', 'pieces', 'count', 'no. of', 
        'number of', 'amt', 'ord qty', 'ordered qty', 'received qty',
        'gr qty', 'deliv qty', 'issue qty', 'receipt qty', 'stock qty',
        'actual qty', 'inventory qty', 'purchased qty', 'delivered qty',
        'received amount', 'batch qty', 'billed qty', 'net qty'
    ]
    for pattern in qty_patterns:
        for i, col in enumerate(cols_lower):
            if pattern in col and not 'unit' in col:
                mappings['quantity'] = df.columns[i]
                break
        if mappings['quantity']:
            break
    
    # Total Amount patterns for ABGN format and general formats
    amount_patterns = [
        'total amount', 'amount', 'total', 'line total', 'ext amt', 'extension',
        'total price', 'line amount', 'net amount', 'final amount', 'value',
        'total value', 'extended price', 'net value', 'extended amount',
        'sub-total', 'gross amount', 'gross total', 'grand total', 'amt total'
    ]
    for pattern in amount_patterns:
        for i, col in enumerate(cols_lower):
            if pattern in col:
                mappings['total_amount'] = df.columns[i]
                break
        if mappings['total_amount']:
            break
    
    # Date patterns for ABGN format and general formats
    date_patterns = [
        'date', 'receipt date', 'gr date', 'transaction date', 'posting date',
        'doc date', 'document date', 'entry date', 'order date', 'created date',
        'invoice date', 'receiving date', 'purchase date', 'issue date', 'received date',
        'delivery date', 'scheduled date', 'arrival date', 'po date', 'bill date',
        'receiving date', 'process date', 'voucher date', 'accounting date'
    ]
    for pattern in date_patterns:
        for i, col in enumerate(cols_lower):
            if pattern in col:
                mappings['date'] = df.columns[i]
                break
        if mappings['date']:
            break
    
    return mappings

def process_abgn_receipt(file_path, sheet_name=None):
    """
    Process ABGN receipt file and extract items with prices
    
    Args:
        file_path (str): Path to the receipt file
        sheet_name (str, optional): Specific sheet to process
        
    Returns:
        list: Extracted receipt items
    """
    try:
        st.info(f"Processing ABGN receipt file: {file_path}")
        
        # Try to open the Excel file with different engines
        try:
            # First try with openpyxl
            xls = pd.ExcelFile(file_path, engine='openpyxl')
        except Exception as e:
            st.warning(f"Failed to open with openpyxl: {str(e)}")
            # Try with xlrd as fallback
            try:
                xls = pd.ExcelFile(file_path, engine='xlrd')
            except Exception as e2:
                st.error(f"Failed to open with both engines: {str(e2)}")
                return []
        
        # Get sheet names
        sheet_names = xls.sheet_names
        
        if not sheet_names:
            st.warning("No sheets found in the file")
            return []
        
        # If no specific sheet name, handle each sheet
        if sheet_name is None:
            all_items = []
            
            for sheet in sheet_names:
                # Skip sheets that are likely summary or metadata
                if sheet.lower() in ['summary', 'contents', 'index', 'toc']:
                    continue
                
                sheet_items = process_receipt_sheet(file_path, sheet)
                if sheet_items:
                    all_items.extend(sheet_items)
                    st.success(f"Extracted {len(sheet_items)} items from sheet: {sheet}")
            
            # Deduplicate items based on item code
            unique_codes = set()
            unique_items = []
            
            for item in all_items:
                code = item.get('item_code', '')
                if code and code not in unique_codes:
                    unique_codes.add(code)
                    unique_items.append(item)
                elif not code:
                    # For items without code, include them all
                    unique_items.append(item)
            
            return unique_items
        else:
            # Process specific sheet
            return process_receipt_sheet(file_path, sheet_name)
    
    except Exception as e:
        st.error(f"Error processing receipt file: {str(e)}")
        import traceback
        st.error(traceback.format_exc())
        return []

def process_receipt_sheet(file_path, sheet_name):
    """
    Process a single sheet from a receipt file
    
    Args:
        file_path (str): Path to the Excel file
        sheet_name (str): Name of sheet to process
        
    Returns:
        list: Processed receipt items
    """
    try:
        # Try different engines
        try:
            df = pd.read_excel(file_path, sheet_name=sheet_name, engine='openpyxl')
        except Exception:
            df = pd.read_excel(file_path, sheet_name=sheet_name, engine='xlrd')
        
        if df.empty:
            st.warning(f"Sheet {sheet_name} is empty")
            return []
        
        # Remove any completely empty rows and columns
        df = df.dropna(how='all').dropna(axis=1, how='all')
        
        # Replace NaN with empty string
        df = df.fillna('')
        
        # Detect receipt columns
        mappings = detect_receipt_columns(df)
        
        # Check if we found essential columns
        if not mappings['name'] and not mappings['item_code']:
            st.warning(f"Could not identify item name or code columns in sheet: {sheet_name}")
            return []
        
        if not mappings['unit_price']:
            st.warning(f"Could not identify unit price column in sheet: {sheet_name}")
            return []
        
        # Process rows into receipt items
        receipt_items = []
        
        # Keep track of the last valid date if date column exists
        current_date = None
        
        for _, row in df.iterrows():
            # Skip header or summary rows
            if is_header_or_summary_row(row):
                continue
            
            # Skip empty rows
            if all(val == '' for val in row):
                continue
            
            # Extract data based on the detected columns
            item = {}
            
            # Get date if available
            if mappings['date']:
                date_val = row[mappings['date']]
                if isinstance(date_val, (pd.Timestamp, datetime)):
                    current_date = date_val
                elif isinstance(date_val, str) and date_val.strip():
                    try:
                        current_date = pd.to_datetime(date_val)
                    except:
                        pass
            
            # Add date to item
            if current_date:
                item['date'] = current_date.strftime('%Y-%m-%d')
            
            # Get item code
            if mappings['item_code']:
                code_val = row[mappings['item_code']]
                if code_val and str(code_val).strip():
                    item['item_code'] = str(code_val).strip()
            
            # Get item name
            if mappings['name']:
                name_val = row[mappings['name']]
                if name_val and str(name_val).strip():
                    item['name'] = str(name_val).strip()
            
            # If we don't have a name or code, skip this row
            if 'name' not in item and 'item_code' not in item:
                continue
            
            # Get unit
            if mappings['unit']:
                unit_val = row[mappings['unit']]
                if unit_val and str(unit_val).strip():
                    item['unit'] = str(unit_val).strip()
            
            # Get unit price - handle different numeric formats
            if mappings['unit_price']:
                price_val = row[mappings['unit_price']]
                if isinstance(price_val, (int, float)) and price_val > 0:
                    item['unit_cost'] = float(price_val)
                elif isinstance(price_val, str) and price_val.strip():
                    # Try to extract number from string (e.g., "$ 10.25")
                    price_str = re.sub(r'[^\d.]', '', price_val)
                    try:
                        if price_str:
                            price_num = float(price_str)
                            if price_num > 0:
                                item['unit_cost'] = price_num
                    except ValueError:
                        pass
            
            # If we have quantity and total amount but no unit price, calculate it
            if 'unit_cost' not in item and mappings['quantity'] and mappings['total_amount']:
                qty = row[mappings['quantity']]
                total = row[mappings['total_amount']]
                
                if isinstance(qty, (int, float)) and isinstance(total, (int, float)) and qty > 0:
                    item['unit_cost'] = total / qty
            
            # Skip items without a price
            if 'unit_cost' not in item or item['unit_cost'] <= 0:
                continue
            
            # Add to receipt items
            receipt_items.append(item)
        
        return receipt_items
    
    except Exception as e:
        st.error(f"Error processing sheet {sheet_name}: {str(e)}")
        import traceback
        st.error(traceback.format_exc())
        return []

def is_header_or_summary_row(row):
    """
    Detect if a row is a header or summary row that should be skipped
    
    Args:
        row (Series): Pandas Series representing a row
        
    Returns:
        bool: True if this is a header or summary row, False otherwise
    """
    # Convert row values to strings and lowercase
    row_vals = [str(val).lower() for val in row if str(val).strip()]
    
    # Check for header indicators
    header_indicators = ['item', 'code', 'description', 'qty', 'unit', 'rate', 'amount', 'date']
    header_count = sum(1 for indicator in header_indicators if any(indicator in val for val in row_vals))
    if header_count >= 3:
        return True
    
    # Check for summary indicators
    summary_indicators = ['total', 'grand total', 'sum', 'subtotal']
    if any(indicator in ' '.join(row_vals) for indicator in summary_indicators):
        return True
    
    return False

def process_generic_receipt(df):
    """
    Process a generic DataFrame of receipt data
    
    Args:
        df (DataFrame): Receipt data
        
    Returns:
        list: Processed receipt items
    """
    # Detect receipt columns
    mappings = detect_receipt_columns(df)
    
    # Check if we found essential columns
    if not mappings['name'] and not mappings['item_code']:
        st.warning("Could not identify item name or code columns")
        return []
    
    if not mappings['unit_price']:
        st.warning("Could not identify unit price column")
        return []
    
    # Process rows into receipt items
    receipt_items = []
    
    for _, row in df.iterrows():
        # Skip header or summary rows
        if is_header_or_summary_row(row):
            continue
        
        # Skip empty rows
        if all(pd.isna(val) or val == '' for val in row):
            continue
        
        # Extract data based on the detected columns
        item = {}
        
        # Get item code
        if mappings['item_code']:
            code_val = row[mappings['item_code']]
            if not pd.isna(code_val) and str(code_val).strip():
                item['item_code'] = str(code_val).strip()
        
        # Get item name
        if mappings['name']:
            name_val = row[mappings['name']]
            if not pd.isna(name_val) and str(name_val).strip():
                item['name'] = str(name_val).strip()
        
        # If we don't have a name or code, skip this row
        if 'name' not in item and 'item_code' not in item:
            continue
        
        # Get unit
        if mappings['unit']:
            unit_val = row[mappings['unit']]
            if not pd.isna(unit_val) and str(unit_val).strip():
                item['unit'] = str(unit_val).strip()
        
        # Get unit price
        if mappings['unit_price']:
            price_val = row[mappings['unit_price']]
            if isinstance(price_val, (int, float)) and price_val > 0:
                item['unit_cost'] = float(price_val)
            elif isinstance(price_val, str) and price_val.strip():
                # Try to extract number from string (e.g., "$ 10.25")
                price_str = re.sub(r'[^\d.]', '', price_val)
                try:
                    if price_str:
                        price_num = float(price_str)
                        if price_num > 0:
                            item['unit_cost'] = price_num
                except ValueError:
                    pass
        
        # If we have quantity and total amount but no unit price, calculate it
        if 'unit_cost' not in item and mappings['quantity'] and mappings['total_amount']:
            qty = row[mappings['quantity']]
            total = row[mappings['total_amount']]
            
            if isinstance(qty, (int, float)) and isinstance(total, (int, float)) and qty > 0:
                item['unit_cost'] = total / qty
        
        # Skip items without a price
        if 'unit_cost' not in item or item['unit_cost'] <= 0:
            continue
        
        # Add to receipt items
        receipt_items.append(item)
    
    return receipt_items

def preview_receipt_columns(file_path, sheet_name=None):
    """
    Display a preview of detected columns in a receipt file
    
    Args:
        file_path (str): Path to the receipt file
        sheet_name (str, optional): Specific sheet to preview
        
    Returns:
        dict: Information about detected columns
    """
    try:
        # Try different engines
        try:
            xls = pd.ExcelFile(file_path, engine='openpyxl')
        except Exception:
            xls = pd.ExcelFile(file_path, engine='xlrd')
        
        # Get sheet names
        sheet_names = xls.sheet_names
        
        if not sheet_names:
            return {"error": "No sheets found in the file"}
        
        # If no sheet specified, use the first non-summary sheet
        if sheet_name is None:
            for sheet in sheet_names:
                if sheet.lower() not in ['summary', 'contents', 'index', 'toc']:
                    sheet_name = sheet
                    break
            
            if sheet_name is None:
                sheet_name = sheet_names[0]  # Use the first sheet if no better option
        
        # Load the sheet
        try:
            df = pd.read_excel(file_path, sheet_name=sheet_name, engine='openpyxl')
        except Exception:
            df = pd.read_excel(file_path, sheet_name=sheet_name, engine='xlrd')
        
        if df.empty:
            return {"error": f"Sheet {sheet_name} is empty"}
        
        # Remove any completely empty rows and columns
        df = df.dropna(how='all').dropna(axis=1, how='all')
        
        # Replace NaN with empty string
        df = df.fillna('')
        
        # Detect receipt columns
        mappings = detect_receipt_columns(df)
        
        # Preview of the data - first 5 rows
        preview_data = df.head(5).to_dict('records')
        
        return {
            "sheet_name": sheet_name,
            "column_mappings": mappings,
            "available_sheets": sheet_names,
            "sample_data": preview_data,
            "columns": list(df.columns)
        }
    
    except Exception as e:
        return {"error": str(e)}