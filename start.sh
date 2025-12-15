#!/bin/bash

# PDF2BPMN - Start Development Servers
# This script starts both the backend API and frontend dev server

echo "🚀 Starting PDF2BPMN Development Environment"
echo "=============================================="

# Check if Neo4j is running
echo "📊 Checking Neo4j connection..."
python -c "from src.pdf2bpmn.graph.neo4j_client import Neo4jClient; c = Neo4jClient(); print('✅ Neo4j OK' if c.verify_connection() else '❌ Neo4j not running'); c.close()" 2>/dev/null || echo "❌ Neo4j check failed"

# Start backend API server
echo ""
echo "🔧 Starting Backend API (port 8000)..."
uv run python run.py api &
BACKEND_PID=$!

# Wait for backend to start
sleep 3

# Check if frontend dependencies are installed
if [ ! -d "frontend/node_modules" ]; then
    echo ""
    echo "📦 Installing frontend dependencies..."
    cd frontend && npm install && cd ..
fi

# Start frontend dev server
echo ""
echo "🎨 Starting Frontend Dev Server (port 5173)..."
cd frontend && npm run dev &
FRONTEND_PID=$!

echo ""
echo "=============================================="
echo "✅ Services started!"
echo "   - Backend API: http://localhost:8000"
echo "   - API Docs: http://localhost:8000/docs"
echo "   - Frontend: http://localhost:5173"
echo ""
echo "Press Ctrl+C to stop all services"
echo "=============================================="

# Wait for user interrupt
trap "echo 'Stopping services...'; kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit 0" SIGINT SIGTERM

wait




