#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
KILLER NAME PUZZLE
==================

Creates:
    killer_puzzle.pdf
    solution_key.txt

Requirements:
    Python 3.10+
    reportlab

Features:
    - 30,000 name entries.
    - 29,999 distinct names.
    - Exactly one duplicated name: Oliver.
    - Page numbers at the bottom of every page.
    - No visible numbering beside names.
    - 25 chapters; only some titles contain a place.
    - Chapters span as many pages as necessary.
    - Chapter titles appear only at chapter beginnings.
    - Automatic page layout.
    - Validation of all 18 clues.
    - Separate answer key.
"""

import io
import random
import re
import urllib.request

from collections import Counter
from itertools import zip_longest
from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas


# ============================================================
# CONFIGURATION
# ============================================================

OUTPUT_PDF = Path("killer_puzzle.pdf")
OUTPUT_KEY = Path("solution_key.txt")

TOTAL_ENTRIES = 30_000
TOTAL_PAGES = 750
ENTRIES_PER_PAGE = 40

RANDOM_SEED = 20261019

KILLER = "Catherine"
KILLER_PAGE = 375

# This is the only permitted duplicate.
REPEATED_NAME = "Oliver"

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
    "Kim", "Kourtney", "Khloe", "Kendall", "Kylie"
}

VOWELS = set("aeiou")

# A 39-entry killer page makes the entry count odd.
# The following page has 41 entries to preserve 30,000 total.
#
# The killer page contains:
#   Oliver twice
#   Catherine once
#   Eli once
#   35 other unique names
#
# All other names on this page are selected so that they fail
# at least one of the killer-name length clues.

SPECIAL_PAGES = {
    100: {"Anna"},
    373: {"Kim"},
    374: {"George", "Sasha"},
    361: {"John"},
    362: {"Paul"},
    363: {"Ringo"},
    600: {"Zack"},
}


# ============================================================
# NAME DATASET
# ============================================================

def download_names():
    """
    Download the name list from GitHub.

    If downloading fails, the program looks for a local file
    named names.txt in the current directory.
    """

    print("Loading the first-name dataset...")

    names = set()

    try:
        request = urllib.request.Request(
            NAMES_URL,
            headers={
                "User-Agent": "KillerNamePuzzleGenerator/1.0"
            },
        )

        with urllib.request.urlopen(request, timeout=120) as response:
            content = response.read().decode("utf-8-sig")

        for line in content.splitlines():
            line = line.strip()

            if not line:
                continue

            # Support plain-text, CSV and tab-separated lists.
            candidate = re.split(r"[\t,;]", line, maxsplit=1)[0]
            candidate = candidate.strip().strip('"').strip("'")

            if (
                candidate.isascii()
                and candidate.isalpha()
                and len(candidate) >= 2
            ):
                names.add(candidate.capitalize())

        print(f"Downloaded {len(names):,} distinct names.")

    except Exception as exc:
        print(f"Online download failed: {exc}")

        local_file = Path("names.txt")

        if not local_file.exists():
            raise RuntimeError(
                "Could not download the name list.\n"
                "Download a plain-text list of first names and "
                "save it as names.txt in the same directory "
                "as main.py."
            ) from exc

        for line in local_file.read_text(
            encoding="utf-8-sig"
        ).splitlines():
            candidate = line.strip()

            if (
                candidate.isascii()
                and candidate.isalpha()
                and len(candidate) >= 2
            ):
                names.add(candidate.capitalize())

        print(f"Loaded {len(names):,} names from names.txt.")

    if len(names) < TOTAL_ENTRIES:
        raise RuntimeError(
            f"Only {len(names):,} distinct names are available. "
            f"At least {TOTAL_ENTRIES:,} are required."
        )

    return names


# ============================================================
# CHAPTER AND PAGE HELPERS
# ============================================================

def chapter_number_for_page(page_number):
    """
    There are 25 chapters, each covering 30 pages.
    """
    return (page_number - 1) // 30 + 1


def chapter_title_for_page(page_number):
    chapter_number = chapter_number_for_page(page_number)
    return CHAPTER_TITLES[chapter_number - 1]


def page_size(page_number):
    """
    Page 375 has 39 entries.
    Page 376 has 41 entries.
    Every other page has 40 entries.

    Total:
        750 pages
        30,000 entries
    """
    if page_number == KILLER_PAGE:
        return 39

    if page_number == KILLER_PAGE + 1:
        return 41

    return ENTRIES_PER_PAGE


def name_satisfies_name_clues(name):
    """
    Check clues that describe the killer's name itself.
    """

    lower = name.lower()

    return (
        len(name) > 3
        and not lower.startswith("s")
        and sum(ch in VOWELS for ch in lower) >= 2
        and not any(
            lower[i] == lower[i + 1]
            for i in range(len(lower) - 1)
        )
        and len(name) != 6
        and not any(ch in lower for ch in "xyz")
        and name != "Alice"
    )


# ============================================================
# BUILD THE BOOK
# ============================================================

def build_pages():
    """
    Build the complete book.

    - 30,000 entries.
    - 750 pages.
    - 40 entries per page, except:
        * killer page: 39 entries;
        * following page: 41 entries.
    - Exactly one duplicate: Oliver appears twice.
    - Required names are placed on designated pages.
    """

    print("Preparing the name list...")

    names = download_names()

    # Names that must be placed at specific locations.
    reserved_names = {
        "Anna",
        "Zack",
        "Kim",
        "Sasha",
        "George",
        "John",
        "Paul",
        "Ringo",
        "Oliver",
        "Catherine",
        "Eli",
        "Alice",
    }

    # Ensure all required names are available.
    names.update(reserved_names)

    # --------------------------------------------------------
    # Prepare the filler names for the killer's page.
    # --------------------------------------------------------

    pool = names - reserved_names

    filler_candidates = [
        name
        for name in pool
        if len(name) in (3, 6)
        and not name.startswith("M")
        and name != "Alice"
    ]

    rng = random.Random(RANDOM_SEED)
    rng.shuffle(filler_candidates)

    if len(filler_candidates) < 35:
        raise RuntimeError(
            "Not enough suitable filler names for the killer's page."
        )

    killer_fillers = filler_candidates[:35]

    # Remove these names from the general pool so that they
    # cannot be used a second time elsewhere.
    used_killer_fillers = set(killer_fillers)

    remaining_names = list(pool - used_killer_fillers)
    rng.shuffle(remaining_names)

    # --------------------------------------------------------
    # Create pages with the desired capacities.
    # --------------------------------------------------------

    pages = []

    for page_number in range(1, TOTAL_PAGES + 1):
        if page_number == KILLER_PAGE:
            size = 39
        elif page_number == KILLER_PAGE + 1:
            size = 41
        else:
            size = ENTRIES_PER_PAGE

        pages.append([None] * size)

    # --------------------------------------------------------
    # Helper to place a name at a particular position.
    # Positions are 1-based.
    # --------------------------------------------------------

    def put(page_number, position, name):
        page = pages[page_number - 1]
        index = position - 1

        if not 0 <= index < len(page):
            raise ValueError(
                f"Invalid position {position} on page {page_number}."
            )

        if page[index] is not None:
            raise ValueError(
                f"Page {page_number}, position {position} is occupied."
            )

        page[index] = name

    # --------------------------------------------------------
    # Place the killer's page.
    # --------------------------------------------------------

    # The killer and Eli sit at the bottom of the left column,
    # one directly below the other, so clue 9 holds whether
    # the page is read column by column or row by row.
    killer_entries = [
        "Oliver",
        "Oliver",
        *killer_fillers[:16],
        KILLER,
        "Eli",
        *killer_fillers[16:],
    ]

    if len(killer_entries) != 39:
        raise AssertionError(
            f"Killer page should contain 39 entries, "
            f"but contains {len(killer_entries)}."
        )

    pages[KILLER_PAGE - 1] = killer_entries

    # --------------------------------------------------------
    # Place the names required by the clues.
    # --------------------------------------------------------

    special_placements = {
        100: ["Anna"],
        373: ["Kim"],
        374: ["George", "Sasha"],
        361: ["John"],
        362: ["Paul"],
        363: ["Ringo"],
        600: ["Zack"],
    }

    for page_number, required_names in special_placements.items():
        for position, name in enumerate(required_names, start=1):
            put(page_number, position, name)

    # --------------------------------------------------------
    # Fill every remaining position.
    # --------------------------------------------------------

    cursor = 0

    for page_number, page in enumerate(pages, start=1):
        for index, current in enumerate(page):
            if current is not None:
                continue

            if cursor >= len(remaining_names):
                raise RuntimeError(
                    "Not enough unique names to fill all pages. "
                    f"Filled {cursor:,} additional positions, "
                    f"but more are required."
                )

            page[index] = remaining_names[cursor]
            cursor += 1

    # --------------------------------------------------------
    # Validate the completed book.
    # --------------------------------------------------------

    all_entries = [
        name
        for page in pages
        for name in page
    ]

    if len(all_entries) != TOTAL_ENTRIES:
        raise AssertionError(
            f"Expected {TOTAL_ENTRIES:,} entries, "
            f"got {len(all_entries):,}."
        )

    if len(pages) != TOTAL_PAGES:
        raise AssertionError(
            f"Expected {TOTAL_PAGES:,} pages, got {len(pages):,}."
        )

    counts = Counter(all_entries)

    duplicates = {
        name: count
        for name, count in counts.items()
        if count > 1
    }

    if duplicates != {"Oliver": 2}:
        raise AssertionError(
            f"Unexpected duplicate names: {duplicates}"
        )

    if len(counts) != TOTAL_ENTRIES - 1:
        raise AssertionError(
            f"Expected {TOTAL_ENTRIES - 1:,} distinct names, "
            f"got {len(counts):,}."
        )

    if pages[KILLER_PAGE - 1].count(KILLER) != 1:
        raise AssertionError(
            "The killer must appear exactly once on the killer's page."
        )

    if pages[KILLER_PAGE - 1].count("Oliver") != 2:
        raise AssertionError(
            "Oliver must appear twice on the killer's page."
        )

    print(f"Pages created: {len(pages):,}")
    print(f"Entries created: {len(all_entries):,}")
    print(f"Distinct names: {len(counts):,}")
    print(f"Additional names used: {cursor:,}")
    print("Only repeated name: Oliver")
    print("Page structure validated.")

    return pages


# ============================================================
# PDF LAYOUT
# ============================================================

def create_pdf(pages):
    """
    Render the book with a page number at the bottom of every
    page and no numbering beside names.

    Chapter titles appear only at the beginning of chapters.
    Continuation pages do not repeat the chapter heading.
    """

    print("Creating the PDF...")

    pdf = canvas.Canvas(
        str(OUTPUT_PDF),
        pagesize=A4,
        pageCompression=1,
    )

    pdf.setTitle("The Killer Name Index")
    pdf.setAuthor("Mystery Puzzle")
    pdf.setSubject("A detective puzzle containing 30,000 names")

    width, height = A4

    margin_left = 18 * mm
    margin_right = 18 * mm
    margin_top = 18 * mm
    margin_bottom = 16 * mm

    left_x = margin_left
    right_x = width / 2 + 5 * mm

    # The entries are laid out in two columns.
    line_height = 10 * mm

    for page_number, entries in enumerate(pages, start=1):
        chapter_number = chapter_number_for_page(page_number)

        # A chapter begins every 30 pages.
        is_chapter_start = (page_number - 1) % 30 == 0

        if is_chapter_start:
            title = CHAPTER_TITLES[chapter_number - 1]

            pdf.setFont("Helvetica-Bold", 17)
            pdf.drawString(
                margin_left,
                height - margin_top,
                f"CHAPTER {chapter_number}",
            )

            pdf.setFont("Helvetica-Bold", 12)
            pdf.drawString(
                margin_left,
                height - margin_top - 9 * mm,
                title.upper(),
            )

            pdf.setLineWidth(0.5)
            pdf.line(
                margin_left,
                height - margin_top - 13 * mm,
                width - margin_right,
                height - margin_top - 13 * mm,
            )

            start_y = height - margin_top - 23 * mm

        else:
            # No chapter title on continuation pages.
            start_y = height - margin_top

        split = (len(entries) + 1) // 2

        left_column = entries[:split]
        right_column = entries[split:]

        # Use a slightly smaller font for long names.
        for column, x in (
            (left_column, left_x),
            (right_column, right_x),
        ):
            for row, name in enumerate(column):
                y = start_y - row * line_height

                if y < margin_bottom:
                    raise RuntimeError(
                        f"Text overflow on internal page {page_number}. "
                        "Reduce line_height or font size."
                    )

                font_size = 9.5 if len(name) <= 13 else 8.5
                pdf.setFont("Helvetica", font_size)

                # No visible entry numbers.
                pdf.drawString(x, y, name)

        # Page numbers let the solver count pages for clues
        # 6, 12, 14 and 16.
        pdf.setFont("Helvetica", 9)
        pdf.drawCentredString(
            width / 2,
            margin_bottom / 2,
            str(page_number),
        )

        pdf.showPage()

        if page_number % 100 == 0:
            print(f"Rendered {page_number:,}/{TOTAL_PAGES:,} pages")

    pdf.save()

    print(f"PDF created: {OUTPUT_PDF.resolve()}")


# ============================================================
# VALIDATE THE 18 CLUES
# ============================================================

def validate_puzzle(pages):
    """
    Check all 18 clues against the generated book.

    If a condition fails, the program stops rather than
    producing an apparently valid answer key.
    """

    killer_page = KILLER_PAGE
    killer_entries = pages[killer_page - 1]

    flat = [
        name
        for page in pages
        for name in page
    ]

    counts = Counter(flat)

    def unique_page_of(name):
        matches = [
            page_number
            for page_number, page in enumerate(pages, start=1)
            if name in page
        ]

        if len(matches) != 1:
            raise AssertionError(
                f"{name} must appear on exactly one page; "
                f"found {matches}"
            )

        return matches[0]

    anna_page = unique_page_of("Anna")
    zack_page = unique_page_of("Zack")
    kim_page = unique_page_of("Kim")
    sasha_page = unique_page_of("Sasha")

    # The page opposite the killer is the preceding page
    # for this puzzle's intended book layout.
    opposite_page = killer_page - 1

    killer_index = flat.index(KILLER)
    eli_index = flat.index("Eli")

    # The same page read row by row across both columns,
    # mirroring the column split in create_pdf.
    split = (len(killer_entries) + 1) // 2
    row_entries = [
        name
        for pair in zip_longest(
            killer_entries[:split], killer_entries[split:]
        )
        for name in pair
        if name is not None
    ]
    row_distance = abs(
        row_entries.index(KILLER) - row_entries.index("Eli")
    )

    chapter_number = chapter_number_for_page(killer_page)
    chapter_title = CHAPTER_TITLES[chapter_number - 1]

    chapter_first_page = (chapter_number - 1) * 30
    chapter_last_page = chapter_first_page + 30

    chapter_names = {
        name
        for page in pages[
            chapter_first_page:chapter_last_page
        ]
        for name in page
    }

    # --------------------------------------------------------
    # All 18 clues
    # --------------------------------------------------------

    checks = [
        (
            "1. The killer's name is longer than three letters.",
            len(KILLER) > 3,
            f"{KILLER} has {len(KILLER)} letters.",
        ),
        (
            "2. The killer's name does not start with an S.",
            not KILLER.lower().startswith("s"),
            f"The name starts with {KILLER[0]}.",
        ),
        (
            "3. The killer's name contains at least two vowels.",
            sum(ch in VOWELS for ch in KILLER.lower()) >= 2,
            f"{KILLER} contains "
            f"{sum(ch in VOWELS for ch in KILLER.lower())} vowels.",
        ),
        (
            "4. The killer is on a page with a repeated name.",
            Counter(killer_entries)[REPEATED_NAME] == 2,
            f"{REPEATED_NAME} appears twice on the killer's page.",
        ),
        (
            "5. The killer's name has no consecutive repeated letter.",
            not any(
                KILLER.lower()[i] == KILLER.lower()[i + 1]
                for i in range(len(KILLER) - 1)
            ),
            "No consecutive letters are identical.",
        ),
        (
            "6. The killer's page is between Anna's page and Zack's page.",
            anna_page < killer_page < zack_page,
            f"Anna: {anna_page}; killer: {killer_page}; Zack: {zack_page}.",
        ),
        (
            "7. The killer's name is not six letters long.",
            len(KILLER) != 6,
            f"{KILLER} has {len(KILLER)} letters.",
        ),
        (
            "8. The letters x, y and z are not in the killer's name.",
            not any(ch in KILLER.lower() for ch in "xyz"),
            "None of x, y or z occurs in the name.",
        ),
        (
            "9. A three-letter name is no more than ten names away.",
            len("Eli") == 3
            and abs(killer_index - eli_index) <= 10
            and row_distance <= 10,
            f"Eli is {abs(killer_index - eli_index)} entries away "
            f"reading by column, {row_distance} reading by row.",
        ),
        (
            "10. The first name on the killer's page shares a letter with the killer.",
            bool(
                set(killer_entries[0].lower())
                & set(KILLER.lower())
            ),
            f"The first entry is {killer_entries[0]}.",
        ),
        (
            "11. The killer's page contains fewer than three names starting with M.",
            sum(
                name.startswith("M")
                for name in killer_entries
            ) < 3,
            f"{sum(name.startswith('M') for name in killer_entries)} "
            "names start with M.",
        ),
        (
            "12. A Kardashian is within four pages of the killer.",
            abs(kim_page - killer_page) <= 4,
            f"Kim is on page {kim_page}.",
        ),
        (
            "13. The killer is not on a page with an even number of names.",
            len(killer_entries) % 2 == 1,
            f"The killer's page has {len(killer_entries)} entries.",
        ),
        (
            "14. The opposite page contains a US president's first name.",
            any(
                name in PRESIDENT_FIRST_NAMES
                for name in pages[opposite_page - 1]
            ),
            f"Page {opposite_page} contains George.",
        ),
        (
            "15. The killer appears in a chapter with a place in its name.",
            CHAPTER_HAS_PLACE[chapter_number - 1],
            f"Chapter {chapter_number}: {chapter_title}. "
            f"{sum(CHAPTER_HAS_PLACE)} of {len(CHAPTERS)} chapter "
            "titles contain a place.",
        ),
        (
            "16. The killer's page is no more than one page away from Sasha.",
            abs(sasha_page - killer_page) <= 1,
            f"Sasha is on page {sasha_page}.",
        ),
        (
            "17. The killer's chapter contains all four Beatles.",
            BEATLES.issubset(chapter_names),
            "John, Paul, George and Ringo are in the same chapter.",
        ),
        (
            "18. The killer isn't Alice.",
            KILLER != "Alice",
            f"The killer is {KILLER}.",
        ),
    ]

    # --------------------------------------------------------
    # Global integrity checks
    # --------------------------------------------------------

    assert len(flat) == TOTAL_ENTRIES

    duplicates = {
        name: count
        for name, count in counts.items()
        if count > 1
    }

    assert duplicates == {REPEATED_NAME: 2}

    assert len(counts) == TOTAL_ENTRIES - 1

    assert len(killer_entries) == 39

    assert len(CHAPTERS) == chapter_number_for_page(TOTAL_PAGES)

    # Clue 15 must eliminate at least one chapter.
    assert not all(CHAPTER_HAS_PLACE), (
        "Every chapter title contains a place, so clue 15 "
        "eliminates nothing."
    )

    # All names on the killer's page except Catherine must fail
    # at least one name-level clue.
    candidates = sorted({
        name
        for name in set(killer_entries)
        if name_satisfies_name_clues(name)
    })

    assert candidates == [KILLER], (
        "The killer page does not have a unique name-level "
        f"candidate. Candidates: {candidates}"
    )

    failed = [
        description
        for description, passed, _ in checks
        if not passed
    ]

    if failed:
        raise AssertionError(
            "Puzzle validation failed:\n"
            + "\n".join(failed)
        )

    print("All 18 clues passed validation.")
    print(f"Unique candidate on killer's page: {KILLER}")

    return checks, candidates


# ============================================================
# ANSWER KEY
# ============================================================

def write_solution_key(checks, candidates):
    """
    Create a separate text file containing the answer
    and explanations of all clues.
    """

    with OUTPUT_KEY.open("w", encoding="utf-8") as file:
        file.write("KILLER NAME PUZZLE — SOLUTION KEY\n")
        file.write("=" * 55 + "\n\n")

        file.write(f"Killer: {KILLER}\n")
        file.write(f"Internal killer page: {KILLER_PAGE}\n")
        file.write(f"Total entries: {TOTAL_ENTRIES:,}\n")
        file.write(f"Distinct names: {TOTAL_ENTRIES - 1:,}\n")
        file.write(f"Total pages: {TOTAL_PAGES:,}\n")
        file.write(f"Only repeated name: {REPEATED_NAME} (twice)\n\n")

        file.write("VERIFICATION OF THE 18 CLUES\n")
        file.write("=" * 55 + "\n\n")

        for description, passed, explanation in checks:
            file.write(f"{description}\n")
            file.write(
                f"Result: {'PASS' if passed else 'FAIL'}\n"
            )
            file.write(f"Explanation: {explanation}\n\n")

        file.write("CANDIDATE CHECK\n")
        file.write("=" * 55 + "\n")

        for candidate in candidates:
            file.write(f"- {candidate}\n")

        file.write(
            "\nOnly Catherine satisfies all name-level clues "
            "on the killer's page.\n"
        )

    print(f"Solution key created: {OUTPUT_KEY.resolve()}")


# ============================================================
# MAIN
# ============================================================

def main():
    print("=" * 60)
    print("KILLER NAME PUZZLE GENERATOR")
    print("=" * 60)

    pages = build_pages()

    # Do not create the PDF until the clues pass validation.
    checks, candidates = validate_puzzle(pages)

    create_pdf(pages)

    write_solution_key(checks, candidates)

    print()
    print("=" * 60)
    print("SUCCESS")
    print("=" * 60)
    print(f"PDF: {OUTPUT_PDF.resolve()}")
    print(f"Answer key: {OUTPUT_KEY.resolve()}")


if __name__ == "__main__":
    main()
