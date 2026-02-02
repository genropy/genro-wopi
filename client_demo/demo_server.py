#!/usr/bin/env python3
"""Simple HTTP server that serves index.html for all paths (SPA routing)."""
import http.server
import socketserver

class SPAHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        # Serve index.html for any path that doesn't have a file extension
        if '.' not in self.path.split('/')[-1]:
            self.path = '/index.html'
        return super().do_GET()

PORT = 3000
with socketserver.TCPServer(("", PORT), SPAHandler) as httpd:
    print(f"Serving at http://localhost:{PORT}")
    httpd.serve_forever()
