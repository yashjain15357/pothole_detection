#!/usr/bin/env bash
set -e

echo "==> Upgrading pip..."
pip install --upgrade pip

echo "==> Installing Python requirements..."
pip install -r backend/requirements.txt

# If node and npm are available, build frontend; otherwise, pre-built dist in repo will be used
if command -v npm >/dev/null 2>&1; then
    echo "==> Node.js detected, building React frontend..."
    cd frontend
    npm install
    npm run build
    cd ..
    mkdir -p backend/frontend/dist
    cp -r frontend/dist/. backend/frontend/dist/
    echo "==> Frontend build completed successfully!"
else
    echo "==> Node.js not detected, using committed pre-built React frontend in backend/frontend/dist"
fi

echo "==> Full build completed successfully!"
