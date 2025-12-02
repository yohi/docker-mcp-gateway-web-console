#!/bin/bash

echo "🔍 Verifying Docker MCP Gateway Console setup..."
echo ""

# Check if required directories exist
echo "📁 Checking directory structure..."
directories=(
    "frontend"
    "frontend/app"
    "backend"
    "backend/app"
    "backend/app/api"
    "backend/app/models"
    "backend/app/services"
    "backend/tests"
)

for dir in "${directories[@]}"; do
    if [ -d "$dir" ]; then
        echo "  ✓ $dir"
    else
        echo "  ✗ $dir (missing)"
        exit 1
    fi
done

echo ""
echo "📄 Checking configuration files..."
files=(
    "frontend/package.json"
    "frontend/tsconfig.json"
    "frontend/next.config.js"
    "frontend/tailwind.config.ts"
    "backend/requirements.txt"
    "backend/pyproject.toml"
    "backend/app/main.py"
    "backend/app/config.py"
    "docker-compose.yml"
    "README.md"
)

for file in "${files[@]}"; do
    if [ -f "$file" ]; then
        echo "  ✓ $file"
    else
        echo "  ✗ $file (missing)"
        exit 1
    fi
done

echo ""
echo "✅ All checks passed! Project structure is set up correctly."
echo ""
echo "Next steps:"
echo "  1. Install frontend dependencies: cd frontend && npm install"
echo "  2. Install backend dependencies: cd backend && pip install -r requirements.txt"
echo "  3. Copy environment files:"
echo "     - cp frontend/.env.local.example frontend/.env.local"
echo "     - cp backend/.env.example backend/.env"
echo "  4. Start development: docker-compose up"
