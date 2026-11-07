#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""לוח הצפייה · בנייה והצפנה של data.enc.json (גרסה 3: בנייה מלאה או מיזוג דלתא).

הרצה:
  בנייה מלאה:  python3 build.py --work DIR [--updated-by NAME] [--force]
  מיזוג דלתא:  python3 build.py --work DIR --merge [--updated-by NAME]
  הצצה בצילום: python3 build.py --work DIR --show ids | events | customers | content | content-short | pins | menus | published [id ...]

DIR מכיל:
  keys.json              {"dk": ..., "devices": {...}}   (מהדרייב, לא נשמר בשום מקום אחר)
  current.enc.json       data.enc.json שנמצא כרגע בריפו (אופציונלי, להשוואה)
  current.src.enc.json   tools/src.enc.json מהריפו: צילום מוצפן של נתוני המקור (חובה ל---merge ול---show)

בנייה מלאה: DIR/src/ מכיל את כל הקבצים:
  events.json      רשימת השורות כפי שמחזיר Notion SQL (ראו SKILL.md)
  customers.json   רשימת השורות כפי שמחזיר Notion SQL
  content.json     הערכים של 'לוח תוכן'!A1:Z  (רשימת שורות, השורה הראשונה כותרות)
  pins.json        הערכים של 'לוח פינטרסט'!A1:N
  menus.json       {"<eventId>": "<טקסט התפריט>"} לאירועים פתוחים (אופציונלי)
  published.json   ["<postId>", ...] רילס/פוסטים שמועדם עבר ו-Metricool כבר לא מציג כממתינים (אופציונלי)

מיזוג: DIR/src/delta.json בלבד (כל המפתחות אופציונליים):
  {"events":    {"upsert": [<שורת Notion>...], "patch": [{"id": "<url או id>", "set": {"שלב": "✅ נסגר"}}], "delete": ["<url או id>"...], "all": ["<url>"...]},
   "customers": {"upsert": [...], "patch": [...], "delete": [...]},
   "content":   {"upsert": [[<שורה מהגיליון>]...], "patch": [{"id": "post28", "set": {"סטטוס": "פורסם", "פורסם בפועל": "2026-11-04 18:30"}}], "delete": ["post14"...], "all": ["post01"...]},
   "pins":      {"upsert": [[...]...], "patch": [...], "delete": [...], "all": [...]},
   "menus":     {"set": {"<eventId>": "<טקסט>"}, "delete": ["<eventId>"...]},
   "published": {"add": ["post28"...]}}
  upsert מחליף שורה שלמה לפי מזהה (url / התא הראשון בשורה) או מוסיף; patch משנה רק את השדות הנתונים (בגיליון: לפי שם העמודה בכותרת);
  "all" = רשימת כל המזהים שקיימים במקור, וכל מה שלא בה נמחק. סדר ההחלה: upsert, patch, delete, all.

פלט: DIR/out/data.json (גלוי, לבדיקה בלבד), DIR/out/data.enc.json (לריפו), DIR/out/src.enc.json (צילום המקור, ל-tools/ בריפו).
קוד יציאה: 0 = נבנה קובץ חדש, 3 = אין שינוי בלוח (לדחוף רק src.enc.json ו-stamp.json), 1 = שגיאה.
"""
import json, re, sys, base64, secrets, datetime, hashlib, argparse, copy
from pathlib import Path
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

ap = argparse.ArgumentParser()
ap.add_argument("--work", required=True)
ap.add_argument("--updated-by", default="viewboard-publish")
ap.add_argument("--force", action="store_true")
ap.add_argument("--merge", action="store_true")
ap.add_argument("--show", nargs="+")
A = ap.parse_args()
W = Path(A.work); SRC = W / "src"; OUT = W / "out"; OUT.mkdir(exist_ok=True)

def load(name, default=None):
    p = SRC / name
    if not p.exists():
        if default is not None: return default
        sys.exit(f"missing {p}")
    return json.load(open(p, encoding="utf-8"))

# ---------- keys ----------
def unb64u(s): return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))
K = json.load(open(W / "keys.json"))
dk = unb64u(K["dk"])
def dec_json(path, key):
    e = json.load(open(path))
    return json.loads(AESGCM(key).decrypt(base64.b64decode(e["iv"]), base64.b64decode(e["ct"]), None))
def enc_json(obj, key):
    iv = secrets.token_bytes(12)
    ct = AESGCM(key).encrypt(iv, json.dumps(obj, ensure_ascii=False, separators=(",", ":")).encode("utf-8"), None)
    return {"v": 1, "iv": base64.b64encode(iv).decode(), "ct": base64.b64encode(ct).decode()}

# ---------- source snapshot / delta ----------
def pid(url):
    return (url or "").rstrip("/").rsplit("/", 1)[-1].replace("-", "")

SNAP = W / "current.src.enc.json"
snap = dec_json(SNAP, dk) if SNAP.exists() else None
SRC_NAMES = ["events", "customers", "content", "pins", "menus", "published"]

if A.show:
    if snap is None: sys.exit("missing current.src.enc.json")
    what, ids = A.show[0], set(A.show[1:])
    def P(x): print(json.dumps(x, ensure_ascii=False))
    if what == "ids":
        print("events:")
        for r in sorted(snap["events"], key=lambda r: r.get("date:תאריך:start") or ""):
            print(f"  {pid(r['url'])}  {r.get('date:תאריך:start')}  {r.get('שלב')}  {r.get('שם אירוע')}")
        print("customers:")
        for r in snap["customers"]: print(f"  {pid(r['url'])}  {r.get('שם מלא')}  bday={r.get('date:תאריך לידה:start')}")
        print("content:", [row[0] for row in snap["content"][1:] if row and row[0]])
        print("pins:", [row[0] for row in snap["pins"][1:] if row and row[0]])
        print("menus:", list(snap["menus"].keys()))
        print("published:", snap["published"])
    elif what in ("events", "customers"):
        for r in snap[what]:
            if not ids or pid(r["url"]) in ids: P(r)
    elif what in ("content", "pins"):
        head = snap[what][0]; P(head)
        for row in snap[what][1:]:
            if row and (not ids or row[0] in ids): P(row)
    elif what == "content-short":
        head = snap["content"][0]
        cols = ["מזהה פוסט", "מועד פרסום", "סטטוס", "פורסם בפועל", "הערות", "מזהה תמונה בפייסבוק", "לייקים", "תגובות", "שיתופים", "צפיות", "ביצועים נכון ל"]
        idx = [head.index(c) for c in cols if c in head]
        print(" | ".join(head[i] for i in idx))
        for n, row in enumerate(snap["content"][1:], start=2):
            if not row or not row[0]: continue
            row = row + [""] * (len(head) - len(row))
            print(f"{n}: " + " | ".join(str(row[i]) for i in idx))
    elif what == "menus":
        for k, v in snap["menus"].items():
            if not ids or k in ids: print(k, "·", len(v), "chars"); print(v); print()
    elif what == "published":
        P(snap["published"])
    else:
        sys.exit(f"unknown --show {what}")
    sys.exit(0)

def merge_rows(rows, d, key, head=None):
    m = {}
    for r in rows:
        k = key(r)
        if k: m[k] = r
    for r in d.get("upsert", []): m[key(r)] = r
    for p in d.get("patch", []):
        k = pid(p["id"]) if key is key_notion else p["id"]
        if k not in m: sys.exit(f"patch: no row {p['id']}")
        if head is None: m[k].update(p["set"])
        else:
            row = m[k] + [""] * (len(head) - len(m[k]))
            for col, val in p["set"].items():
                if col not in head: sys.exit(f"patch: no column {col}")
                row[head.index(col)] = val
            m[k] = row
    for x in d.get("delete", []): m.pop(pid(x) if key is key_notion else x, None)
    if d.get("all") is not None:
        keep = {pid(x) if key is key_notion else x for x in d["all"]}
        m = {k: v for k, v in m.items() if k in keep}
    return list(m.values())
def key_notion(r): return pid(r.get("url"))
def key_sheet(row): return row[0] if row else None

if A.merge:
    if snap is None: sys.exit("missing current.src.enc.json (run a full build first)")
    delta = load("delta.json", {})
    src = {k: copy.deepcopy(snap.get(k)) for k in SRC_NAMES}
    src["menus"] = src.get("menus") or {}; src["published"] = src.get("published") or []
    for name in ("events", "customers"):
        src[name] = merge_rows(src[name], delta.get(name, {}), key_notion)
    for name in ("content", "pins"):
        d = delta.get(name, {})
        head = src[name][0]
        rows = merge_rows(src[name][1:], d, key_sheet, head)
        src[name] = [head] + rows
    dm = delta.get("menus", {})
    src["menus"].update(dm.get("set", {}))
    for k in dm.get("delete", []): src["menus"].pop(k, None)
    src["published"] = sorted(set(src["published"]) | set(delta.get("published", {}).get("add", [])))
    changed = {k: (snap.get(k) != src[k]) for k in SRC_NAMES}
    print("delta applied:", ", ".join(k for k, v in changed.items() if v) or "nothing changed")
else:
    src = {"events": load("events.json"), "customers": load("customers.json"), "content": load("content.json"),
           "pins": load("pins.json"), "menus": load("menus.json", {}), "published": load("published.json", [])}

(OUT / "src.enc.json").write_text(json.dumps(enc_json(src, dk)), encoding="utf-8")

TZ = datetime.timezone(datetime.timedelta(hours=2))
now = datetime.datetime.now(TZ)
today = now.date()
first_of_month = today.replace(day=1)
def add_months(d, n):
    y, m = d.year, d.month + n
    while m > 12: y, m = y + 1, m - 12
    while m < 1: y, m = y - 1, m + 12
    return d.replace(year=y, month=m)
RANGE_FROM = add_months(first_of_month, -1).isoformat()
RANGE_TO = (add_months(first_of_month, 3) - datetime.timedelta(days=1)).isoformat()

STAGES = {
    "🆕 ליד נקלט": "lead", "🎨 עיצוב תפריט": "design", "⏳ ממתין לאישור תפריט": "pending",
    "🍽️ תפריט מאושר": "approved", "🎉 האירוע עבר": "done", "🙏 תודה נשלחה": "thanked",
    "⭐ המלצה נשלחה": "reviewed", "✅ נסגר": "closed", "❌ בוטל": "cancelled",
}
PAGE_ORDER = ["הבית שלי", "הסיפור מאחורי המנה", "מאחורי הקלעים", "האורחים שלי", "שירן ואליס", "טיפ שימושי", "רמז לערב הבא"]

def jlist(v):
    if not v: return []
    if isinstance(v, list): return v
    try: return json.loads(v)
    except Exception: return []

def clean_menu(text):
    if not text: return []
    t = text.replace("<br />", "\n").replace("<br>", "\n").replace("\\|", "|")
    t = re.sub(r"</?b>", "", t)
    t = re.sub(r"^#+\s*", "", t, flags=re.M)
    lines = [re.sub(r"\s+", " ", l).strip(" ·-*") for l in t.split("\n")]
    # שורות הערה שלמות בסוגריים ("(הועתק מקובץ...)", "(התפריט נשלח...)") הן מטא ולא מנות
    return [l for l in lines if l and not l.startswith("עודכן:") and not (l.startswith("(") and l.endswith(")"))]

# ---------- customers ----------
customers = {}
for r in src["customers"]:
    cid = pid(r.get("url"))
    phone = (r.get("מספר טלפון") or "").replace(" ", "").replace("-", "")
    if phone.startswith("0"): phone = "+972" + phone[1:]
    customers[cid] = {
        "name": r.get("שם מלא"), "phone": phone or None, "eventType": r.get("סוג אירוע"),
        "allergies": jlist(r.get("אלרגיות והגבלות תזונתיות")), "prefs": jlist(r.get("העדפות קולינריות")),
        "restaurants": r.get("מסעדות אהובות"), "source": r.get("איך שמעו עלינו"), "referrer": r.get("ממליץ"),
        "birthday": r.get("date:תאריך לידה:start"), "notes": r.get("הערות"),
    }

# ---------- events ----------
menus = src["menus"]
published = set(src["published"])
all_events = []
for r in src["events"]:
    date = (r.get("date:תאריך:start") or "")[:10]
    if not date: continue
    eid = pid(r.get("url"))
    cids = [pid(u) for u in jlist(r.get("לקוח"))]
    cid = cids[0] if cids else None
    c = customers.get(cid, {})
    stage = r.get("שלב") or ""
    adults = int(r.get("מבוגרים") or 0)
    price = r.get("מחיר לסועד")
    total = (price or 0) * adults if price else None
    shop_txt = (r.get("רשימת קניות") or "").strip()
    shopping = []
    for line in shop_txt.split("\n"):
        line = line.strip(" ·-")
        if not line: continue
        parts = [x.strip() for x in line.split("·")]
        if len(parts) >= 2: shopping.append({"name": parts[1], "qty": parts[2] if len(parts) > 2 else "", "category": parts[0]})
        else: shopping.append({"name": parts[0], "qty": "", "category": "אחר"})
    menu_text = menus.get(eid) or ((r.get("תפריט סופי") or "") if len(r.get("תפריט סופי") or "") > 150 else "")
    start = r.get("date:תאריך:start") or ""
    time = start[11:16] if len(start) > 10 and r.get("date:תאריך:is_datetime") else "20:30"
    all_events.append({
        "id": eid, "notionUrl": f"https://app.notion.com/{eid}", "date": date, "time": time,
        "title": r.get("שם אירוע"), "stage": stage, "stageKey": STAGES.get(stage, "unknown"),
        "kind": "couple" if adults <= 2 else "group", "customerId": cid, "customer": c.get("name"),
        "phone": c.get("phone"), "eventType": c.get("eventType"), "adults": adults, "kids": int(r.get("ילדים") or 0),
        "pricePerDiner": price, "total": total, "free": price == 0, "location": r.get("מיקום"),
        "menu": clean_menu(menu_text), "menuNote": None,
        "allergies": [a for a in c.get("allergies", []) if a != "אין אלרגיות או רגישויות"],
        "prefs": c.get("prefs", []), "restaurants": c.get("restaurants"), "source": c.get("source"),
        "referrer": c.get("referrer"), "notes": r.get("הערות"), "customerNotes": c.get("notes"), "liked": None,
        "history": [], "summaryDoc": r.get("מסמך סיכום") or None, "cost": r.get("עלות") if isinstance(r.get("עלות"), (int, float)) else None,
        "shopping": shopping or None, "shoppingAt": None, "shoppingDoc": None,
    })
by_c = {}
for e in all_events: by_c.setdefault(e["customerId"], []).append(e)
for e in all_events:
    e["history"] = [f"{x['date']} · {x['title']}" for x in sorted(by_c[e["customerId"]], key=lambda x: x["date"])
                    if x["date"] < e["date"] and x["stageKey"] != "cancelled"]
events = [e for e in all_events if RANGE_FROM <= e["date"] <= RANGE_TO and e["stageKey"] != "cancelled"]
for e in events:
    for k in ("cost", "shopping", "shoppingAt", "shoppingDoc"):
        if e[k] is None: del e[k]

# ---------- content (sheet) ----------
def rows_to_dicts(values):
    head = values[0]
    return [dict(zip(head, row + [""] * (len(head) - len(row)))) for row in values[1:] if any(row)]

content = []
tstr = today.isoformat()
def status_of(st, published_at, date):
    if st == "פורסם" or published_at: return "published", "פורסם"
    if "מאושר" in st:
        return ("overdue", "מועד עבר, לא פורסם") if date < tstr else ("scheduled", "מתוזמן")
    return "draft", "טיוטה"

for r in rows_to_dicts(src["content"]):
    when = r.get("מועד פרסום", ""); date = when[:10]
    if not date: continue
    notes = r.get("הערות", "") or ""; st = r.get("סטטוס", "") or ""
    is_reel = "רילס" in st or re.match(r"\s*רילס\s*\d", notes) is not None
    has_story = "סטורי" in notes
    base_time = when[11:16] if len(when) > 10 else None
    fb_text = r.get("טקסט פייסבוק") or ""; ig_text = r.get("טקסט אינסטגרם") or ""
    def num(k):
        v = (r.get(k) or "").replace(",", "").strip()
        return int(float(v)) if re.fullmatch(r"-?\d+(\.\d+)?", v) else None
    perf = {"likes": num("לייקים"), "comments": num("תגובות"), "shares": num("שיתופים"), "views": num("צפיות")}
    perf = perf if any(v is not None for v in perf.values()) else None
    perf_as_of = (r.get("ביצועים נכון ל") or "").strip() or None
    if r["מזהה פוסט"] in published and st != "פורסם":
        st = "פורסם"   # Metricool כבר פרסם, הגיליון עוד לא עודכן
    file_id = r.get("מזהה קובץ לפרסום") or None
    plats = (["facebook"] if r.get("פייסבוק") == "כן" else []) + (["instagram"] if r.get("אינסטגרם") == "כן" else [])
    for platform in plats:
        t = base_time
        if not is_reel and platform == "instagram" and base_time == "12:00": t = "19:30"   # Make: FB 12:00, IG 19:30
        s, s_txt = status_of(st, r.get("פורסם בפועל"), date)
        content.append({"id": f"{r['מזהה פוסט']}-{platform[:2]}", "postId": r["מזהה פוסט"], "date": date, "time": t,
                        "type": "reel" if is_reel else "post", "platform": platform, "status": s, "statusText": s_txt,
                        "page": r.get("עמוד תוכן") or None, "audience": r.get("קהל יעד") or None,
                        "text": fb_text if platform == "facebook" else (ig_text or fb_text),
                        "fileId": file_id, "thumb": None, "perf": perf, "perfAsOf": perf_as_of, "notes": notes or None})
    if is_reel and has_story:
        s, s_txt = status_of(st, r.get("פורסם בפועל"), date)
        content.append({"id": f"{r['מזהה פוסט']}-story", "postId": r["מזהה פוסט"], "date": date, "time": base_time,
                        "type": "story", "platform": "instagram", "status": s, "statusText": s_txt,
                        "page": r.get("עמוד תוכן") or None, "audience": r.get("קהל יעד") or None, "text": "סטורי של הרילס",
                        "fileId": file_id, "thumb": None, "perf": None, "perfAsOf": None, "notes": None})

for r in rows_to_dicts(src["pins"]):
    when = r.get("מועד פרסום", ""); date = when[:10]
    if not date: continue
    s = "published" if (date <= tstr or r.get("פורסם בפועל")) else "scheduled"   # פינים מתוזמנים בפינטרסט עצמו; הגיליון לא מקבל "פורסם בפועל"
    content.append({"id": r["מזהה פין"], "postId": r["מזהה פין"], "date": date, "time": when[11:16] or None, "type": "pin",
                    "platform": "pinterest", "status": s, "statusText": "פורסם" if s == "published" else "מתוזמן",
                    "page": r.get("עמוד תוכן") or None, "audience": r.get("לוח פינטרסט") or None,
                    "text": r.get("כותרת פינטרסט") or "", "fileId": r.get("מזהה קובץ לפרסום") or None,
                    "thumb": None, "perf": None, "perfAsOf": None, "notes": None})
content = [c for c in content if RANGE_FROM <= c["date"] <= RANGE_TO]

# ---------- holidays (static list, 2026-10 .. 2028-12) ----------
HOLIDAYS = json.load(open(Path(__file__).resolve().parent / "holidays.json", encoding="utf-8"))
holidays = [h for h in HOLIDAYS if h["end"] >= RANGE_FROM and h["date"] <= RANGE_TO]

# ---------- birthdays ----------
birthdays = []
for cid, c in customers.items():
    b = c.get("birthday")
    if not b or not c.get("phone"): continue
    year = int(b[:4])
    if year > 2012: continue   # תאריכי אירוע שנכנסו בטעות לשדה תאריך לידה
    birthdays.append({"customerId": cid, "name": c["name"], "phone": c["phone"], "monthDay": b[5:10], "birthYear": year})

data = {
    "v": 1, "updatedAt": now.isoformat(timespec="minutes"), "updatedBy": A.updated_by,
    "range": {"from": RANGE_FROM, "to": RANGE_TO},
    "stages": [{"key": v, "label": k} for k, v in STAGES.items()], "pages": PAGE_ORDER,
    "events": sorted(events, key=lambda e: e["date"]),
    "content": sorted(content, key=lambda c: (c["date"], c["time"] or "")),
    "holidays": holidays, "birthdays": birthdays,
}

# ---------- encryption ----------

def fingerprint(d):
    d = dict(d); d.pop("updatedAt", None); d.pop("updatedBy", None)
    return hashlib.sha256(json.dumps(d, ensure_ascii=False, sort_keys=True).encode()).hexdigest()

cur = W / "current.enc.json"
if cur.exists() and not A.force:
    try:
        enc0 = json.load(open(cur))
        old = json.loads(AESGCM(dk).decrypt(base64.b64decode(enc0["iv"]), base64.b64decode(enc0["ct"]), None))
        if fingerprint(old) == fingerprint(data):
            print("no change"); sys.exit(3)
    except SystemExit: raise
    except Exception as ex:
        print(f"current file unreadable ({ex}), rebuilding")

(OUT / "data.json").write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
iv = secrets.token_bytes(12)
ct = AESGCM(dk).encrypt(iv, json.dumps(data, ensure_ascii=False, separators=(",", ":")).encode("utf-8"), None)
wraps = []
for name, dev in K["devices"].items():
    wiv = secrets.token_bytes(12)
    wraps.append({"iv": base64.b64encode(wiv).decode(), "ct": base64.b64encode(AESGCM(unb64u(dev)).encrypt(wiv, dk, None)).decode()})
secrets.SystemRandom().shuffle(wraps)
enc = {"v": 2, "iv": base64.b64encode(iv).decode(), "ct": base64.b64encode(ct).decode(), "w": wraps}
(OUT / "data.enc.json").write_text(json.dumps(enc), encoding="utf-8")

# verify round trip with a device key
dev0 = unb64u(next(iter(K["devices"].values())))
ok = None
for w in enc["w"]:
    try: ok = AESGCM(dev0).decrypt(base64.b64decode(w["iv"]), base64.b64decode(w["ct"]), None); break
    except Exception: pass
assert ok == dk
dec = json.loads(AESGCM(ok).decrypt(base64.b64decode(enc["iv"]), base64.b64decode(enc["ct"]), None))
assert len(dec["events"]) == len(events)
print(f"built: events {len(events)} · content {len(content)} · holidays {len(holidays)} · birthdays {len(birthdays)} · range {RANGE_FROM}..{RANGE_TO}")
