"""Pytest bootstrap: deterministic fixture mode, no live credentials."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ["FIELDROOK_FIXTURES"] = "always"
os.environ.pop("MODEL_API_KEY", None)
