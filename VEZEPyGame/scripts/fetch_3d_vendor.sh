#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
VENDOR_DIR="$ROOT_DIR/app/ui/static/js/vendor"
DRACO_DIR="$VENDOR_DIR/draco"

mkdir -p "$VENDOR_DIR" "$DRACO_DIR"

echo "Fetching three.js loaders (v0.158.0)…"
curl -fsSL "https://unpkg.com/three@0.158.0/examples/jsm/loaders/GLTFLoader.js" -o "$VENDOR_DIR/GLTFLoader.js"
curl -fsSL "https://unpkg.com/three@0.158.0/examples/jsm/loaders/DRACOLoader.js" -o "$VENDOR_DIR/DRACOLoader.js"

echo "Fetching DRACO decoders (matching three examples)…"
curl -fsSL "https://unpkg.com/three@0.158.0/examples/jsm/libs/draco/draco_decoder.js" -o "$DRACO_DIR/draco_decoder.js"
curl -fsSL "https://unpkg.com/three@0.158.0/examples/jsm/libs/draco/draco_wasm_wrapper.js" -o "$DRACO_DIR/draco_wasm_wrapper.js"
curl -fsSL "https://unpkg.com/three@0.158.0/examples/jsm/libs/draco/draco_decoder.wasm" -o "$DRACO_DIR/draco_decoder.wasm"

echo "Fetching three-pathfinding (v0.9.0)…"
curl -fsSL "https://unpkg.com/three-pathfinding@0.9.0/dist/three-pathfinding.module.js" -o "$VENDOR_DIR/three-pathfinding.module.js"

echo "Done. Files placed under $VENDOR_DIR and $DRACO_DIR"
