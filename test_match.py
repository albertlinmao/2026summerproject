import re

def _normalize_name(name: str) -> str:
    if not name:
        return ""
    s = name.strip().lower()
    s = re.sub(r"[^a-z0-9\s\-]", "", s)
    s = re.sub(r"\s+", " ", s)
    return s

def _try_match_athlete(athlete_name: str, by_normalized: dict) -> any:
    if not athlete_name:
        return None
    normalized = _normalize_name(athlete_name)
    
    # Strategy 1: Exact normalized match
    if normalized in by_normalized:
        return by_normalized[normalized]
    
    # Strategy 2: Reversed name parts
    parts = normalized.split(" ")
    if len(parts) >= 2:
        reversed_normalized = " ".join(reversed(parts))
        if reversed_normalized in by_normalized:
            return by_normalized[reversed_normalized]
    
    # Strategy 3: First initial + full last name
    if len(parts) >= 2:
        initial_last = parts[0][0] + " " + " ".join(parts[1:])
        if initial_last in by_normalized:
            return by_normalized[initial_last]
    
    # Strategy 4: Substring containment
    for norm, athlete in by_normalized.items():
        if norm in normalized or normalized in norm:
            return athlete
    
    return None

# Test with demo data athlete names
athlete_names = ["Emma Johnson", "Olivia Davis", "Sophia Martinez", "Isabella Rodriguez", "Mia Smith", "Charlotte Lee"]

by_normalized = {}
for name in athlete_names:
    by_normalized[_normalize_name(name)] = name

test_names = [
    "emma johnson",          # exact case diff
    "Emma Johnson",          # original case
    "  Emma Johnson  ",      # with extra whitespace
    "EMMA JOHNSON",          # all caps
    "Sophia Martinez",       # another athlete
    "Sophie Martinez",       # similar but different (should not match)
    "Lin, Sophie",         # reversed with comma
]

print("=== Name Normalization ===")
for name in athlete_names:
    print(f"  {repr(name)} -> {_normalize_name(name)}")

print("\n=== Athlete Matching ===")
for name in test_names:
    matched = _try_match_athlete(name, by_normalized)
    if matched:
        print(f"  {repr(name)} -> {matched}")
    else:
        print(f"  {repr(name)} -> NO MATCH")