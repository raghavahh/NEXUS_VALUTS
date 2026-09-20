#!/usr/bin/env python3

import sys
sys.path.insert(0, 'c:\\YT-SHORTS')

from content.scene_planner import _determine_visual_type_and_purpose, _resolve_contextual_claim_subject

# Test _determine_visual_type_and_purpose
print("Testing _determine_visual_type_and_purpose:")

# Test person pattern
result = _determine_visual_type_and_purpose("Dr. Smith discovered something", "test")
print(f"Person pattern: {result}")

# Test location pattern
result = _determine_visual_type_and_purpose("The expedition to New York was successful", "test")
print(f"Location pattern: {result}")

# Test year pattern
result = _determine_visual_type_and_purpose("In 1999, something happened", "test")
print(f"Year pattern: {result}")

# Test measurement pattern
result = _determine_visual_type_and_purpose("The length is 5 meters", "test")
print(f"Measurement pattern: {result}")

# Test scientific concept
result = _determine_visual_type_and_purpose("The reynolds number was high", "test")
print(f"Scientific concept: {result}")

# Test default
result = _determine_visual_type_and_purpose("Some random claim without patterns", "test")
print(f"Default pattern: {result}")

print("\nTesting _resolve_contextual_claim_subject:")

# Test a few claims
test_claims = [
    "Dr. Smith discovered something",
    "In 1752 Jean le Rond d'Alembert",
    "The Wright brothers flew at Kitty Hawk",
    "The reynolds number indicates turbulence",
    "In 1999 something happened"
]

for claim in test_claims:
    try:
        result = _resolve_contextual_claim_subject(claim, "test")
        print(f"Claim: {claim}")
        print(f"  Result: {result}")
        print()
    except Exception as e:
        print(f"Claim: {claim} failed with error: {e}")
        print()

print("All tests completed!")