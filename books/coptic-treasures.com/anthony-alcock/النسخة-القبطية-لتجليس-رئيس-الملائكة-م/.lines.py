import fitz
doc = fitz.open("book.pdf")
for pno in [0,1,2,24]:
    p=doc[pno]
    print(f"========== PAGE {pno+1}  rect={p.rect} ==========")
    d=p.get_text("dict")
    for b in d["blocks"]:
        if b.get("type")!=0: continue
        for l in b["lines"]:
            txt="".join(s["text"] for s in l["spans"])
            y=round(l["bbox"][1],1); x=round(l["bbox"][0],1)
            fonts="|".join(sorted({s["font"] for s in l["spans"]}))
            print(f"  y={y:6.1f} x={x:6.1f} [{fonts}] {repr(txt)}")
