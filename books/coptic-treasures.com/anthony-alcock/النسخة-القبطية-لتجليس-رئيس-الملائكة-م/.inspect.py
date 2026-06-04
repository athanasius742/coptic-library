import fitz
doc = fitz.open("book.pdf")
# fonts per page
print("=== FONTS p1 ===")
for f in doc[0].get_fonts(full=True):
    print(f)
print("=== RAW TEXT p1 ===")
print(repr(doc[0].get_text()[:1500]))
print("=== RAW TEXT p2 (first 800) ===")
print(repr(doc[1].get_text()[:800]))
print("=== 'oth' chars sample p5 ===")
import collections
c=collections.Counter()
for ch in doc[4].get_text():
    o=ord(ch)
    if not ch.isspace() and not (0x41<=o<=0x7A) and not ch.isdigit():
        c[ch]+=1
print(c.most_common(40))
