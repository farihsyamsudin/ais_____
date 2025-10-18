#!/bin/bash
echo "Stopping all services..."
pkill -f "python app.py"
pkill -f "python3 -m http.server 8000"
echo "✅ All services stopped"
