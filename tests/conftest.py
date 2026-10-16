import os
import sys

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

os.environ.setdefault("SECRET_KEY", "test-only-secret-key")
os.environ.setdefault("APP_ENV", "test")
