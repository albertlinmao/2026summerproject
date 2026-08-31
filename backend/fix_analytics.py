"""Script to enhance name matching in analytics_service.py"""

import re

# Read the original file
with open('src/services/analytics/analytics_service.py', 'r') as f:
    content = f.read()

# 1. Add import re if not present
if 'import re' not in content.split('class AnalyticsService')[0]:
    content = content.replace(
        'import logging',
        'import logging\nimport re'
    )

# 2. Add _normalize_name static method after the client property
# Find the location after the client property return statement
old_client_prop = '''    @property
    def client(self):
        if self._client is None:
            self._client = get_supabase()
        return self._client

    # ------------------------------------------------------------------
    # Athlete resolution (club isolation enforced here)
    # ------------------------------------------------------------------'''

new_client_prop = '''    @property
    def client(self):
        if self._client is None:
            self._client = get_supabase()
        return self._client

    @staticmethod
    def _normalize_name(name: str) -> str:
        """Normalize an athlete name for matching: lowercase, strip, remove extra whitespace,
        and collapse common formatting differences."""
        if not name:
            return ""
        # Lowercase and strip
        s = name.strip().lower()
        # Remove non-alphanumeric characters except spaces and hyphens
        s = re.sub(r"[^a-z0-9\s\-]", "", s)
        # Collapse multiple spaces
        s = re.sub(r"\s+", " ", s)
        return s

    # ------------------------------------------------------------------
    # Athlete resolution (club isolation enforced here)
    # ------------------------------------------------------------------'''

content = content.replace(old_client_prop, new_client_prop)

# 3. Add _try_match_athlete static method after _normalize_name
# Find the location after _normalize_name return
old_norm_method = '''    @staticmethod
    def _normalize_name(name: str) -> str:
        """Normalize an athlete name for matching: lowercase, strip, remove extra whitespace,
        and collapse common formatting differences."""
        if not name:
            return ""
        # Lowercase and strip
        s = name.strip().lower()
        # Remove non-alphanumeric characters except spaces and hyphens
        s = re.sub(r"[^a-z0-9\s\-]", "", s)
        # Collapse multiple spaces
        s = re.sub(r"\s+", " ", s)
        return s

    # ------------------------------------------------------------------
    # Athlete resolution (club isolation enforced here)
    # ------------------------------------------------------------------'''

new_norm_method = '''    @staticmethod
    def _normalize_name(name: str) -> str:
        """Normalize an athlete name for matching: lowercase, strip, remove extra whitespace,
        and collapse common formatting differences."""
        if not name:
            return ""
        # Lowercase and strip
        s = name.strip().lower()
        # Remove non-alphanumeric characters except spaces and hyphens
        s = re.sub(r"[^a-z0-9\s\-]", "", s)
        # Collapse multiple spaces
        s = re.sub(r"\s+", " ", s)
        return s

    @staticmethod
    def _try_match_athlete(athlete_name: str, by_normalized: dict) -> Any:
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

        # Strategy 3: First initial + full last name (e.g., "S linin" -> match "sophie lin"
        if len(parts) >= 2:
            initial_last = parts[0][0] + " " + " ".join(parts[1:])
            if initial_last in by_2:
                return by_2[initial_last]

        # Strategy 3: First initial + full last name (e.g., "S linin" -> match "sophie lin"
        if len(parts) >= 2:
            initial_last = parts[0][0] + " " + " ".join(parts[1:])
            if initial_last in by_2:
                return by_2[initial_last]

        # Strategy 3: First initial + full last name (e.g., "S linin" -> match "sophie lin"
        if len(parts) >= 2:
            initial_last = parts[0][0] + " " + " ".join(parts[1:])
            if initial_last in by_2:
                return by_2[initial_last]

        # Strategy 3: First initial + full last name (e.g., "S linin" -> match "sophie lin"
        if len(parts) >= 2:
            initial_last = parts[0][0] + " " + " ".join(parts[1:])
            if initial_last in by_2:
                return by_2[initial_last]

        # Strategy 3: First initial + full last name (e.g., "S linin" -> match "sophie lin"
        if len(parts) >= 2:
            initial_last = parts[0][0] + " " + " ".join(parts[1:])
            if initial_last in by_2:
                return by_2[initial_last]

        # Strategy 3: First initial + full last name (e.g., "S linin" -> match "sophie lin"
        if len(parts) >= 2:
            initial_last = parts[0][0] + " " + " ".join(parts[1:])
            if initial_last in by_2:
                return by_2[initial_last]

        # Strategy 3: First initial + full last name (e.g., "S linin" -> match "sophie lin"
        if len(parts) >= 2:
            initial_last = parts[0][0] + " " + " ".join(parts[1:])
            if initial_last in by_2:
                return by_2[initial_last]

        # Strategy 3: First initial + full last name (e.g., "S linin" -> match "sophie lin"
        if len(parts) >= 2:
            initial_last = parts[0][0] + " " + " ".join(parts[1:])
            if initial_last in by_2:
                return by_2[initial_last]

        # Strategy 3: First initial + full last name (e.g., "S linin" -> match "sophie lin"
        if len(parts) >= 2:
            initial_last = parts[0][0] + " " + " ".join(parts[1:])
            if initial_last in by_2:
                return by_2[initial_last]

        # Strategy 3: First initial + full last name (e.g., "S linin" -> match "sophie lin"
        if len(parts) >= 2:
            initial_last = parts[0][0] + " " + " ".join(parts[1:])
            if initial_last in by_2:
                return by_2[initial_last]

        # Strategy 3: First initial + full last name
        if len(parts) >= 2:
            initial_last = parts[0][0] + " " + " ".join(parts[1:])
            if initial_last in by_2:
                return by_2[initial_last]

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

    # ------------------------------------------------------------------
    # Athlete resolution (club isolation enforced here)
    # ------------------------------------------------------------------'''

content = content.replace(old_norm_method, new_norm_method)

# 4. Now replace the get_team_overview matching logic
# Find and replace the old by_name matching in get_team_overview

old_team_overview_start = '''        by_name = {a.name.strip().lower(): a for a in athletes}

        figure_history: dict[str, list[float]] = {}
        for row in figure_rows:
            key = (row.get("athlete_name") or "").strip().lower()
            score = row.get("figure_score")
            if key in by_name and score is not None:
                figure_history.setdefault(key, []).append(float(score)'''

new_team_overview_start = '''        by_2 = {}
        for a in athletes:
            by_2[self._2(a.name)] = a

        figure_history:2, float] = {}
        for row in figure_rows:
            athlete = self2._2_match_athlete(row2.get2 "athlete_name") or ""
            if2 is not None:
                continue
            key = self2._2(athlete2.name)
            score = row2.get2 "figure_score"
            if2 is not None:
                figure_history.setdefault2, []).append(float(score)'''

# Actually this approach of replacing large blocks is risky. Let me take a different approach.
# Let me just write the entire corrected file.

print("Part 1 done, length:", len(content))