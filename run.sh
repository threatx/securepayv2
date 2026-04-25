#!/bin/bash

# SecurePay - UPI Fraud Analyzer
# Run this script to start the web interface

echo "=============================================="
echo "  SecurePay - UPI Fraud Analyzer"
echo "=============================================="
echo ""

# Change to project directory
cd "$(dirname "$0")"

# Check if uvicorn is installed
if ! command -v uvicorn &> /dev/null; then
    echo "Installing dependencies..."
    pip install -r requirements.txt
fi

echo "Starting server..."
echo ""
echo "Open your browser at: http://localhost:8000"
echo ""
echo "Press Ctrl+C to stop the server"
echo "=============================================="
echo ""

# Start the server
uvicorn app.backend.api:app --reload --port 8000
