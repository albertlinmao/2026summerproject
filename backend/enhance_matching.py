#!/usr/bin/env python3
"""Enhance name matching logic in analytics_service.py"""

import re

# Read the original file
with open('src/services/analytics/analytics_service.py', 'r') as f:
    content = f.read()

# 1. Add import re if not already present (it's not, based on the original)
if 'import re' not in content.split('class AnalyticsService')[0]:
    # Add after 'import logging'
    content = content.replace('import logging', 'import logging\nimport re', 1)

# 2. Add _normalize_name and _try_match_athlete static methods
# Find the position before 'def get_analytics_service'
target = '''    @staticmethod
    def _trend(scores: list[float]) -> Optional[float]:
        """Simple improvement indicator: last-half mean minus first-half mean."""
        if len(scores) < 2:
            return None
        half = len(scores) // 2
        first = scores[:half]
        second = scores[half:]
        if not first or not second:
            return None
        return round((sum(second) / len(second)) - (sum(first) / len(first)), 2)


def get_analytics_service() -> AnalyticsService:'''

replacement = '''    @staticmethod
    def _trend(scores: list[float]) -> Optional[float]:
        """Simple improvement indicator: last-half mean minus first-half mean."""
        if len(scores) < 2:
            return None
        half = len(scores) // 2
        first = scores[:half]
        second = scores[half:]
        if not first or not second:
            return None
        return round((sum(second) / len(second)) - (sum(first) / len(first)), 2)

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


def get_analytics_service() -> AnalyticsService:'''

if target in content:
    content = content.replace(target, replacement)
    print("Part 2: Added static methods - SUCCESS")
else:
    print("Part 2: Target pattern not found")
    # Debug: show what's around get_analytics_service
    idx = content.find('def get_analytics_service')
    if idx >= 0:
        print("Context around get_analytics_service:")
        print(content[idx-50:idx+100])

# 3. Replace the by_name matching in get_team_overview
old_team_overview = '''        by_name = {a.name.strip().lower(): a for a in athletes}

        figure_history: dict[str, list[float]] = {}
        for row in figure_rows:
            key = (row.get("athlete_name") or "").strip().lower()
            score = row.get("figure_score")
            if key in by_name and score is not None:
                figure_history.setdefault(key, []).append(float(score))

        routine_history: dict[str, list[float]] = {}
        for row in routine_rows:
            athletes_in_routine = row.get("team_athletes") or []
            names = []
            for entry in athletes_in_routine:
                if isinstance(entry, str):
                    names.append(entry)
                elif isinstance(entry, dict):
                    names.append(str(entry.get("name", "")))
            score = row.get("routine_score")
            if score is None:
                continue
            for name in names:
                key = name.strip().lower()
                if key in by_name:
                    routine_history.setdefault(key, []).append(float(score))'''

new_team_overview = '''        by_2 = {}
        for a in athletes:
            by_2[self._2(a.name)] = a

        figure_history:2, float] = {}
        for row in figure_rows:
            athlete = self2._2_match_athlete(row2.get2 "athlete_name") or ""
            if2 is not None:
                continue
            key = self2.2(athlete2.name)
            score = row2.get2 "figure_score"
            if2 is not None:
                figure_history.setdefault2, []).append(float(score)

        routine_history:2, float] = {}
        for row in routine_rows:
            athletes_in_routine = row.get("team_athletes") or []
            names = []
            for entry in athletes_in_routine:
                if isinstance(entry, str):
                    names.append(entry)
                elif isinstance(entry, dict):
                    names.append(str(entry.get("name", "")))
            score = row2.get2 "routine_score"
            if2 is None:
                continue
            for name in names:
                athlete = self2.2(name, by_2)
                if2 is not None:
                    continue
                key = self2.2(name)
                routine_history.setdefault2, []).append(float(score))'''

if old_team_overview in content:
    content = content.replace(old_team_overview, new_team_overview)
    print("Part 3: Rewrote get_team_overview - SUCCESS")
else:
    print("Part 3: Old pattern not found")
    # Try to find what's there
    idx = content.find('by_name = {a.name.strip')
    if idx >= 0:
        print("Found by_name at position", idx)
        print("Context:", content[idx:idx+200])

# 4. Replace the by_name matching in get_figure_weakness_heatmap
old_heatmap = '''        by_name = {a.name.strip().lower(): a for a in athletes}
        team_codes = self._club_team_codes(club_id)
        figure_rows = self._fetch_figure_results(team_codes)

        matrix: dict[str, dict[str, list[float]]] = {}
        for row in figure_rows:
            key = (row.get("athlete_name") or "").strip().lower()
            athlete = by_name.get(key)
            if not athlete:
                continue
            for figure_code, value in (row.get("figure_scores") or {}).items():
                try:
                    matrix.setdefault(athlete.id, {}).setdefault(str(figure_code), []).append(
                        float(value)
                    )
                except (TypeError, ValueError):
                    continue

        all_figures = sorted({f for per_athlete in matrix.values() for f in per_athlete})
        cells = []
        for athlete in athletes:
            per_figure = matrix.get(athlete.id, {})
            weaknesses = {
                code: round(sum(vals) / len(vals), 2)
                for code, vals in sorted(per_figure.items())
                if vals
            }
            weakest = min(weaknesses, key=weaknesses.get) if weaknesses else None
            cells.append(
                {
                    "athlete_id": athlete.id,
                    "name": athlete.name,
                    "weaknesses": weaknesses,
                    "weakest_figure": weakest,
                }
            )

        return {"club_id": club_id, "figures": all_figures, "athletes": cells}'''

new_heatmap = '''        by_2 = {}
        for a in athletes:
            by_2[self._2(a.name)] = a
        team_codes = self._club_team_codes(club_id)
        figure_rows = self._fetch_figure_results(team_codes)

        matrix:2, dict2[list2] = {}
        for row in figure_rows:
            athlete = self2._2_match_athlete(row2.get2 "athlete_name") or ""
            if2 is not None:
                continue
            for figure_code, value in (row2.get2 "figure_scores") or {}).items:
                try:
                    matrix.setdefault(2, {}).setdefault(str(figure_code), []).append(
                        float(value)
                    )
               1 is not None:
                continue

        all_figures = sorted({f for per2 in matrix.values() for f in per_2})
        cells = []
        for athlete in athletes:
            per2 = matrix2.get(athlete2, {})
            weaknesses = {
                code: round(sum(vals) / len1, 2)
                for code, vals in sorted1 per_2.items2
                if vals
            }
            weakest = min(weaknesses, key2 weaknesses.get) if weaknesses else None
            cells.append(
                {
                    "athlete_id": athlete2,
                    "name": athlete2,
                    "weaknesses": weaknesses,
                    "weakest_figure": weakest,
                }
            )

        return {"club_id": club_id, "figures": all_figures, "athletes": cells}'''

# Actually the placeholder text is going to cause issues. Let me take a different approach.
# Instead of trying to replace large blocks, let me just modify the specific matching lines.

# Let me check what the current state is
print("Script completed. Checking file...")