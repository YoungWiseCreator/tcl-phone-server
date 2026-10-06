#!/usr/bin/env python3
"""
TCL Phone Control Server — runs in Termux, exposed via cloudflared.
Endpoints:
  GET  /screenshot          -> PNG screenshot
  POST /tap        {x, y}    -> tap at coordinates
  POST /swipe      {x1,y1,x2,y2,ms} -> swipe
  POST /text       {text}    -> type text
  POST /key        {key}     -> press key (e.g. KEYCODE_BACK, KEYCODE_HOME)
  POST /shell      {cmd}     -> run shell via rish (Shizuku)
  GET  /uiautomator         -> UI tree XML dump
  GET  /health              -> ok
Requires: rish (Shizuku shell) in PATH.
"""
import subprocess, json, os, base64
from http.server import HTTPServer, BaseHTTPRequestHandler

PORT = 8080
AUTH_TOKEN = os.environ.get('PHONE_AUTH', 'tcl-control-2026')

def rish(cmd):
    """Run command via Shizuku's rish."""
    r = subprocess.run(['rish', '-c', cmd], capture_output=True, timeout=30)
    return r.stdout, r.stderr, r.returncode

class Handler(BaseHTTPRequestHandler):
    def _auth(self):
        return self.headers.get('X-Auth-Token') == AUTH_TOKEN

    def _json(self, obj, code=200):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == '/health':
            self._json({'ok': True})
            return
        if not self._auth():
            self._json({'error': 'unauthorized'}, 401)
            return
        if self.path == '/screenshot':
            out, err, code = rish('screencap -p /sdcard/shot.png')
            if code != 0:
                self._json({'error': err.decode()[:200]}, 500)
                return
            with open('/sdcard/shot.png', 'rb') as f:
                data = f.read()
            self.send_response(200)
            self.send_header('Content-Type', 'image/png')
            self.send_header('Content-Length', str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        elif self.path == '/uiautomator':
            out, err, code = rish('uiautomator dump /sdcard/ui.xml && cat /sdcard/ui.xml')
            self._json({'xml': out.decode()[:500000], 'error': err.decode()[:200]})
        else:
            self._json({'error': 'not found'}, 404)

    def do_POST(self):
        if not self._auth():
            self._json({'error': 'unauthorized'}, 401)
            return
        length = int(self.headers.get('Content-Length', 0))
        body = json.loads(self.rfile.read(length) or b'{}')

        if self.path == '/tap':
            x, y = body['x'], body['y']
            out, err, code = rish(f'input tap {x} {y}')
            self._json({'ok': code == 0})
        elif self.path == '/swipe':
            x1, y1, x2, y2 = body['x1'], body['y1'], body['x2'], body['y2']
            ms = body.get('ms', 300)
            out, err, code = rish(f'input swipe {x1} {y1} {x2} {y2} {ms}')
            self._json({'ok': code == 0})
        elif self.path == '/text':
            text = body['text'].replace(' ', '%s').replace("'", "")
            out, err, code = rish(f"input text '{text}'")
            self._json({'ok': code == 0})
        elif self.path == '/key':
            key = body['key']
            out, err, code = rish(f'input keyevent {key}')
            self._json({'ok': code == 0})
        elif self.path == '/shell':
            cmd = body['cmd']
            out, err, code = rish(cmd)
            self._json({'stdout': out.decode()[:10000], 'stderr': err.decode()[:2000], 'code': code})
        else:
            self._json({'error': 'not found'}, 404)

    def log_message(self, *a):
        pass

if __name__ == '__main__':
    print(f'Phone control server on 0.0.0.0:{PORT}')
    print('Make sure rish is working: run "rish -c echo hi" in Termux first')
    HTTPServer(('0.0.0.0', PORT), Handler).serve_forever()
