import re

text = """ J1 Karen ROSOLOWSKI Svetlana MALINOVSKAYA Rachael NAESSENS 
 J2 Olivia ZHANG Denise SHIVELY Dana BRADLEY 
 J3 Heidi LURENZ Shannon KORPELA Laura GANZEL 
 J4 Debbie LATCHFORD Ginny JASONTEK """

for line in text.splitlines():
    if not line.strip(): continue
    rest = line.strip()[2:].strip()
    names = re.findall(r"[A-Z][A-Za-z\.\-\']+\s+[A-Z\-\']{2,}(?:\s+[A-Z\-\']{2,})*", rest)
    print(line.strip()[:2], names)