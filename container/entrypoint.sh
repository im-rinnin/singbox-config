#!/bin/sh
set -eu

PROFILE_DIR=${SINGBOX_PROFILE_DIR:-/opt/singbox/profiles}
PASSWORD_FILE=${SINGBOX_PASSWORD_FILE:-/run/secrets/singbox-config-password}
ACTIVE_PROFILE_FILE=${SINGBOX_ACTIVE_PROFILE_FILE:-/run/profile/active.profile}
RUN_DIR=${SINGBOX_RUN_DIR:-/run/singbox}
GNUPGHOME=${GNUPGHOME:-$RUN_DIR/gnupg}
SINGBOX_BIN=${SINGBOX_BIN:-/usr/local/bin/sing-box}
CONFIG_FILE="$RUN_DIR/active.json"

fail() {
    printf '%s\n' "singbox: $*" >&2
    exit 1
}

profile_name() {
    if [ -n "${SINGBOX_PROFILE:-}" ]; then
        profile=$SINGBOX_PROFILE
    else
        [ -r "$ACTIVE_PROFILE_FILE" ] || fail "active profile file is missing"
        profile=$(tr -d '\r\n' < "$ACTIVE_PROFILE_FILE")
    fi
    case "$profile" in
        ''|*[!A-Za-z0-9._-]*) fail "invalid profile name" ;;
    esac
    printf '%s\n' "$profile"
}

list_profiles() {
    found=0
    for path in "$PROFILE_DIR"/*.json.gpg; do
        [ -f "$path" ] || continue
        found=1
        basename "$path" .json.gpg
    done
    [ "$found" -eq 1 ] || fail "no encrypted profiles found"
}

prepare_config() {
    profile=$1
    encrypted="$PROFILE_DIR/$profile.json.gpg"
    [ -f "$encrypted" ] || fail "profile is not available: $profile"
    [ -r "$PASSWORD_FILE" ] || fail "password file is missing"
    mkdir -p "$RUN_DIR" "$GNUPGHOME"
    chmod 0700 "$RUN_DIR" "$GNUPGHOME"
    rm -f "$CONFIG_FILE"
    gpg \
        --batch \
        --quiet \
        --no-options \
        --no-auto-check-trustdb \
        --pinentry-mode loopback \
        --passphrase-file "$PASSWORD_FILE" \
        --decrypt \
        --output "$CONFIG_FILE" \
        "$encrypted" || fail "unable to decrypt profile: $profile"
    chmod 0600 "$CONFIG_FILE"
    "$SINGBOX_BIN" check -c "$CONFIG_FILE" >/dev/null \
        || fail "profile failed sing-box check: $profile"
}

command=${1:-run}
case "$command" in
    list)
        list_profiles
        exit 0
        ;;
    check)
        profile=${2:-$(profile_name)}
        prepare_config "$profile"
        exit 0
        ;;
    version)
        exec "$SINGBOX_BIN" version
        ;;
    run)
        prepare_config "$(profile_name)"
        exec "$SINGBOX_BIN" run -c "$CONFIG_FILE"
        ;;
    *)
        fail "unknown command: $command"
        ;;
esac
