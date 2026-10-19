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
    - Exactly one duplicated name: REPEATED_NAME.
    - Page numbers at the bottom of every page.
    - No visible numbering beside names.
    - 25 chapters; only some titles contain a place.
    - Chapter titles appear only at chapter beginnings.
    - Names in COLUMNS columns, filled column by column.
    - Validation of all 18 clues, including that every
      name-level clue eliminates at least one name.
    - Separate answer key.
"""

import math
import random
import re
import urllib.request

from collections import Counter
from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

from conf import (
    BALANCING_PAGE,
    BEATLES,
    BEATLE_PAGES,
    CHAPTERS,
    CHAPTER_HAS_PLACE,
    CHAPTER_TITLES,
    COLUMNS,
    DECOY,
    ENTRIES_PER_PAGE,
    FILLERS_PER_NAME_CLUE,
    KARDASHIAN,
    KARDASHIAN_FIRST_NAMES,
    KILLER,
    KILLER_PAGE,
    KILLER_PAGE_SIZE,
    LOWER_BOUND,
    NAMES_URL,
    NEIGHBOUR,
    OUTPUT_KEY,
    OUTPUT_PDF,
    PAGES_PER_CHAPTER,
    PRESIDENT_AFTER,
    PRESIDENT_BEFORE,
    PRESIDENT_FIRST_NAMES,
    RANDOM_SEED,
    RARE_INITIAL,
    REPEATED_NAME,
    SPECIAL_PLACEMENTS,
    THREE_LETTER_NAME,
    TOTAL_ENTRIES,
    TOTAL_PAGES,
    UPPER_BOUND,
    VOWELS,
)


# ============================================================
# NAME CLUES
# ============================================================

def has_double_letter(name):
    lower = name.lower()

    return any(
        lower[i] == lower[i + 1]
        for i in range(len(lower) - 1)
    )


# Clues that describe the killer's name itself.
NAME_CLUES = {
    1: lambda name: len(name) > 3,
    2: lambda name: not name.lower().startswith("s"),
    3: lambda name: sum(ch in VOWELS for ch in name.lower()) >= 2,
    5: lambda name: not has_double_letter(name),
    7: lambda name: len(name) != 6,
    8: lambda name: not any(ch in name.lower() for ch in "xyz"),
    18: lambda name: name != DECOY,
}


def failed_name_clues(name):
    return [
        number
        for number, passes in NAME_CLUES.items()
        if not passes(name)
    ]


def name_satisfies_name_clues(name):
    return not failed_name_clues(name)


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
    There are 25 chapters, each covering PAGES_PER_CHAPTER pages.
    """
    return (page_number - 1) // PAGES_PER_CHAPTER + 1


def chapter_title_for_page(page_number):
    chapter_number = chapter_number_for_page(page_number)
    return CHAPTER_TITLES[chapter_number - 1]


def page_size(page_number):
    """
    KILLER_PAGE has one entry fewer than ENTRIES_PER_PAGE,
    BALANCING_PAGE one more, so the book holds TOTAL_PAGES
    full pages' worth: TOTAL_ENTRIES.
    """
    if page_number == KILLER_PAGE:
        return KILLER_PAGE_SIZE

    if page_number == BALANCING_PAGE:
        return ENTRIES_PER_PAGE + 1

    return ENTRIES_PER_PAGE


def column_layout(entries):
    """
    Split a page into COLUMNS columns, filled column by column.
    Every column except possibly the last has the same height.
    """
    rows = math.ceil(len(entries) / COLUMNS)

    return [
        entries[start:start + rows]
        for start in range(0, len(entries), rows)
    ]


def row_reading_order(entries):
    """
    The page's entries read row by row across all columns.
    """
    columns = column_layout(entries)

    return [
        column[row]
        for row in range(len(columns[0]))
        for column in columns
        if row < len(column)
    ]


# ============================================================
# BUILD THE BOOK
# ============================================================

def pick_killer_page_fillers(pool, rng, count):
    """
    Choose the other names on the killer's page.

    Every filler fails at least one name clue. For each name
    clue, FILLERS_PER_NAME_CLUE fillers fail that clue alone,
    so the solver needs every name clue to reach the killer.
    No filler starts with RARE_INITIAL (clue 11).
    """

    by_failed_clues = {}

    for name in sorted(pool):
        if name.startswith(RARE_INITIAL):
            continue

        failed = tuple(failed_name_clues(name))

        if failed:
            by_failed_clues.setdefault(failed, []).append(name)

    fillers = []

    # Clue 18 is covered by the decoy itself.
    for number in NAME_CLUES:
        if number == 18:
            continue

        single = by_failed_clues.get((number,), [])

        if len(single) < FILLERS_PER_NAME_CLUE:
            raise RuntimeError(
                f"Not enough names that fail only clue {number}."
            )

        fillers += rng.sample(single, FILLERS_PER_NAME_CLUE)

    chosen = set(fillers)

    multiple = [
        name
        for failed, names in by_failed_clues.items()
        if len(failed) > 1
        for name in names
        if name not in chosen
    ]

    fillers += rng.sample(multiple, count - len(fillers))
    rng.shuffle(fillers)

    return fillers


def build_killer_page(fillers):
    """
    The repeated name opens the page twice. The killer and the
    three-letter name sit at the bottom of the left column, one
    directly below the other, so clue 9 holds whether the page
    is read column by column or row by row.
    """

    column_height = math.ceil(KILLER_PAGE_SIZE / COLUMNS)
    fillers_above_killer = column_height - 4

    return [
        REPEATED_NAME,
        REPEATED_NAME,
        *fillers[:fillers_above_killer],
        KILLER,
        THREE_LETTER_NAME,
        *fillers[fillers_above_killer:],
    ]


def build_pages():
    """
    Build the complete book.

    - TOTAL_ENTRIES entries on TOTAL_PAGES pages.
    - ENTRIES_PER_PAGE entries per page, except:
        * killer page: one fewer;
        * balancing page: one more.
    - Exactly one duplicate: REPEATED_NAME appears twice.
    - Required names are placed on designated pages.
    """

    print("Preparing the name list...")

    names = download_names()

    killer_page_names = {
        REPEATED_NAME, KILLER, THREE_LETTER_NAME, DECOY
    }

    reserved_names = killer_page_names | {
        name
        for placed in SPECIAL_PLACEMENTS.values()
        for name in placed
    }

    # Ensure all required names are available.
    names.update(reserved_names)

    # The placed Kardashian is the only one in the book, so
    # clue 12 points to a single page. Sorting keeps the book
    # reproducible for a given RANDOM_SEED.
    pool = sorted(names - reserved_names - KARDASHIAN_FIRST_NAMES)

    rng = random.Random(RANDOM_SEED)

    # The decoy takes one of the filler slots, at random.
    fillers = pick_killer_page_fillers(
        pool, rng, KILLER_PAGE_SIZE - 5
    )
    fillers.insert(rng.randrange(len(fillers) + 1), DECOY)

    used_fillers = set(fillers)
    remaining_names = [
        name for name in pool if name not in used_fillers
    ]
    rng.shuffle(remaining_names)

    # --------------------------------------------------------
    # Create pages with the desired capacities.
    # --------------------------------------------------------

    pages = [
        [None] * page_size(page_number)
        for page_number in range(1, TOTAL_PAGES + 1)
    ]

    pages[KILLER_PAGE - 1] = build_killer_page(fillers)

    for page_number, required_names in SPECIAL_PLACEMENTS.items():
        if page_number == KILLER_PAGE:
            raise ValueError("The killer's page is built separately.")

        for index, name in enumerate(required_names):
            pages[page_number - 1][index] = name

    # --------------------------------------------------------
    # Fill every remaining position.
    # --------------------------------------------------------

    cursor = 0

    for page in pages:
        for index, current in enumerate(page):
            if current is not None:
                continue

            if cursor >= len(remaining_names):
                raise RuntimeError(
                    "Not enough unique names to fill all pages."
                )

            page[index] = remaining_names[cursor]
            cursor += 1

    # --------------------------------------------------------
    # Validate the completed book.
    # --------------------------------------------------------

    all_entries = [name for page in pages for name in page]
    counts = Counter(all_entries)

    duplicates = {
        name: count
        for name, count in counts.items()
        if count > 1
    }

    if len(all_entries) != TOTAL_ENTRIES:
        raise AssertionError(
            f"Expected {TOTAL_ENTRIES:,} entries, "
            f"got {len(all_entries):,}."
        )

    if duplicates != {REPEATED_NAME: 2}:
        raise AssertionError(
            f"Unexpected duplicate names: {duplicates}"
        )

    if pages[KILLER_PAGE - 1].count(KILLER) != 1:
        raise AssertionError(
            "The killer must appear exactly once on the killer's page."
        )

    print(f"Pages created: {len(pages):,}")
    print(f"Entries created: {len(all_entries):,}")
    print(f"Distinct names: {len(counts):,}")
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

    column_width = (width - margin_left - margin_right) / COLUMNS
    column_gap = 3 * mm

    line_height = 8 * mm

    for page_number, entries in enumerate(pages, start=1):
        chapter_number = chapter_number_for_page(page_number)

        is_chapter_start = (page_number - 1) % PAGES_PER_CHAPTER == 0

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

        for column_index, column in enumerate(column_layout(entries)):
            x = margin_left + column_index * column_width

            for row, name in enumerate(column):
                y = start_y - row * line_height

                if y < margin_bottom:
                    raise RuntimeError(
                        f"Text overflow on internal page {page_number}. "
                        "Reduce line_height or font size."
                    )

                # Use a smaller font for names too wide for a column.
                font_size = 9.5 if len(name) <= 13 else 8.5

                while (
                    pdf.stringWidth(name, "Helvetica", font_size)
                    > column_width - column_gap
                ):
                    font_size -= 0.5

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
    Check all 18 clues against the generated book, and check
    that a solver applying them reaches the killer alone.

    If a condition fails, the program stops rather than
    producing an apparently valid answer key.
    """

    killer_page = KILLER_PAGE
    killer_entries = pages[killer_page - 1]

    flat = [name for page in pages for name in page]
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

    lower_name, upper_name = LOWER_BOUND[0], UPPER_BOUND[0]
    lower_page = unique_page_of(lower_name)
    upper_page = unique_page_of(upper_name)
    kardashian_page = unique_page_of(KARDASHIAN[0])
    neighbour_page = unique_page_of(NEIGHBOUR[0])

    def presidents_on(page_number):
        if not 1 <= page_number <= TOTAL_PAGES:
            return []

        return [
            name
            for name in pages[page_number - 1]
            if name in PRESIDENT_FIRST_NAMES
        ]

    # In a printed book the opposite page is the preceding one;
    # read on screen, it may be taken as the following one.
    opposite_pages = (killer_page - 1, killer_page + 1)

    killer_index = flat.index(KILLER)
    three_letter_index = flat.index(THREE_LETTER_NAME)

    # The same page read row by row across all columns,
    # mirroring the layout in create_pdf.
    row_entries = row_reading_order(killer_entries)
    row_distance = abs(
        row_entries.index(KILLER)
        - row_entries.index(THREE_LETTER_NAME)
    )

    def chapter_names(page_number):
        first = (chapter_number_for_page(page_number) - 1) \
            * PAGES_PER_CHAPTER

        return {
            name
            for page in pages[first:first + PAGES_PER_CHAPTER]
            for name in page
        }

    chapter_number = chapter_number_for_page(killer_page)
    chapter_title = CHAPTER_TITLES[chapter_number - 1]
    vowel_count = sum(ch in VOWELS for ch in KILLER.lower())
    rare_count = sum(
        name.startswith(RARE_INITIAL) for name in killer_entries
    )

    # --------------------------------------------------------
    # All 18 clues
    # --------------------------------------------------------

    checks = [
        (
            "1. The killer's name is longer than three letters.",
            NAME_CLUES[1](KILLER),
            f"{KILLER} has {len(KILLER)} letters.",
        ),
        (
            "2. The killer's name does not start with an S.",
            NAME_CLUES[2](KILLER),
            f"The name starts with {KILLER[0]}.",
        ),
        (
            "3. The killer's name contains at least two vowels.",
            NAME_CLUES[3](KILLER),
            f"{KILLER} contains {vowel_count} vowels.",
        ),
        (
            "4. The killer is on a page with a repeated name.",
            Counter(killer_entries)[REPEATED_NAME] == 2,
            f"{REPEATED_NAME} appears twice on the killer's page.",
        ),
        (
            "5. The killer's name has no consecutive repeated letter.",
            NAME_CLUES[5](KILLER),
            "No consecutive letters are identical.",
        ),
        (
            f"6. The killer's page is between {lower_name}'s page "
            f"and {upper_name}'s page.",
            lower_page < killer_page < upper_page,
            f"{lower_name}: {lower_page}; killer: {killer_page}; "
            f"{upper_name}: {upper_page}.",
        ),
        (
            "7. The killer's name is not six letters long.",
            NAME_CLUES[7](KILLER),
            f"{KILLER} has {len(KILLER)} letters.",
        ),
        (
            "8. The letters x, y and z are not in the killer's name.",
            NAME_CLUES[8](KILLER),
            "None of x, y or z occurs in the name.",
        ),
        (
            "9. A three-letter name is no more than ten names away.",
            len(THREE_LETTER_NAME) == 3
            and abs(killer_index - three_letter_index) <= 10
            and row_distance <= 10,
            f"{THREE_LETTER_NAME} is "
            f"{abs(killer_index - three_letter_index)} entries away "
            f"reading by column, {row_distance} reading by row.",
        ),
        (
            "10. The first name on the killer's page shares a letter "
            "with the killer.",
            bool(
                set(killer_entries[0].lower()) & set(KILLER.lower())
            ),
            f"The first entry is {killer_entries[0]}.",
        ),
        (
            "11. The killer's page contains fewer than three names "
            f"starting with {RARE_INITIAL}.",
            rare_count < 3,
            f"{rare_count} names start with {RARE_INITIAL}.",
        ),
        (
            "12. A Kardashian is within four pages of the killer.",
            abs(kardashian_page - killer_page) <= 4,
            f"{KARDASHIAN[0]} is on page {kardashian_page}.",
        ),
        (
            "13. The killer is not on a page with an even number "
            "of names.",
            len(killer_entries) % 2 == 1,
            f"The killer's page has {len(killer_entries)} entries.",
        ),
        (
            "14. The opposite page contains a US president's first "
            "name.",
            all(presidents_on(page) for page in opposite_pages),
            "; ".join(
                f"page {page}: {', '.join(presidents_on(page))}"
                for page in opposite_pages
            ) + ".",
        ),
        (
            "15. The killer appears in a chapter with a place in its "
            "name.",
            CHAPTER_HAS_PLACE[chapter_number - 1],
            f"Chapter {chapter_number}: {chapter_title}. "
            f"{sum(CHAPTER_HAS_PLACE)} of {len(CHAPTERS)} chapter "
            "titles contain a place.",
        ),
        (
            "16. The killer's page is no more than one page away "
            f"from {NEIGHBOUR[0]}.",
            abs(neighbour_page - killer_page) <= 1,
            f"{NEIGHBOUR[0]} is on page {neighbour_page}.",
        ),
        (
            "17. The killer's chapter contains all four Beatles.",
            BEATLES.issubset(chapter_names(killer_page)),
            "John, Paul, George and Ringo are in the same chapter.",
        ),
        (
            f"18. The killer isn't {DECOY}.",
            NAME_CLUES[18](KILLER),
            f"{DECOY} is on the killer's page and passes every "
            "other name clue.",
        ),
    ]

    failed = [
        description
        for description, passed, _ in checks
        if not passed
    ]

    if failed:
        raise AssertionError(
            "Puzzle validation failed:\n" + "\n".join(failed)
        )

    # --------------------------------------------------------
    # Global integrity checks
    # --------------------------------------------------------

    duplicates = {
        name: count
        for name, count in counts.items()
        if count > 1
    }

    assert len(flat) == TOTAL_ENTRIES
    assert duplicates == {REPEATED_NAME: 2}
    assert len(counts) == TOTAL_ENTRIES - 1
    assert len(killer_entries) == KILLER_PAGE_SIZE
    assert len(CHAPTERS) == chapter_number_for_page(TOTAL_PAGES)

    # Clue 15 must eliminate at least one chapter.
    assert not all(CHAPTER_HAS_PLACE), (
        "Every chapter title contains a place, so clue 15 "
        "eliminates nothing."
    )

    # --------------------------------------------------------
    # Page-level clues, applied as a solver would
    # --------------------------------------------------------

    kardashian_pages = [
        page_number
        for page_number, page in enumerate(pages, start=1)
        if KARDASHIAN_FIRST_NAMES & set(page)
    ]

    assert kardashian_pages == [kardashian_page], (
        f"Kardashians appear on pages {kardashian_pages}."
    )

    possible_pages = [
        page_number
        for page_number in range(1, TOTAL_PAGES + 1)
        if len(set(pages[page_number - 1]))
        < len(pages[page_number - 1])                       # 4
        and lower_page < page_number < upper_page           # 6
        and abs(kardashian_page - page_number) <= 4         # 12
        and len(pages[page_number - 1]) % 2 == 1            # 13
        and any(
            presidents_on(page)
            for page in (page_number - 1, page_number + 1)
        )                                                   # 14
        and CHAPTER_HAS_PLACE[
            chapter_number_for_page(page_number) - 1
        ]                                                   # 15
        and abs(neighbour_page - page_number) <= 1          # 16
        and BEATLES.issubset(chapter_names(page_number))    # 17
    ]

    assert possible_pages == [killer_page], (
        f"Page-level clues leave pages {possible_pages}."
    )

    # Each of clues 4 and 13 alone, within the range of clue 6,
    # must already single out the killer's page.
    for clue, test in (
        ("4", lambda page: len(set(page)) < len(page)),
        ("13", lambda page: len(page) % 2 == 1),
    ):
        matches = [
            page_number
            for page_number in range(lower_page + 1, upper_page)
            if test(pages[page_number - 1])
        ]

        assert matches == [killer_page], (
            f"Clue {clue} matches pages {matches}."
        )

    # --------------------------------------------------------
    # Name-level clues on the killer's page
    # --------------------------------------------------------

    eliminations = {
        name: failed_name_clues(name)
        for name in dict.fromkeys(killer_entries)
    }

    candidates = [
        name for name, failed in eliminations.items() if not failed
    ]

    assert candidates == [KILLER], (
        "The killer page does not have a unique name-level "
        f"candidate. Candidates: {candidates}"
    )

    # Every name clue must be the only reason some name on the
    # page is eliminated; otherwise that clue does no work.
    sole_reasons = {
        failed[0]
        for failed in eliminations.values()
        if len(failed) == 1
    }

    assert sole_reasons == set(NAME_CLUES), (
        "These name clues never eliminate a name on their own: "
        f"{sorted(set(NAME_CLUES) - sole_reasons)}"
    )

    print("All 18 clues passed validation.")
    print("Exactly one name is left on the killer's page.")

    return checks, eliminations


# ============================================================
# ANSWER KEY
# ============================================================

def write_solution_key(checks, eliminations):
    """
    Create a separate text file containing the answer,
    explanations of all clues and the elimination of every
    other name on the killer's page.
    """

    with OUTPUT_KEY.open("w", encoding="utf-8") as file:
        file.write("KILLER NAME PUZZLE — SOLUTION KEY\n")
        file.write("=" * 55 + "\n\n")

        file.write(f"Killer: {KILLER}\n")
        file.write(f"Killer's page: {KILLER_PAGE}\n")
        file.write(f"Total entries: {TOTAL_ENTRIES:,}\n")
        file.write(f"Distinct names: {TOTAL_ENTRIES - 1:,}\n")
        file.write(f"Total pages: {TOTAL_PAGES:,}\n")
        file.write(f"Only repeated name: {REPEATED_NAME} (twice)\n\n")

        file.write("VERIFICATION OF THE 18 CLUES\n")
        file.write("=" * 55 + "\n\n")

        for description, passed, explanation in checks:
            file.write(f"{description}\n")
            file.write(f"Result: {'PASS' if passed else 'FAIL'}\n")
            file.write(f"Explanation: {explanation}\n\n")

        file.write("NAMES ON THE KILLER'S PAGE\n")
        file.write("=" * 55 + "\n")

        for name, failed in eliminations.items():
            if failed:
                reasons = ", ".join(str(number) for number in failed)
                file.write(f"- {name}: eliminated by clue {reasons}\n")
            else:
                file.write(f"- {name}: satisfies every name clue\n")

        file.write(
            f"\nOnly {KILLER} satisfies all name-level clues "
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
    checks, eliminations = validate_puzzle(pages)

    create_pdf(pages)

    write_solution_key(checks, eliminations)

    print()
    print("=" * 60)
    print("SUCCESS")
    print("=" * 60)
    print(f"PDF: {OUTPUT_PDF.resolve()}")
    print(f"Answer key: {OUTPUT_KEY.resolve()}")


if __name__ == "__main__":
    main()
