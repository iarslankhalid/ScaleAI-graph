#!/usr/bin/env python3
"""
Development runner script for ScaleAI GraphRAG.
Starts both the API server and the frontend dashboard.
"""

import subprocess
import sys
import os
import signal
from pathlib import Path
import time

PROJECT_ROOT = Path(__file__).parent
FRONTEND_DIR = PROJECT_ROOT / "Frontend"

def run_api():
    """Start the FastAPI backend server."""
    return subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "src.api.main:app", "--reload", "--host", "0.0.0.0", "--port", "8000"],
        cwd=PROJECT_ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True
    )

def run_frontend():
    """Start the frontend dev server."""
    return subprocess.Popen(
        [sys.executable, "serve.py"],
        cwd=FRONTEND_DIR,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True
    )

def main():
    print("""
╔════════════════════════════════════════════════════════════════════════╗
║                                                                        ║
║   🔮 ScaleAI GraphRAG Development Environment                          ║
║                                                                        ║
╠════════════════════════════════════════════════════════════════════════╣
║                                                                        ║
║   Starting services...                                                 ║
║                                                                        ║
║   📡 API Server:    http://localhost:8000                              ║
║   📊 Dashboard:     http://localhost:3000                              ║
║   📚 API Docs:      http://localhost:8000/docs                         ║
║                                                                        ║
║   Press Ctrl+C to stop all services                                    ║
║                                                                        ║
╚════════════════════════════════════════════════════════════════════════╝
    """)
    
    processes = []
    
    try:
        # Start API server
        print("🚀 Starting API server...")
        api_proc = run_api()
        processes.append(api_proc)
        time.sleep(2)  # Give API time to start
        
        # Start frontend
        print("🌐 Starting frontend server...")
        frontend_proc = run_frontend()
        processes.append(frontend_proc)
        
        print("\n✅ All services started! Open http://localhost:3000 in your browser.\n")
        print("-" * 70)
        
        # Print output from processes
        while True:
            for proc in processes:
                if proc.poll() is not None:
                    # Process has terminated
                    continue
                try:
                    line = proc.stdout.readline()
                    if line:
                        print(line.strip())
                except:
                    pass
            time.sleep(0.1)
            
    except KeyboardInterrupt:
        print("\n\n👋 Shutting down services...")
        for proc in processes:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
        print("✅ All services stopped.")
        sys.exit(0)

if __name__ == "__main__":
    main()
