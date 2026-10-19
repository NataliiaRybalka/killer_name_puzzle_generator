# -*- coding: utf-8 -*-

"""
Puzzle configuration for main.py.

Spoiler: this file names the killer and every page the clues
point to. Do not open it if you want to solve the puzzle.
"""

from pathlib import Path


OUTPUT_PDF = Path("killer_puzzle.pdf")
OUTPUT_KEY = Path("solution_key.txt")

TOTAL_ENTRIES = 30_000
TOTAL_PAGES = 250
ENTRIES_PER_PAGE = 120
PAGES_PER_CHAPTER = 10

# Names are written in this many columns, filled column by column.
COLUMNS = 4

RANDOM_SEED = 20261019

KILLER = "Victoria"
KILLER_PAGE = 163
KILLER_PAGE_SIZE = ENTRIES_PER_PAGE - 1

# The page with one extra entry that balances the killer's page.
# It lies outside the range of clue 6, so clues 6 and 13
# together leave only the killer's page.
BALANCING_PAGE = TOTAL_PAGES

# Clue 4: the only permitted duplicate. It opens the killer's
# page twice, so it is also the first name for clue 10.
REPEATED_NAME = "Edward"

# Clue 9: the three-letter name directly below the killer.
THREE_LETTER_NAME = "Leo"

# Clue 18: on the killer's page, passes every other name clue.
DECOY = "Valerie"

# Clue 6: the killer's page lies between these two names' pages.
LOWER_BOUND = ("Amelia", 50)
UPPER_BOUND = ("Zoe", 217)

# Clue 12: the only Kardashian in the book.
KARDASHIAN = ("Khloe", 160)

# Clue 16: the killer's page is at most one page away.
NEIGHBOUR = ("Nadia", KILLER_PAGE - 1)

# Clue 14: presidents on both pages around the killer's page.
PRESIDENT_BEFORE = ("George", KILLER_PAGE - 1)
PRESIDENT_AFTER = ("Abraham", KILLER_PAGE + 1)

# Clue 17: John, Paul and Ringo sit in the killer's chapter;
# George is PRESIDENT_BEFORE.
BEATLE_PAGES = {"John": 161, "Paul": 165, "Ringo": 168}

# Public dataset containing first names.
NAMES_URL = (
    "https://raw.githubusercontent.com/"
    "hackerb9/ssa-baby-names/main/allnames.txt"
)

# (title, has a place in its title).
# The chapter containing the killer must have a place in its title.
# Titles without a place avoid any geographic word, so that
# clue 15 eliminates those chapters unambiguously.
CHAPTERS = [
    ("Whispers in the Dark", False),
    ("Paris and the French Countryside", True),
    ("The Last Letter", False),
    ("The Scottish Highlands", True),
    ("Secrets and Lies", False),
    ("Tokyo and Mount Fuji", True),
    ("A Matter of Trust", False),
    ("The Streets of Madrid", True),
    ("Silent Witnesses", False),
    ("Amsterdam and the Netherlands", True),
    ("Echoes of the Past", False),
    ("The Midnight Hour", False),
    ("London and the English Countryside", True),
    ("Broken Promises", False),
    ("The Norwegian Fjords", True),
    ("Shadows and Masks", False),
    ("The Streets of Prague", True),
    ("The Final Clue", False),
    ("The Beaches of California", True),
    ("Unspoken Truths", False),
    ("The Nile and Ancient Egypt", True),
    ("Strangers at Midnight", False),
    ("The Coast of New Zealand", True),
    ("Fading Footsteps", False),
    ("Rome and the Italian Coast", True),
]

CHAPTER_TITLES = [title for title, _ in CHAPTERS]
CHAPTER_HAS_PLACE = [has_place for _, has_place in CHAPTERS]

BEATLES = {"John", "Paul", "George", "Ringo"}

PRESIDENT_FIRST_NAMES = {
    "George", "John", "James", "Abraham", "Ulysses",
    "Rutherford", "Chester", "Grover", "Benjamin",
    "William", "Theodore", "Woodrow", "Warren",
    "Calvin", "Herbert", "Franklin", "Harry",
    "Dwight", "Lyndon", "Richard", "Gerald",
    "Jimmy", "Ronald", "Bill", "Barack",
    "Donald", "Joe",
}

KARDASHIAN_FIRST_NAMES = {
    "Kim", "Kourtney", "Khloe", "Kendall", "Kylie", "Kris", "Rob"
}

# Names placed on fixed pages, outside the killer's page.
SPECIAL_PLACEMENTS = {}

for _name, _page in (
    LOWER_BOUND,
    UPPER_BOUND,
    KARDASHIAN,
    NEIGHBOUR,
    PRESIDENT_BEFORE,
    PRESIDENT_AFTER,
    *BEATLE_PAGES.items(),
):
    SPECIAL_PLACEMENTS.setdefault(_page, []).append(_name)

VOWELS = set("aeiou")

# Clue 11: names starting with this letter stay rare on the
# killer's page.
RARE_INITIAL = "M"

# Fillers on the killer's page that fail exactly one name clue,
# per clue, so that every name clue eliminates someone.
FILLERS_PER_NAME_CLUE = 3
