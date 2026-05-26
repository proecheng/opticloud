#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"

COMPOSE_CMD="${COMPOSE_CMD:-docker compose}"
BLUE_GREEN_STATE_FILE="${BLUE_GREEN_STATE_FILE:-${REPO_ROOT}/.deploy/blue-green-state}"
BLUE_GREEN_BLUE_HEALTH_URL="${BLUE_GREEN_BLUE_HEALTH_URL:-http://localhost:${BLUE_WEB_PORT:-3001}/healthz}"
BLUE_GREEN_GREEN_HEALTH_URL="${BLUE_GREEN_GREEN_HEALTH_URL:-http://localhost:${GREEN_WEB_PORT:-3002}/healthz}"
BLUE_GREEN_SWITCH_CMD="${BLUE_GREEN_SWITCH_CMD:-:}"
BLUE_GREEN_TIMEOUT_SECONDS="${BLUE_GREEN_TIMEOUT_SECONDS:-30}"
BLUE_GREEN_HEALTH_INTERVAL_SECONDS="${BLUE_GREEN_HEALTH_INTERVAL_SECONDS:-2}"

usage() {
  cat <<'USAGE'
Usage:
  blue-green.sh deploy <image_tag>
  blue-green.sh rollback
  blue-green.sh status

Environment:
  COMPOSE_CMD                         Compose command, default: docker compose
  BLUE_GREEN_STATE_FILE               Active/previous slot state file
  BLUE_GREEN_BLUE_HEALTH_URL          Blue slot health URL checked before traffic switch
  BLUE_GREEN_GREEN_HEALTH_URL         Green slot health URL checked before traffic switch
  BLUE_GREEN_SWITCH_CMD               Command run after health succeeds to switch traffic
  BLUE_GREEN_TIMEOUT_SECONDS          Health wait timeout, default: 30
  BLUE_GREEN_HEALTH_INTERVAL_SECONDS  Health poll interval, default: 2
  OPTICLOUD_ROLLBACK_IMAGE_TAG        Fallback rollback tag when state has no previous image tag
USAGE
}

slot_compose_file() {
  case "$1" in
    blue) printf '%s\n' "${REPO_ROOT}/docker-compose.blue.yml" ;;
    green) printf '%s\n' "${REPO_ROOT}/docker-compose.green.yml" ;;
    *) printf 'unknown slot: %s\n' "$1" >&2; return 1 ;;
  esac
}

other_slot() {
  case "$1" in
    blue) printf 'green\n' ;;
    green) printf 'blue\n' ;;
    *) printf 'blue\n' ;;
  esac
}

state_value() {
  local key="$1"
  if [[ ! -f "${BLUE_GREEN_STATE_FILE}" ]]; then
    return 1
  fi

  awk -F= -v key="${key}" '
    $1 == key {
      value = $0
      sub("^[^=]*=", "", value)
      sub(/^[[:space:]]*/, "", value)
      sub(/[[:space:]]*$/, "", value)
      print value
      found = 1
      exit
    }
    END {
      if (!found) {
        exit 1
      }
    }
  ' "${BLUE_GREEN_STATE_FILE}"
}

current_slot() {
  local slot
  slot="$(state_value active_slot || true)"
  case "${slot}" in
    blue|green) printf '%s\n' "${slot}"; return 0 ;;
  esac

  # Backward compatible with the initial plain "blue" / "green" state file.
  if [[ -f "${BLUE_GREEN_STATE_FILE}" ]]; then
    slot="$(tr -d '[:space:]' < "${BLUE_GREEN_STATE_FILE}")"
    case "${slot}" in
      blue|green) printf '%s\n' "${slot}"; return 0 ;;
    esac
  fi
  printf 'blue\n'
}

current_image_tag() {
  local image_tag
  image_tag="$(state_value active_image_tag || true)"
  if [[ -n "${image_tag}" ]]; then
    printf '%s\n' "${image_tag}"
    return 0
  fi
  return 1
}

previous_slot_from_state() {
  local slot
  slot="$(state_value previous_slot || true)"
  case "${slot}" in
    blue|green) printf '%s\n' "${slot}"; return 0 ;;
  esac
  return 1
}

previous_image_tag_from_state() {
  local image_tag
  image_tag="$(state_value previous_image_tag || true)"
  if [[ -n "${image_tag}" ]]; then
    printf '%s\n' "${image_tag}"
    return 0
  fi
  return 1
}

write_state() {
  local active_slot="$1"
  local active_image_tag="$2"
  local previous_slot="$3"
  local previous_image_tag="$4"
  local tmp_file
  tmp_file="${BLUE_GREEN_STATE_FILE}.tmp"

  mkdir -p "$(dirname "${BLUE_GREEN_STATE_FILE}")"
  {
    printf 'active_slot=%s\n' "${active_slot}"
    printf 'active_image_tag=%s\n' "${active_image_tag}"
    printf 'previous_slot=%s\n' "${previous_slot}"
    printf 'previous_image_tag=%s\n' "${previous_image_tag}"
    printf 'updated_at=%s\n' "$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
  } > "${tmp_file}"
  mv "${tmp_file}" "${BLUE_GREEN_STATE_FILE}"
}

compose_up() {
  local slot="$1"
  local image_tag="$2"
  OPTICLOUD_IMAGE_TAG="${image_tag}" ${COMPOSE_CMD} -f "$(slot_compose_file "${slot}")" up -d
}

compose_stop() {
  local slot="$1"
  ${COMPOSE_CMD} -f "$(slot_compose_file "${slot}")" stop
}

slot_health_url() {
  case "$1" in
    blue) printf '%s\n' "${BLUE_GREEN_BLUE_HEALTH_URL}" ;;
    green) printf '%s\n' "${BLUE_GREEN_GREEN_HEALTH_URL}" ;;
    *) printf 'unknown slot: %s\n' "$1" >&2; return 1 ;;
  esac
}

wait_for_health() {
  local slot="$1"
  local health_url
  health_url="$(slot_health_url "${slot}")"
  local deadline=$((SECONDS + BLUE_GREEN_TIMEOUT_SECONDS))
  until curl --fail --silent --show-error --max-time 5 "${health_url}" >/dev/null; do
    if (( SECONDS >= deadline )); then
      printf 'health check timed out for %s slot at %s\n' "${slot}" "${health_url}" >&2
      return 1
    fi
    sleep "${BLUE_GREEN_HEALTH_INTERVAL_SECONDS}"
  done
}

switch_traffic() {
  BLUE_GREEN_ACTIVE_SLOT="$1" BLUE_GREEN_ACTIVE_HEALTH_URL="$(slot_health_url "$1")" sh -c "${BLUE_GREEN_SWITCH_CMD}"
}

deploy() {
  local image_tag="$1"
  local active
  local active_image_tag
  local inactive
  active="$(current_slot)"
  active_image_tag="$(current_image_tag || true)"
  inactive="$(other_slot "${active}")"

  compose_up "${inactive}" "${image_tag}"
  wait_for_health "${inactive}"
  switch_traffic "${inactive}"
  write_state "${inactive}" "${image_tag}" "${active}" "${active_image_tag}"
  compose_stop "${active}"
  printf 'deployed %s to %s\n' "${image_tag}" "${inactive}"
}

rollback() {
  local active
  local active_image_tag
  local previous
  local rollback_image_tag
  active="$(current_slot)"
  active_image_tag="$(current_image_tag || true)"
  previous="$(previous_slot_from_state || other_slot "${active}")"
  rollback_image_tag="$(previous_image_tag_from_state || true)"

  if [[ -z "${rollback_image_tag}" ]]; then
    rollback_image_tag="${OPTICLOUD_ROLLBACK_IMAGE_TAG:-}"
  fi
  if [[ -z "${rollback_image_tag}" ]]; then
    printf 'rollback image tag unavailable; set OPTICLOUD_ROLLBACK_IMAGE_TAG or deploy from tagged state first\n' >&2
    return 2
  fi

  compose_up "${previous}" "${rollback_image_tag}"
  wait_for_health "${previous}"
  switch_traffic "${previous}"
  write_state "${previous}" "${rollback_image_tag}" "${active}" "${active_image_tag}"
  compose_stop "${active}"
  printf 'rolled back to %s with %s\n' "${previous}" "${rollback_image_tag}"
}

status() {
  printf 'active_slot=%s\n' "$(current_slot)"
  printf 'active_image_tag=%s\n' "$(current_image_tag || true)"
  printf 'previous_slot=%s\n' "$(previous_slot_from_state || other_slot "$(current_slot)")"
  printf 'previous_image_tag=%s\n' "$(previous_image_tag_from_state || true)"
  printf 'state_file=%s\n' "${BLUE_GREEN_STATE_FILE}"
  printf 'blue_health_url=%s\n' "${BLUE_GREEN_BLUE_HEALTH_URL}"
  printf 'green_health_url=%s\n' "${BLUE_GREEN_GREEN_HEALTH_URL}"
}

main() {
  local command="${1:-}"
  case "${command}" in
    deploy)
      if [[ $# -ne 2 ]]; then
        usage >&2
        return 2
      fi
      deploy "$2"
      ;;
    rollback)
      if [[ $# -ne 1 ]]; then
        usage >&2
        return 2
      fi
      rollback
      ;;
    status)
      if [[ $# -ne 1 ]]; then
        usage >&2
        return 2
      fi
      status
      ;;
    -h|--help|help)
      usage
      ;;
    *)
      usage >&2
      return 2
      ;;
  esac
}

main "$@"
