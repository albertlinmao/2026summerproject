import pdfplumber
import re

path = 'swim-meets/2026/JuniorOlympicChampionships/figure/Detailed_-_Age_Group_12_and_Under_Figures.pdf'
with pdfplumber.open(path) as pdf:
    text = pdf.pages[0].extract_text()
    lines = [ln.rstrip() for ln in text.splitlines()]
    for line in lines:
        if line.lstrip().startswith('F1:'):
            print("HEADER:")
            print(repr(line))
        if line.strip().startswith('J1'):
            print(repr(line))
        if line.strip().startswith('J5'):
            print(repr(line))
