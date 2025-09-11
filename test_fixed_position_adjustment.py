#!/usr/bin/env python3
"""
Test script to verify the fixed column position adjustment logic.
"""

def adjust_positions_for_consecutive_inserts(positions):
    """
    Fixed version of the position adjustment method.
    """
    if len(positions) <= 1:
        return positions.copy()
        
    # Sort positions with their original indices to maintain correspondence with column_names
    indexed_positions = list(enumerate(positions))
    indexed_positions.sort(key=lambda x: x[1])  # Sort by position
    
    adjusted = {}
    
    # Process positions from left to right
    for i, (original_index, pos) in enumerate(indexed_positions):
        # Count how many columns were inserted to the left of this position
        # Only count insertions at positions strictly less than current position
        insertions_to_left = sum(1 for j in range(i) if indexed_positions[j][1] < pos)
        adjusted[original_index] = pos + insertions_to_left
    
    # Return adjusted positions in original order
    return [adjusted[i] for i in range(len(positions))]

# Test cases
test_cases = [
    # Test case 1: Selecting columns 4 and 5, want to add "to the right" (after each)
    ([5, 6], "Selected cols 4,5 -> insert after them at positions 5,6"),
    
    # Test case 2: Selecting columns 4, 5, and 7, want to add "to the right" 
    ([5, 6, 8], "Selected cols 4,5,7 -> insert after them at positions 5,6,8"),
    
    # Test case 3: Non-consecutive positions with gaps
    ([2, 5, 8], "Selected cols 1,4,7 -> insert after them at positions 2,5,8"),
    
    # Test case 4: Single position
    ([3], "Single column 2 -> insert after at position 3"),
    
    # Test case 5: All consecutive positions 
    ([1, 2, 3], "Selected cols 0,1,2 -> insert after them at positions 1,2,3"),
]

print("Testing FIXED column position adjustment logic:")
print("=" * 55)

for positions, description in test_cases:
    original_positions = positions.copy()
    adjusted_positions = adjust_positions_for_consecutive_inserts(positions)
    
    print(f"\n{description}")
    print(f"Original positions: {original_positions}")
    print(f"Adjusted positions: {adjusted_positions}")
    
    # Show what happens step by step for consecutive cases
    if len(positions) > 1:
        print("Step by step:")
        for i, (orig, adj) in enumerate(zip(original_positions, adjusted_positions)):
            print(f"  Column {i}: position {orig} -> {adj}")

print("\n" + "=" * 55)
print("Expected results:")
print("- [5, 6] -> [5, 7]: First at 5, second at 7 (6+1 due to first insertion)")
print("- [5, 6, 8] -> [5, 7, 10]: Positions shift by number of previous insertions")
print("- [2, 5, 8] -> [2, 6, 10]: Non-consecutive positions also shift correctly")
print("- [1, 2, 3] -> [1, 3, 5]: Each position shifts by number of previous insertions")
