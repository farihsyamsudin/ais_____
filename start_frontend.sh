#!/bin/bash
cd "$(dirname "$0")/frontend"
echo "🌐 Starting frontend on http://localhost:8000"
python3 -m http.server 8000
