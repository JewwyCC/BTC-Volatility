#!/bin/bash
# Docker cleanup script for testing new implementation
# This script safely stops and removes old containers, networks, and volumes

set -e

# Save original working directory
ORIGINAL_DIR="$(pwd)"

echo "🧹 Cleaning up Docker resources..."

# Stop and remove containers
echo "Stopping containers..."
# Try from project root (if script is run from project root)
docker compose down 2>/dev/null || true
# Try from docker subdirectory (if docker/compose.yaml exists)
if [ -f "docker/compose.yaml" ]; then
    (cd docker && docker compose down 2>/dev/null) || true
fi

# Restore original directory
cd "$ORIGINAL_DIR"

# Remove containers by name (in case they exist outside compose)
echo "Removing containers by name..."
docker rm -f zookeeper kafka mlflow ml-prediction-api 2>/dev/null || true

# Remove old networks
echo "Removing networks..."
docker network rm ml-pipeline-network kafka-network 2>/dev/null || true

# Optionally remove volumes (uncomment if you want to start fresh)
# WARNING: This will delete MLflow data!
# echo "Removing volumes..."
# docker volume rm mlflow-artifacts 2>/dev/null || true

echo "✅ Cleanup complete!"
echo ""
echo "Note: MLflow data in ./mlruns is preserved (not removed)"
echo "To start fresh with new setup, run:"
echo "  docker compose up -d"

