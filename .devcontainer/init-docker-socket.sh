#!/usr/bin/env sh
set -eu

uid="${UID:-$(id -u)}"

run_user_dir_base="${RUN_USER_DIR_BASE:-/run/user}"
rootful_docker_sock="${ROOTFUL_DOCKER_SOCK:-/var/run/docker.sock}"

xdg_runtime_dir="${XDG_RUNTIME_DIR:-}"
xdg_docker_sock=""
if [ -n "${xdg_runtime_dir}" ]; then
  xdg_docker_sock="${xdg_runtime_dir}/docker.sock"
fi

run_user_docker_sock="${run_user_dir_base}/${uid}/docker.sock"

socket_exists() {
  if [ "${DOCKER_SOCKET_TEST_FILE_OK:-}" = "1" ]; then
    [ -e "$1" ]
  else
    [ -S "$1" ]
  fi
}

for candidate in "${xdg_docker_sock}" "${run_user_docker_sock}" "${rootful_docker_sock}"; do
  if [ -n "${candidate}" ] && socket_exists "${candidate}"; then
    DOCKER_SOCKET="${candidate}"
    export DOCKER_SOCKET
    printf 'DOCKER_SOCKET=%s\n' "${DOCKER_SOCKET}"
    exit 0
  fi
done

echo "ERROR: Docker socket not found. Checked:" >&2
if [ -n "${xdg_docker_sock}" ]; then
  echo "  - ${xdg_docker_sock}" >&2
fi
echo "  - ${run_user_docker_sock}" >&2
echo "  - ${rootful_docker_sock}" >&2
exit 1

