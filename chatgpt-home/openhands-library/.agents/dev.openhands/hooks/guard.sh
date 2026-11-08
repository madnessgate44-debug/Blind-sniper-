#!/bin/bash
# PreToolUse guard: thin wrapper. The decision logic lives in guard.py so it can
# parse the hook JSON and split the command into real argv tokens.
set -u
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec python3 "$here/guard.py"
