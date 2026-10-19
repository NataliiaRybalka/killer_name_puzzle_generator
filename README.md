python3.14 -m venv .venv

pip install reportlab

source .venv/bin/activate

python main.py

# Check that the clues lead to exactly one name (spoiler-free)

python check_solution.py
