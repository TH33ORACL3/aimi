#!/bin/bash
# Verify Claude Code (Homebrew cask) is installed and routed to the same custom
# model Grok uses today: ~/.grok/config.toml [model.deepseek-v4-flash-thinking]
#   base_url = https://api.deepseek.com/anthropic
#   model    = deepseek-v4-flash
#   token    = $DEEPSEEK_API_KEY (bearer, never a literal key)
# All Claude Code model tiers (default, small-fast, opus/sonnet/haiku) must
# resolve to deepseek-v4-flash in a fresh interactive shell.
#
# Real entry points driven here: `brew`, a fresh `zsh -i -c` (which sources
# ~/.zshrc, where the config lives), the `claude` wrapper + real binary, and
# the DeepSeek Anthropic-compatible endpoint itself (claude -p completion).
set -u

EXPECTED_ENV="https://api.deepseek.com/anthropic|deepseek-v4-flash|deepseek-v4-flash|deepseek-v4-flash|deepseek-v4-flash|deepseek-v4-flash"
FAILS=0

check() { # check <label> <command...>
    local label="$1"; shift
    if "$@" >/dev/null 2>&1; then
        echo "PASS: $label"
    else
        echo "FAIL: $label"
        FAILS=$((FAILS + 1))
    fi
}

# 1. Install evidence: cask present, real binary under /opt/homebrew, 2.x version
check "claude-code cask installed" brew list --cask claude-code
check "claude resolves under /opt/homebrew" bash -c '[[ "$(command -v claude)" == /opt/homebrew/bin/claude ]]'
check "claude --version is 2.x" bash -c 'claude --version | grep -qE "^2\.[0-9]+"'

# 2. Config: fresh interactive shell resolves every ANTHROPIC_* tier var
check "fresh shell env matches expected model routing" bash -c \
    "[[ \"\$(zsh -i -c 'echo \"\$ANTHROPIC_BASE_URL|\$ANTHROPIC_MODEL|\$ANTHROPIC_SMALL_FAST_MODEL|\$ANTHROPIC_DEFAULT_OPUS_MODEL|\$ANTHROPIC_DEFAULT_SONNET_MODEL|\$ANTHROPIC_DEFAULT_HAIKU_MODEL\"')\" == \"$EXPECTED_ENV\" ]]"

# 3. Config: AUTH_TOKEN equals DEEPSEEK_API_KEY, key value never printed
check "ANTHROPIC_AUTH_TOKEN == DEEPSEEK_API_KEY" bash -c \
    "[[ \"\$(zsh -i -c '[[ \"\$ANTHROPIC_AUTH_TOKEN\" == \"\$DEEPSEEK_API_KEY\" ]] && echo MATCH')\" == MATCH ]]"

# 4. Keyless persistence: no literal key material in the ANTHROPIC_* block
check "no literal keys in ANTHROPIC_* lines of ~/.zshrc" bash -c \
    "[[ \"\$(grep 'ANTHROPIC' \"\$HOME/.zshrc\" | grep -c 'sk-')\" == 0 ]]"
check "~/.zshrc references api.deepseek.com/anthropic" bash -c \
    "grep -q 'api.deepseek.com/anthropic' \"\$HOME/.zshrc\""
check "~/.zshrc references deepseek-v4-flash" bash -c \
    "grep -q 'deepseek-v4-flash' \"\$HOME/.zshrc\""

# 5. Wrappers still resolve to the installed binary
check "claude is a shell function (wrapper intact)" bash -c \
    "zsh -i -c 'type claude' | grep -q 'shell function'"
check "claude-dan alias intact" bash -c \
    "zsh -i -c 'alias claude-dan' | grep -q 'claude --dangerously-skip-permissions'"
check "claude --version via wrapper is 2.x" bash -c \
    "zsh -i -c 'claude --version' | grep -qE '^2\.[0-9]+'"

# 6. Launch smoke: real completion through the DeepSeek endpoint, twice
for run in 1 2; do
    out="$(zsh -i -c 'claude -p "Reply with exactly: OK"' 2>/dev/null)"
    rc=$?
    if [[ $rc -eq 0 ]] && grep -q '^OK$' <<<"$out"; then
        echo "PASS: claude -p smoke run $run (exit 0, response contains OK)"
    else
        echo "FAIL: claude -p smoke run $run (exit=$rc)"
        FAILS=$((FAILS + 1))
    fi
done

echo
if [[ $FAILS -eq 0 ]]; then
    echo "ALL CHECKS PASSED"
    exit 0
else
    echo "$FAILS CHECK(S) FAILED"
    exit 1
fi
