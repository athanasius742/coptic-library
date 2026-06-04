import fitz, collections
doc = fitz.open("book.pdf")
fontuse=collections.Counter()
samples=collections.defaultdict(list)
for pno,p in enumerate(doc):
    d=p.get_text("dict")
    for b in d["blocks"]:
        if b.get("type")!=0: continue
        for l in b["lines"]:
            for s in l["spans"]:
                fn=s["font"]
                fontuse[fn]+=len(s["text"].strip())
                if s["text"].strip() and len(samples[fn])<6:
                    samples[fn].append((pno+1,s["text"]))
print("=== FONT USAGE (chars) ===")
for fn,n in fontuse.most_common():
    print(f"{n:6d}  {fn}")
print()
for fn,ss in samples.items():
    print("###",fn)
    for pno,t in ss:
        print(f"  p{pno}: {repr(t)}")
