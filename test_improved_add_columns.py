#!/usr/bin/env python3
"""
Test script to demonstrate the improved AddColumnsCommand
that can add multiple columns at different positions efficiently.
"""

import pandas as pd
import sys
import os

# Add the project directory to sys.path so we can import pandaplot modules
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

def test_improved_add_columns():
    """Test the improved AddColumnsCommand with multiple positions."""
    
    # Create a sample dataframe
    original_data = pd.DataFrame({
        'A': [1, 2, 3, 4, 5],
        'B': [10, 20, 30, 40, 50], 
        'C': [100, 200, 300, 400, 500],
        'D': [1000, 2000, 3000, 4000, 5000]
    })
    
    print("Original DataFrame:")
    print(original_data)
    print(f"Columns: {list(original_data.columns)}")
    print()
    
    # Simulate the scenario where columns 1, 3, and 4 were deleted
    # and we want to recreate them with specific names and default values
    
    # Column operations: [(position, name, default_value), ...]
    # Note: These will be processed from highest position to lowest
    # to avoid position shifts during insertion
    column_operations = [
        (1, "NewCol_1", "default1"),    # Insert at position 1  
        (3, "NewCol_3", 42),           # Insert at position 3
        (4, "NewCol_4", 3.14)          # Insert at position 4
    ]
    
    print("Column operations to perform:")
    for pos, name, default in column_operations:
        print(f"  Insert '{name}' at position {pos} with default value: {default}")
    print()
    
    # Simulate the improved AddColumnsCommand logic
    def simulate_improved_add_columns(data, operations):
        """Simulate the improved AddColumnsCommand logic."""
        
        # Group operations by consecutive positions (processed high to low)
        def group_consecutive_operations(ops):
            if not ops:
                return []
            
            # Sort operations by position (descending) to process from end to beginning
            sorted_ops = sorted(ops, key=lambda x: x[0], reverse=True)
            
            # For simplicity and correctness, process each operation individually
            # to avoid complex position adjustment logic when grouping
            return [[op] for op in sorted_ops]
        
        def insert_column_group(df, group, num_rows):
            """Insert a group of consecutive columns."""
            if not group:
                return df
            
            # The group is already sorted by position (descending)
            # Get the insertion position (lowest position in the group)
            insertion_pos = min(pos for pos, _, _ in group)
            
            # Validate position
            insertion_pos = max(0, min(insertion_pos, len(df.columns)))
            
            # Prepare new columns data
            new_columns_data = {}
            for pos, column_name, default_value in group:
                new_columns_data[column_name] = pd.Series([default_value] * num_rows, name=column_name)
            
            # Insert columns at the specified position
            if insertion_pos >= len(df.columns):
                # Append at end
                for column_name, column_data in new_columns_data.items():
                    df[column_name] = column_data
            else:
                # Insert at specific position
                existing_cols = list(df.columns)
                # Order new columns by their intended positions
                sorted_new_cols = sorted(group, key=lambda x: x[0])
                new_col_names = [name for _, name, _ in sorted_new_cols]
                
                # Create the new column order
                new_column_order = (existing_cols[:insertion_pos] + 
                                  new_col_names + 
                                  existing_cols[insertion_pos:])
                
                # Add the new columns to the dataframe
                for column_name, column_data in new_columns_data.items():
                    df[column_name] = column_data
                
                # Reorder columns
                df = df[new_column_order]
            
            return df
        
        # Group operations by consecutive positions
        operation_groups = group_consecutive_operations(operations)
        
        print("Operation groups (processed from end to beginning):")
        for i, group in enumerate(operation_groups):
            print(f"  Group {i+1}: {group}")
        print()
        
        # Process groups from end to beginning to avoid position shifts
        result_data = data.copy()
        num_rows = len(result_data)
        
        for group in operation_groups:
            print(f"Processing group: {group}")
            result_data = insert_column_group(result_data, group, num_rows)
            print(f"Result after group: {list(result_data.columns)}")
            print()
        
        return result_data
    
    # Test the improved logic
    result = simulate_improved_add_columns(original_data, column_operations)
    
    print("Final result:")
    print(result)
    print(f"Final columns: {list(result.columns)}")
    print()
    
    # Verify the positions
    expected_columns = ['A', 'NewCol_1', 'B', 'NewCol_3', 'NewCol_4', 'C', 'D']
    actual_columns = list(result.columns)
    
    print("Verification:")
    print(f"Expected columns: {expected_columns}")
    print(f"Actual columns:   {actual_columns}")
    print(f"Match: {expected_columns == actual_columns}")
    
    # Show default values were applied correctly
    print("\nDefault values verification:")
    print(f"NewCol_1 values: {result['NewCol_1'].tolist()}")
    print(f"NewCol_3 values: {result['NewCol_3'].tolist()}")
    print(f"NewCol_4 values: {result['NewCol_4'].tolist()}")

if __name__ == "__main__":
    test_improved_add_columns()
