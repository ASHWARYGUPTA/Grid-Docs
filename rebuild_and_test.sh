#!/bin/bash
set -e

echo "==================================="
echo "🧹 1. CLEARING ALL CACHES"
echo "==================================="
echo "Cleaning Python caches..."
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
rm -rf backend/.pytest_cache backend/.mypy_cache backend/.ruff_cache backend/.uv 2>/dev/null || true

echo "Cleaning Node caches..."
rm -rf frontend/.next frontend/node_modules/.cache 2>/dev/null || true

echo "Clearing Docker builder cache..."
docker builder prune -f

echo ""
echo "==================================="
echo "🧪 2. RUNNING ALL TESTS"
echo "==================================="
echo "Running backend test suite..."
cd backend
uv run pytest
cd ..

# If you have frontend tests, you can uncomment this:
# echo "Running frontend test suite..."
# cd frontend
# npm run test
# cd ..

echo ""
echo "==================================="
echo "🏗️ 3. REBUILDING CODEBASE"
echo "==================================="
echo "Building Frontend production bundle..."
cd frontend
npm run build
cd ..

echo "Rebuilding and restarting Docker containers (without cache)..."
docker compose down
docker compose build --no-cache
docker compose up -d

echo ""
echo "✅ SUCCESS: All tests passed and codebase rebuilt from scratch!"
