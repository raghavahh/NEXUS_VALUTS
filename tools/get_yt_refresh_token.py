#!/usr/bin/env python3
"""
One-time helper to generate YouTube OAuth refresh token.
Run locally ONCE, then add YT_REFRESH_TOKEN to GitHub Secrets.
"""
import urllib.parse
import urllib.request
import json
import http.server
import socketserver
import webbrowser
import threading
import time
import sys
import os

def main():
    client_id = os.getenv("YT_CLIENT_ID") or input("YT_CLIENT_ID: ").strip()
    client_secret = os.getenv("YT_CLIENT_SECRET") or input("YT_CLIENT_SECRET: ").strip()
    
    if not client_id or not client_secret:
        print("Error: Both YT_CLIENT_ID and YT_CLIENT_SECRET required")
        sys.exit(1)

    port = 8080
    redirect = f"http://localhost:{port}/"
    scope = "https://www.googleapis.com/auth/youtube.upload https://www.googleapis.com/auth/yt-analytics.readonly"
    auth_url = (
        f"https://accounts.google.com/o/oauth2/v2/auth?"
        f"client_id={client_id}&"
        f"redirect_uri={urllib.parse.quote(redirect)}&"
        f"response_type=code&"
        f"scope={urllib.parse.quote(scope)}&"
        f"access_type=offline&"
        f"prompt=consent"
    )

    print(f"\n1. Open this URL in browser:\n{auth_url}\n")
    code_holder = {}

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path.startswith("/?code="):
                code_holder["code"] = self.path.split("code=")[1].split("&")[0]
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b"Success! Close this tab.")
            else:
                self.send_response(404)
                self.end_headers()
        def log_message(self, *a): pass

    with socketserver.TCPServer(("", port), Handler) as srv:
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        webbrowser.open(auth_url)
        while "code" not in code_holder:
            time.sleep(0.5)
        srv.shutdown()

    code = code_holder["code"]
    data = urllib.parse.urlencode({
        "code": code,
        "client_id": client_id,
        "client_secret": client_secret,
        "redirect_uri": redirect,
        "grant_type": "authorization_code"
    }).encode()
    
    resp = json.loads(urllib.request.urlopen(
        urllib.request.Request(
            "https://oauth2.googleapis.com/token",
            data=data,
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )
    ).read())

    print(f"\nYT_REFRESH_TOKEN={resp['refresh_token']}")
    print("\nAdd this to GitHub Repository Secrets → YT_REFRESH_TOKEN")

if __name__ == "__main__":
    main()
