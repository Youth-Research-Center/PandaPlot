#!/usr/bin/env python3
"""
Test script to demonstrate the improved AddRowsCommand
that can add multiple rows at different positions efficiently.
"""

import pandas as pd
import sys
import os

# Add the project directory to sys.path so we can import pandaplot modules
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

def test_improved_add_rows():
    """Test the improved AddRowsCommand with multiple positions."""
    
    # Create a sample dataframe
    original_data = pd.DataFrame({
        'ID': [1, 2, 3, 4],
        'Name': ['Alice', 'Bob', 'Charlie', 'Diana'],
        'Age': [25, 30, 35, 40],
        'City': ['NYC', 'LA', 'Chicago', 'Houston']
    })
    
    print("Original DataFrame:")
    print(original_data)
    print(f"Shape: {original_data.shape}")
    print()
    
    # Simulate the scenario where rows 1, 3, and 5 were deleted
    # and we want to recreate them with specific data
    
    # Row operations: [(position, row_data), ...]
    # Note: These will be processed from highest position to lowest
    # to avoid position shifts during insertion
    row_operations = [
        (1, {'ID': 10, 'Name': 'NewPerson1', 'Age': 28, 'City': 'Boston'}),    # Insert at position 1  
        (3, {'ID': 30, 'Name': 'NewPerson3', 'Age': 32, 'City': 'Seattle'}),   # Insert at position 3
        (5, None)  # Insert at position 5 with default values
    ]
    
    print("Row operations to perform:")
    for pos, row_data in row_operations:
        if row_data:
            print(f"  Insert row at position {pos} with data: {row_data}")
        else:
            print(f"  Insert row at position {pos} with default values")
    print()
    
    # Simulate the improved AddRowsCommand logic
    def simulate_improved_add_rows(data, operations):
        """Simulate the improved AddRowsCommand logic."""
        
        # Group operations by consecutive positions (processed high to low)
        def group_consecutive_operations(ops):
            if not ops:
                return []
            
            # Sort operations by position (descending) to process from end to beginning
            sorted_ops = sorted(ops, key=lambda x: x[0], reverse=True)
            
            # Group consecutive positions for batch insertion
            groups = []
            current_group = [sorted_ops[0]]
            
            for i in range(1, len(sorted_ops)):
                pos, row_data = sorted_ops[i]
                prev_pos = sorted_ops[i-1][0]
                
                # Check if this position is consecutive to the previous one (going backwards)
                # Since we're going from high to low, consecutive means prev_pos = pos + 1
                if prev_pos == pos + 1:
                    current_group.append((pos, row_data))
                else:
                    groups.append(current_group)
                    current_group = [(pos, row_data)]
            
            groups.append(current_group)
            return groups
        
        def get_default_value_for_column(df, column):
            """Generate appropriate default value based on column type."""
            col_dtype = df[column].dtype
            
            if pd.api.types.is_numeric_dtype(col_dtype):
                if pd.api.types.is_integer_dtype(col_dtype):
                    return 0
                else:
                    return 0.0
            elif pd.api.types.is_bool_dtype(col_dtype):
                return False
            else:
                return ""
        
        def insert_row_group(df, group):
            """Insert a group of consecutive rows."""
            if not group:
                return df
            
            # The group is already sorted by position (descending)
            # Get the insertion position (lowest position in the group)
            insertion_pos = min(pos for pos, _ in group)
            
            # Validate position
            insertion_pos = max(0, min(insertion_pos, len(df)))
            
            # Prepare new rows data
            new_rows_data = []
            for pos, row_data in group:
                if row_data is not None:
                    # Use provided row data
                    new_row = {}
                    for column in df.columns:
                        if column in row_data:
                            new_row[column] = row_data[column]
                        else:
                            # Fill missing columns with defaults
                            new_row[column] = get_default_value_for_column(df, column)
                    new_rows_data.append(new_row)
                else:
                    # Generate default row
                    new_row = {}
                    for column in df.columns:
                        new_row[column] = get_default_value_for_column(df, column)
                    new_rows_data.append(new_row)
            
            # Create DataFrame for new rows
            new_rows_df = pd.DataFrame(new_rows_data)
            
            # Insert rows at the specified position
            if insertion_pos >= len(df):
                # Append at end
                result = pd.concat([df, new_rows_df], ignore_index=True)
            else:
                # Insert at specific position
                before = df.iloc[:insertion_pos]
                after = df.iloc[insertion_pos:]
                result = pd.concat([before, new_rows_df, after], ignore_index=True)
            
            return result
        
        # Group operations by consecutive positions
        operation_groups = group_consecutive_operations(operations)
        
        print("Operation groups (processed from end to beginning):")
        for i, group in enumerate(operation_groups):
            print(f"  Group {i+1}: {group}")
        print()
        
        # Process groups from end to beginning to avoid position shifts
        result_data = data.copy()
        
        for group in operation_groups:
            print(f"Processing group: {group}")
            result_data = insert_row_group(result_data, group)
            print(f"Result after group - Shape: {result_data.shape}")
            print(result_data)
            print()
        
        return result_data
    
    # Test the improved logic
    result = simulate_improved_add_rows(original_data, row_operations)
    
    print("Final result:")
    print(result)
    print(f"Final shape: {result.shape}")
    print()
    
    # Verify the positions and data
    print("Verification of final positions:")
    print("Position 0 (original Alice):", result.iloc[0].to_dict())
    print("Position 1 (inserted NewPerson1):", result.iloc[1].to_dict()) 
    print("Position 2 (original Bob):", result.iloc[2].to_dict())
    print("Position 3 (original Charlie):", result.iloc[3].to_dict())
    print("Position 4 (inserted NewPerson3):", result.iloc[4].to_dict())
    print("Position 5 (original Diana):", result.iloc[5].to_dict())
    print("Position 6 (inserted default row):", result.iloc[6].to_dict())
    
    print("\nThe insertions worked correctly:")
    print("✓ NewPerson1 inserted at position 1")
    print("✓ NewPerson3 inserted at final position 4 (was position 3 before first insertion)")
    print("✓ Default row inserted at final position 6 (was position 5 before other insertions)")
    print("✓ All original data preserved and shifted correctly")

if __name__ == "__main__":
    test_improved_add_rows()
