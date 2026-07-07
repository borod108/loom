#!/usr/bin/env bash
# loom full-flow integration test
#
# Simulates a developer's real day: several tasks in PARALLEL, each in its own
# tmux session, all feeding one vault, with task lifecycle independence.
#
#   bash tests/test_full_flow.sh            # mock mode: isolated tmux server +
#                                           # mock claude that fires real loom hooks.
#                                           # Free, no API usage, CI-safe.
#   bash tests/test_full_flow.sh --real     # real claude sessions (haiku).
#                                           # Uses plan credits + your real vault;
#                                           # auto-answers trust/permission prompts.
#   --keep                                  # don't clean up artifacts at the end
#
# What is asserted (both modes):
#   1. `loom new` x3 → three SEPARATE tmux sessions, all alive at once
#   2. Goal auto-delivery (send_after_ready watcher)
#   3. Hook telemetry: status transitions land in vault frontmatter
#   4. The vault GROWS from all three tasks (three research notes)
#   5. Finishing ONE task does not touch the other two (independence)
#   6. A NEXT task can consume what previous tasks put in the vault
#   7. Archive + dashboard reflect reality at the end

set -u
cd "$(dirname "$0")/.."
LOOM_DIR="$(pwd)"
export LOOM_DIR

MODE="mock"
KEEP=0
for arg in "$@"; do
  case "$arg" in
    --real) MODE="real" ;;
    --keep) KEEP=1 ;;
  esac
done

PASS=0; FAIL=0
pass() { PASS=$((PASS+1)); echo "  ✓ $*"; }
fail() { FAIL=$((FAIL+1)); echo "  ✗ FAIL: $*"; }
check() { # check <description> <command...>
  local desc="$1"; shift
  if "$@" >/dev/null 2>&1; then pass "$desc"; else fail "$desc"; fi
}

wait_for() { # wait_for <seconds> <description> <command...>
  local secs="$1" desc="$2"; shift 2
  local deadline=$(( $(date +%s) + secs ))
  while [ "$(date +%s)" -lt "$deadline" ]; do
    if "$@" >/dev/null 2>&1; then pass "$desc"; return 0; fi
    sleep 1
  done
  fail "$desc (timed out after ${secs}s)"
  return 1
}

echo "loom full-flow test — mode: $MODE"
echo "──────────────────────────────────"

# ═══════════════════════════════════════════════════════════════════════════
# Environment setup
# ═══════════════════════════════════════════════════════════════════════════

WORK=$(mktemp -d /tmp/loom-flow.XXXXXX)
PROJ_A="$WORK/proj-alpha"; PROJ_B="$WORK/proj-beta"; PROJ_C="$WORK/proj-gamma"; PROJ_D="$WORK/proj-delta"
mkdir -p "$PROJ_A" "$PROJ_B" "$PROJ_C" "$PROJ_D"

if [ "$MODE" = "mock" ]; then
  # Fully isolated: own vault, own state, own tmux server, mock claude.
  export LOOM_VAULT="$WORK/vault"
  export LOOM_SESSION_PREFIX="lft"
  export XDG_STATE_HOME="$WORK/state"
  export XDG_CONFIG_HOME="$WORK/config"
  export LOOM_NOTIFICATIONS=""     # no desktop noise from a test
  export LOOM_DISTILL="off"
  TMUX_SOCKET="loomflow$$"

  MOCKBIN="$WORK/bin"
  mkdir -p "$MOCKBIN"

  # tmux wrapper → dedicated server so the user's tmux is untouched.
  # -f /dev/null: user's tmux.conf must not leak into the test server.
  cat > "$MOCKBIN/tmux" <<EOF
#!/usr/bin/env bash
exec /usr/bin/tmux -f /dev/null -L $TMUX_SOCKET "\$@"
EOF

  # systemd-run wrapper → run the goal watcher directly, KEEPING this PATH
  # (a real systemd-run scope would lose the tmux wrapper).
  cat > "$MOCKBIN/systemd-run" <<'EOF'
#!/usr/bin/env bash
while [[ "${1:-}" == --* ]]; do shift; done
nohup "$@" >/dev/null 2>&1 &
EOF

  # Mock claude: renders a ready prompt, then behaves like a diligent agent —
  # it fires the REAL loom hooks and does "work" against the REAL vault code
  # paths. Commands it understands on stdin:
  #   research:<topic>:<sentence>  → writes a research note into the vault
  #   read:<dir>                   → prints every vault note in <dir> to the pane
  #   /exit                        → fires session-end and exits
  cat > "$MOCKBIN/claude" <<'EOF'
#!/usr/bin/env bash
SESSION_ID=""
while [ $# -gt 0 ]; do
  case "$1" in
    --session-id|--resume) SESSION_ID="$2"; shift 2 ;;
    --model) shift 2 ;;
    *) shift ;;
  esac
done
HOOKS="$LOOM_DIR/hooks"
fire() {
  printf '{"session_id":"%s","cwd":"%s","transcript_path":"/tmp/mock-transcript-%s.jsonl","hook_event_name":"%s"}' \
    "$SESSION_ID" "$PWD" "$SESSION_ID" "$2" | python3 "$HOOKS/$1.py" >/dev/null 2>&1
}
fire session-start SessionStart
echo "mock claude started (session $SESSION_ID)"
echo ""
echo "   Haiku 4.5 (mock)                    \$0.00"
echo "❯ "
while IFS= read -r line; do
  [ -z "$line" ] && continue
  if [ "$line" = "/exit" ]; then break; fi
  fire user-prompt-submit UserPromptSubmit
  echo "❯ $line"
  case "$line" in
    research:*)
      topic="${line#research:}"; topic="${topic%%:*}"
      text="${line#research:*:}"
      mkdir -p "$LOOM_VAULT/40-Research"
      printf -- "---\ntopic: %s\ndate: 2026-07-06\n---\n\n# %s\n\n%s\n" \
        "$topic" "$topic" "$text" > "$LOOM_VAULT/40-Research/$topic.md"
      echo "● Wrote research note: $topic"
      ;;
    read:*)
      dir="${line#read:}"
      echo "● Vault knowledge in $dir:"
      cat "$LOOM_VAULT/$dir"/*.md 2>/dev/null || echo "  (nothing found)"
      ;;
    *)
      echo "● ok: $line"
      ;;
  esac
  fire stop Stop
  echo "❯ "
done
fire session-end SessionEnd
echo "mock claude exiting"
EOF
  chmod +x "$MOCKBIN/tmux" "$MOCKBIN/systemd-run" "$MOCKBIN/claude"
  export PATH="$MOCKBIN:$PATH"

  # Pre-start the isolated server with the TEST environment, and force panes
  # to run non-login /bin/sh: login shells re-source the user's rc files,
  # which rewrite PATH and would shadow the mock claude with the real one.
  tmux start-server
  tmux new-session -d -s _keeper -x 200 -y 50 "sleep 3600"
  tmux set -g default-command /bin/sh

  LOOM="$LOOM_DIR/bin/loom"
  VAULT="$LOOM_VAULT"
  MODEL="mock-model"
  "$LOOM" init --no-git >/dev/null

  # Values each "task" contributes to the shared vault
  GOAL_A="research:flow-alpha:The alpha constant is 17."
  PROMPT_B="research:flow-beta:The beta constant is 23."
  PROMPT_C="research:flow-gamma:The gamma constant is 42."
  READ_CMD="read:40-Research"

else
  # Real mode: the actual claude binary, haiku model, your real vault.
  LOOM="$LOOM_DIR/bin/loom"
  VAULT=$(python3 -c "
import sys; sys.path.insert(0, '$LOOM_DIR/lib')
from loom import Config; print(Config().vault)")
  MODEL="claude-haiku-4-5"
  TMUX_SOCKET=""   # user's default server

  GOAL_A="Create a research note at $VAULT/40-Research/flow-alpha.md with YAML frontmatter (topic: flow-alpha) and the exact sentence: The alpha constant is 17. Nothing else. Then stop."
  PROMPT_B="Create a research note at $VAULT/40-Research/flow-beta.md with YAML frontmatter (topic: flow-beta) and the exact sentence: The beta constant is 23. Nothing else. Then stop."
  PROMPT_C="Create a research note at $VAULT/40-Research/flow-gamma.md with YAML frontmatter (topic: flow-gamma) and the exact sentence: The gamma constant is 42. Nothing else. Then stop."
  READ_CMD="Read the three notes $VAULT/40-Research/flow-alpha.md flow-beta.md flow-gamma.md and reply with the three constants on one line."
fi

TASK_A="flow-a"; TASK_B="flow-b"; TASK_C="flow-c"; TASK_D="flow-d"
SES() { echo "$( [ "$MODE" = mock ] && echo lft || echo loom )-$1"; }

pane() { tmux capture-pane -p -t "$(SES "$1"):claude" 2>/dev/null; }

# Real mode: babysit the sessions like the human would — accept trust
# dialogs, approve permission prompts. Runs in the background per task.
babysit() { # babysit <slug> <seconds>
  local slug="$1" secs="$2"
  local deadline=$(( $(date +%s) + secs ))
  while [ "$(date +%s)" -lt "$deadline" ]; do
    local p; p=$(pane "$slug")
    if echo "$p" | grep -q "trust this folder"; then
      tmux send-keys -t "$(SES "$slug"):claude" Enter
      sleep 3
    elif echo "$p" | grep -qE "Do you want|Yes, and"; then
      tmux send-keys -t "$(SES "$slug"):claude" "1"
      sleep 3
    else
      sleep 2
    fi
  done
}

note_has() { # note_has <file> <text>
  grep -q "$2" "$1" 2>/dev/null
}

# ═══════════════════════════════════════════════════════════════════════════
# 1. Start three tasks in parallel — separate tmux sessions
# ═══════════════════════════════════════════════════════════════════════════
echo ""
echo "Phase 1: three parallel tasks"

"$LOOM" new "$TASK_A" --dir "$PROJ_A" -m "$MODEL" --goal "$GOAL_A" </dev/null >/dev/null 2>&1 \
  && pass "loom new $TASK_A (with --goal)" || fail "loom new $TASK_A"
"$LOOM" new "$TASK_B" --dir "$PROJ_B" -m "$MODEL" </dev/null >/dev/null 2>&1 \
  && pass "loom new $TASK_B" || fail "loom new $TASK_B"
"$LOOM" new "$TASK_C" --dir "$PROJ_C" -m "$MODEL" </dev/null >/dev/null 2>&1 \
  && pass "loom new $TASK_C" || fail "loom new $TASK_C"

check "three separate tmux sessions exist" bash -c \
  "tmux has-session -t $(SES $TASK_A) && tmux has-session -t $(SES $TASK_B) && tmux has-session -t $(SES $TASK_C)"

check "task notes created for all three" bash -c \
  "test -f '$VAULT/10-Tasks/$TASK_A.md' && test -f '$VAULT/10-Tasks/$TASK_B.md' && test -f '$VAULT/10-Tasks/$TASK_C.md'"

if [ "$MODE" = "real" ]; then
  babysit "$TASK_A" 90 & BS_A=$!
  babysit "$TASK_B" 20 & BS_B=$!
  babysit "$TASK_C" 20 & BS_C=$!
  wait "$BS_B" "$BS_C" 2>/dev/null
fi

# Hook telemetry: session-start flips status away from "starting"
wait_for 60 "hooks registered claude start (status != starting) for $TASK_B" bash -c \
  "grep -E '^status: (waiting|working)' '$VAULT/10-Tasks/$TASK_B.md'"

# ═══════════════════════════════════════════════════════════════════════════
# 2. Goal auto-delivery + parallel work → vault grows from ALL tasks
# ═══════════════════════════════════════════════════════════════════════════
echo ""
echo "Phase 2: goal delivery + vault grows from every task"

# Task A got its instruction via --goal (watcher). B and C get theirs by send.
"$LOOM" send "$TASK_B" -y "$PROMPT_B" >/dev/null 2>&1 && pass "sent work to $TASK_B" || fail "send to $TASK_B"
"$LOOM" send "$TASK_C" -y "$PROMPT_C" >/dev/null 2>&1 && pass "sent work to $TASK_C" || fail "send to $TASK_C"

if [ "$MODE" = "real" ]; then
  wait "$BS_A" 2>/dev/null
  babysit "$TASK_A" 60 & babysit "$TASK_B" 60 & babysit "$TASK_C" 60 &
  wait
fi

wait_for 120 "vault note from $TASK_A (goal was auto-delivered)" test -f "$VAULT/40-Research/flow-alpha.md"
wait_for 120 "vault note from $TASK_B" test -f "$VAULT/40-Research/flow-beta.md"
wait_for 120 "vault note from $TASK_C" test -f "$VAULT/40-Research/flow-gamma.md"

check "alpha note content correct"  note_has "$VAULT/40-Research/flow-alpha.md" "The alpha constant is 17"
check "beta note content correct"   note_has "$VAULT/40-Research/flow-beta.md"  "The beta constant is 23"
check "gamma note content correct"  note_has "$VAULT/40-Research/flow-gamma.md" "The gamma constant is 42"

wait_for 60 "hook telemetry: $TASK_B back to waiting after its turn" bash -c \
  "grep -q '^status: waiting' '$VAULT/10-Tasks/$TASK_B.md'"

check "loom ls shows all three tasks" bash -c \
  "'$LOOM' ls --plain | grep -c '^flow-' | grep -qE '^[34]'"

check "loom search finds knowledge across tasks" bash -c \
  "'$LOOM' search 'constant is' | grep -q flow-beta"

# ═══════════════════════════════════════════════════════════════════════════
# 3. Independence: finishing ONE task must not touch the others
# ═══════════════════════════════════════════════════════════════════════════
echo ""
echo "Phase 3: task independence"

"$LOOM" done "$TASK_A" --no-distill --yes >/dev/null 2>&1 \
  && pass "loom done $TASK_A --no-distill --yes" || fail "loom done $TASK_A"

check "$TASK_A session is gone" bash -c "! tmux has-session -t $(SES $TASK_A) 2>/dev/null"
check "$TASK_B session STILL ALIVE after killing $TASK_A" tmux has-session -t "$(SES $TASK_B)"
check "$TASK_C session STILL ALIVE after killing $TASK_A" tmux has-session -t "$(SES $TASK_C)"
check "$TASK_A archived to 90-Archive" test -f "$VAULT/90-Archive/$TASK_A.md"
check "$TASK_A's research SURVIVES its task" test -f "$VAULT/40-Research/flow-alpha.md"

# B is still responsive after A's death?
"$LOOM" send "$TASK_B" -y "ping-after-sibling-death" >/dev/null 2>&1
if [ "$MODE" = "real" ]; then babysit "$TASK_B" 30; fi
wait_for 60 "$TASK_B still responds after $TASK_A was archived" bash -c \
  "$LOOM preview $TASK_B --lines 40 2>/dev/null | grep -q 'ping-after-sibling-death'"

# ═══════════════════════════════════════════════════════════════════════════
# 4. The NEXT task consumes what the previous tasks put in the vault
# ═══════════════════════════════════════════════════════════════════════════
echo ""
echo "Phase 4: next task reuses vault knowledge"

"$LOOM" new "$TASK_D" --dir "$PROJ_D" -m "$MODEL" </dev/null >/dev/null 2>&1 \
  && pass "loom new $TASK_D" || fail "loom new $TASK_D"
if [ "$MODE" = "real" ]; then babysit "$TASK_D" 45; fi
sleep 2

"$LOOM" send "$TASK_D" -y "$READ_CMD" >/dev/null 2>&1 && pass "asked $TASK_D to use the vault" || fail "send to $TASK_D"
if [ "$MODE" = "real" ]; then babysit "$TASK_D" 90; fi

wait_for 120 "$TASK_D retrieved alpha knowledge (17)" bash -c "pane_out=\$('$LOOM' preview '$TASK_D' --lines 60 2>/dev/null); echo \"\$pane_out\" | grep -q '17'"
check "$TASK_D retrieved beta knowledge (23)"  bash -c "'$LOOM' preview '$TASK_D' --lines 60 2>/dev/null | grep -q '23'"
check "$TASK_D retrieved gamma knowledge (42)" bash -c "'$LOOM' preview '$TASK_D' --lines 60 2>/dev/null | grep -q '42'"

# ═══════════════════════════════════════════════════════════════════════════
# 5. Session end telemetry + final state
# ═══════════════════════════════════════════════════════════════════════════
echo ""
echo "Phase 5: session end + final vault state"

"$LOOM" send "$TASK_D" -y "/exit" >/dev/null 2>&1
wait_for 60 "SessionEnd flipped $TASK_D to idle" bash -c \
  "grep -q '^status: idle' '$VAULT/10-Tasks/$TASK_D.md'"
check "session-end logged in $TASK_D note" bash -c \
  "grep -q 'Claude session ended' '$VAULT/10-Tasks/$TASK_D.md'"

check "dashboard exists and mentions live tasks" bash -c \
  "grep -q 'flow-b' '$VAULT/00-Dashboard/Active Tasks.md'"

# ═══════════════════════════════════════════════════════════════════════════
# Cleanup
# ═══════════════════════════════════════════════════════════════════════════
echo ""
if [ "$KEEP" = "0" ]; then
  for t in "$TASK_B" "$TASK_C" "$TASK_D"; do
    "$LOOM" done "$t" --no-distill --yes >/dev/null 2>&1
  done
  if [ "$MODE" = "mock" ]; then
    tmux kill-server 2>/dev/null   # only kills the isolated -L server (wrapper)
    rm -rf "$WORK"
  else
    # real mode: remove test artifacts from the real vault
    rm -f "$VAULT/40-Research/flow-alpha.md" "$VAULT/40-Research/flow-beta.md" "$VAULT/40-Research/flow-gamma.md"
    rm -f "$VAULT/90-Archive/$TASK_A.md" "$VAULT/90-Archive/$TASK_B.md" "$VAULT/90-Archive/$TASK_C.md" "$VAULT/90-Archive/$TASK_D.md"
    python3 -c "
import sys; sys.path.insert(0, '$LOOM_DIR/lib')
from loom import Config, VaultManager, StateManager
cfg = Config(); v = VaultManager(cfg); s = StateManager(cfg)
for t in ('$TASK_A','$TASK_B','$TASK_C','$TASK_D'): s.remove(t)
v.rebuild_dashboard()"
    rm -rf "$WORK"
  fi
  echo "  (cleaned up — use --keep to inspect artifacts)"
else
  echo "  Artifacts kept: $WORK  (vault: $VAULT)"
fi

echo ""
echo "──────────────────────────────────"
echo "Results: $PASS passed, $FAIL failed  (mode: $MODE)"
[ "$FAIL" = "0" ]
