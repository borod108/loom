#!/usr/bin/env bash
# Integration tests for loom session lifecycle and status detection.
# These tests verify the BEHAVIORS the TmuxManager must provide,
# not the implementation. Swap implementations freely as long as these pass.
#
# Requirements: tmux, python3, loom installed (bin/loom in PATH or LOOM_DIR set)
#
# Usage: ./tests/test_status.sh [--verbose]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOOM_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
LOOM_BIN="$LOOM_DIR/bin/loom"
PYTHON="${PYTHON:-python3}"

VERBOSE="${1:-}"
PASS=0; FAIL=0; SKIP=0
TEST_SLUG="loom-test-$$"
TEST_SESSION="loom-$TEST_SLUG"

# ── Helpers ──────────────────────────────────────────────────────────────────

pass() { PASS=$((PASS+1)); [ -n "$VERBOSE" ] && echo "PASS: $1" || printf '.'; }
fail() { FAIL=$((FAIL+1)); echo "FAIL: $1"; }
skip() { SKIP=$((SKIP+1)); [ -n "$VERBOSE" ] && echo "SKIP: $1" || printf 's'; }

check_prereq() {
  if ! command -v "$1" &>/dev/null; then
    echo "SKIP ALL: $1 not found (required for status tests)"
    exit 0
  fi
}

cleanup() {
  tmux kill-session -t "$TEST_SESSION" 2>/dev/null || true
  # Clean up test vault entries
  export XDG_CONFIG_HOME="/tmp/loom-test-$$/config"
  export XDG_STATE_HOME="/tmp/loom-test-$$/state"
  export LOOM_VAULT="/tmp/loom-test-$$"
  rm -rf "/tmp/loom-test-$$"
}

# ── Setup ─────────────────────────────────────────────────────────────────────

check_prereq tmux
check_prereq python3

trap cleanup EXIT

# Isolated config for tests
export XDG_CONFIG_HOME="/tmp/loom-test-$$/config"
export XDG_STATE_HOME="/tmp/loom-test-$$/state"
export LOOM_VAULT="/tmp/loom-test-$$"
mkdir -p "$XDG_CONFIG_HOME/loom" "$XDG_STATE_HOME" "$LOOM_VAULT"
echo "$LOOM_DIR" > "$XDG_CONFIG_HOME/loom/loom_dir"
cat > "$XDG_CONFIG_HOME/loom/config" <<EOF
LOOM_VAULT="$LOOM_VAULT"
LOOM_SESSION_PREFIX="loom"
LOOM_DISTILL="off"
LOOM_NOTIFICATIONS="bell"
EOF

echo ""
echo "loom status tests"
echo "──────────────────"

# ── Test: tmux is running ──────────────────────────────────────────────────────

if ! tmux info &>/dev/null; then
  # Start a test tmux server
  tmux new-session -d -s "loom-server-check" sleep 60 2>/dev/null || true
fi

# ── Test: TmuxManager.session_exists false for unknown slug ──────────────────

RESULT=$($PYTHON -c "
import sys; sys.path.insert(0, '$LOOM_DIR/lib')
from loom import Config, TmuxManager
cfg = Config(); t = TmuxManager(cfg)
print(t.session_exists('nonexistent-slug-99999'))
")
if [ "$RESULT" = "False" ]; then
  pass "session_exists returns False for unknown slug"
else
  fail "session_exists returned '$RESULT' for unknown slug (expected False)"
fi

# ── Test: new_session creates tmux session ────────────────────────────────────

SESSION_UUID="test-$(cat /proc/sys/kernel/random/uuid 2>/dev/null || uuidgen 2>/dev/null || echo 'uuid-fallback')"
$PYTHON -c "
import sys; sys.path.insert(0, '$LOOM_DIR/lib')
from loom import Config, TmuxManager
cfg = Config(); t = TmuxManager(cfg)
ok = t.new_session('$TEST_SLUG', '/tmp', '$SESSION_UUID')
" 2>/dev/null || true

sleep 0.5

if tmux has-session -t "$TEST_SESSION" 2>/dev/null; then
  pass "new_session creates tmux session"
else
  fail "new_session did not create tmux session '$TEST_SESSION'"
fi

# ── Test: session_exists returns True for running session ─────────────────────

RESULT=$($PYTHON -c "
import sys; sys.path.insert(0, '$LOOM_DIR/lib')
from loom import Config, TmuxManager
cfg = Config(); t = TmuxManager(cfg)
print(t.session_exists('$TEST_SLUG'))
")
if [ "$RESULT" = "True" ]; then
  pass "session_exists returns True for running session"
else
  fail "session_exists returned '$RESULT' for running session (expected True)"
fi

# ── Test: capture_pane returns a string (not empty necessarily) ───────────────

RESULT=$($PYTHON -c "
import sys; sys.path.insert(0, '$LOOM_DIR/lib')
from loom import Config, TmuxManager
cfg = Config(); t = TmuxManager(cfg)
pane = t.capture_pane('$TEST_SLUG', lines=5)
print(type(pane).__name__)
")
if [ "$RESULT" = "str" ]; then
  pass "capture_pane returns string"
else
  fail "capture_pane returned type '$RESULT' (expected str)"
fi

# ── Test: send_keys returns True for live session ─────────────────────────────

RESULT=$($PYTHON -c "
import sys; sys.path.insert(0, '$LOOM_DIR/lib')
from loom import Config, TmuxManager
cfg = Config(); t = TmuxManager(cfg)
# Send harmless command (echo, not Enter press)
ok = t.send_keys('$TEST_SLUG', '# loom test', False)
print(ok)
")
if [ "$RESULT" = "True" ]; then
  pass "send_keys returns True for live session"
else
  fail "send_keys returned '$RESULT' (expected True)"
fi

# ── Test: kill_session removes the session ────────────────────────────────────

$PYTHON -c "
import sys; sys.path.insert(0, '$LOOM_DIR/lib')
from loom import Config, TmuxManager
cfg = Config(); t = TmuxManager(cfg)
t.kill_session('$TEST_SLUG')
"

sleep 0.3

if ! tmux has-session -t "$TEST_SESSION" 2>/dev/null; then
  pass "kill_session removes the tmux session"
else
  fail "kill_session did not remove session '$TEST_SESSION'"
fi

# ── Test: list_sessions only returns loom-prefixed sessions ──────────────────

# Create a non-loom session
tmux new-session -d -s "other-session-$$" 2>/dev/null || true

RESULT=$($PYTHON -c "
import sys; sys.path.insert(0, '$LOOM_DIR/lib')
from loom import Config, TmuxManager
cfg = Config(); t = TmuxManager(cfg)
sessions = t.list_sessions()
slugs = [s['slug'] for s in sessions]
# Should not include the non-loom session
bad = [s for s in slugs if s.startswith('other')]
print('ok' if not bad else f'bad:{bad}')
")
tmux kill-session -t "other-session-$$" 2>/dev/null || true

if [ "$RESULT" = "ok" ]; then
  pass "list_sessions filters to loom-prefixed sessions only"
else
  fail "list_sessions included non-loom sessions: $RESULT"
fi

# ── Summary ──────────────────────────────────────────────────────────────────

echo ""
echo "──────────────────"
echo "Results: ${PASS} passed, ${FAIL} failed, ${SKIP} skipped"
echo ""

[ $FAIL -eq 0 ]
