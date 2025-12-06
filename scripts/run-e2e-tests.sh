#!/bin/bash

# Script to run E2E tests with Docker Compose
# This script starts the application stack and runs Playwright tests

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Resolve project root
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMPOSE_FILE="$PROJECT_ROOT/docker-compose.test.yml"

echo -e "${GREEN}Starting E2E test environment...${NC}"

# Function to cleanup on exit
cleanup() {
    echo -e "${YELLOW}Cleaning up...${NC}"
    cd "$PROJECT_ROOT"
    docker-compose -f "$COMPOSE_FILE" down -v
}

# Register cleanup function
trap cleanup EXIT

# Start the services
echo -e "${GREEN}Starting services...${NC}"
cd "$PROJECT_ROOT"
docker-compose -f "$COMPOSE_FILE" up -d frontend backend

# Wait for services to be healthy
echo -e "${GREEN}Waiting for services to be ready...${NC}"
timeout=120
elapsed=0
interval=5

while [ $elapsed -lt $timeout ]; do
    if docker-compose -f "$COMPOSE_FILE" ps | grep -q "healthy"; then
        frontend_healthy=$(docker-compose -f "$COMPOSE_FILE" ps frontend | grep -c "healthy" || echo "0")
        backend_healthy=$(docker-compose -f "$COMPOSE_FILE" ps backend | grep -c "healthy" || echo "0")
        
        if [ "$frontend_healthy" -gt 0 ] && [ "$backend_healthy" -gt 0 ]; then
            echo -e "${GREEN}Services are ready!${NC}"
            break
        fi
    fi
    
    echo "Waiting for services to be healthy... ($elapsed/$timeout seconds)"
    sleep $interval
    elapsed=$((elapsed + interval))
done

if [ $elapsed -ge $timeout ]; then
    echo -e "${RED}Timeout waiting for services to be ready${NC}"
    docker-compose -f "$COMPOSE_FILE" logs
    exit 1
fi

# Run E2E tests
echo -e "${GREEN}Running E2E tests...${NC}"
cd "$PROJECT_ROOT/frontend"

# Install Playwright browsers if not already installed
if [ ! -d "$HOME/.cache/ms-playwright" ]; then
    echo -e "${YELLOW}Installing Playwright browsers...${NC}"
    npx playwright install --with-deps
fi

# Run tests
if npm run test:e2e; then
    echo -e "${GREEN}E2E tests passed!${NC}"
    exit 0
else
    echo -e "${RED}E2E tests failed!${NC}"
    
    # Show logs on failure
    cd "$PROJECT_ROOT"
    echo -e "${YELLOW}Backend logs:${NC}"
    docker-compose -f "$COMPOSE_FILE" logs backend
    
    echo -e "${YELLOW}Frontend logs:${NC}"
    docker-compose -f "$COMPOSE_FILE" logs frontend
    
    exit 1
fi
