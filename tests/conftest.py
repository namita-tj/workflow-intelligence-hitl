# Ensure project root is importable when running tests
# Adds the repository root (parent of the tests folder) to sys.path so
# imports like `from rule_based_detector import ...` work regardless of
# how pytest sets the current working directory.
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
