"""Application settings kept in one easy-to-find place."""

from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
DATABASE_PATH = BASE_DIR / "library.db"
LOAN_PERIOD_DAYS = 14
DAILY_FINE_NAIRA = 200
APP_TITLE = "Digital Library and Book Lending System"

