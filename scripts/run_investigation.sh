#!/usr/bin/env bash
set -o pipefail

cd -- "$(dirname -- "$0")/.." || exit 1
mkdir -p outputs

python -u -m agentic_soc.main "$@" 2>&1 | tee outputs/investigation.log