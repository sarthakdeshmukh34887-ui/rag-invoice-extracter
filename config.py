import os
from dotenv import load_dotenv

load_dotenv()

# Change the variable name here to match what app.py expects:
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# Root directory alignments
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
INPUT_FOLDER = os.path.join(BASE_DIR, "invoices")
OUTPUT_FOLDER = os.path.join(BASE_DIR, "output")

# Auto-generate paths if missing
os.makedirs(INPUT_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)