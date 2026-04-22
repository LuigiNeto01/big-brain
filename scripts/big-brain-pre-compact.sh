#!/usr/bin/env bash
set -u

if command -v big-brain >/dev/null 2>&1; then
  big-brain hook pre-compact --stdin || true
fi
