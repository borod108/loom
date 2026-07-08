#!/usr/bin/env bash
# Run all loom tests and report results.
set -euo pipefail

LOOM_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PASS=0; FAIL=0

pass() { PASS=$((PASS+1)); echo "  ✓ $*"; }
fail() { FAIL=$((FAIL+1)); echo "  ✗ $*"; }

hr() { echo ""; echo "── $* ──────────────────────────────────────────"; }

# ── Unit tests ──────────────────────────────────────────────────────────────
hr "Unit tests (VaultManager + StateManager)"
if python3 -m unittest \
    tests/test_vault.py \
    tests/test_state.py \
    -v 2>&1 | grep -E "^(ok|FAIL|ERROR|Ran)" | while read -r line; do
    case "$line" in
        ok*) pass "${line#ok }" ;;
        FAIL*|ERROR*) fail "${line}" ;;
    esac
  done
then
  echo ""
else
  FAIL=$((FAIL+1))
  echo "  Unit test runner failed"
fi

# Re-run to get correct exit code and counts
UNIT_RESULT=$(python3 -m unittest tests/test_vault.py tests/test_state.py 2>&1 | tail -1)
echo "  $UNIT_RESULT"
echo ""
if echo "$UNIT_RESULT" | grep -q "^OK"; then
  PASS=$((PASS+1))
else
  FAIL=$((FAIL+1))
fi

# ── Integration tests (tmux) ─────────────────────────────────────────────────
hr "Integration tests (TmuxManager — requires tmux)"
if command -v tmux &>/dev/null; then
  if bash tests/test_status.sh; then
    pass "All tmux integration tests (status)"
  else
    fail "tmux integration tests (status)"
  fi
  if bash tests/test_tmux_skill.sh; then
    pass "All tmux skill tests (session isolation + targeting)"
  else
    fail "tmux skill tests"
  fi
else
  echo "  SKIP: tmux not found"
fi

# ── Quick CLI smoke tests ─────────────────────────────────────────────────────
hr "CLI smoke tests"

export LOOM_VAULT="/tmp/loom-smoke-$$"
export XDG_CONFIG_HOME="/tmp/loom-smoke-cfg-$$"
export XDG_STATE_HOME="/tmp/loom-smoke-state-$$"
mkdir -p "$XDG_CONFIG_HOME/loom" "$XDG_STATE_HOME"
echo "$LOOM_DIR" > "$XDG_CONFIG_HOME/loom/loom_dir"
cat > "$XDG_CONFIG_HOME/loom/config" <<EOF
LOOM_VAULT="$LOOM_VAULT"
LOOM_SESSION_PREFIX="loom"
LOOM_DISTILL="off"
LOOM_NOTIFICATIONS="bell"
LOOM_DEFAULT_MODEL="claude-opus-4-6"
EOF

# Test: loom --help
if python3 "$LOOM_DIR/bin/loom" --help &>/dev/null; then
  pass "loom --help works"
else
  fail "loom --help failed"
fi

# Test: loom init
if python3 "$LOOM_DIR/bin/loom" init --no-git 2>&1 | grep -q "Initialized"; then
  pass "loom init"
else
  fail "loom init"
fi

# Test: vault structure
for d in 00-Dashboard 10-Tasks 20-Projects 30-Decisions 40-Research 90-Archive; do
  if [ -d "$LOOM_VAULT/$d" ]; then
    pass "vault dir: $d"
  else
    fail "vault dir missing: $d"
  fi
done

# Test: loom ls (empty)
LS_OUT=$(python3 "$LOOM_DIR/bin/loom" ls 2>&1)
if echo "$LS_OUT" | grep -q "No active tasks"; then
  pass "loom ls shows empty state"
else
  fail "loom ls empty state: $LS_OUT"
fi

# Test: loom ls --all (empty)
LS_ALL=$(python3 "$LOOM_DIR/bin/loom" ls --all 2>&1)
if echo "$LS_ALL" | grep -q "No tasks"; then
  pass "loom ls --all shows empty state"
else
  fail "loom ls --all empty: $LS_ALL"
fi

# Test: loom adr
ADR_OUT=$(python3 "$LOOM_DIR/bin/loom" adr "Test Decision" 2>&1)
if echo "$ADR_OUT" | grep -q "Created"; then
  pass "loom adr creates file"
else
  fail "loom adr: $ADR_OUT"
fi
if ls "$LOOM_VAULT/30-Decisions/ADR-001-"*.md &>/dev/null; then
  pass "ADR file exists in vault"
else
  fail "ADR file not found"
fi

# Test: loom rebuild (nothing to rebuild)
if python3 "$LOOM_DIR/bin/loom" rebuild 2>&1 | grep -q "Rebuilt"; then
  pass "loom rebuild"
else
  fail "loom rebuild"
fi

# Test: web server module syntax
if python3 -c "import ast; ast.parse(open('$LOOM_DIR/web/server.py').read())" 2>&1; then
  pass "web/server.py parses cleanly"
else
  fail "web/server.py syntax error"
fi

# Test: lib module imports
if python3 -c "
import sys; sys.path.insert(0,'$LOOM_DIR/lib')
from loom import Config, VaultManager, StateManager, TmuxManager, NotifyManager
print('ok')
" 2>&1 | grep -q ok; then
  pass "lib/loom.py imports cleanly"
else
  fail "lib/loom.py import error"
fi

# Cleanup
rm -rf "/tmp/loom-smoke-$$" "/tmp/loom-smoke-cfg-$$" "/tmp/loom-smoke-state-$$"

# ── Hook syntax checks ────────────────────────────────────────────────────────
hr "Hook syntax checks"
for hook in "$LOOM_DIR/hooks/"*.py; do
  name=$(basename "$hook")
  if python3 -c "import ast; ast.parse(open('$hook').read())" 2>&1; then
    pass "hooks/$name parses"
  else
    fail "hooks/$name syntax error"
  fi
done

# ── Summary ───────────────────────────────────────────────────────────────────
echo ""
echo "════════════════════════════════════════"
echo "Results: ${PASS} passed, ${FAIL} failed"
echo "════════════════════════════════════════"
[ $FAIL -eq 0 ]
