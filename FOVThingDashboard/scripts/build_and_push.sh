#!/usr/bin/env bash
set -euo pipefail

# --- config (override via env if you like) ---
REGISTRY="${REGISTRY:-docker.io}"
NAMESPACE="${NAMESPACE:-YOUR_DOCKER_USERNAME}"   # <- change me
BACKEND_IMAGE="${BACKEND_IMAGE:-$REGISTRY/$NAMESPACE/fov-backend}"
FRONTEND_IMAGE="${FRONTEND_IMAGE:-$REGISTRY/$NAMESPACE/fov-frontend}"
VERSION="${VERSION:-$(git rev-parse --short HEAD)}"

echo "Version: $VERSION"
echo "Backend image:  $BACKEND_IMAGE:$VERSION"
echo "Frontend image: $FRONTEND_IMAGE:$VERSION"

# Build & tag
docker build -t "$BACKEND_IMAGE:$VERSION"  -f app/Dockerfile    app
docker build -t "$FRONTEND_IMAGE:$VERSION" -f client/Dockerfile client

# Optional 'latest' tags
docker tag "$BACKEND_IMAGE:$VERSION"  "$BACKEND_IMAGE:latest"
docker tag "$FRONTEND_IMAGE:$VERSION" "$FRONTEND_IMAGE:latest"

# Push
docker push "$BACKEND_IMAGE:$VERSION"
docker push "$FRONTEND_IMAGE:$VERSION"
docker push "$BACKEND_IMAGE:latest"
docker push "$FRONTEND_IMAGE:latest"

# Save version for deploy step
echo "$VERSION" > .deploy_version
echo "Pushed images with tag: $VERSION"
