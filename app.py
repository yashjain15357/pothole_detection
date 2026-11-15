import os
import sys
import importlib.util
from pathlib import Path

root_dir = Path(__file__).resolve().parent
backend_dir = root_dir / 'backend'

if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

os.chdir(str(backend_dir))

# Load backend/app.py explicitly to avoid circular import with root app.py
backend_app_path = backend_dir / 'app.py'
spec = importlib.util.spec_from_file_location("backend_app", str(backend_app_path))
backend_module = importlib.util.module_from_spec(spec)
sys.modules["backend_app"] = backend_module
spec.loader.exec_module(backend_module)

app = backend_module.app

if __name__ == '__main__':
    from database import init_database
    init_database()
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
