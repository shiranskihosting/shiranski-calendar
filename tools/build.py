#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""לוח הצפייה · בנייה והצפנה של data.enc.json (גרסה 2, לריצה המתוזמנת).

הרצה:  python3 build2.py --work DIR [--updated-by NAME] [--force]
DIR מכיל:
  keys.json            {"dk": ..., "devices": {"phone": ..., "desktop": ...}}   (מהדרייב, לא נשמר בשום מקום אחר)
  src/events.json      רשימת השורות כפי שמחזיר Notion SQL (ראו SKILL.md)
  src/customers.json   רשימת השורות כפי שמחזיר Notion SQL
  src/content.json     הערכים של 'לוח תוכן'!A1:U  (רשימת שורות, השורה הראשונה כותרות)
  src/pins.json        הערכים של 'לוח פינטרסט'!A1:N
  src/menus.json       {"<eventId>": "<טקסט התפריט>"} לאירועים פתוחים (אופציונלי)
  src/published.json   ["<postId>", ...] רילס/פוסטים שמועדם עבר ו-Metricool כבר לא מציג כממתינים (אופציונלי)
  current.enc.json     הקובץ שנמצא כרגע בריפו (אופציונלי, להשוואה)
פלט: DIR/out/data.json (גלוי, לבדיקה בלבד) ו-DIR/out/data.enc.json (לריפו).
קוד יציאה: 0 = נבנה קובץ חדש, 3 = אין שינוי (לא לדחוף), 1 = שגיאה.
"""
import json, re, sys, base64, secrets, datetime, hashlib, argparse
from pathlib import Path

ap = argparse.ArgumentParser()
ap.add_argument("--work", required=True)
ap.add_argument("--updated-by", default="viewboard-publish")
ap.add_argument("--force", action="store_true")
A = ap.parse_args()
W = Path(A.work); SRC = W / "src"; OUT = W / "out"; OUT.mkdir(exist_ok=True)

def load(name, default=None):
    p = SRC / name
    if not p.exists():
        if default is not None: return default
        sys.exit(f"missing {p}")
    return json.load(open(p, encoding="utf-8"))

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

def pid(url):
    return (url or "").rstrip("/").rsplit("/", 1)[-1].replace("-", "")

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
    return [l for l in lines if l and not l.startswith("עודכן:")]

# ---------- customers ----------
customers = {}
for r in load("customers.json"):
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
menus = load("menus.json", {})
published = set(load("published.json", []))
all_events = []
for r in load("events.json"):
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

for r in rows_to_dicts(load("content.json")):
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

for r in rows_to_dicts(load("pins.json")):
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

# ---------- encryption helpers ----------
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
def unb64u(s): return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))
K = json.load(open(W / "keys.json"))
dk = unb64u(K["dk"])

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
