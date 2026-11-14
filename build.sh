#!/usr/bin/env bash
# Render build script for Fix My City — Pothole Detection
set -e

echo "==> Installing Python dependencies..."
pip install --upgrade pip
pip install -r backend/requirements.txt

echo "==> Installing Node dependencies & building React frontend..."
cd frontend
npm ci
npm run build
cd ..

echo "==> Copying React build into Flask static directory..."
mkdir -p backend/frontend/dist
cp -r frontend/dist/. backend/frontend/dist/

echo "==> Build complete!"
