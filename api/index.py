urllib.request
from datetime import date, timedelta, datetime

BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
ADMIN = str(os.environ.get("ADMIN_CHAT_ID", ""))
STATE_CHAT = str(os.environ.get("STATE_CHAT_ID", "") or ADMIN)
KEY_SECRET = os.environ.get("KEY_SECRET", "KMJ-TIPS-VERIFY-KEY-2026")
API = "https://api.telegram.org/bot" + BOT_TOKEN
DEFAULT_STATE = "VALID_DAYS=2\n"
CHARS = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"

HELP = (
    "KMJ VERIFY v9 Control Bot\n"
    "Use the buttons below - or type commands:\n\n"
    "/approve DEVICEID [days or YYYY-MM-DD]\n"
    "/revoke DEVICEID\n"
    "/days N\n"
    "/genkey DEVICEID [days or date]\n"
    "/genlist [days] [count]\n"
    "/used KEY BUYERID [date]\n"
    "/list  /stats  /users  /menu  /init"
)

def B(text, data):
    return {"text": text, "callback_data": data}

def main_kb():
    return {"inline_keyboard": [
        [B("📊 Dashboard", "m:stats"), B("👥 Users", "m:users")],
        [B("⏳ Pending", "m:pending"), B("📈 Activity", "m:activity")],
        [B("✅ Approve User", "a:approve"), B("🚫 Revoke User", "a:revoke")],
        [B("🔑 Device Key", "a:genkey"), B("🎲 Random Keys", "a:genlist")],
        [B("🏷️ Mark Used", "a:used"), B("📅 Global Days", "a:days")],
        [B("📥 Downloads", "m:downloads"), B("📋 Full List", "m:list")],
        [B("❓ Help", "m:help")],
    ]}

def back_kb():
    return {"inline_keyboard": [[B("⬅️ Main Menu", "m:menu")]]}

def days_kb():
    return {"inline_keyboard": [
        [B("📅 1 Day", "d:1"), B("📅 2 Days", "d:2"), B("📅 7 Days", "d:7")],
        [B("📅 15 Days", "d:15"), B("📅 30 Days", "d:30"), B("📅 90 Days", "d:90")],
        [B("📅 365 Days", "d:365"), B("❌ Cancel", "m:menu")],
    ]}

# ---------------- Telegram API ----------------

def api(method, params=None):
    data = json.dumps(params or {}).encode()
    req = urllib.request.Request(API + "/" + method, data=data,
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=25) as r:
            return json.loads(r.read().decode())
    except Exception as e:
        print("API error", method, e)
        return {"ok": False}

def reply(text, kb=None):
    p = {"chat_id": ADMIN, "text": text}
    if kb:
        p["reply_markup"] = kb
    return api("sendMessage", p)

def animate_search(mid, label):
    """Stylish progress animation: edits the panel message a few times."""
    if not mid:
        return
    frames = ["[▱▱▱▱▱] 0%", "[▰▱▱▱▱] 25%", "[▰▰▰▱▱] 55%", "[▰▰▰▰▱] 80%", "[▰▰▰▰▰] 100%"]
    for f in frames:
        edit_msg(mid, "%s\n%s" % (label, f), None)
        time.sleep(0.35)

def edit_msg(mid, text, kb=None):
    p = {"chat_id": ADMIN, "message_id": mid, "text": text}
    if kb:
        p["reply_markup"] = kb
    return api("editMessageText", p)

# ---------------- State: control list (pure text) ----------------

def st_lines(text):
    return [l.strip() for l in (text or "").replace("\r", "").split("\n") if l.strip()]

def st_days(text):
    for l in st_lines(text):
        u = l.upper().replace(" ", "")
        if u.startswith("VALID_DAYS="):
            try:
                return int(u.split("=", 1)[1])
            except Exception:
                pass
    return 2

def st_body(text):
    out = []
    for l in st_lines(text):
        if l.upper().replace(" ", "").startswith("VALID_DAYS="):
            continue
        if l.upper().replace(" ", "").startswith("VALID_HOURS="):
            continue
        out.append(l)
    return out

def st_build(days, body_lines):
    return "VALID_DAYS=%d\n%s" % (days, "\n".join(body_lines))

def control_lines(text):
    return [l for l in st_body(text) if not l.startswith("#")]

def spec_of(token, default_days):
    if not token:
        return "%dD" % default_days
    t = token.strip().upper()
    if t.endswith("D") and t[:-1].isdigit():
        return t
    if t.isdigit():
        return t + "D"
    return t

def _approve_keep(l, did):
    if l.startswith("#X|") and len(l.split("|")) > 1 and l.split("|")[1].strip().upper() == did.upper():
        return False  # approving removes this device's block
    if l.startswith("#"):
        return True
    return l.split("|")[0].strip().upper() != did.upper()

def op_approve(text, did, token):
    days = st_days(text)
    body = [l for l in st_body(text) if _approve_keep(l, did)]
    body.append("%s | %s" % (did.upper(), spec_of(token, days)))
    return st_build(days, body)

def op_remove(text, did):
    body = [l for l in st_body(text) if l.startswith("#") or l.split("|")[0].strip().upper() != did.upper()]
    return st_build(st_days(text), body)

def op_set_days(text, n):
    return st_build(n, st_body(text))

def op_add_keys(text, key_lines):
    return st_build(st_days(text), st_body(text) + key_lines)

def op_mark_used(text, key, buyer, token):
    days = st_days(text)
    out, done = [], False
    for l in st_body(text):
        first = l.split("|")[0].strip().upper()
        if not l.startswith("#") and first == key.upper() and "USED" not in l.upper():
            out.append("%s | USED | %s | %s" % (key.upper(), buyer.upper(), spec_of(token, days)))
            done = True
        else:
            out.append(l)
    return st_build(days, out), done

def is_approved(text, did):
    for l in control_lines(text):
        if l.split("|")[0].strip().upper() == did.upper():
            return True
    return False

def device_key(did, token):
    t = (token or "").strip()
    if "-" in t and len(t) == 10:
        ymd = t.replace("-", "")
        label = t
    else:
        d = int(t) if t.isdigit() else 30
        label = (date.today() + timedelta(days=d)).isoformat()
        ymd = label.replace("-", "")
    msg = ("%s|%s" % (did.upper(), ymd)).encode()
    sig = hmac.new(KEY_SECRET.encode(), msg, hashlib.sha256).hexdigest().upper()[:12]
    return "KMJ-%s-%s" % (ymd, sig), label

def random_key(days):
    p = lambda n: "".join(random.choice(CHARS) for _ in range(n))
    return "KMJ-%s-%s | %dD" % (p(6), p(6), days)

def list_stats(text):
    ids = active = fresh = used = 0
    today = date.today().isoformat()
    for l in control_lines(text):
        parts = [p.strip() for p in l.split("|")]
        first = parts[0].upper()
        if first.startswith("KMJ-") and len(first) == 17:
            if "USED" in l.upper():
                used += 1
            else:
                fresh += 1
        else:
            ids += 1
            spec = parts[1].upper() if len(parts) > 1 else ""
            if spec.endswith("D") or spec >= today or spec == "":
                active += 1
    return ids, active, fresh, used


def blocked_ids(text):
    out = set()
    for l in st_lines(text):
        if l.startswith("#X|"):
            parts = l.split("|")
            if len(parts) > 1:
                out.add(parts[1].strip().upper())
    return out

def is_blocked(text, did):
    return did.upper() in blocked_ids(text)

def op_revoke_full(text, did):
    """Revoke that really sticks: remove the ID line, remove USED key
    lines bound to this device, and add a blocklist line (#X|<did>)
    which the app honors above every approval (v11+)."""
    days = st_days(text)
    did = did.upper()
    out = []
    for l in st_body(text):
        if l.startswith("#X|"):
            if l.split("|")[1].strip().upper() != did:
                out.append(l)
            continue
        if l.startswith("#"):
            out.append(l)
            continue
        parts = [x.strip() for x in l.split("|")]
        first = parts[0].upper()
        if first == did:
            continue
        if len(parts) >= 3 and parts[1].upper() == "USED" and parts[2].upper() == did:
            continue
        out.append(l)
    out.append("#X|" + did)
    return st_build(days, out)

def op_unblock(text, did):
    body = [l for l in st_body(text) if not (l.startswith("#X|") and l.split("|")[1].strip().upper() == did.upper())]
    return st_build(st_days(text), body)

# ---------------- State: user registry (#U lines, written by apps) ----------------

def parse_users(text):
    users = []
    for l in st_lines(text):
        if l.startswith("#U|"):
            p = l.split("|")
            if len(p) >= 7:
                try:
                    users.append({
                        "id": p[1], "model": p[2],
                        "battery": int(p[3]) if p[3].lstrip("-").isdigit() else -1,
                        "last": int(p[4]), "status": p[5], "first": int(p[6]),
                    })
                except Exception:
                    pass
    return users

def fmt_ago(ms):
    if not ms:
        return "never"
    sec = max(0, int(time.time() - ms / 1000.0))
    if sec < 90:
        return "just now"
    if sec < 3600:
        return "%d min ago" % (sec // 60)
    if sec < 86400:
        return "%d h ago" % (sec // 3600)
    return "%d d ago" % (sec // 86400)

def fmt_time(ms):
    try:
        return datetime.fromtimestamp(ms / 1000.0).strftime("%d %b %H:%M")
    except Exception:
        return "-"

def user_line(u):
    bat = ("%d%%" % u["battery"]) if u["battery"] >= 0 else "?"
    return "%s\n%s | Battery %s | %s | %s" % (u["id"], u["model"], bat, u["status"], fmt_ago(u["last"]))

# ---------------- State: pending step (#B line) ----------------

def get_pending(text):
    for l in st_lines(text):
        if l.startswith("#B|"):
            p = l.split("|")
            return {"action": p[1] if len(p) > 1 else "", "step": p[2] if len(p) > 2 else "", "data": p[3] if len(p) > 3 else ""}
    return None

def set_pending(text, action, step="", data=""):
    body = [l for l in st_body(text) if not l.startswith("#B|")]
    if action:
        body.append("#B|%s|%s|%s" % (action, step, data))
    return st_build(st_days(text), body)

# ---------------- State storage (pinned message) ----------------

def get_state():
    r = api("getChat", {"chat_id": STATE_CHAT})
    if not r.get("ok"):
        return DEFAULT_STATE, None
    pm = (r.get("result") or {}).get("pinned_message") or {}
    txt = pm.get("text") or pm.get("caption") or ""
    return (txt if txt.strip() else DEFAULT_STATE), pm.get("message_id")

def set_state(text, mid):
    if mid:
        r = api("editMessageText", {"chat_id": STATE_CHAT, "message_id": mid, "text": text})
        if r.get("ok"):
            return mid
    r = api("sendMessage", {"chat_id": STATE_CHAT, "text": text})
    if r.get("ok"):
        mid = r["result"]["message_id"]
        api("pinChatMessage", {"chat_id": STATE_CHAT, "message_id": mid, "disable_notification": True})
        return mid
    return None

def save(new_text):
    _, mid = get_state()
    return set_state(new_text, mid)

# ---------------- Screens ----------------

def scr_dashboard(text):
    ids, active, fresh, used = list_stats(text)
    users = parse_users(text)
    now = int(time.time() * 1000)
    online = len([u for u in users if now - u["last"] < 30 * 60 * 1000])
    pend = len([u for u in users if u["status"] != "ACTIVE" and not is_approved(text, u["id"]) and not is_blocked(text, u["id"])])
    today0 = int(datetime.combine(date.today(), datetime.min.time()).timestamp() * 1000)
    new_today = len([u for u in users if u["first"] >= today0])
    return ("📊 KMJ VERIFY - Dashboard\n\n"
            "Total devices (app installs): %d\n"
            "Active in last 30 min: %d\n"
            "New devices today: %d\n"
            "Pending requests: %d\n\n"
            "Approved IDs in list: %d (active: %d)\n"
            "Fresh keys: %d | Sold keys: %d\n"
            "Global days: %d\n\n"
            "Pick an action:" % (len(users), online, new_today, pend, ids, active, fresh, used, st_days(text)))

def scr_users(text):
    users = sorted(parse_users(text), key=lambda u: -u["last"])
    if not users:
        return "No users yet.\n\nJab koi app kholega, uska device yahan dikhega (model, battery, status)."
    out = ["👥 All Users (%d):\n" % len(users)]
    for u in users[:12]:
        out.append(user_line(u))
    if len(users) > 12:
        out.append("... and %d more" % (len(users) - 12))
    return "\n\n".join(out)

def scr_pending(text):
    users = sorted(parse_users(text), key=lambda u: -u["last"])
    pend = [u for u in users if u["status"] != "ACTIVE" and not is_approved(text, u["id"]) and not is_blocked(text, u["id"])]
    if not pend:
        return "No pending requests.\n\nSab approved hain, ya abhi koi naya user nahi aaya.", None
    out = ["⏳ Pending Requests (%d):\n" % len(pend)]
    rows = []
    for u in pend[:8]:
        out.append(user_line(u))
        rows.append([B("✅ Approve %s (%dD)" % (u["id"][:9] + "..", st_days(text)), "apg:" + u["id"])])
    rows.append([B("⬅️ Main Menu", "m:menu")])
    return "\n\n".join(out), {"inline_keyboard": rows}

def scr_activity(text):
    users = sorted(parse_users(text), key=lambda u: -u["last"])
    if not users:
        return "No activity yet."
    out = ["📈 Latest Activity:\n"]
    for u in users[:10]:
        out.append("%s - %s\n%s | Battery %s | %s" % (
            fmt_time(u["last"]), u["id"], u["model"],
            ("%d%%" % u["battery"]) if u["battery"] >= 0 else "?",
            "Approved user" if is_approved(text, u["id"]) or u["status"] == "ACTIVE" else "Waiting"))
    return "\n\n".join(out)

def scr_downloads(text):
    users = parse_users(text)
    today0 = int(datetime.combine(date.today(), datetime.min.time()).timestamp() * 1000)
    week0 = today0 - 6 * 86400 * 1000
    new_today = sorted([u for u in users if u["first"] >= today0], key=lambda u: -u["first"])
    new_week = len([u for u in users if u["first"] >= week0])
    out = ["📥 Downloads (app installs)\n\n"
           "Total devices that opened the app: %d\n"
           "New today: %d\n"
           "New this week: %d" % (len(users), len(new_today), new_week)]
    if new_today:
        out.append("\nToday's new devices:")
        for u in new_today[:8]:
            out.append("%s\n%s | %s" % (u["id"], u["model"], fmt_time(u["first"])))
    out.append("\nNote: ye count un devices ka hai jinhone app khola (install karke chalaya). Sirf file download karke app na kholne wale isme nahi aate.")
    return "\n".join(out)

def scr_list(text):
    lines = control_lines(text)
    body = "\n".join(lines) if lines else "(empty)"
    return "📋 Control List (VALID_DAYS=%d):\n\n%s" % (st_days(text), body)

# ---------------- Button flows ----------------

ASK = {
    ("approve", "id"): "Approve karne ke liye user ki Device ID bhejo:",
    ("revoke", "id"): "Revoke (block) karne ke liye Device ID bhejo:",
    ("genkey", "id"): "Device Key ke liye user ki Device ID bhejo:",
    ("genlist", "days"): None,
    ("used", "key"): "Jo random key bechi hai wo bhejo (KMJ-......):",
    ("used", "buyer"): "Buyer ki Device ID bhejo:",
}

def start_flow(action):
    state, _ = get_state()
    if action == "genlist":
        save(set_pending(state, "genlist", "days"))
        reply("Random keys: kitne din ki validity?", days_kb())
        return
    if action == "days":
        reply("Global days set karo - sab naye approvals ke liye:", days_kb())
        save(set_pending(state, "days", "pick"))
        return
    step = "id" if action in ("approve", "revoke", "genkey") else "key"
    save(set_pending(state, action, step))
    reply(ASK[(action, step)], back_kb())

def finish_days_choice(p, days):
    """A day-count button was tapped inside a pending flow."""
    action = p["action"]
    state, _ = get_state()
    if action == "approve":
        did = p["data"]
        save(set_pending(op_approve(state, did, str(days)), ""))
        reply("Approved: %s for %d day(s).\nUser ka app kuch seconds me khul jayega." % (did, days), main_kb())
    elif action == "genkey":
        did = p["data"]
        key, label = device_key(did, str(days))
        save(set_pending(state, ""))
        reply("Device key for %s\nValid till: %s\n\n%s\n\nSirf ye key user ko bhejo. Sirf usi device par chalegi, internet ki bhi zarurat nahi." % (did, label, key), main_kb())
    elif action == "genlist":
        save(set_pending(state, "genlist", "count", str(days)))
        reply("Kitni keys banau?", {"inline_keyboard": [
            [B("🔢 5 Keys", "cnt:5"), B("🔢 10 Keys", "cnt:10"), B("🔢 20 Keys", "cnt:20")],
            [B("❌ Cancel", "m:menu")]]})
    elif action == "days":
        save(op_set_days(state, days))
        reply("Global days set: %d\nNaye approvals (bina apne days wale) ab %d din ke honge." % (days, days), main_kb())

def handle_pending_text(text_in):
    state, _ = get_state()
    p = get_pending(state)
    if not p:
        return False
    action, step, data = p["action"], p["step"], p["data"]
    val = text_in.strip()
    if action == "approve" and step == "id":
        did = val.upper()
        save(set_pending(state, "approve", "days", did))
        reply("Device: %s\nKitne din ke liye approve karu?" % did, days_kb())
        return True
    if action == "revoke" and step == "id":
        did = val.upper()
        save(set_pending(state, "revoke", "confirm", did))
        reply("Pakka revoke karu?\nDevice: %s\nUser agle app open par block ho jayega." % did,
              {"inline_keyboard": [[B("🚫 Yes, Revoke", "cf:revoke"), B("❌ Cancel", "m:menu")]]})
        return True
    if action == "genkey" and step == "id":
        did = val.upper()
        save(set_pending(state, "genkey", "days", did))
        reply("Device: %s\nKey kitne din ki ho?" % did, days_kb())
        return True
    if action == "used" and step == "key":
        save(set_pending(state, "used", "buyer", val.upper()))
        reply(ASK[("used", "buyer")], back_kb())
        return True
    if action == "used" and step == "buyer":
        new, done = op_mark_used(state, data, val.upper(), None)
        save(set_pending(new, ""))
        if done:
            reply("Key %s ab sirf %s par chalegi (USED mark ho gayi)." % (data, val.upper()), main_kb())
        else:
            reply("Key list me nahi mili (galat key ya pehle se USED).", main_kb())
        return True
    return False

def handle_callback(cb):
    data = cb.get("data") or ""
    mid = (cb.get("message") or {}).get("message_id")
    api("answerCallbackQuery", {"callback_query_id": cb.get("id")})
    state, _ = get_state()
    if data == "m:menu":
        save(set_pending(state, ""))
        if mid:
            edit_msg(mid, scr_dashboard(state), main_kb())
        else:
            reply(scr_dashboard(state), main_kb())
    elif data == "m:stats":
        if mid: animate_search(mid, "🔍 Loading dashboard...")
        edit_msg(mid, scr_dashboard(state), main_kb()) if mid else reply(scr_dashboard(state), main_kb())
    elif data == "m:users":
        if mid: animate_search(mid, "🔍 Searching users...")
        edit_msg(mid, scr_users(state), back_kb()) if mid else reply(scr_users(state), back_kb())
    elif data == "m:pending":
        if mid: animate_search(mid, "🔍 Searching pending requests...")
        txt, kb = scr_pending(state)
        edit_msg(mid, txt, kb or back_kb()) if mid else reply(txt, kb or back_kb())
    elif data == "m:activity":
        if mid: animate_search(mid, "🔍 Loading activity...")
        edit_msg(mid, scr_activity(state), back_kb()) if mid else reply(scr_activity(state), back_kb())
    elif data == "m:downloads":
        if mid: animate_search(mid, "🔍 Counting downloads...")
        edit_msg(mid, scr_downloads(state), back_kb()) if mid else reply(scr_downloads(state), back_kb())
    elif data == "m:list":
        if mid: animate_search(mid, "🔍 Loading full list...")
        edit_msg(mid, scr_list(state), back_kb()) if mid else reply(scr_list(state), back_kb())
    elif data == "m:help":
        edit_msg(mid, HELP, back_kb()) if mid else reply(HELP, back_kb())
    elif data.startswith("a:"):
        start_flow(data[2:])
    elif data.startswith("apg:"):
        did = data[4:]
        save(op_approve(state, did, None))
        reply("Approved: %s (%d day(s))." % (did, st_days(state)), 
