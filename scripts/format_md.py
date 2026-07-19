import re

with open("Prompts to load data from Figure result.md", "r", encoding="utf-8") as f:
    text = f.read()

# The file contains sections separated by $$
sections = text.split("$$")

formatted_sections = []

for sec in sections:
    sec = sec.strip()
    if not sec:
        continue
    
    # Try to extract the date if it's the first line
    lines = sec.splitlines()
    date_match = re.match(r"^(\d{4}-\d{2}-\d{2})$", lines[0].strip())
    
    if date_match:
        date = date_match.group(1)
        content = "\n".join(lines[1:]).strip()
        formatted_sections.append(f"## {date}\n\n{content}")
    else:
        # Check if it starts with "Prompts to load"
        if lines[0].strip().startswith("Prompts to"):
             title = lines[0].strip()
             content = "\n".join(lines[1:]).strip()
             formatted_sections.append(f"## {title}\n\n{content}")
        else:
             formatted_sections.append(sec)

final_text = "\n\n---\n\n".join(formatted_sections)

# Clean up escapes like \_
final_text = final_text.replace(r"\_", "_")
final_text = final_text.replace(r"\*", "*")
# Clean up duplicate newlines
final_text = re.sub(r'\n{3,}', '\n\n', final_text)

with open("Prompts to load data from Figure result.md", "w", encoding="utf-8") as f:
    f.write("# Prompts to load data from Figure result\n\n")
    f.write(final_text)
    f.write("\n")
