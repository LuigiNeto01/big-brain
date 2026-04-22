#!/usr/bin/env bash
set -u

if command -v big-brain >/dev/null 2>&1; then
  big-brain hook session-end --stdin || true
fi
