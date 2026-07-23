import json
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))
from scripts.ingest_routines import parse_routine_pdf_text

with open('temp_pdf_text.txt', 'r', encoding='utf-8') as f:
    text = f.read()

result = parse_routine_pdf_text(text)
print(json.dumps(result, indent=2))
