#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: scripts/capture-baseline.sh {baseline|updated}

Run docker compose exec to collect test artifacts (pytest, Jest, Playwright) and copy them
to artifacts/<mode>/ with a timestamped filename. Requires docker compose services to be running.
EOF
}

if [ "${1:-}" = "-h" ] || [ "${1:-}" = "--help" ]; then
  usage
  exit 0
fi

if [ "$#" -ne 1 ]; then
  usage >&2
  exit 2
fi

MODE=$1
case "$MODE" in
  baseline|updated) ;;
  *)
    usage >&2
    exit 2
    ;;
esac

TIMESTAMP=${REGRESSION_TIMESTAMP:-$(date -u +%Y%m%d-%H%M%S)}
ARTIFACT_ROOT=${ARTIFACT_ROOT:-artifacts}
ARTIFACT_DIR="${ARTIFACT_ROOT}/${MODE}"
mkdir -p "$ARTIFACT_DIR"

COMPOSE_FILES=${COMPOSE_FILE:-docker-compose.yml}
IFS=':' read -r -a COMPOSE_ARRAY <<< "$COMPOSE_FILES"
COMPOSE_FLAGS=()
for file in "${COMPOSE_ARRAY[@]}"; do
  if [ ! -f "$file" ]; then
    echo "ERROR: Compose file not found: $file" >&2
    exit 3
  fi
  COMPOSE_FLAGS+=("-f" "$file")
done

if ! command -v docker >/dev/null 2>&1; then
  echo "ERROR: docker command is required" >&2
  exit 3
fi

TTY_FLAG=""
if [ "${CI:-}" = "true" ] || [ "${TERM:-}" = "dumb" ] || [ ! -t 0 ]; then
  TTY_FLAG="-T"
fi

compose_exec() {
  local cmd=(docker compose "${COMPOSE_FLAGS[@]}" exec)
  if [ -n "$TTY_FLAG" ]; then
    cmd+=("$TTY_FLAG")
  fi
  cmd+=("$@")
  "${cmd[@]}"
}

compose_cp() {
  docker compose "${COMPOSE_FLAGS[@]}" cp "$@"
}

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

capture_backend() {
  ensure_service_running "backend"
  local results_path="/tmp/pytest-${MODE}.json"
  local coverage_path="/tmp/coverage-backend-${MODE}.json"

  compose_exec backend pytest \
    --json-report \
    --json-report-file="$results_path" \
    --cov \
    --cov-report=json:"$coverage_path" \
    --durations=0

  compose_cp "backend:${results_path}" "${ARTIFACT_DIR}/pytest-results-${TIMESTAMP}.json"
  compose_cp "backend:${coverage_path}" "${ARTIFACT_DIR}/coverage-backend-${TIMESTAMP}.json"
}

capture_frontend_unit() {
  ensure_service_running "frontend"
  local results_path="/tmp/jest-${MODE}.json"
  local coverage_path="/tmp/coverage-frontend-${MODE}.json"

  compose_exec frontend npm test -- \
    --json \
    --outputFile="$results_path" \
    --coverage \
    --coverageReporters=json \
    --reporters=default \
    --reporters=jest-junit

  compose_cp "frontend:${results_path}" "${ARTIFACT_DIR}/jest-results-${TIMESTAMP}.json"
  compose_cp "frontend:${coverage_path}" "${ARTIFACT_DIR}/coverage-frontend-${TIMESTAMP}.json"
}

capture_frontend_e2e() {
  ensure_service_running "frontend"
  local results_path="/tmp/playwright-${MODE}.json"

  compose_exec frontend npm run test:e2e -- \
    --reporter=json \
    --output-file="$results_path"

  compose_cp "frontend:${results_path}" "${ARTIFACT_DIR}/playwright-results-${TIMESTAMP}.json"
}

write_metadata() {
  local iso_ts
  iso_ts="$(echo "$TIMESTAMP" | sed 's#\([0-9]\{4\}\)\([0-9]\{2\}\)\([0-9]\{2\}\)-\([0-9]\{2\}\)\([0-9]\{2\}\)\([0-9]\{2\}\)#\1-\2-\3T\4:\5:\6Z#')"
  local compose_json
  compose_json="["
  local compose_file
  for compose_file in "${COMPOSE_ARRAY[@]}"; do
    compose_json+="\"${compose_file}\"," 
  done
  compose_json="${compose_json%,}"
  compose_json+="]"
  cat > "${ARTIFACT_DIR}/metadata-${TIMESTAMP}.json" <<EOF
{
  "mode": "${MODE}",
  "timestamp": "${iso_ts}",
  "compose_files": ${compose_json}
}
EOF
}

capture_backend
capture_frontend_unit
capture_frontend_e2e
write_metadata

echo "Artifacts written to ${ARTIFACT_DIR}"
