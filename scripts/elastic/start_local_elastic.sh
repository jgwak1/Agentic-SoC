#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
ELASTIC_DIR="$ROOT/infra/elastic-local"

if ! docker info >/dev/null 2>&1; then
    echo "Docker is not running."
    exit 1
fi

if [ ! -x "$ELASTIC_DIR/start.sh" ]; then
    echo "Elastic local environment not found."
    exit 1
fi

echo "Starting local Elastic..."

cd "$ELASTIC_DIR"
./start.sh

echo
echo "Elasticsearch: http://localhost:9200"
echo "Kibana:        http://localhost:5601"