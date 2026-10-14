#!/bin/sh
set -eu

ROOT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
TEST_DIR=$(mktemp -d "${TMPDIR:-/tmp}/singbox-service-test.XXXXXX")
trap 'rm -rf "$TEST_DIR"' EXIT

mkdir -p "$TEST_DIR/bin"
printf '%s\n' test-password > "$TEST_DIR/password"
printf '%s\n' main-http-dns > "$TEST_DIR/active.profile"
printf '%s\n' 0 > "$TEST_DIR/restarts"

cat > "$TEST_DIR/bin/docker" <<'EOF'
#!/bin/sh
set -eu
case "${1:-}" in
    run)
        exit 0
        ;;
    container)
        [ "${2:-}" = inspect ]
        exit 0
        ;;
    restart)
        count=$(cat "$SINGBOX_TEST_RESTARTS")
        count=$((count + 1))
        printf '%s\n' "$count" > "$SINGBOX_TEST_RESTARTS"
        [ "$count" -gt 1 ]
        ;;
    *)
        exit 0
        ;;
esac
EOF
chmod 0755 "$TEST_DIR/bin/docker"

if PATH="$TEST_DIR/bin:$PATH" \
    SINGBOX_TEST_RESTARTS="$TEST_DIR/restarts" \
    SINGBOX_SERVICE_DIR="$TEST_DIR/state" \
    SINGBOX_PASSWORD_FILE="$TEST_DIR/password" \
    SINGBOX_SERVICE_NAME=singbox-service-test \
    SINGBOX_IMAGE=singbox-service:test \
    "$ROOT_DIR/bin/singbox-service" use vps-backup-http-dns >/dev/null 2>&1; then
    printf '%s\n' 'profile switch unexpectedly succeeded' >&2
    exit 1
fi

[ "$(tr -d '\r\n' < "$TEST_DIR/state/profile/active.profile")" = main-http-dns ]
[ "$(cat "$TEST_DIR/restarts")" = 2 ]
printf '%s\n' 'SERVICE_ROLLBACK_OK'
