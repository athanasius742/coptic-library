import fitz, collections
doc = fitz.open("book.pdf")
sz=collections.Counter()
for p in doc:
    for b in p.get_text("dict")["blocks"]:
        if b.get("type")!=0: continue
        for l in b["lines"]:
            for s in l["spans"]:
                if s["text"].strip():
                    sz[round(s["size"],1)]+=len(s["text"])
print("font sizes (size: chars):")
for s,n in sorted(sz.items()):
    print(f"  {s}: {n}")
# show how section numbers / headings look: find lines starting with digit+dot in bold
print("\n=== bold spans (likely section numbers) ===")
for pno,p in enumerate(doc):
    for b in p.get_text("dict")["blocks"]:
        if b.get("type")!=0: continue
        for l in b["lines"]:
            for s in l["spans"]:
                if "Bold" in s["font"] and s["text"].strip():
                    print(f"  p{pno+1} sz={round(s['size'],1)} {repr(s['text'])}")
