#!/bin/bash
# Build Lambda layer with dependencies

set -e

echo "Building Lambda layer..."

cd src/lambda/shared

# Install dependencies to python/ directory
pip install -r requirements.txt -t python/ --upgrade

# Copy our library
cp -r ../../../lib/ragstack_common python/

echo "Lambda layer built successfully!"
echo "Contents:"
ls -la python/
