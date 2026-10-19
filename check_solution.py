#!/usr/bin/env python3
"""
Independent check of the generated puzzle.

Solves the book as a reader would: reads only killer_puzzle.pdf
and the clue texts in solution_key.txt, applies all 18 clues to
every entry, and compares the result with conf.py. It shares no
logic with main.py.

It never prints the killer's name or any page number, so it is
safe to run without spoiling the answer.

How to run (from the repository root):
    source .venv/bin/activate
    python main.py              # generate the book first
    python check_solution.py

Exits with 0 and prints "RESULT: OK" when exactly one name is
left and it matches conf.py; otherwise exits with 1.

Requires pdftotext (poppler-utils: sudo apt install poppler-utils).
"""

import html
import importlib.util
import re
import subprocess
import sys
from collections import defaultdict
from itertools import product
from pathlib import Path

REPO = Path(__file__).resolve().parent
PDF = REPO / "killer_puzzle.pdf"

# ---------- read the book exactly as printed ----------
raw = subprocess.run(
    ["pdftotext", "-bbox", str(PDF), "-"], capture_output=True, text=True, check=True
).stdout
word_re = re.compile(
    r'<word xMin="([\d.]+)" yMin="([\d.]+)" xMax="[\d.]+" yMax="[\d.]+">(.*?)</word>'
)
pages = []  # per page: dict(names_col, names_row, chapter_title or None, number)
for chunk in raw.split("<page ")[1:]:
    words = [(float(x), float(y), html.unescape(w)) for x, y, w in word_re.findall(chunk)]
    number = int(max(words, key=lambda t: t[1])[2])  # page number: lowest word
    words = [t for t in words if not t[2].isdigit()]
    title = None
    if words and words[0][2] == "CHAPTER":
        y_title = sorted({round(y) for _, y, w in words if w.isupper() and w != "CHAPTER"})[0]
        title = " ".join(w for x, y, w in sorted(words) if round(y) == y_title)
        words = [t for t in words if not t[2].isupper()]
    xs = sorted({round(x) for x, _, _ in words})
    cols = [sorted((y, w) for x, y, w in words if round(x) == cx) for cx in xs]
    names_col = [w for c in cols for _, w in c]
    names_row = [w for x, y, w in sorted(words, key=lambda t: (round(t[1]), t[0]))]
    pages.append(dict(number=number, col=names_col, row=names_row, title=title))

assert [p["number"] for p in pages] == list(range(1, len(pages) + 1))
chapter_of, titles = {}, []
for p in pages:
    if p["title"]:
        titles.append(p["title"])
    chapter_of[p["number"]] = len(titles)
P = {p["number"]: p for p in pages}
N = len(pages)

# ---------- clue texts (what the reader gets) ----------
clue_text = {}
for line in (REPO / "solution_key.txt").open(encoding="utf-8"):
    m = re.match(r"^(\d+)\. (.*)$", line.strip())
    if m:
        clue_text[int(m[1])] = m[2]
assert sorted(clue_text) == list(range(1, 19)), clue_text
lower_n, upper_n = re.search(r"between (\w+)'s page and (\w+)'s page", clue_text[6]).groups()
neigh_n = re.search(r"away from (\w+)\.", clue_text[16])[1]
decoy_n = re.search(r"isn't (\w+)\.", clue_text[18])[1]
rare = re.search(r"starting with (\w)\.", clue_text[11])[1]

def pages_of(name):
    return [n for n, p in P.items() if name in p["col"]]

PRESIDENTS = {"George", "John", "James", "Thomas", "Abraham", "Andrew", "Ulysses",
              "Rutherford", "Chester", "Grover", "Benjamin", "William", "Theodore",
              "Woodrow", "Warren", "Calvin", "Herbert", "Franklin", "Harry", "Dwight",
              "Lyndon", "Richard", "Gerald", "Jimmy", "Ronald", "Bill", "Barack",
              "Donald", "Joe", "Martin", "Zachary", "Millard"}
KARDASHIANS_STRICT = {"Kim", "Kourtney", "Khloe", "Rob"}
KARDASHIANS_BROAD = KARDASHIANS_STRICT | {"Kris", "Kendall", "Kylie", "Robert", "Khloé"}
PLACE_WORDS = {"PARIS", "FRENCH", "SCOTTISH", "HIGHLANDS", "TOKYO", "FUJI", "MADRID",
               "AMSTERDAM", "NETHERLANDS", "LONDON", "ENGLISH", "NORWEGIAN", "PRAGUE",
               "CALIFORNIA", "NILE", "EGYPT", "ZEALAND", "ROME", "ITALIAN"}
print("Chapter titles judged as containing a place / not:")
for i, t in enumerate(titles, 1):
    print(f"  {i:2} {'PLACE' if set(t.split()) & PLACE_WORDS else '-----'} {t}")

# ---------- every entry in the book is a candidate ----------
entries = [(n, i, name) for n, p in P.items() for i, name in enumerate(p["col"])]

def make_clues(y_vowel, opposite, read9, kard):
    def vowels(s):
        return sum(c in ("aeiouy" if y_vowel else "aeiou") for c in s.lower())
    lo, hi = pages_of(lower_n), pages_of(upper_n)
    ne = pages_of(neigh_n)
    kp = [n for n, p in P.items() if kard & set(p["col"])]
    def near3(n, i, name):
        p = P[n]
        orders = {"col": [p["col"]], "row": [p["row"]], "both": [p["col"], p["row"]]}[read9]
        res = []
        for order in orders:
            k = order.index(name)
            res.append(any(len(w) == 3 and w != name and abs(j - k) <= 10
                           for j, w in enumerate(order)))
        return all(res)
    def opp(n):
        cand = {"prev": [n - 1], "next": [n + 1], "either": [n - 1, n + 1]}[opposite]
        return any(1 <= c <= N and PRESIDENTS & set(P[c]["col"]) for c in cand)
    chap_names = defaultdict(set)
    for n, p in P.items():
        chap_names[chapter_of[n]] |= set(p["col"])
    return {
        1: lambda n, i, w: len(w) > 3,
        2: lambda n, i, w: not w.lower().startswith("s"),
        3: lambda n, i, w: vowels(w) >= 2,
        4: lambda n, i, w: len(set(P[n]["col"])) < len(P[n]["col"]),
        5: lambda n, i, w: not any(a == b for a, b in zip(w.lower(), w.lower()[1:])),
        6: lambda n, i, w: any(a < n < b for a in lo for b in hi),
        7: lambda n, i, w: len(w) != 6,
        8: lambda n, i, w: not set("xyz") & set(w.lower()),
        9: near3,
        10: lambda n, i, w: bool(set(P[n]["col"][0].lower()) & set(w.lower())),
        11: lambda n, i, w: sum(x.startswith(rare) for x in P[n]["col"]) < 3,
        12: lambda n, i, w: any(abs(k - n) <= 4 for k in kp),
        13: lambda n, i, w: len(P[n]["col"]) % 2 == 1,
        14: lambda n, i, w: opp(n),
        15: lambda n, i, w: bool(set(titles[chapter_of[n] - 1].split()) & PLACE_WORDS),
        16: lambda n, i, w: any(abs(k - n) <= 1 for k in ne),
        17: lambda n, i, w: {"John", "Paul", "George", "Ringo"} <= chap_names[chapter_of[n]],
        18: lambda n, i, w: w != decoy_n,
    }

def solve(clues, skip=()):
    return [(n, i, w) for n, i, w in entries
            if all(f(n, i, w) for k, f in clues.items() if k not in skip)]

spec = importlib.util.spec_from_file_location("conf", REPO / "conf.py")
conf = importlib.util.module_from_spec(spec); spec.loader.exec_module(conf)

print(f"\nBook: {N} pages, {len(entries)} entries, chapters: {len(titles)}")
for name in (lower_n, upper_n, neigh_n, decoy_n):
    print(f"{name} appears on {len(pages_of(name))} page(s).")

base = make_clues(False, "prev", "both", KARDASHIANS_STRICT)
result = solve(base)
print(f"\nAll 18 clues (base reading): {len(result)} entry(ies) left; "
      f"matches conf.KILLER: {[w for *_, w in result] == [conf.KILLER]}; "
      f"page matches conf.KILLER_PAGE: {[n for n, *_ in result] == [conf.KILLER_PAGE]}")

print("\nPer clue: entries eliminated alone (of 30,000) | left if this clue is dropped")
for k in range(1, 19):
    alone = sum(not base[k](*e) for e in entries)
    left = len(solve(base, skip=(k,)))
    print(f"  {k:2}: {alone:6} | {left}")

print("\nAlternative readings (y as vowel / opposite page / clue 9 order / Kardashians):")
for yv, opp, r9, kard in product([False, True], ["prev", "next", "either"],
                                 ["col", "row", "both"], ["strict", "broad"]):
    res = solve(make_clues(yv, opp, r9, KARDASHIANS_STRICT if kard == "strict" else KARDASHIANS_BROAD))
    ok = [w for *_, w in res] == [conf.KILLER]
    if not ok:
        print(f"  FAIL y={yv} opposite={opp} clue9={r9} kard={kard}: {len(res)} left")
print("  (only failures are listed)")

ok = [w for *_, w in result] == [conf.KILLER]
print("\nRESULT:", "OK" if ok else "FAILED")
sys.exit(0 if ok else 1)
