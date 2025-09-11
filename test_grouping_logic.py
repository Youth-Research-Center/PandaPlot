#!/usr/bin/env python3
"""
Test the consecutive grouping logic for AddColumnsCommand
"""

def group_consecutive_positions(reference_positions, column_names, default_values):
    """Test version of the grouping logic"""
    # Create list of (reference_position, column_name, default_value, original_index)
    items = list(zip(reference_positions, column_names, default_values, range(len(column_names))))
    
    # Sort by reference position
    items.sort(key=lambda x: x[0])
    
    if not items:
        return []
    
    groups = []
    current_group = [items[0]]
    
    for i in range(1, len(items)):
        current_pos = items[i][0]
        prev_pos = items[i-1][0]
        
        # If positions are consecutive, add to current group
        if current_pos == prev_pos + 1:
            current_group.append(items[i])
        else:
            # Start a new group
            groups.append(current_group)
            current_group = [items[i]]
    
    # Don't forget the last group
    groups.append(current_group)
    
    return groups

# Test cases
print("Testing consecutive position grouping:")
print("=" * 50)

# Test case 1: b, c, e selection (positions 1, 2, 4)
positions = [1, 2, 4]
names = ['x', 'y', 'z'] 
defaults = [None, None, None]
groups = group_consecutive_positions(positions, names, defaults)

print("Case 1: Select columns b(1), c(2), e(4)")
print("Original: a b c d e")
print("Reference positions:", positions)
print("Column names:", names)
print("Groups found:")
for i, group in enumerate(groups):
    group_positions = [item[0] for item in group]
    group_names = [item[1] for item in group]
    print(f"  Group {i+1}: positions {group_positions}, columns {group_names}")

print("\nExpected result for 'right' insertion:")
print("- Group 1 (positions [1,2]): insert 'x','y' after position 2 -> a b c x y d e")
print("- Group 2 (position [4]): insert 'z' after position 4 -> a b c x y d e z")

print("\n" + "=" * 50)

# Test case 2: Non-consecutive selection (1, 3, 5)
positions = [1, 3, 5]
names = ['p', 'q', 'r'] 
defaults = [None, None, None]
groups = group_consecutive_positions(positions, names, defaults)

print("Case 2: Select columns b(1), d(3), f(5)")
print("Original: a b c d e f g")
print("Reference positions:", positions)
print("Groups found:")
for i, group in enumerate(groups):
    group_positions = [item[0] for item in group]
    group_names = [item[1] for item in group]
    print(f"  Group {i+1}: positions {group_positions}, columns {group_names}")

print("\nExpected result for 'right' insertion:")
print("- Insert 'p' after pos 1, 'q' after pos 3, 'r' after pos 5")
print("- Final: a b p c d q e f r g")
