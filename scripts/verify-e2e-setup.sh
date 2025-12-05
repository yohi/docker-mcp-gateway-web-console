#!/bin/bash

# Script to verify E2E test setup
# This script checks that all necessary components are in place

set -e

# Get script directory and project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}Verifying E2E test setup...${NC}"

# Check if Playwright is installed
echo -n "Checking Playwright installation... "
if (cd "$PROJECT_ROOT/frontend" && npx playwright --version > /dev/null 2>&1); then
    echo -e "${GREEN}✓${NC}"
else
    echo -e "${RED}✗${NC}"
    echo -e "${RED}Playwright is not installed. Run: cd frontend && npm install${NC}"
    exit 1
fi

# Check if test files exist
echo -n "Checking E2E test files... "
if [ -f "$PROJECT_ROOT/frontend/e2e/auth.spec.ts" ] && \
   [ -f "$PROJECT_ROOT/frontend/e2e/catalog.spec.ts" ] && \
   [ -f "$PROJECT_ROOT/frontend/e2e/containers.spec.ts" ] && \
   [ -f "$PROJECT_ROOT/frontend/e2e/inspector.spec.ts" ]; then
    echo -e "${GREEN}✓${NC}"
else
    echo -e "${RED}✗${NC}"
    echo -e "${RED}Some E2E test files are missing${NC}"
    exit 1
fi

# Check if Playwright config exists
echo -n "Checking Playwright configuration... "
if [ -f "$PROJECT_ROOT/frontend/playwright.config.ts" ]; then
    echo -e "${GREEN}✓${NC}"
else
    echo -e "${RED}✗${NC}"
    echo -e "${RED}Playwright configuration is missing${NC}"
    exit 1
fi

# Check if Docker Compose files exist
echo -n "Checking Docker Compose files... "
if [ -f "$PROJECT_ROOT/docker-compose.yml" ] && [ -f "$PROJECT_ROOT/docker-compose.test.yml" ]; then
    echo -e "${GREEN}✓${NC}"
else
    echo -e "${RED}✗${NC}"
    echo -e "${RED}Docker Compose files are missing${NC}"
    exit 1
fi

# Validate Docker Compose configurations
echo -n "Validating Docker Compose configurations... "
if (cd "$PROJECT_ROOT" && docker-compose config --quiet 2>/dev/null && docker-compose -f docker-compose.test.yml config --quiet 2>/dev/null); then
    echo -e "${GREEN}✓${NC}"
else
    echo -e "${RED}✗${NC}"
    echo -e "${RED}Docker Compose configuration is invalid${NC}"
    exit 1
fi

# Check if TypeScript compiles
echo -n "Checking TypeScript compilation... "
if (cd "$PROJECT_ROOT/frontend" && npx tsc --noEmit e2e/*.ts 2>/dev/null); then
    echo -e "${GREEN}✓${NC}"
else
    echo -e "${RED}✗${NC}"
    echo -e "${RED}TypeScript compilation failed${NC}"
    exit 1
fi

# Check if GitHub Actions workflow exists
echo -n "Checking GitHub Actions workflow... "
if [ -f "$PROJECT_ROOT/.github/workflows/e2e-tests.yml" ]; then
    echo -e "${GREEN}✓${NC}"
else
    echo -e "${YELLOW}⚠${NC} GitHub Actions workflow not found (optional)"
fi

# Check if documentation exists
echo -n "Checking documentation... "
if [ -f "$PROJECT_ROOT/frontend/e2e/README.md" ] && [ -f "$PROJECT_ROOT/INTEGRATION_TESTING.md" ]; then
    echo -e "${GREEN}✓${NC}"
else
    echo -e "${YELLOW}⚠${NC} Some documentation is missing (optional)"
fi

echo ""
echo -e "${GREEN}✓ E2E test setup verification complete!${NC}"
echo ""
echo "Next steps:"
echo "1. Install Playwright browsers: cd frontend && npx playwright install"
echo "2. Run E2E tests: ./scripts/run-e2e-tests.sh"
echo "3. Or run tests locally: cd frontend && npm run test:e2e"
echo ""
