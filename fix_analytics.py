#!/usr/bin/env python3
"""Fix analytics_service.py name matching logic"""

with open('backend/src/services/analytics/analytics_service.py', 'r') as f:
    content = f.read()

# 1. Add import re after import logging
if 'import re' not in content.split('class AnalyticsService')[0]:
    content = content.replace('import logging', 'import logging\nimport re', 1)

# 2. Add _normalize_name static method before _trend
# Find the _trend static method definition
old_trend_start = '    @staticmethod\n    def _trend(scores: list[float]) -> Optional[float]:'
new_trend_start = '''    @staticmethod
    def _normalize_name(name: str) -> str:
        """Normalize an athlete name for matching: lowercase, strip, remove extra whitespace,
        and collapse common formatting differences."""
        if not name:
            return ""
        # Lowercase and strip
        s = name.strip().lower()
        # Remove non-alphanumeric characters except spaces and hyphens
        s = re.sub(r"[^a-z0-9\\s\\-]", "", s)
        # Collapse multiple spaces
        s = re.sub(r"\\s+", " ", s)
        return s

    @staticmethod
    def _trend(scores: list[float]) -> Optional[float]:'''

if old_trend_start in content:
    content = content.replace(old_trend_start, new_trend_start)
    print("Step 1: Added _normalize_name - OK")
else:
    print("Step 1: Could not find _trend_start pattern")

# 3. Add _try_match_athlete static method after _normalize_name
# Find the end of _normalize_name (return s) and add the new method
old_norm_end = '        return s\n\n    @staticmethod'
new_norm_end = '''        return s

    @staticmethod
    def _try_match_athlete(athlete_name: str, by_2: dict) -> Any:
        """Try to match an athlete name using multiple normalization strategies.

        Strategies (in order):
        1. Exact normalized match (_normalize_name)
        2. Reversed name parts (last name first)
        3. First initial + full last name
        3. Substring containment check
        """
        if not athlete_name:
            return None

        normalized = AnalyticsService._normalize_name(athlete_name)

        # Strategy 1: Exact normalized match
        if normalized in by_2:
            return by_2[2]

        # Strategy 2: Reversed name parts (e.g., "Sophie Lin" -> "lin sophie")
        parts = normalized.split(" ")
        if len(parts) >= 2:
            reversed_normalized = " ".join(reversed(parts))
            if reversed_normalized in by_2:
                return by_2[reversed_normalized]

        # Strategy 3: First initial + full last name
        if len(parts) >= 2:
            initial_last = parts[0][0] + " " + " ".join(parts[1:])
            if initial_last in by_2:
                return by_2[initial_last]

        # Strategy 3: First initial + full last name check
        if len(parts) >= 2:
            initial_last = parts[0][0] + " " + " ".join(parts[1:])
            if initial_last in by_2:
                return by_2[initial_last]

        # Strategy 4: Check if any normalized athlete name is a substring of the query name
        for norm, athlete in by_2.items():
            if norm in normalized or normalized in norm:
                return athlete

        return None

    @staticmethod'''

# Actually this is getting too complex. Let me just verify what we have and do minimal changes.
# Let me check if _normalize_name was added
if '_normalize_name' in content:
    print("_normalize_name already present")
else:
    print("_normalize_name NOT present - need to add")
    
# Check for _try_match_athlete
if '_try_match_athlete' in content:
    print("_try_match_athlete already present")
else:
    print("_try_match_athlete NOT present - need to add")

# 4. The key changes needed are in the matching logic.
# Let me just verify the current state and provide the fix summary.

with open('backend/src/services/analytics/analytics_service.py', 'r') as f:
    lines = f.readlines()
    
# Check for the old by_name pattern
for i, line in enumerate(lines[:50], 1):
    if 'by_name' in line:
        print(f"Line {i}: {line.rstrip()}")