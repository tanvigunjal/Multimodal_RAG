#!/bin/bash
set -e

echo "Setting up directories..."
mkdir -p data/uploads figures

echo "Setting permissions..."
sudo chown -R 1000:1000 data figures
chmod -R 775 data figures

echo "Building and starting containers..."
docker-compose down
docker-compose build --no-cache
docker-compose up -d

echo "Checking container status..."
docker-compose ps

echo "Deployment complete!"