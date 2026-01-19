#!/usr/bin/env bash
# Start frontend in production mode

set -euo pipefail

cd "$(dirname "$0")/../client"

# Build if build/ doesn't exist or --rebuild flag passed
if [ ! -d "build" ] || [ "${1:-}" = "--rebuild" ]; then
    echo "Building production frontend..."
    npm run build
    echo "✓ Build complete"
fi

echo "Starting production frontend server on port 3000..."
npx serve -s build -l 3000
