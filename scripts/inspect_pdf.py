import pdfplumber
from pathlib import Path
path = Path('swim-meets/2026/YouthChampionshipand12uinvitational/figure/Detailed_-_Age_Group_12_and_Under_Figures.pdf')
print('exists', path.exists())
with pdfplumber.open(path) as pdf:
    print('pages', len(pdf.pages))
    for i, page in enumerate(pdf.pages[:5], 1):
        text = page.extract_text() or ''
        print(f'--- PAGE {i} ---')
        print(text[:8000])
        print()
