"""Pytest bootstrap: deterministic fixture mode, no live credentials."""

import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ["FIELDROOK_FIXTURES"] = "always"
os.environ["MODEL_API_KEY"] = ""

_db_fd, _db_path = tempfile.mkstemp(prefix="fieldrook-test-", suffix=".db")
os.close(_db_fd)
os.environ["FIELDROOK_DB_PATH"] = _db_path
os.environ["FIELDROOK_DEMO_STATE"] = tempfile.mkdtemp(prefix="fieldrook-demo-")
os.environ.pop("FIELDROOK_FIXTURE_WORKER", None)
os.environ.pop("FIELDROOK_ACTIONS_ENABLED", None)
