#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
ELASTIC_DIR="$ROOT/infra/elastic-local"

if [ ! -x "$ELASTIC_DIR/stop.sh" ]; then
    echo "Elastic local environment not found."
    exit 1
fi

echo "Stopping local Elastic..."

cd "$ELASTIC_DIR"
./stop.sh

echo "Local Elastic stopped."