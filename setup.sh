#!/bin/bash
# CivicEase AI — Quick Start (macOS / Linux)
# Run this script once after cloning the repo.
# Usage: bash setup.sh

set -e

echo ""
echo "========================================"
echo "  CivicEase AI - Setup Script (Unix)"
echo "========================================"
echo ""

# Step 1: Check Python
echo "[1/5] Checking Python version..."
if ! command -v python3 &>/dev/null; then
    echo "ERROR: python3 is not installed. Install it from https://python.org"
    exit 1
fi
echo "      Found: $(python3 --version)"

# Step 2: Create virtual environment
echo "[2/5] Creating virtual environment..."
if [ -d "venv" ]; then
    echo "      venv/ already exists, skipping."
else
    python3 -m venv venv
    echo "      venv/ created."
fi

# Step 3: Activate and install dependencies
echo "[3/5] Installing dependencies..."
source venv/bin/activate
pip install -r requirements.txt --quiet
echo "      Dependencies installed."

# Step 4: Set up .env
echo "[4/5] Setting up environment file..."
if [ -f ".env" ]; then
    echo "      .env already exists, skipping."
else
    cp .env.example .env
    echo "      .env created from template."
    echo ""
    echo "  ACTION REQUIRED: Open .env and set your GROQ_API_KEY"
    echo "  Get a free key at: https://console.groq.com"
    echo ""
fi

# Step 5: Build vector database
echo "[5/5] Building RAG vector database..."
python core/rag_engine.py
echo "      Vector database built at chroma_db/"

echo ""
echo "========================================"
echo "  Setup complete!"
echo ""
echo "  To start the app:"
echo "    source venv/bin/activate"
echo "    python app.py"
echo ""
echo "  Then open: http://127.0.0.1:5000"
echo "========================================"
echo ""
