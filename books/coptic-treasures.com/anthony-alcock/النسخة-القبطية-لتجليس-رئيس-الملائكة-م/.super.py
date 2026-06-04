import fitz
doc = fitz.open("book.pdf")
# Look at page1: examine spans of the body line containing 'Toutôn.1' to see if '1' is a separate raised span
p=doc[0]
for b in p.get_text("dict")["blocks"]:
    if b.get("type")!=0: continue
    for l in b["lines"]:
        txt="".join(s["text"] for s in l["spans"])
        if "Touton" in txt or "Toutôn" in txt or "received it" in txt or "hills" in txt:
            print("LINE:",repr(txt))
            for s in l["spans"]:
                print("   span", repr(s["text"]), "size",round(s["size"],2),
                      "flags",s["flags"],"origin_y",round(s["origin"][1],1),
                      "bbox_y0",round(s["bbox"][1],1),"font",s["font"])
            print()
