#!/usr/bin/env bash
# Render build script for Pothole Detection Backend API
set -e

echo "==> Upgrading pip..."
pip install --upgrade pip

echo "==> Installing Python requirements..."
pip install -r backend/requirements.txt

echo "==> Backend build completed successfully!"
