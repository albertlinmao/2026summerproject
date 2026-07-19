import re

header = '     F1: Straight Ballet Leg F2: Barracuda           F3: Kip                 F4: Swanita Spinning 18'
j1 = 'J1   Candy HIPP              Karen ROSOLOWSKI        Shannon KORPELA         Linda WITTER'
j5 = 'J5                                                                           Heidi LURENZ'

# find columns
columns = []
for m in re.finditer(r"(F\d+):\s*(.*?)(?=\s+F\d+:|$)", header):
    f_short = m.group(1)
    f_name = m.group(2).strip()
    start_idx = m.start(1)
    columns.append((start_idx, f_short, f_name))

print("Columns:", columns)

def parse_judges(line, columns):
    # Find all non-space segments that could be names, but names can have 1 space between first and last.
    # So split by 2+ spaces.
    # To get positions with re.split, we can use re.finditer instead:
    res = {}
    for m in re.finditer(r"[^\s](?:[^\s]|\s(?!\s))*[^\s]|[^\s]", line[2:]):
        val = m.group(0).strip()
        pos = m.start(0) + 2
        # find the column that is closest or immediately preceding
        closest_col = None
        # Usually names align closely with the header start
        # Let's just find the column whose start_idx is closest to pos
        best_diff = 999
        for c_start, f_short, _ in columns:
            diff = abs(c_start - pos)
            # Or if it's within a certain range
            if diff < best_diff:
                best_diff = diff
                closest_col = f_short
        res[closest_col] = val
    return res

print("J1:", parse_judges(j1, columns))
print("J5:", parse_judges(j5, columns))
