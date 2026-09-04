#!/usr/bin/env python3
"""Simple HTTP server to view OTHER_UNKNOWN images."""

import http.server
import socketserver
import os
import webbrowser
from pathlib import Path

PORT = 8765
HANDLER = http.server.SimpleHTTPRequestHandler

if __name__ == '__main__':
    os.chdir('\\\\orshfs.intel.com\\ORAnalysis$\\1276_MAODATA\\Config\\etch\\AME\\tbatson\\Defects\\BE')
    
    with socketserver.TCPServer(("", PORT), HANDLER) as httpd:
        url = f"http://localhost:{PORT}/rollups/OTHER_UNKNOWN/OTHER_UNKNOWN_IMAGES_TILES.html"
        print(f"Server running at {url}")
        webbrowser.open(url)
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nServer stopped.")
