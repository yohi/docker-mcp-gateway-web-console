#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: scripts/run-tests.sh {backend|frontend|e2e|all}

Runs test suites inside docker compose services with json/junit artifacts:
  backend  - pytest with coverage
  frontend - npm test (Jest) with coverage
  e2e      - npm run test:e2e (Playwright)
  all      - backend -> frontend -> e2e (stop on first failure)
EOF
}

if [ "${1:-}" = "-h" ] || [ "${1:-}" = "--help" ]; then
  usage
  exit 0
fi

if [ "$#" -lt 1 ]; then
  usage
  exit 2
fi

MODE=$1
case "$MODE" in
  backend|frontend|e2e|all) ;;
  *)
    usage >&2
    exit 2
    ;;
esac

COMPOSE_FILES=${COMPOSE_FILE:-docker-compose.yml}
IFS=':' read -r -a COMPOSE_ARRAY <<< "$COMPOSE_FILES"

if ! command -v docker >/dev/null 2>&1; then
  echo "ERROR: Docker is not installed or not in PATH" >&2
  exit 3
fi

if ! command -v timeout >/dev/null 2>&1; then
  echo "ERROR: timeout command is required" >&2
  exit 3
fi

for file in "${COMPOSE_ARRAY[@]}"; do
  if [ ! -f "$file" ]; then
    echo "ERROR: Compose file not found: $file" >&2
    exit 3
  fi
done

COMPOSE_FLAGS=()
for file in "${COMPOSE_ARRAY[@]}"; do
  COMPOSE_FLAGS+=("-f" "$file")
done

TTY_FLAG=""
if [ "${CI:-}" = "true" ] || [ "${TERM:-}" = "dumb" ] || [ ! -t 0 ]; then
  TTY_FLAG="-T"
fi

# When running all, widen the default timeout unless explicitly overridden.
if [ "$MODE" = "all" ] && [ -z "${TEST_TIMEOUT:-}" ]; then
  TEST_TIMEOUT=1200
fi

ensure_service_running() {
  local service="$1"
  local running_output
  if ! running_output=$(docker compose "${COMPOSE_FLAGS[@]}" ps --services --filter status=running); then
    echo "ERROR: Failed to inspect docker compose services" >&2
    return 3
  fi

  if ! echo "$running_output" | tr -d '\r' | grep -qx "$service"; then
    echo "ERROR: ${service} service is not running. Start with: docker compose up -d" >&2
    return 3
  fi

  return 0
}

run_with_timeout() {
  local duration="$1"
  shift

  set +e
  timeout "$duration" "$@"
  local exit_code=$?
  set -e

  if [ "$exit_code" -eq 124 ]; then
    echo "ERROR: Test timed out after ${duration} seconds" >&2
    return 4
  fi

  return "$exit_code"
}

run_backend_tests() {
  ensure_service_running "backend" || return $?

  local duration="${TEST_TIMEOUT:-300}"
  local cmd=(docker compose "${COMPOSE_FLAGS[@]}" exec)
  if [ -n "$TTY_FLAG" ]; then
    cmd+=("$TTY_FLAG")
  fi
  cmd+=(
    backend
    pytest
    --json-report
    --json-report-file=/tmp/pytest-results.json
    --cov
    --cov-report=json:/tmp/coverage.json
    --junit-xml=/tmp/junit.xml
  )

  run_with_timeout "$duration" "${cmd[@]}"
}

run_frontend_tests() {
  ensure_service_running "frontend" || return $?

  local duration="${TEST_TIMEOUT:-180}"
  local cmd=(docker compose "${COMPOSE_FLAGS[@]}" exec)
  if [ -n "$TTY_FLAG" ]; then
    cmd+=("$TTY_FLAG")
  fi
  cmd+=(
    frontend
    npm
    test
    --
    --json
    --outputFile=/tmp/jest-results.json
    --coverage
    --coverageReporters=json
    --reporters=default
    --reporters=jest-junit
  )

  run_with_timeout "$duration" "${cmd[@]}"
}

run_e2e_tests() {
  ensure_service_running "frontend" || return $?

  local duration="${TEST_TIMEOUT:-600}"
  local cmd=(docker compose "${COMPOSE_FLAGS[@]}" exec)
  if [ -n "$TTY_FLAG" ]; then
    cmd+=("$TTY_FLAG")
  fi
  cmd+=(
    frontend
    npm
    run
    test:e2e
    --
    --reporter=json
    --reporter=junit
    --output-file=/tmp/playwright-results.json
  )

  run_with_timeout "$duration" "${cmd[@]}"
}

run_all_tests() {
  run_backend_tests || return $?
  run_frontend_tests || return $?
  run_e2e_tests
}

case "$MODE" in
  backend)
    run_backend_tests
    ;;
  frontend)
    run_frontend_tests
    ;;
  e2e)
    run_e2e_tests
    ;;
  all)
    run_all_tests
    ;;
esac
