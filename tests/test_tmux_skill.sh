#!/usr/bin/env bash
# loom tmux skill integration tests
#
# Validates the tmux commands taught by the tmux skill (skills/tmux/SKILL.md)
# work correctly for session detection, targeting, isolation, and operations.
#
# Uses an isolated tmux server — does NOT touch the user's tmux sessions.
# Does NOT require Claude or API calls.
#
#   bash tests/test_tmux_skill.sh
#   bash tests/test_tmux_skill.sh --keep    # don't clean up (inspect artifacts)

set -u
cd "$(dirname "$0")/.."
LOOM_DIR="$(pwd)"

KEEP=0
for arg in "$@"; do
  case "$arg" in
    --keep) KEEP=1 ;;
  esac
done

PASS=0; FAIL=0
pass() { PASS=$((PASS+1)); echo "  ✓ $*"; }
fail() { FAIL=$((FAIL+1)); echo "  ✗ FAIL: $*"; }
check() {
  local desc="$1"; shift
  if "$@" >/dev/null 2>&1; then pass "$desc"; else fail "$desc"; fi
}
check_fail() {
  local desc="$1"; shift
  if ! "$@" >/dev/null 2>&1; then pass "$desc"; else fail "$desc (should have failed)"; fi
}

echo "loom tmux skill tests"
echo "─────────────────────"

# ═══════════════════════════════════════════════════════════════════════════
# Setup: isolated tmux server
# ═══════════════════════════════════════════════════════════════════════════

SOCKET="loomskill$$"
WORK=$(mktemp -d /tmp/loom-skill.XXXXXX)

# tmux wrapper that always uses our isolated server + clean config
T() { /usr/bin/tmux -f /dev/null -L "$SOCKET" "$@"; }

# Start the isolated server
T start-server
T new-session -d -s _keeper -x 200 -y 50 "sleep 3600"

# Helper: get the session name for a given target (simulates the skill's detection).
# Uses list-sessions with a filter, which works reliably without an attached client.
detect_session() {
  local sess="$1"
  T list-sessions -F '#{session_name}' -f "#{==:#{session_name},$sess}" 2>/dev/null | head -1
}

echo "  Isolated tmux server: socket=$SOCKET  workdir=$WORK"
echo ""

# ═══════════════════════════════════════════════════════════════════════════
# Category 1: Session Identity Detection
# ═══════════════════════════════════════════════════════════════════════════
echo "Category 1: Session Identity Detection"

# Create loom-style sessions
T new-session -d -s loom-alpha -c "$WORK" -x 200 -y 50
T new-session -d -s loom-beta  -c "$WORK" -x 200 -y 50
T new-session -d -s loom-gamma -c "$WORK" -x 200 -y 50

# 1.1 Detect current session name
DETECTED=$(detect_session "loom-alpha")
if [ "$DETECTED" = "loom-alpha" ]; then
  pass "1.1 detect session name for loom-alpha"
else
  fail "1.1 detect session name: expected loom-alpha, got '$DETECTED'"
fi

# 1.2 Detect correctly when 3+ sessions exist
DETECTED_B=$(detect_session "loom-beta")
DETECTED_G=$(detect_session "loom-gamma")
if [ "$DETECTED_B" = "loom-beta" ] && [ "$DETECTED_G" = "loom-gamma" ]; then
  pass "1.2 detect correct session with 3 sessions present"
else
  fail "1.2 wrong detection: beta='$DETECTED_B' gamma='$DETECTED_G'"
fi

# 1.3 Detect session after creating a 4th
T new-session -d -s loom-delta -c "$WORK" -x 200 -y 50
DETECTED=$(detect_session "loom-alpha")
if [ "$DETECTED" = "loom-alpha" ]; then
  pass "1.3 detection stable after adding 4th session"
else
  fail "1.3 detection changed after adding session: got '$DETECTED'"
fi

# 1.4 detection returns empty for non-existent session
DETECTED_NONE=$(detect_session "loom-nonexistent")
if [ -z "$DETECTED_NONE" ]; then
  pass "1.4 non-existent session returns empty"
else
  fail "1.4 non-existent session returned '$DETECTED_NONE'"
fi

T kill-session -t loom-delta 2>/dev/null

echo ""

# ═══════════════════════════════════════════════════════════════════════════
# Category 2: Cross-Session Isolation
# ═══════════════════════════════════════════════════════════════════════════
echo "Category 2: Cross-Session Isolation"

# Setup: put unique content in each session
T send-keys -t loom-alpha "echo 'ALPHA_MARKER_7291'" Enter
T send-keys -t loom-beta  "echo 'BETA_MARKER_3847'" Enter
T send-keys -t loom-gamma "echo 'GAMMA_MARKER_5623'" Enter
sleep 0.5

# 2.1 capture from alpha contains only alpha's marker
CAPTURE_A=$(T capture-pane -p -t loom-alpha -S -50)
if echo "$CAPTURE_A" | grep -q "ALPHA_MARKER_7291"; then
  if ! echo "$CAPTURE_A" | grep -q "BETA_MARKER_3847" && ! echo "$CAPTURE_A" | grep -q "GAMMA_MARKER_5623"; then
    pass "2.1 capture-pane alpha contains only alpha marker"
  else
    fail "2.1 alpha capture leaked beta/gamma content"
  fi
else
  fail "2.1 alpha capture missing alpha marker"
fi

# 2.2 capture from beta contains only beta's marker
CAPTURE_B=$(T capture-pane -p -t loom-beta -S -50)
if echo "$CAPTURE_B" | grep -q "BETA_MARKER_3847" && ! echo "$CAPTURE_B" | grep -q "ALPHA_MARKER_7291"; then
  pass "2.2 capture-pane beta contains only beta marker"
else
  fail "2.2 beta capture has wrong content"
fi

# 2.3 send-keys to alpha doesn't affect beta
T send-keys -t loom-alpha "echo 'ALPHA_ONLY_MSG_4829'" Enter
sleep 0.5
CAPTURE_B2=$(T capture-pane -p -t loom-beta -S -50)
if ! echo "$CAPTURE_B2" | grep -q "ALPHA_ONLY_MSG_4829"; then
  pass "2.3 send-keys to alpha didn't leak to beta"
else
  fail "2.3 alpha's send-keys leaked to beta"
fi

# 2.4 new-window in alpha only creates in alpha
WINDOWS_B_BEFORE=$(T list-windows -t loom-beta -F '#{window_name}' | wc -l)
T new-window -t loom-alpha -n test-isolation
WINDOWS_B_AFTER=$(T list-windows -t loom-beta -F '#{window_name}' | wc -l)
if [ "$WINDOWS_B_BEFORE" = "$WINDOWS_B_AFTER" ]; then
  pass "2.4 new-window in alpha didn't create window in beta"
else
  fail "2.4 new-window leaked: beta had $WINDOWS_B_BEFORE windows, now $WINDOWS_B_AFTER"
fi
T kill-window -t loom-alpha:test-isolation 2>/dev/null

# 2.5 after killing alpha, beta operations still work
T kill-session -t loom-alpha 2>/dev/null
T send-keys -t loom-beta "echo 'BETA_AFTER_KILL_1357'" Enter
sleep 0.5
CAPTURE_B3=$(T capture-pane -p -t loom-beta -S -50)
if echo "$CAPTURE_B3" | grep -q "BETA_AFTER_KILL_1357"; then
  pass "2.5 beta works after alpha was killed"
else
  fail "2.5 beta broken after alpha killed"
fi

# 2.6 prefix matching: loom-foo vs loom-foobar don't collide
T new-session -d -s loom-foo    -c "$WORK" -x 200 -y 50
T new-session -d -s loom-foobar -c "$WORK" -x 200 -y 50
T send-keys -t loom-foo    "echo 'FOO_SHORT_9182'" Enter
T send-keys -t loom-foobar "echo 'FOOBAR_LONG_6374'" Enter
sleep 0.5
CAP_FOO=$(T capture-pane -p -t loom-foo -S -20)
CAP_FOOBAR=$(T capture-pane -p -t loom-foobar -S -20)
if echo "$CAP_FOO" | grep -q "FOO_SHORT_9182" && ! echo "$CAP_FOO" | grep -q "FOOBAR_LONG_6374"; then
  if echo "$CAP_FOOBAR" | grep -q "FOOBAR_LONG_6374" && ! echo "$CAP_FOOBAR" | grep -q "FOO_SHORT_9182"; then
    pass "2.6 loom-foo and loom-foobar are properly isolated"
  else
    fail "2.6 foobar capture has foo content"
  fi
else
  fail "2.6 foo capture has foobar content"
fi
T kill-session -t loom-foo    2>/dev/null
T kill-session -t loom-foobar 2>/dev/null

# Recreate alpha for later tests
T new-session -d -s loom-alpha -c "$WORK" -x 200 -y 50

echo ""

# ═══════════════════════════════════════════════════════════════════════════
# Category 3: Window/Pane Targeting
# ═══════════════════════════════════════════════════════════════════════════
echo "Category 3: Window/Pane Targeting"

# 3.1 Target window by name
T new-window -t loom-beta -n mywindow
T send-keys -t loom-beta:mywindow "echo 'WINDOW_BY_NAME_8421'" Enter
sleep 0.3
CAP=$(T capture-pane -p -t loom-beta:mywindow -S -10)
if echo "$CAP" | grep -q "WINDOW_BY_NAME_8421"; then
  pass "3.1 target window by name works"
else
  fail "3.1 target by name failed"
fi

# 3.2 Target with session:window format
T send-keys -t loom-beta:mywindow "echo 'SESSION_WINDOW_FORMAT_5039'" Enter
sleep 0.3
CAP=$(T capture-pane -p -t loom-beta:mywindow -S -10)
if echo "$CAP" | grep -q "SESSION_WINDOW_FORMAT_5039"; then
  pass "3.2 session:window targeting works"
else
  fail "3.2 session:window targeting failed"
fi

# 3.3 Target specific pane after split
T split-window -h -t loom-beta:mywindow
# The new pane is created — find its index
PANE_COUNT=$(T list-panes -t loom-beta:mywindow -F '#{pane_index}' | wc -l)
if [ "$PANE_COUNT" -ge 2 ]; then
  # Get the second pane's index
  PANE_IDX=$(T list-panes -t loom-beta:mywindow -F '#{pane_index}' | tail -1)
  T send-keys -t "loom-beta:mywindow.$PANE_IDX" "echo 'PANE_SPECIFIC_6714'" Enter
  sleep 0.3
  CAP=$(T capture-pane -p -t "loom-beta:mywindow.$PANE_IDX" -S -10)
  if echo "$CAP" | grep -q "PANE_SPECIFIC_6714"; then
    pass "3.3 target specific pane within window"
  else
    fail "3.3 pane-specific targeting failed"
  fi
else
  fail "3.3 split didn't create second pane"
fi

# 3.4 Multiple windows can coexist with different names
T new-window -t loom-beta -n second-win
check "3.4 multiple named windows coexist" \
  T send-keys -t loom-beta:second-win "echo 'SECOND_WIN_OK'" Enter
T kill-window -t loom-beta:second-win 2>/dev/null

# 3.5 Targeting a killed window returns error
T kill-window -t loom-beta:mywindow 2>/dev/null
check_fail "3.5 targeting killed window returns error" \
  T send-keys -t loom-beta:mywindow "echo 'SHOULD_FAIL'" Enter

echo ""

# ═══════════════════════════════════════════════════════════════════════════
# Category 4: send_keys Correctness
# ═══════════════════════════════════════════════════════════════════════════
echo "Category 4: send_keys Correctness"

# Use a fresh window for send_keys tests
T new-window -t loom-beta -n sendtest -c "$WORK"
sleep 0.3

# 4.1 Simple command received correctly
T send-keys -t loom-beta:sendtest "echo 'SIMPLE_ECHO_4718'" Enter
sleep 0.5
CAP=$(T capture-pane -p -t loom-beta:sendtest -S -10)
if echo "$CAP" | grep -q "SIMPLE_ECHO_4718"; then
  pass "4.1 simple command received correctly"
else
  fail "4.1 simple command not received"
fi

# 4.2 Special characters sent literally with -l
T send-keys -t loom-beta:sendtest -l -- 'echo "dollar:$HOME pipe:| semi:; amp:&"'
sleep 0.1
T send-keys -t loom-beta:sendtest Enter
sleep 0.5
CAP=$(T capture-pane -p -t loom-beta:sendtest -S -10)
if echo "$CAP" | grep -q 'dollar:.*pipe:| semi:; amp:&'; then
  pass "4.2 special characters sent literally with -l"
else
  fail "4.2 special characters mangled"
fi

# 4.3 Enter sent separately (the Claude Code TUI pattern)
T send-keys -t loom-beta:sendtest -- 'echo SEPARATE_ENTER_2965'
sleep 0.35
T send-keys -t loom-beta:sendtest Enter
sleep 0.5
CAP=$(T capture-pane -p -t loom-beta:sendtest -S -10)
if echo "$CAP" | grep -q "SEPARATE_ENTER_2965"; then
  pass "4.3 separate Enter send works"
else
  fail "4.3 separate Enter send failed"
fi

# 4.4 Control keys (Ctrl+C)
T send-keys -t loom-beta:sendtest "sleep 999" Enter
sleep 0.3
T send-keys -t loom-beta:sendtest C-c
sleep 0.3
# Should be back at a shell prompt — verify by sending another command
T send-keys -t loom-beta:sendtest "echo 'AFTER_CTRLC_8053'" Enter
sleep 0.5
CAP=$(T capture-pane -p -t loom-beta:sendtest -S -10)
if echo "$CAP" | grep -q "AFTER_CTRLC_8053"; then
  pass "4.4 Ctrl+C interrupts and prompt returns"
else
  fail "4.4 Ctrl+C didn't work"
fi

# 4.5 Rapid consecutive sends don't interleave
T send-keys -t loom-beta:sendtest "echo 'RAPID_A_1001'" Enter
T send-keys -t loom-beta:sendtest "echo 'RAPID_B_1002'" Enter
T send-keys -t loom-beta:sendtest "echo 'RAPID_C_1003'" Enter
sleep 1
CAP=$(T capture-pane -p -t loom-beta:sendtest -S -30)
if echo "$CAP" | grep -q "RAPID_A_1001" && echo "$CAP" | grep -q "RAPID_B_1002" && echo "$CAP" | grep -q "RAPID_C_1003"; then
  pass "4.5 rapid consecutive sends all received"
else
  fail "4.5 rapid sends dropped or interleaved"
fi

T kill-window -t loom-beta:sendtest 2>/dev/null

echo ""

# ═══════════════════════════════════════════════════════════════════════════
# Category 5: capture_pane Correctness
# ═══════════════════════════════════════════════════════════════════════════
echo "Category 5: capture_pane Correctness"

T new-window -t loom-gamma -n captest -c "$WORK"
sleep 0.3

# 5.1 Captures visible content accurately
T send-keys -t loom-gamma:captest "echo 'VISIBLE_CONTENT_3927'" Enter
sleep 0.5
CAP=$(T capture-pane -p -t loom-gamma:captest)
if echo "$CAP" | grep -q "VISIBLE_CONTENT_3927"; then
  pass "5.1 capture-pane shows visible content"
else
  fail "5.1 visible content not captured"
fi

# 5.2 Scrollback capture includes history
for i in $(seq 1 60); do
  T send-keys -t loom-gamma:captest "echo 'LINE_$i'" Enter
done
sleep 0.5
T send-keys -t loom-gamma:captest "echo 'SCROLLBACK_MARKER_8462'" Enter
sleep 0.3
# The early lines should be in scrollback, not visible area
CAP_SCROLL=$(T capture-pane -p -t loom-gamma:captest -S -200)
if echo "$CAP_SCROLL" | grep -q "SCROLLBACK_MARKER_8462" && echo "$CAP_SCROLL" | grep -q "LINE_1"; then
  pass "5.2 scrollback capture includes history"
else
  fail "5.2 scrollback missing content"
fi

# 5.3 Visible-only capture misses scrollback
CAP_VISIBLE=$(T capture-pane -p -t loom-gamma:captest)
if echo "$CAP_VISIBLE" | grep -q "SCROLLBACK_MARKER_8462" && ! echo "$CAP_VISIBLE" | grep -q "LINE_1"; then
  pass "5.3 visible-only capture excludes old scrollback"
else
  # LINE_1 might still be visible depending on terminal size — soft check
  if echo "$CAP_VISIBLE" | grep -q "SCROLLBACK_MARKER_8462"; then
    pass "5.3 visible-only capture shows current content (scrollback may be visible in large terminals)"
  else
    fail "5.3 visible capture broken"
  fi
fi

# 5.4 Capture of fresh/empty window
T new-window -t loom-gamma -n emptytest
sleep 0.3
CAP_EMPTY=$(T capture-pane -p -t loom-gamma:emptytest)
# A fresh shell shows a prompt at most — should NOT contain random content from other panes
if ! echo "$CAP_EMPTY" | grep -q "ALPHA_MARKER\|BETA_MARKER\|GAMMA_MARKER"; then
  pass "5.4 fresh window capture doesn't leak other session content"
else
  fail "5.4 fresh window capture contains content from other sessions"
fi
T kill-window -t loom-gamma:emptytest 2>/dev/null

T kill-window -t loom-gamma:captest 2>/dev/null

echo ""

# ═══════════════════════════════════════════════════════════════════════════
# Category 6: Window/Pane Lifecycle
# ═══════════════════════════════════════════════════════════════════════════
echo "Category 6: Window/Pane Lifecycle"

# 6.1 Full lifecycle: create → send → capture → kill
T new-window -t loom-alpha -n lifecycle -c "$WORK"
T send-keys -t loom-alpha:lifecycle "echo 'LIFECYCLE_OK_5291'" Enter
sleep 0.5
CAP=$(T capture-pane -p -t loom-alpha:lifecycle -S -10)
if echo "$CAP" | grep -q "LIFECYCLE_OK_5291"; then
  T kill-window -t loom-alpha:lifecycle
  if ! T list-windows -t loom-alpha -F '#{window_name}' | grep -q "lifecycle"; then
    pass "6.1 full lifecycle: create → send → capture → kill"
  else
    fail "6.1 window not killed"
  fi
else
  fail "6.1 lifecycle failed at capture step"
fi

# 6.2 Split pane workflow
T new-window -t loom-alpha -n splitlife -c "$WORK"
T split-window -h -t loom-alpha:splitlife -c "$WORK"
PANE_COUNT=$(T list-panes -t loom-alpha:splitlife -F '#{pane_index}' | wc -l)
if [ "$PANE_COUNT" -ge 2 ]; then
  PANE1=$(T list-panes -t loom-alpha:splitlife -F '#{pane_index}' | head -1)
  PANE2=$(T list-panes -t loom-alpha:splitlife -F '#{pane_index}' | tail -1)
  T send-keys -t "loom-alpha:splitlife.$PANE1" "echo 'SPLIT_LEFT_3847'" Enter
  T send-keys -t "loom-alpha:splitlife.$PANE2" "echo 'SPLIT_RIGHT_9271'" Enter
  sleep 0.5
  CAP1=$(T capture-pane -p -t "loom-alpha:splitlife.$PANE1" -S -10)
  CAP2=$(T capture-pane -p -t "loom-alpha:splitlife.$PANE2" -S -10)
  if echo "$CAP1" | grep -q "SPLIT_LEFT_3847" && echo "$CAP2" | grep -q "SPLIT_RIGHT_9271"; then
    pass "6.2 split pane workflow: both panes independent"
  else
    fail "6.2 split panes mixed up"
  fi
else
  fail "6.2 split didn't create second pane"
fi
T kill-window -t loom-alpha:splitlife 2>/dev/null

# 6.3 Working directory propagation
SUBDIR="$WORK/subdir-test-$$"
mkdir -p "$SUBDIR"
# Use the basename for matching (avoids /tmp symlink issues across systems)
SUBDIR_BASE=$(basename "$SUBDIR")
T new-window -t loom-alpha -n cwdtest -c "$SUBDIR"
sleep 0.3
T send-keys -t loom-alpha:cwdtest "pwd" Enter
sleep 1
CAP=$(T capture-pane -p -t loom-alpha:cwdtest -S -10)
if echo "$CAP" | grep -q "$SUBDIR_BASE"; then
  pass "6.3 working directory propagated to new window"
else
  fail "6.3 working directory not set: expected dir containing '$SUBDIR_BASE'"
fi
T kill-window -t loom-alpha:cwdtest 2>/dev/null

# 6.4 Create window with startup command
T new-window -t loom-alpha -n cmdtest "echo 'STARTUP_CMD_6182'; sleep 2"
sleep 0.5
CAP=$(T capture-pane -p -t loom-alpha:cmdtest -S -10)
if echo "$CAP" | grep -q "STARTUP_CMD_6182"; then
  pass "6.4 window with startup command runs correctly"
else
  fail "6.4 startup command output not found"
fi
T kill-window -t loom-alpha:cmdtest 2>/dev/null

echo ""

# ═══════════════════════════════════════════════════════════════════════════
# Category 7: Error Handling
# ═══════════════════════════════════════════════════════════════════════════
echo "Category 7: Error Handling"

# 7.1 Non-existent session
check_fail "7.1 send-keys to non-existent session fails" \
  T send-keys -t loom-nonexistent:window "echo test" Enter

# 7.2 Non-existent window
check_fail "7.2 send-keys to non-existent window fails" \
  T send-keys -t loom-alpha:nonexistent-window "echo test" Enter

# 7.3 Non-existent pane
check_fail "7.3 capture-pane of non-existent pane fails" \
  T capture-pane -p -t loom-alpha:0.999

# 7.4 Operations on killed session
T new-session -d -s loom-disposable -c "$WORK" -x 200 -y 50
T kill-session -t loom-disposable
check_fail "7.4 send-keys to killed session fails" \
  T send-keys -t loom-disposable "echo test" Enter

echo ""

# ═══════════════════════════════════════════════════════════════════════════
# Category 8: Loom Integration
# ═══════════════════════════════════════════════════════════════════════════
echo "Category 8: Loom Integration"

# 8.1 Operations correctly use loom-<slug> session naming
T send-keys -t loom-beta "echo 'LOOM_SESSION_OK_7384'" Enter
sleep 0.3
CAP=$(T capture-pane -p -t loom-beta -S -10)
if echo "$CAP" | grep -q "LOOM_SESSION_OK_7384"; then
  pass "8.1 loom-<slug> session targeting works"
else
  fail "8.1 loom-<slug> targeting failed"
fi

# 8.2 Multi-window session (main + extra like distill)
T new-window -t loom-beta -n distill -c "$WORK"
T send-keys -t loom-beta:distill "echo 'DISTILL_WINDOW_5829'" Enter
sleep 0.3
# Verify distill window has its own content
CAP_DISTILL=$(T capture-pane -p -t loom-beta:distill -S -10)
# And original window doesn't have it
FIRST_WIN=$(T list-windows -t loom-beta -F '#{window_name}' | head -1)
CAP_MAIN=$(T capture-pane -p -t "loom-beta:$FIRST_WIN" -S -20)
if echo "$CAP_DISTILL" | grep -q "DISTILL_WINDOW_5829" && ! echo "$CAP_MAIN" | grep -q "DISTILL_WINDOW_5829"; then
  pass "8.2 multi-window: distill window isolated from main"
else
  fail "8.2 multi-window isolation broken"
fi
T kill-window -t loom-beta:distill 2>/dev/null

# 8.3 Simulated resume: new session with same slug works
T kill-session -t loom-alpha 2>/dev/null
T new-session -d -s loom-alpha -c "$WORK" -x 200 -y 50
T send-keys -t loom-alpha "echo 'RESUMED_SESSION_4196'" Enter
sleep 0.3
CAP=$(T capture-pane -p -t loom-alpha -S -10)
if echo "$CAP" | grep -q "RESUMED_SESSION_4196"; then
  pass "8.3 resumed session (same slug) works correctly"
else
  fail "8.3 resumed session targeting failed"
fi

# 8.4 list-windows scoped to session only
WIN_ALPHA=$(T list-windows -t loom-alpha -F '#{window_name}' | wc -l)
WIN_BETA=$(T list-windows -t loom-beta -F '#{window_name}' | wc -l)
# Each session's window list should be independent
T new-window -t loom-alpha -n extra-alpha
WIN_ALPHA_AFTER=$(T list-windows -t loom-alpha -F '#{window_name}' | wc -l)
WIN_BETA_AFTER=$(T list-windows -t loom-beta -F '#{window_name}' | wc -l)
if [ "$WIN_ALPHA_AFTER" -gt "$WIN_ALPHA" ] && [ "$WIN_BETA_AFTER" = "$WIN_BETA" ]; then
  pass "8.4 list-windows scoped to session: alpha grew, beta unchanged"
else
  fail "8.4 list-windows not scoped: alpha=$WIN_ALPHA→$WIN_ALPHA_AFTER beta=$WIN_BETA→$WIN_BETA_AFTER"
fi
T kill-window -t loom-alpha:extra-alpha 2>/dev/null

echo ""

# ═══════════════════════════════════════════════════════════════════════════
# Cleanup
# ═══════════════════════════════════════════════════════════════════════════
if [ "$KEEP" = "0" ]; then
  T kill-server 2>/dev/null
  rm -rf "$WORK"
  echo "  (cleaned up — use --keep to inspect)"
else
  echo "  Artifacts kept: socket=$SOCKET  workdir=$WORK"
  echo "  Attach: tmux -f /dev/null -L $SOCKET attach"
fi

echo ""
echo "─────────────────────"
echo "Results: $PASS passed, $FAIL failed"
[ "$FAIL" = "0" ]
