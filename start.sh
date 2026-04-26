#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENGINE_DIR="$PROJECT_ROOT/backend/engine"
ENGINE_BUILD_DIR="$ENGINE_DIR/build"
API_DIR="$PROJECT_ROOT/backend/api"
FRONTEND_DIR="$PROJECT_ROOT/frontend"

# 1. Build C++ Engine
echo "Building C++ Engine..."
mkdir -p "$ENGINE_BUILD_DIR"
cd "$ENGINE_BUILD_DIR"
cmake ..
cmake --build .

# 2. Setup Python Environment
echo "Setting up Python Environment..."
cd "$API_DIR"
if [ ! -d "venv" ]; then
  python -m venv venv
fi
./venv/bin/python -m pip install -r requirements.txt
cp ../engine/build/logistics_engine.*.pyd . 2>/dev/null || true
cp ../engine/build/logistics_engine.*.so . 2>/dev/null || true
./venv/bin/python -m uvicorn main:app --port 8000 &

# 3. Setup Frontend
echo "Setting up Frontend..."
cd "$FRONTEND_DIR"
npm install
npm run dev
