#!/usr/bin/env python3
"""Tiny local server for the roadmap page. Binds 127.0.0.1 only. Stdlib only.

  python3 serve.py --port 8797 --out DIR --interval 900
Routes: / (index.html), /roadmap.json, /narrative.json, /digest.md, /refresh (rebuild now).
"""
import argparse
import datetime
import http.server
import json
import os
import sqlite3
import subprocess
import sys
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import collect  # noqa: E402  (aliases + source paths)

LOCK = threading.Lock()
STATE = {"last": None, "ok": None, "secs": None, "err": "", "fingerprint": None, "skipped": 0}
SHIPLOG_DB = os.path.expanduser("~/.local/share/shiplog/shiplog.db")


def log(msg):
    print("%s roadmap: %s" % (time.strftime("%H:%M:%S"), msg), flush=True)


def _ro_one(path, sql):
    try:
        con = sqlite3.connect("file:" + path + "?mode=ro", uri=True, timeout=5)
        try:
            return con.execute(sql).fetchone()
        finally:
            con.close()
    except Exception as e:
        return ("err", type(e).__name__)


def fingerprint():
    """Cheap change check: newest mem observation id, shiplog rows/mtime, each repo's HEAD, and today's date (window rolls)."""
    fp = {"day": datetime.date.today().isoformat(),
          "mem_max_id": _ro_one(collect.MEM_DB, "SELECT max(id) FROM observations")}
    try:
        fp["ship"] = [_ro_one(SHIPLOG_DB, "SELECT max(id), count(*) FROM ships"), os.path.getmtime(SHIPLOG_DB)]
    except OSError:
        fp["ship"] = None
    heads = {}
    for repo in sorted(collect.load_aliases()["repos"]):
        if not (os.path.isdir(os.path.join(repo, ".git")) or os.path.isfile(os.path.join(repo, ".git"))):
            continue
        try:
            r = subprocess.run(["git", "--no-optional-locks", "-C", repo, "rev-parse", "HEAD"], capture_output=True, text=True, timeout=15)
            heads[repo] = r.stdout.strip()
        except Exception:
            heads[repo] = "?"
    fp["heads"] = heads
    return json.loads(json.dumps(fp))


def maybe_rebuild(out, since, force=False):
    """Skip the full collect when nothing upstream changed (unless forced)."""
    fp = fingerprint()
    npath = os.path.join(out, "narrative.json")
    nm = os.path.getmtime(npath) if os.path.isfile(npath) else None
    if not force and fp == STATE.get("fingerprint") and nm != STATE.get("narr_mtime") and STATE.get("narr_mtime") is not None:
        STATE["narr_mtime"] = nm
        subprocess.run([sys.executable, os.path.join(HERE, "render.py"), "--out", out], capture_output=True, timeout=120)
        log("unchanged data; narrative.json changed, re-rendered only")
        return dict(STATE)
    STATE["narr_mtime"] = nm
    if not force and fp == STATE.get("fingerprint") and os.path.isfile(os.path.join(out, "index.html")):
        STATE["skipped"] += 1
        log("unchanged (skipped rebuild #%d)" % STATE["skipped"])
        return dict(STATE)
    st = rebuild(out, since)
    if st["ok"]:
        STATE["fingerprint"] = fp
    log("rebuilt ok=%s in %ss%s" % (st["ok"], st["secs"], " (forced)" if force else ""))
    return st


def rebuild(out, since):
    with LOCK:
        t = time.time()
        try:
            r = subprocess.run([sys.executable, os.path.join(HERE, "collect.py"), "--out", out, "--since", since],
                               capture_output=True, text=True, timeout=600)
            if r.returncode == 0:
                r = subprocess.run([sys.executable, os.path.join(HERE, "render.py"), "--out", out],
                                   capture_output=True, text=True, timeout=120)
            STATE["ok"] = r.returncode == 0
            STATE["err"] = (r.stderr or "")[-400:] if r.returncode else ""
        except Exception as e:
            STATE["ok"], STATE["err"] = False, str(e)
        STATE["secs"] = round(time.time() - t, 1)
        STATE["last"] = time.strftime("%Y-%m-%dT%H:%M:%S")
        return dict(STATE)


def make_handler(out, since):
    files = {"/": ("index.html", "text/html; charset=utf-8"), "/index.html": ("index.html", "text/html; charset=utf-8"),
             "/roadmap.json": ("roadmap.json", "application/json"), "/narrative.json": ("narrative.json", "application/json"),
             "/digest.md": ("digest.md", "text/markdown; charset=utf-8")}

    class H(http.server.BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def _send(self, code, body, ctype, mtime=None):
            self.send_response(code)
            if mtime:
                self.send_header("Last-Modified", self.date_time_string(mtime))
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            path = self.path.split("?")[0]
            if path == "/refresh":
                st = maybe_rebuild(out, since, force=True)
                return self._send(200 if st["ok"] else 500, json.dumps(st).encode(), "application/json")
            if path in files:
                name, ctype = files[path]
                fp = os.path.join(out, name)
                if os.path.isfile(fp):
                    with open(fp, "rb") as f:
                        return self._send(200, f.read(), ctype, os.path.getmtime(fp))
            self._send(404, b"not found", "text/plain")

    return H


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8797)
    ap.add_argument("--out", default=os.path.join(os.path.dirname(HERE), "out"))
    ap.add_argument("--interval", type=int, default=900)
    ap.add_argument("--since", default="180d")
    a = ap.parse_args()
    out = os.path.abspath(os.path.expanduser(a.out))
    os.makedirs(out, exist_ok=True)
    maybe_rebuild(out, a.since)

    def loop():
        while True:
            time.sleep(max(30, a.interval))
            maybe_rebuild(out, a.since)

    threading.Thread(target=loop, daemon=True).start()
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", a.port), make_handler(out, a.since))
    print("roadmap: http://127.0.0.1:%d/  (rebuild every %ds, out=%s)" % (a.port, a.interval, out), flush=True)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
