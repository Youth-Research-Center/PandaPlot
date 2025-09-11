#!/usr/bin/env python3
"""
Test script to verify the column position adjustment logic.
"""

def adjust_positions_for_consecutive_inserts(positions):
    """
    Test version of the position adjustment method.
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
        insertions_to_left = sum(1 for j in range(i) if indexed_positions[j][1] <= pos)
        adjusted[original_index] = pos + insertions_to_left
    
    # Return adjusted positions in original order
    return [adjusted[i] for i in range(len(positions))]

# Test cases
test_cases = [
    # Test case 1: Selecting columns 4 and 5, want to add "to the right"
    ([5, 6], "Selected cols 4,5 -> insert after them at positions 5,6"),
    
    # Test case 2: Selecting columns 4, 5, and 7, want to add "to the right" 
    ([5, 6, 8], "Selected cols 4,5,7 -> insert after them at positions 5,6,8"),
    
    # Test case 3: Non-consecutive positions
    ([2, 5, 8], "Selected cols 1,4,7 -> insert after them at positions 2,5,8"),
    
    # Test case 4: Single position
    ([3], "Single column 2 -> insert after at position 3"),
    
    # Test case 5: Consecutive positions starting from 0
    ([1, 2, 3], "Selected cols 0,1,2 -> insert after them at positions 1,2,3"),
]

print("Testing column position adjustment logic:")
print("=" * 50)

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

print("\n" + "=" * 50)
print("Expected behavior:")
print("- When selecting columns 4,5 and adding 'to the right':")
print("  - First new column goes at position 5 (after column 4)")
print("  - Second new column goes at position 6 (after column 5, accounting for shift)")
print("- Final result: original cols [0,1,2,3,4,5,6,...] become [0,1,2,3,NEW1,4,NEW2,5,6,...]")
