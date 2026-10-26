"""Pytest bootstrap: deterministic fixture mode, no live credentials."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ["FIELDROOK_FIXTURES"] = "always"
# Set (not pop): load_settings() loads the root .env file but never overrides
# keys already present, so this keeps the suite hermetic even when a real key
# exists on the machine. Empty string means "no key" to load_settings().
os.environ["MODEL_API_KEY"] = ""
