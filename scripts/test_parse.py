import re
import pdfplumber
import json

def test_parse(path):
    text_chunks = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages[:1]:
            text_chunks.append(page.extract_text() or "")
    text = "\n".join(text_chunks)
    lines = [ln.rstrip() for ln in text.splitlines()]

    event_name = lines[0].strip()
    meet_name = lines[1].strip()
    city_date_match = re.match(r"^(.+?)\s+(\d{1,2}\s+[A-Z]{3}\s+\d{4})\s*$", lines[2].strip())
    host_city = city_date_match.group(1).strip() if city_date_match else ""
    event_date = city_date_match.group(2).strip() if city_date_match else ""

    print(f"Event: {event_name}")
    print(f"Meet: {meet_name}")
    print(f"City: {host_city}, Date: {event_date}")

    figures_dict = {} # F1 -> {'figure_code': 'Figure 1', 'figure_code_short': 'F1', ...}
    judges_panels = {} # F1 -> {'J1': ..., 'J2': ...}
    figure_shorts = []

    i = 0
    while i < len(lines):
        line = lines[i]
        if line.lstrip().startswith("F1:"):
            # We found the F1 F2 F3 headers
            f_matches = re.findall(r"(F\d+):\s*(.*?)(?=\s+F\d+:|$)", line.strip())
            for idx, (f_short, f_name) in enumerate(f_matches):
                figure_shorts.append(f_short)
                figures_dict[f_short] = {
                    "figure_code": f"Figure {idx+1}",
                    "figure_code_short": f_short,
                    "name": f_name.strip(),
                }
                judges_panels[f_short] = {}
            # next line is DD
            i += 1
            dd_line = lines[i]
            dds = re.findall(r"DD:\s*([0-9.]+)", dd_line)
            for idx, dd in enumerate(dds):
                if idx < len(figure_shorts):
                    figures_dict[figure_shorts[idx]]["degree_difficulty"] = float(dd)

            # next lines are J1 to J4
            for _ in range(4):
                i += 1
                j_line = lines[i].strip()
                if j_line.startswith("J"):
                    j_num = j_line[:2]
                    # The judges are separated by 2+ spaces usually. 
                    # Let's extract by splitting on 2+ spaces.
                    j_names = re.split(r'\s{2,}', j_line[2:].strip())
                    for idx, j_name in enumerate(j_names):
                        if idx < len(figure_shorts):
                            judges_panels[figure_shorts[idx]][j_num] = j_name

            break
        i += 1

    # find the full figure names
    while i < len(lines):
        line = lines[i].strip()
        fm = re.match(r"^Figure\s+(\d+)\s+(.+?)\s+([0-9.]+)$", line)
        if fm:
            fig_idx = int(fm.group(1)) - 1
            if fig_idx < len(figure_shorts):
                f_short = figure_shorts[fig_idx]
                # Fix encoding issues like 'Swanita Spinning 180'
                full_name = fm.group(2).strip()
                figures_dict[f_short]["name"] = full_name
                figures_dict[f_short]["degree_difficulty"] = float(fm.group(3))
        if "Total:" in line:
            break
        i += 1

    figures = list(figures_dict.values())
    judges = []
    for f_short, panel in judges_panels.items():
        judges.append({
            "figure_code_short": f_short,
            "figure_name": figures_dict[f_short]["name"],
            "panel": panel
        })

    print(json.dumps(figures, indent=2))
    print(json.dumps(judges, indent=2))

test_parse("swim-meets/2026/YouthChampionshipand12uinvitational/figure/Detailed_-_Age_Group_12_and_Under_Figures.pdf")