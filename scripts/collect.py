#!/usr/bin/env python3
"""Collect roadmap data from claude-mem, shiplog and git. Python 3 stdlib only.

Writes <out>/roadmap.json and <out>/digest.md.  Read-only against every source.
"""
import argparse
import collections
import datetime as dt
import glob
import html
import json
import os
import re
import sqlite3
import statistics
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(HERE)
ALIASES = os.path.join(SKILL, "aliases.json")
DEFAULT_ALIASES = ALIASES
MEM_DB = os.path.expanduser("~/.claude-mem/claude-mem.db")
SHIPLOG = os.path.expanduser("~/.local/bin/shiplog")
TOMB_GLOBS = ["~/Desktop/Projects/*.ARCHIVED.txt", "~/Desktop/Projects/*.ARCHIVED"]

# ---------------------------------------------------------------- redaction
# Private companion-mode content must never be emitted. Extend freely.
REDACT_DENYLIST = [
    r"\bsam\b", r"girlfriend", r"gf mode", r"sexy", r"spicy", r"heat ladder",
    r"heat-ladder", r"nsfw", r"explicit", r"lingerie", r"nude", r"flirt",
    r"companion mode", r"sam-harbor", r"private mode", r"private chat", r"kink",
    # broader SAM-adjacent vocabulary (2026-11-20: "private pack prompt (persona/heat/affect/bond…)" leaked)
    r"private pack", r"private gate", r"\bheat\b", r"\bbond\b", r"\baffect\b", r"\bpersona",
    r"emotional depth", r"ex machina", r"\bher\b", r"intimate", r"romanc", r"\berotic",
    r"partner voice", r"\bpartner pack", r"\bwren\b", r"desire", r"seduc",
]
DENY_RE = re.compile("|".join(REDACT_DENYLIST), re.I)
MASKS = [
    re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+"),
    re.compile(r"(?<![\w])(?:\+?1[\s.-]?)?\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}(?![\w])"),
    re.compile(r"\b(?:sk|pk|rk)-[A-Za-z0-9_-]{16,}"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}"),
    re.compile(r"\b[A-Fa-f0-9]{32,}\b"),
    re.compile(r"(?=[A-Za-z0-9+/=]*\d)(?=[A-Za-z0-9+/=]*[A-Za-z])[A-Za-z0-9+/=]{32,}"),
]

REDACT_ON = True
REDACTIONS = collections.Counter()


def clean(s, kind="text", maxlen=None):
    """Return redacted text, or None if it must be dropped."""
    if s is None:
        return None
    s = re.sub(r"\s+", " ", html.unescape(str(s))).strip()
    if not s:
        return None
    if REDACT_ON:
        if DENY_RE.search(s):
            REDACTIONS[kind] += 1
            return None
        for m in MASKS:
            s, n = m.subn("[redacted]", s)
            if n:
                REDACTIONS["masked"] += n
    if maxlen and len(s) > maxlen:
        s = s[: maxlen - 1].rstrip() + "…"
    return s


# ---------------------------------------------------------------- helpers
def atomic_write(path, text):
    tmp = "%s.tmp.%d" % (path, os.getpid())
    with open(tmp, "w") as f:
        f.write(text)
    os.replace(tmp, path)


MIN_BASE = 20      # minimum prior-4 baseline (units) before a momentum % is reported
BUILD_TYPES = ("feature", "bugfix", "change", "refactor")
ALL_TYPES = BUILD_TYPES + ("discovery", "decision")


def wk(d):
    y, w, _ = d.isocalendar()
    return "%d-W%02d" % (y, w)


def wk_monday(k):
    y, w = k.split("-W")
    return dt.date.fromisocalendar(int(y), int(w), 1)


def parse_since(s, now):
    m = re.fullmatch(r"(\d+)d", s.strip())
    if m:
        return (now - dt.timedelta(days=int(m.group(1)))).date()
    return dt.date.fromisoformat(s.strip()[:10])


def load_aliases():
    with open(ALIASES) as f:
        a = json.load(f)
    projs = a["projects"]
    exact = {}
    prefix = []
    for name, r in projs.items():
        for e in r.get("exact", []):
            exact[e.lower()] = name
        exact[name.lower()] = name
        for p in r.get("prefix", []):
            prefix.append((p.lower(), name))
    prefix.sort(key=lambda x: -len(x[0]))
    drop = {d.lower() for d in a.get("drop", [])}
    drop_pat = [re.compile(p, re.I) for p in a.get("drop_patterns", [])]
    repos = {}
    for name, r in projs.items():
        for p in r.get("repos", []):
            repos[os.path.expanduser(p)] = name
    kws = []
    for name, r in projs.items():
        for k in r.get("keywords", []):
            kws.append((k.lower(), name, re.compile(r"(?<![A-Za-z0-9])" + re.escape(k) + r"(?![A-Za-z0-9])", re.I)))
    return dict(projs=projs, exact=exact, prefix=prefix, drop=drop, drop_pat=drop_pat, repos=repos, kws=kws)


def canon_raw(A, raw):
    """Return (canonical|None, is_drop). Own-name fallback handled by caller."""
    low = raw.lower().strip()
    if low in A["exact"]:
        return A["exact"][low], False
    for p, name in A["prefix"]:
        if low.startswith(p):
            return name, False
    if low in A["drop"] or any(p.search(raw) for p in A["drop_pat"]):
        return None, True
    return None, False


def own_name(raw):
    if any(c.isupper() for c in raw):
        return raw.strip()
    return re.sub(r"[-_]+", " ", raw).strip().title()


def canon_by_repo(A, path):
    if not path:
        return None
    path = os.path.expanduser(path)
    best = None
    for r, name in A["repos"].items():
        if path == r or path.startswith(r.rstrip("/") + "/"):
            if best is None or len(r) > len(best[0]):
                best = (r, name)
    return best[1] if best else None


def day_of(ms):
    return dt.datetime.fromtimestamp(ms / 1000.0).date()


# ---------------------------------------------------------------- mem
def collect_mem(A, since_date, notes):
    ms0 = int(dt.datetime.combine(since_date, dt.time.min).timestamp() * 1000)
    con = sqlite3.connect("file:" + MEM_DB + "?mode=ro", uri=True, timeout=30)
    con.execute("PRAGMA query_only=1")
    cur = con.cursor()
    DAY = "strftime('%Y-%m-%d', created_at_epoch/1000, 'unixepoch', 'localtime')"
    rows = cur.execute(
        "SELECT project, %s d, type, count(*) FROM observations WHERE created_at_epoch>=? GROUP BY 1,2,3" % DAY,
        (ms0,)).fetchall()

    raw_total = collections.Counter()
    for p, d, t, c in rows:
        raw_total[p] += c
    total_obs = sum(raw_total.values())
    weekly_all = collections.Counter()      # every observation in window (attributed or not) by ISO week
    for p, d, t, c in rows:
        weekly_all[wk(dt.date.fromisoformat(d))] += c

    # classify raw projects
    cmap = {}      # raw -> canonical name or None (unattributed)
    dropraw = []
    for raw, n in raw_total.items():
        c, isdrop = canon_raw(A, raw)
        if c:
            cmap[raw] = c
        elif isdrop:
            cmap[raw] = None
            dropraw.append(raw)
        elif n >= 30 and clean(raw, "projname") is not None:
            cmap[raw] = own_name(raw)
        else:
            cmap[raw] = None

    daily = collections.defaultdict(lambda: collections.defaultdict(collections.Counter))  # canon->day->type->n
    for p, d, t, c in rows:
        cn = cmap.get(p)
        if cn:
            daily[cn][d][t] += c

    # keyword attribution of dropped buckets
    cands = collections.defaultdict(list)   # canon -> [(day,type,title)]
    attributed_kw = 0
    if A["kws"] and dropraw:
        like = " OR ".join(["lower(title) LIKE ?"] * len(A["kws"]))
        lp = ["%" + k[0] + "%" for k in A["kws"]]
        for i in range(0, len(dropraw), 400):
            chunk = dropraw[i:i + 400]
            q = ("SELECT %s d, type, title FROM observations WHERE created_at_epoch>=? AND project IN (%s) AND (%s)"
                 % (DAY, ",".join("?" * len(chunk)), like))
            for d, t, title in cur.execute(q, [ms0] + chunk + lp):
                if not title:
                    continue
                for k, name, rx in A["kws"]:
                    if rx.search(title):
                        daily[name][d][t] += 1
                        attributed_kw += 1
                        if t in ("feature", "decision"):
                            cands[name].append((d, t, title))
                        break

    # milestone candidates from attributed raw projects
    keep_raw = [r for r, c in cmap.items() if c]
    for i in range(0, len(keep_raw), 400):
        chunk = keep_raw[i:i + 400]
        q = ("SELECT project, d, type, title FROM (SELECT project, %s d, type, title, "
             "ROW_NUMBER() OVER (PARTITION BY project ORDER BY created_at_epoch DESC) rn "
             "FROM observations WHERE created_at_epoch>=? AND type IN ('feature','decision') AND project IN (%s)) "
             "WHERE rn<=60" % (DAY, ",".join("?" * len(chunk))))
        for p, d, t, title in cur.execute(q, [ms0] + chunk):
            if title:
                cands[cmap[p]].append((d, t, title))

    # session summaries
    sums = collections.defaultdict(list)
    for i in range(0, len(keep_raw), 400):
        chunk = keep_raw[i:i + 400]
        q = ("SELECT project, created_at_epoch, completed, next_steps FROM (SELECT project, created_at_epoch, completed, next_steps, "
             "ROW_NUMBER() OVER (PARTITION BY project ORDER BY created_at_epoch DESC) rn "
             "FROM session_summaries WHERE created_at_epoch>=? AND project IN (%s)) WHERE rn<=3" % ",".join("?" * len(chunk)))
        for p, ep, comp, nxt in cur.execute(q, [ms0] + chunk):
            sums[cmap[p]].append((ep, comp, nxt))
    con.close()

    attributed = sum(sum(c.values()) for dd in daily.values() for c in dd.values())
    return dict(daily=daily, cands=cands, sums=sums, total_obs=total_obs, attributed=attributed,
                attributed_kw=attributed_kw, weekly_all=weekly_all)


# ---------------------------------------------------------------- shiplog
def collect_ships(A, out, since_date):
    if not os.access(SHIPLOG, os.X_OK):
        return []
    tmp = os.path.join(out, ".shiplog-tmp.%d.jsonl" % os.getpid())
    try:
        subprocess.run([SHIPLOG, "export", "--format", "jsonl", "--out", tmp], capture_output=True, timeout=60, check=True)
        lines = open(tmp).read().splitlines()
    except Exception as e:
        return []
    finally:
        try:
            os.remove(tmp)
        except OSError:
            pass
    ships = []
    for ln in lines:
        try:
            r = json.loads(ln)
        except ValueError:
            continue
        at = (r.get("at") or "")[:10]
        if not at or at < since_date.isoformat():
            continue
        raw = r.get("project") or ""
        c, isdrop = canon_raw(A, raw)
        if not c:
            c = canon_by_repo(A, r.get("repo_path"))
        if not c and raw and not isdrop:
            c = own_name(raw.split("/")[-1])
        r["_canon"] = c
        r["_date"] = at
        ships.append(r)
    return ships


# ---------------------------------------------------------------- git
def collect_git(A, since_date):
    per = collections.defaultdict(lambda: collections.defaultdict(int))   # canon->week->n
    days = collections.defaultdict(set)
    seen_by_proj = collections.defaultdict(set)   # canon -> full hashes already counted (clones share history)
    scanned = 0
    total = 0
    for repo, name in A["repos"].items():
        if not os.path.isdir(os.path.join(repo, ".git")) and not os.path.isfile(os.path.join(repo, ".git")):
            continue
        scanned += 1
        try:
            r = subprocess.run(["git", "--no-optional-locks", "-C", repo, "log", "--since=" + since_date.isoformat(),
                                "--format=%H%x09%ct", "--no-merges", "--branches", "HEAD"],
                               capture_output=True, text=True, timeout=90)
        except Exception:
            continue
        seen = seen_by_proj[name]
        for ln in r.stdout.splitlines():
            h, _, ct = ln.partition("\t")
            if not ct.isdigit() or h in seen:
                continue
            seen.add(h)
            d = dt.date.fromtimestamp(int(ct))
            per[name][wk(d)] += 1
            days[name].add(d.isoformat())
            total += 1
    return per, days, scanned, total


# ---------------------------------------------------------------- tombstones
def collect_tombstones():
    out = []
    for g in TOMB_GLOBS:
        for p in glob.glob(os.path.expanduser(g)):
            stem = os.path.basename(p)
            stem = re.sub(r"\.ARCHIVED(\.txt)?$", "", stem)
            out.append((stem, dt.date.fromtimestamp(os.path.getmtime(p))))
    return out


# ---------------------------------------------------------------- build
def spans_from(weeks, window_end):
    if not weeks:
        return []
    idx = sorted(wk_monday(w).toordinal() // 7 for w in weeks)
    res = []
    s = e = idx[0]
    for i in idx[1:]:
        if i - e - 1 <= 2:
            e = i
        else:
            res.append((s, e))
            s = e = i
    res.append((s, e))
    out = []
    for s, e in res:
        start = dt.date.fromordinal(s * 7 + 0)
        # ordinal//7 buckets start on Monday? date.toordinal()%7==1 for Monday; normalise via monday lookup
        out.append((s, e))
    # convert using real monday dates
    mondays = {wk_monday(w).toordinal() // 7: wk_monday(w) for w in weeks}
    final = []
    for s, e in out:
        sd = mondays.get(s) or min(m for k, m in mondays.items() if k >= s)
        ed = (mondays.get(e) or sd) + dt.timedelta(days=6)
        final.append({"start": sd.isoformat(), "end": min(ed, window_end).isoformat()})
    return final


def thin(items, n=12):
    items = sorted(items, key=lambda x: x["date"])
    if len(items) <= n:
        return items
    step = (len(items) - 1) / float(n - 1)
    return [items[round(i * step)] for i in range(n)]


def build(args):
    global REDACT_ON
    REDACT_ON = not args.no_redact
    t0 = time.time()
    now = dt.datetime.now()
    window_end = now.date()
    since = parse_since(args.since, now)
    A = load_aliases()
    out = os.path.abspath(os.path.expanduser(args.out))
    os.makedirs(out, exist_ok=True)

    timing = {}
    t = time.time()
    mem = collect_mem(A, since, None)
    timing["mem"] = round(time.time() - t, 2)
    t = time.time()
    ships = collect_ships(A, out, since)
    timing["shiplog"] = round(time.time() - t, 2)
    t = time.time()
    gweeks, gdays, repos_scanned, git_total = collect_git(A, since)
    timing["git"] = round(time.time() - t, 2)
    tombs = collect_tombstones()

    names = set(mem["daily"]) | set(gweeks) | {s["_canon"] for s in ships if s["_canon"]}
    names = {n for n in names if clean(n, "projname") is not None} if REDACT_ON else names

    suspect_rows = 0
    suspect_days = collections.defaultdict(set)
    projects = []
    d0 = wk_monday(wk(window_end))
    CW = [wk(d0 - dt.timedelta(weeks=i)) for i in range(1, 9)]   # complete weeks, newest first
    for name in names:
        dd = mem["daily"].get(name, {})
        totals_by_day = {d: sum(c.values()) for d, c in dd.items()}
        # backfill guard
        if totals_by_day:
            med = statistics.median(totals_by_day.values())
            act_days = sorted(set(totals_by_day) | gdays.get(name, set()))
            ords = [dt.date.fromisoformat(d).toordinal() for d in act_days]
            for d, n in totals_by_day.items():
                if n >= 10 and n > 5 * med:
                    o = dt.date.fromisoformat(d).toordinal()
                    if not any(x != o and abs(x - o) <= 21 for x in ords):
                        suspect_days[name].add(d)
                        suspect_rows += n
        weeks = {}
        types_tot = collections.Counter()
        for d, c in dd.items():
            if d in suspect_days[name]:
                continue
            w = wk(dt.date.fromisoformat(d))
            wv = weeks.setdefault(w, {"mem": 0, "commits": 0, "by_type": {}})
            for ty, n in c.items():
                wv["mem"] += n
                wv["by_type"][ty] = wv["by_type"].get(ty, 0) + n
                types_tot[ty] += n
        for w, n in gweeks.get(name, {}).items():
            wv = weeks.setdefault(w, {"mem": 0, "commits": 0, "by_type": {}})
            wv["commits"] += n
        commits = sum(gweeks.get(name, {}).values())
        basis = "git" if commits >= 10 else "mem"
        for w, wv in weeks.items():
            wv["act"] = wv["commits"] if basis == "git" else wv["mem"]
        active_weeks = {w for w, wv in weeks.items() if wv["act"] > 0}
        if not active_weeks:
            active_weeks = set(weeks)
        spans = spans_from(active_weeks, window_end)

        pships = [s for s in ships if s["_canon"] == name]
        # dates
        dates = [d for d in totals_by_day if d not in suspect_days[name]] + sorted(gdays.get(name, set())) + [s["_date"] for s in pships]
        if not dates:
            continue
        if sum(types_tot.values()) + commits == 0:
            continue   # ship-only name with no recorded work; counted in portfolio ships only
        first_seen, last_seen = min(dates), max(dates)
        age = (window_end - dt.date.fromisoformat(last_seen)).days
        status = "active" if age < 7 else ("cooling" if age < 30 else "dormant")

        # milestones
        seen_titles = set()
        red_ms = 0
        cands = []
        for d, ty, title in sorted(mem["cands"].get(name, []), reverse=True):
            if d in suspect_days[name]:
                continue
            key = title.lower()
            if key in seen_titles:
                continue
            seen_titles.add(key)
            ct = clean(title, "milestone", 140)
            if ct:
                cands.append({"date": d, "title": ct, "kind": ty})
            else:
                red_ms += 1          # withheld text; milestone counts only feed lists, totals come from obs counts
            if len(cands) >= 40:
                break
        decisions_recent = [c for c in cands if c["kind"] == "decision"][:6]
        ms = thin(cands, 12)
        # counts always include every row; redacted rows only lose their text (omitted from display list)
        ship_counts = collections.Counter(s.get("status") for s in pships)
        agents = collections.Counter((s.get("agent") or "unknown").lower() for s in pships)
        pship_out = []
        red_ships = 0
        for s in sorted(pships, key=lambda x: x.get("at", ""), reverse=True):
            summ = clean(s.get("summary"), "ship", 160)
            if not summ:
                red_ships += 1
                continue
            pship_out.append({"date": s["_date"], "at": s.get("at"), "agent": (s.get("agent") or "").lower() or None,
                              "summary": summ, "status": s.get("status"),
                              "tests": clean(s.get("tests"), "ship", 140),
                              "deploy": clean(s.get("deploy"), "ship", 120),
                              "branch": clean(s.get("branch"), "ship", 80)})
        for s in pship_out[:10]:
            ms.append({"date": s["date"], "title": s["summary"], "kind": "ship"})

        # summaries
        nxt, comp = [], []
        red_next = 0
        for ep, c, n in sorted(mem["sums"].get(name, []), reverse=True):
            cn = clean(n, "next", 280)
            if cn and cn not in nxt:
                nxt.append(cn)
            elif n and not cn:
                red_next += 1
            cc = clean(c, "completed", 280)
            if cc and cc not in comp:
                comp.append(cc)

        tt = types_tot
        build_n = sum(tt[k] for k in BUILD_TYPES)
        explore = round(tt["discovery"] / build_n, 2) if build_n else None
        # momentum
        # last 4 COMPLETE weeks vs the 4 before; the in-progress current ISO week (wl[0]) is excluded.
        # Unit is the project's own basis (commits if git-based else mem obs); result is % of its own baseline.
        last4 = sum(weeks.get(w, {}).get("act", 0) for w in CW[:4])
        prior4 = sum(weeks.get(w, {}).get("act", 0) for w in CW[4:8])
        mom = round((last4 - prior4) * 100.0 / prior4) if prior4 >= MIN_BASE else None

        projects.append({
            "name": name, "status": status, "basis": basis,
            "first_seen": first_seen, "last_seen": last_seen,
            "weeks": dict(sorted(weeks.items())), "spans": spans,
            "totals": {"obs": sum(tt.values()), "commits": commits, "features": tt["feature"], "bugfixes": tt["bugfix"],
                       "changes": tt["change"], "refactors": tt["refactor"], "decisions": tt["decision"],
                       "discoveries": tt["discovery"],
                       "ships": ship_counts["shipped"], "held": ship_counts["held"], "failed": ship_counts["failed"]},
            "redacted": {"ships": red_ships, "milestones": red_ms, "next_steps": red_next},
            "explore_ratio": explore, "milestones": ms, "decisions": decisions_recent, "ships": pship_out[:12],
            "next_steps": nxt[:3], "recent_completed": comp[:3], "agents": dict(agents),
            "momentum": mom, "recent4": last4, "prior4": prior4, "momentum_unit": "commits" if basis == "git" else "mem obs",
        })

    # tombstones
    notes = []
    for stem, mt in tombs:
        sl = re.sub(r"[^a-z0-9]", "", stem.lower())
        for p in projects:
            # canonical name only: a tombstoned sub-repo (e.g. "Vid2Skill Mobile") doesn't end the whole project
            if re.sub(r"[^a-z0-9]", "", p["name"].lower()) == sl:
                if mt >= dt.date.fromisoformat(p["last_seen"]) - dt.timedelta(days=3):
                    p["status"] = "archived"
                    p["archived_at"] = mt.isoformat()
                else:
                    notes.append("tombstone '%s' (%s) predates later activity in %s; not archived" % (stem, mt, p["name"]))

    projects.sort(key=lambda p: (p["last_seen"], p["totals"]["obs"] + p["totals"]["commits"]), reverse=True)

    # portfolio
    weekly = collections.Counter()
    bytype = collections.Counter()
    for p in projects:
        for w, wv in p["weeks"].items():
            weekly[w] += wv["act"]
        for k, v in p["totals"].items():
            pass
        bytype.update({"feature": p["totals"]["features"], "bugfix": p["totals"]["bugfixes"], "change": p["totals"]["changes"],
                       "refactor": p["totals"]["refactors"], "decision": p["totals"]["decisions"], "discovery": p["totals"]["discoveries"]})
    ship_status = collections.Counter(s.get("status") or "?" for s in ships)
    listed = sum(p["totals"]["ships"] + p["totals"]["held"] + p["totals"]["failed"] for p in projects)
    ships_total = len(ships)
    # portfolio momentum: ONE unit = all memory observations (attributed + unattributed), minus suspect backfill days
    wmem = collections.Counter(mem["weekly_all"])
    for nm, ds in suspect_days.items():
        for d in ds:
            dd = mem["daily"].get(nm, {}).get(d)
            if dd:
                wmem[wk(dt.date.fromisoformat(d))] -= sum(dd.values())
    wmem = {k: v for k, v in wmem.items() if v > 0}
    pl4 = sum(wmem.get(w, 0) for w in CW[:4])
    pp4 = sum(wmem.get(w, 0) for w in CW[4:8])
    pmom = {"unit": "memory observations (attributed + unattributed)", "last4": pl4, "prior4": pp4,
            "pct": round((pl4 - pp4) * 100.0 / pp4) if pp4 >= MIN_BASE else None,
            "last4_weeks": [CW[3], CW[0]], "prior4_weeks": [CW[7], CW[4]], "in_progress_week": wk(window_end), "min_baseline": MIN_BASE}
    agents = collections.Counter((s.get("agent") or "unknown").lower() for s in ships)
    # scoped numbers: only the listed lanes (used by the renderer in focus mode)
    swk = collections.Counter()
    for p in projects:
        for w, wv in p["weeks"].items():
            swk[w] += wv["mem"]
    swk = {k: v for k, v in swk.items() if v > 0}
    sl4 = sum(swk.get(w, 0) for w in CW[:4])
    sp4 = sum(swk.get(w, 0) for w in CW[4:8])
    sagents = collections.Counter()
    for p in projects:
        sagents.update(p["agents"])
    scoped = {"unit": "memory observations in listed lanes", "weekly_mem_total": dict(sorted(swk.items())),
              "momentum": {"unit": "memory observations in listed lanes", "last4": sl4, "prior4": sp4,
                           "pct": round((sl4 - sp4) * 100.0 / sp4) if sp4 >= MIN_BASE else None,
                           "last4_weeks": [CW[3], CW[0]], "prior4_weeks": [CW[7], CW[4]],
                           "in_progress_week": wk(window_end), "min_baseline": MIN_BASE},
              "ships_by_status": {k: sum(p["totals"][t] for p in projects) for k, t in (("shipped", "ships"), ("held", "held"), ("failed", "failed"))},
              "ships_total": listed, "agents": dict(sagents)}
    focus = os.path.abspath(ALIASES) != os.path.abspath(DEFAULT_ALIASES)
    # near-dup collapse: agents re-log the same decision ("…Full Feature Spec Received/Defined/Delivered")
    all_dec, seen_keys = [], set()
    for d in sorted([dict(d, project=p["name"]) for p in projects for d in p["decisions"]], key=lambda x: x["date"], reverse=True):
        key = (d["project"], " ".join(re.findall(r"[a-z0-9]+", d["title"].lower())[:4]))
        if key in seen_keys:
            continue
        seen_keys.add(key)
        all_dec.append(d)
    all_dec = all_dec[:15]

    coverage = round(mem["attributed"] / mem["total_obs"], 4) if mem["total_obs"] else 0
    meta = {
        "generated_at": now.astimezone().isoformat(timespec="seconds"),
        "title": getattr(args, "title", None) or "Roadmap",
        "focus": focus, "unit_label": "workstreams" if focus else "projects",
        "window_start": since.isoformat(), "window_end": window_end.isoformat(), "since_arg": args.since,
        "ships": {"total": ships_total, "in_listed_projects": listed, "unlisted": ships_total - listed},
        "current_week": wk(window_end),
        "sources": {"mem_obs": mem["total_obs"], "ship_entries": len(ships), "git_commits": git_total, "repos_scanned": repos_scanned},
        "coverage": coverage, "keyword_attributed": mem["attributed_kw"],
        "suspect_backfill_rows": suspect_rows,
        "suspect_backfill": {k: sorted(v) for k, v in suspect_days.items() if v},
        "redactions": dict(REDACTIONS) | {"total": sum(REDACTIONS[k] for k in REDACTIONS if k != "masked")},
        "redaction_on": REDACT_ON, "notes": notes, "timing": timing,
    }
    roadmap = {"meta": meta, "projects": projects,
               "portfolio": {"weekly_totals": dict(sorted(weekly.items())), "by_type_totals": dict(bytype),
                             "weekly_mem_total": dict(sorted(wmem.items())), "momentum": pmom,
                             "ships_total": ships_total,
                             "ships_by_status": dict(ship_status), "agents": dict(agents), "scoped": scoped, "decisions": all_dec}}
    meta["timing"]["total"] = round(time.time() - t0, 2)
    atomic_write(os.path.join(out, "digest.md"), make_digest(roadmap))
    atomic_write(os.path.join(out, "roadmap.json"), json.dumps(roadmap, indent=1))
    return roadmap


def spark(weeks, keys):
    bars = "▁▂▃▄▅▆▇█"
    vals = [weeks.get(k, {}).get("act", 0) for k in keys]
    m = max(vals) or 1
    return "".join(bars[min(7, int(v * 7.99 / m))] if v else "·" for v in vals)


def make_digest(R):
    m, P = R["meta"], R["projects"]
    L = []
    L.append("# Roadmap digest  (%s .. %s, generated %s)" % (m["window_start"], m["window_end"], m["generated_at"]))
    pm = R["portfolio"]["momentum"]
    L.append("Ships logged in window: %d (all shiplog rows; %d in listed projects, %d unlisted). Withheld-text items still count in totals."
             % (m["ships"]["total"], m["ships"]["in_listed_projects"], m["ships"]["unlisted"]))
    L.append("Portfolio momentum (%s): %s  [last 4 complete weeks %d vs prior 4 %d; in-progress week %s excluded]"
             % (pm["unit"], ("%+d%%" % pm["pct"]) if pm["pct"] is not None else "n/a", pm["last4"], pm["prior4"], pm["in_progress_week"]))
    L.append("Sources: %(mem_obs)d mem obs, %(ship_entries)d shiplog entries, %(git_commits)d commits, %(repos_scanned)d repos." % m["sources"])
    L.append("Coverage: %.0f%% of mem activity attributed to a project (%.0f%% unattributed). Suspect backfill rows excluded: %d."
             % (m["coverage"] * 100, 100 - m["coverage"] * 100, m["suspect_backfill_rows"]))
    L.append("Statuses: " + ", ".join("%s=%d" % (s, sum(1 for p in P if p["status"] == s)) for s in ("active", "cooling", "dormant", "archived")))
    wt = R["portfolio"]["weekly_totals"]
    keys = sorted(wt)
    L.append("Portfolio weekly activity (oldest->newest, %d wks): %s" % (len(keys), " ".join(str(wt[k]) for k in keys[-16:])))
    L.append("")
    allk = keys
    for i, p in enumerate(P):
        t = p["totals"]
        if i >= 14:
            if i == 14:
                L.append("## Other projects (one line each)")
            L.append("- %s [%s] last %s; obs %d, commits %d" % (p["name"], p["status"], p["last_seen"], t["obs"], t["commits"]))
            continue
        L.append("## %s [%s] %s .. %s%s" % (p["name"], p["status"], p["first_seen"], p["last_seen"],
                                          "  (archived %s)" % p["archived_at"] if p.get("archived_at") else ""))
        L.append("spans: " + ", ".join("%s..%s" % (s["start"], s["end"]) for s in p["spans"]))
        L.append("activity[%s]: %s" % (p["basis"], spark(p["weeks"], allk)))
        L.append("totals: obs %d | commits %d | feat %d | bugfix %d | decisions %d | discoveries %d | ships %d | held %d"
                 % (t["obs"], t["commits"], t["features"], t["bugfixes"], t["decisions"], t["discoveries"], t["ships"], t["held"] + t["failed"]))
        L.append("explore_ratio %s | momentum %s | agents %s" % (p["explore_ratio"], ("%+d%% of own baseline (%s, last4 %d vs prior4 %d)" % (p["momentum"], p["momentum_unit"], p["recent4"], p["prior4"])) if p["momentum"] is not None else "n/a", p["agents"] or "-"))
        for ms in [x for x in p["milestones"] if x["kind"] != "ship"][-6:]:
            L.append("  milestone %s [%s] %s" % (ms["date"], ms["kind"], ms["title"]))
        for s in p["ships"][:3]:
            L.append("  ship %s [%s] %s" % (s["date"], s["status"], s["summary"]))
        for n in p["next_steps"][:2]:
            L.append("  next: " + n)
        for c in p["recent_completed"][:1]:
            L.append("  done: " + c)
        L.append("")
    if R["portfolio"]["decisions"]:
        L.append("## Latest decisions")
        for d in R["portfolio"]["decisions"][:10]:
            L.append("- %s %s: %s" % (d["date"], d["project"], d["title"]))
    return "\n".join(L[:300]) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--since", default="180d")
    ap.add_argument("--no-redact", action="store_true")
    ap.add_argument("--aliases", help="alternate lane map (e.g. a single-project focus file); default aliases.json")
    ap.add_argument("--title", default="Roadmap", help="page/deck title")
    a = ap.parse_args()
    global ALIASES
    if a.aliases:
        ALIASES = os.path.abspath(os.path.expanduser(a.aliases))
    R = build(a)
    m = R["meta"]
    print("collect ok: %d projects, coverage %.1f%%, suspect rows %d, redactions %s, timing %s"
          % (len(R["projects"]), m["coverage"] * 100, m["suspect_backfill_rows"], m["redactions"].get("total"), m["timing"]))


if __name__ == "__main__":
    main()
