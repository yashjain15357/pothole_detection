import os
import sys
import importlib.util
from pathlib import Path

root_dir = Path(__file__).resolve().parent
backend_dir = root_dir / 'backend'

if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

os.chdir(str(backend_dir))

backend_app_path = backend_dir / 'app.py'
spec = importlib.util.spec_from_file_location("backend_app", str(backend_app_path))
backend_module = importlib.util.module_from_spec(spec)
sys.modules["backend_app"] = backend_module
spec.loader.exec_module(backend_module)

app = backend_module.app
