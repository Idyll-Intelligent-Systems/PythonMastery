import os
import sys
from pathlib import Path

# Ensure the repository root is importable when running pytest from any location
ROOT_DIR = Path(__file__).resolve().parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

# Also ensure top-level packages (VEZEPy*) import correctly when tests run from subpackages
PARENT = ROOT_DIR
if str(PARENT) not in sys.path:
    sys.path.insert(0, str(PARENT))
