import fitz, sys
doc = fitz.open("book.pdf")
def classify(s):
    c={'ar':0,'lat':0,'cop':0,'pua':0,'pres':0,'oth':0,'dig':0}
    for ch in s:
        o=ord(ch)
        if ch.isspace(): continue
        if 0x0600<=o<=0x06FF or 0x0750<=o<=0x077F: c['ar']+=1
        elif 0xFB50<=o<=0xFEFF: c['pres']+=1
        elif 0x2C80<=o<=0x2CFF or 0x03E2<=o<=0x03EF: c['cop']+=1
        elif 0xE000<=o<=0xF8FF: c['pua']+=1
        elif 0x41<=o<=0x7A: c['lat']+=1
        elif ch.isdigit(): c['dig']+=1
        else: c['oth']+=1
    return c
for i,p in enumerate(doc):
    txt=p.get_text()
    imgs=p.get_images(full=True)
    area=p.rect.width*p.rect.height
    imgarea=0
    for b in p.get_text("dict")["blocks"]:
        if b.get("type")==1:
            x0,y0,x1,y1=b["bbox"]; imgarea+=(x1-x0)*(y1-y0)
    c=classify(txt)
    print(f"p{i+1:02d} chars={len(txt):5d} imgs={len(imgs)} imgcov={imgarea/area:.2f} {c}")
