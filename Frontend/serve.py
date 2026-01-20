#!/usr/bin/env python3
"""
Simple development server for the GraphRAG Frontend.
Serves static files and proxies API requests to the FastAPI backend.
"""

import http.server
import socketserver
import os
import sys
from pathlib import Path

PORT = 3000
DIRECTORY = Path(__file__).parent

class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(DIRECTORY), **kwargs)
    
    def end_headers(self):
        # Add CORS headers for development
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', '*')
        super().end_headers()

def main():
    os.chdir(DIRECTORY)
    
    with socketserver.TCPServer(("", PORT), Handler) as httpd:
        print(f"""
╔════════════════════════════════════════════════════════════════╗
║         🔮 ScaleAI GraphRAG Dashboard                          ║
╠════════════════════════════════════════════════════════════════╣
║                                                                ║
║   Frontend running at:  http://localhost:{PORT}                 ║
║   API should run at:    http://localhost:8000                  ║
║                                                                ║
║   Make sure to start the API server first:                     ║
║   $ cd .. && uvicorn src.api.main:app --reload                 ║
║                                                                ║
║   Press Ctrl+C to stop                                         ║
║                                                                ║
╚════════════════════════════════════════════════════════════════╝
        """)
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n👋 Shutting down frontend server...")
            sys.exit(0)

if __name__ == "__main__":
    main()
