"""
AI QA Regression Testing Agent — Streamlit entry point.
Run from project root: streamlit run app.py
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from dashboard.ui import main

if __name__ == "__main__":
    main()
