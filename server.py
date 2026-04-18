"""
White Rabbit AI Chatbot — Universal Backend
=============================================
One codebase, many clients. All branding and content driven by:
  - config.json (branding, languages, system prompt)
  - Google Sheet (knowledge base + unanswered questions log)
  - Environment variables (API keys, secrets)

Deploy per client with different config.json + env vars.
"""

import os
import json
import time
import uuid
import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Request, Depends, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import anthropic
import gspread
from google.oauth2.service_account import Credentials

# ─── LOAD CONFIG ──────────────────────────────────────────────────────

CONFIG_PATH = Path(os.getenv("BEERBOT_CONFIG", "config.json"))
with open(CONFIG_PATH, "r", encoding="utf-8") as f:
    CFG = json.load(f)

BOT = CFG["bot"]
BRAND = CFG["branding"]
LANGUAGES = CFG["languages"]
WELCOME = CFG["welcome_messages"]
PLACEHOLDERS = CFG["placeholders"]
DISCLAIMER = CFG["disclaimer"]

# ─── ENV VARS ─────────────────────────────────────────────────────────

API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin2026")
SHEET_ID = os.getenv("GOOGLE_SHEET_ID", "")
SA_PATH = os.getenv("GOOGLE_SA_JSON", "service-account.json")
SA_CONTENT = os.getenv("GOOGLE_SA_JSON_CONTENT", "")
RATE_LIMIT = int(os.getenv("RATE_LIMIT", "15"))
KB_REFRESH = int(os.getenv("KB_REFRESH_SECONDS", "300"))

LOG_DIR = Path(os.getenv("LOG_DIR", "./logs"))
LOG_DIR.mkdir(exist_ok=True)

# ─── GOOGLE SHEETS ────────────────────────────────────────────────────

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.readonly",
]
_gc = None


def get_gc():
    global _gc
    if _gc:
        return _gc
    try:
        if SA_CONTENT:
            creds = Credentials.from_service_account_info(json.loads(SA_CONTENT), scopes=SCOPES)
        elif os.path.exists(SA_PATH):
            creds = Credentials.from_service_account_file(SA_PATH, scopes=SCOPES)
        else:
            print("⚠️  No Google credentials — Sheet integration disabled")
            return None
        _gc = gspread.authorize(creds)
        print("✅ Google Sheets connected")
        return _gc
    except Exception as e:
        print(f"⚠️  Sheets auth failed: {e}")
        return None


# ─── KNOWLEDGE BASE CACHE ────────────────────────────────────────────

FALLBACK_KB = "No knowledge base loaded. Please check Google Sheet connection."
_kb = {"text": FALLBACK_KB, "ts": 0}


def refresh_kb():
    gc = get_gc()
    if not gc or not SHEET_ID:
        return _kb["text"]
    if time.time() - _kb["ts"] < KB_REFRESH:
        return _kb["text"]
    try:
        ws = gc.open_by_key(SHEET_ID).worksheet("Knowledge Base")
        rows = ws.get_all_values()
        lines, cat = [], ""
        for row in rows[1:]:
            if len(row) < 2 or not row[1].strip():
                continue
            c = row[0].strip()
            if c and c != cat:
                lines.append(f"\n{c.upper()}:")
                cat = c
            lines.append(f"- {row[1].strip()}")
        if lines:
            _kb["text"] = "\n".join(lines)
            _kb["ts"] = time.time()
            print(f"✅ KB refreshed ({len(lines)} entries)")
    except Exception as e:
        print(f"⚠️  KB refresh failed: {e}")
    return _kb["text"]


def log_unanswered_sheet(lang, source, question, bot_reply):
    gc = get_gc()
    if not gc or not SHEET_ID:
        return
    try:
        sh = gc.open_by_key(SHEET_ID)
        try:
            ws = sh.worksheet("Unanswered")
        except gspread.exceptions.WorksheetNotFound:
            ws = sh.add_worksheet("Unanswered", 1000, 8)
            ws.update("A1:H1", [["Datum", "Jazyk", "Zdroj", "Dotaz", "Odpověď bota", "Vaše odpověď", "Stav", "V KB?"]])
            ws.format("A1:H1", {"textFormat": {"bold": True}})

        lang_map = {l["code"]: f"{l['flag']} {l['code'].upper()}" for l in LANGUAGES}
        src_map = {"widget": "🌐 Web", "tablet": "📱 iPad", "qr": "📷 QR"}
        ws.append_row([
            datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M"),
            lang_map.get(lang, lang),
            src_map.get(source, source),
            question,
            bot_reply[:200],
            "",
            "Nový",
            "FALSE",
        ], value_input_option="USER_ENTERED")
    except Exception as e:
        print(f"⚠️  Sheet log failed: {e}")


# ─── SYSTEM PROMPT ────────────────────────────────────────────────────

LANG_NAMES = {
    "cs": "Czech", "en": "English", "de": "German", "es": "Spanish",
    "fr": "French", "it": "Italian", "ja": "Japanese", "ko": "Korean",
    "zh": "Chinese", "uk": "Ukrainian", "pl": "Polish",
}


def build_system_prompt(lang_code: str) -> str:
    kb = refresh_kb()
    tmpl = CFG["system_prompt_template"]
    return tmpl.format(
        bot_name=BOT["name"],
        bot_emoji=BOT["bot_emoji"],
        tagline=BOT["tagline"],
        lang_name=LANG_NAMES.get(lang_code, "English"),
        lang_code=lang_code,
        knowledge_base=kb,
    )


# ─── DETECTION ────────────────────────────────────────────────────────

UNKNOWN_MARKERS = [
    "nevím", "don't know", "not sure", "nemám informac",
    "kontaktujte", "contact", "zeptejte se", "ask at",
    "+420 778", "visit@beermuseum", "na recepci",
    "kann ich nicht", "no tengo esa información",
    "je ne sais pas", "non so", "わかりません",
    "모르겠", "不知道", "nie wiem", "не знаю",
]


def is_unknown(reply: str) -> bool:
    r = reply.lower()
    return any(m in r for m in UNKNOWN_MARKERS)


# ─── LOCAL LOGGING ────────────────────────────────────────────────────

def log_local(sid, lang, source, q, a, ip, flagged):
    f = LOG_DIR / f"chat-{datetime.now(timezone.utc).strftime('%Y-%m-%d')}.jsonl"
    with open(f, "a", encoding="utf-8") as fh:
        fh.write(json.dumps({
            "ts": datetime.now(timezone.utc).isoformat(),
            "sid": sid, "lang": lang, "src": source,
            "ip": hashlib.sha256(ip.encode()).hexdigest()[:12],
            "q": q, "a": a, "flagged": flagged,
        }, ensure_ascii=False) + "\n")


# ─── RATE LIMITER ─────────────────────────────────────────────────────

_rl: dict[str, list[float]] = {}


def rate_ok(ip: str) -> bool:
    now = time.time()
    _rl.setdefault(ip, [])
    _rl[ip] = [t for t in _rl[ip] if now - t < 60]
    if len(_rl[ip]) >= RATE_LIMIT:
        return False
    _rl[ip].append(now)
    return True


# ─── APP ──────────────────────────────────────────────────────────────

app = FastAPI(title=f"{BOT['name']} API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["POST", "GET", "OPTIONS"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="static"), name="static")

llm = anthropic.Anthropic(api_key=API_KEY) if API_KEY else None


class ChatReq(BaseModel):
    messages: list[dict]
    language: str = "en"
    session_id: Optional[str] = None
    source: str = "widget"


class ChatRes(BaseModel):
    reply: str
    session_id: str


@app.on_event("startup")
async def startup():
    refresh_kb()
    print(f"🚀 {BOT['name']} started")


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "bot": BOT["name"],
        "api": bool(API_KEY),
        "sheets": get_gc() is not None,
        "kb_entries": _kb["text"].count("\n-"),
    }


@app.post("/chat", response_model=ChatRes)
async def chat(req: ChatReq, request: Request):
    ip = request.client.host if request.client else "x"
    if not rate_ok(ip):
        raise HTTPException(429, "Too many requests")
    if not llm:
        raise HTTPException(500, "API not configured")

    sid = req.session_id or uuid.uuid4().hex[:8]
    user_msg = req.messages[-1]["content"] if req.messages else ""

    try:
        resp = llm.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1024,
            system=build_system_prompt(req.language),
            messages=req.messages,
        )
        reply = resp.content[0].text
    except Exception as e:
        print(f"LLM error: {e}")
        raise HTTPException(502, "Chat unavailable")

    flagged = is_unknown(reply)
    log_local(sid, req.language, req.source, user_msg, reply, ip, flagged)

    if flagged:
        try:
            log_unanswered_sheet(req.language, req.source, user_msg, reply)
        except Exception:
            pass

    return ChatRes(reply=reply, session_id=sid)


@app.post("/kb/refresh")
async def force_refresh(p: str = Query(...)):
    if p != ADMIN_PASSWORD:
        raise HTTPException(403)
    _kb["ts"] = 0
    kb = refresh_kb()
    return {"ok": True, "entries": kb.count("\n-")}


@app.get("/config.js")
async def config_js():
    """Serve client config as JS for the frontend."""
    client_cfg = {
        "bot": BOT,
        "branding": BRAND,
        "languages": LANGUAGES,
        "welcome": WELCOME,
        "placeholders": PLACEHOLDERS,
        "disclaimer": DISCLAIMER,
        "landing_cta": CFG.get("landing_cta", {}),
        "agency_credit": CFG.get("agency_credit", ""),
        "website_url": CFG.get("website_url", ""),
        "website_label": CFG.get("website_label", ""),
    }
    js = f"window.__BOTCFG__ = {json.dumps(client_cfg, ensure_ascii=False)};"
    return HTMLResponse(content=js, media_type="application/javascript")


# ─── FRONTEND (served from templates/) ────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def index():
    return FileResponse("templates/index.html")


@app.get("/widget.js")
async def widget_js():
    return FileResponse("templates/widget.js", media_type="application/javascript")


# ─── ADMIN ────────────────────────────────────────────────────────────

def auth(p: str = Query(...)):
    if p != ADMIN_PASSWORD:
        raise HTTPException(403)
    return True


@app.get("/admin/api")
async def admin_api(_=Depends(auth), days: int = Query(7), flagged_only: bool = Query(False)):
    entries = []
    for lf in sorted(LOG_DIR.glob("chat-*.jsonl"), reverse=True)[:days]:
        for line in open(lf, encoding="utf-8"):
            try:
                e = json.loads(line)
                if flagged_only and not e.get("flagged"):
                    continue
                entries.append(e)
            except:
                pass
    return entries


@app.get("/admin", response_class=HTMLResponse)
async def admin(_=Depends(auth)):
    sheet_url = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}" if SHEET_ID else ""
    return ADMIN_HTML.replace("__SHEET_URL__", sheet_url).replace("__BOT_NAME__", BOT["name"])


# ─── ADMIN HTML ───────────────────────────────────────────────────────

ADMIN_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>__BOT_NAME__ Admin</title>
<link href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;700&display=swap" rel="stylesheet">
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:'DM Sans',sans-serif;background:#0a0a0a;color:#e8e8e8;min-height:100vh}
.hdr{background:#111;border-bottom:1px solid #222;padding:20px 32px;display:flex;align-items:center;gap:16px;position:sticky;top:0;z-index:10;flex-wrap:wrap}
.hdr h1{font-size:22px;color:#fdc300}.hdr .sub{color:#666;font-size:13px}
.hdr-actions{margin-left:auto;display:flex;gap:8px}
.hdr-actions a{background:#1a1a1a;border:1px solid #333;color:#fdc300;padding:8px 16px;border-radius:8px;text-decoration:none;font-size:13px}
.hdr-actions a:hover{background:#222}
.ctrl{padding:16px 32px;display:flex;gap:10px;flex-wrap:wrap;align-items:center}
.ctrl button,.ctrl select{background:#1a1a1a;border:1px solid #333;color:#ccc;padding:8px 14px;border-radius:8px;cursor:pointer;font:13px 'DM Sans',sans-serif}
.ctrl button:hover{background:#222}.ctrl button.on{background:#fdc300;color:#000;font-weight:700;border-color:#fdc300}
.stats{padding:0 32px 16px;display:flex;gap:14px;flex-wrap:wrap}
.sc{background:#111;border:1px solid #1a1a1a;border-radius:12px;padding:16px 24px;min-width:130px}
.sc .v{font-size:28px;font-weight:700;color:#fdc300}.sc .l{font-size:12px;color:#666;margin-top:4px}
.logs{padding:0 32px 32px}
.le{background:#111;border:1px solid #1a1a1a;border-radius:10px;padding:14px 18px;margin-bottom:6px;transition:.15s}
.le:hover{background:#151515}.le.fl{border-left:3px solid #e74c3c}
.lm{display:flex;gap:10px;flex-wrap:wrap;font-size:12px;color:#555;margin-bottom:6px}
.lm .fb{background:rgba(231,76,60,.12);color:#e74c3c;padding:2px 8px;border-radius:4px;font-weight:600}
.lq{color:#e8e8e8;margin-bottom:4px}.lq strong{color:#fdc300}
.la{color:#777;font-size:14px}
.empty{text-align:center;padding:60px;color:#444}
.sb{display:inline-block;padding:2px 8px;border-radius:4px;font-size:11px;font-weight:600}
.sw{background:rgba(52,152,219,.12);color:#3498db}
.st{background:rgba(46,204,113,.12);color:#2ecc71}
.sq{background:rgba(155,89,182,.12);color:#9b59b6}
.banner{margin:0 32px 16px;padding:12px 20px;background:rgba(46,204,113,.06);border:1px solid rgba(46,204,113,.15);border-radius:10px;font-size:13px;color:#2ecc71}
.banner a{color:#2ecc71;font-weight:700}
</style></head><body>
<div class="hdr"><div><h1>__BOT_NAME__ Admin</h1><div class="sub">White Rabbit AI Chatbot Dashboard</div></div>
<div class="hdr-actions"><a href="__SHEET_URL__" target="_blank" id="sl">📊 Google Sheet</a><a href="#" onclick="rkb()">🔄 Refresh KB</a></div></div>
<div class="banner" id="bn" style="display:none">📊 KB synced from <a href="__SHEET_URL__" target="_blank">Google Sheet</a>. Unanswered → "Unanswered" tab.</div>
<div class="ctrl">
<button onclick="ld(7)" class="on" id="b7">7d</button><button onclick="ld(30)" id="b30">30d</button><button onclick="ld(90)" id="b90">90d</button>
<button onclick="tf()" id="bf">⚠️ Flagged</button>
<select id="lf" onchange="af()"><option value="">All langs</option><option value="cs">🇨🇿</option><option value="en">🇬🇧</option><option value="de">🇩🇪</option><option value="es">🇪🇸</option><option value="fr">🇫🇷</option><option value="it">🇮🇹</option><option value="ja">🇯🇵</option><option value="ko">🇰🇷</option><option value="zh">🇨🇳</option></select>
<select id="sf" onchange="af()"><option value="">All sources</option><option value="widget">🌐 Web</option><option value="tablet">📱 iPad</option><option value="qr">📷 QR</option></select>
<button onclick="csv()">📥 CSV</button></div>
<div class="stats" id="ss"></div><div class="logs" id="ll"></div>
<script>
const P=new URLSearchParams(location.search).get('p');let D=[],fo=false;
const FL={cs:'🇨🇿',en:'🇬🇧',de:'🇩🇪',es:'🇪🇸',fr:'🇫🇷',it:'🇮🇹',ja:'🇯🇵',ko:'🇰🇷',zh:'🇨🇳',uk:'🇺🇦',pl:'🇵🇱'};
const SL={widget:'Web',tablet:'iPad',qr:'QR'},SC={widget:'sw',tablet:'st',qr:'sq'};
if(!document.getElementById('sl').href.includes('__SHEET'))document.getElementById('bn').style.display='block';
async function ld(d){document.querySelectorAll('.ctrl button[id^=b]').forEach(b=>b.classList.remove('on'));
let b=document.getElementById('b'+d);if(b)b.classList.add('on');
try{let r=await fetch('/admin/api?p='+encodeURIComponent(P)+'&days='+d);D=await r.json();af()}catch(e){document.getElementById('ll').innerHTML='<div class="empty">Error</div>'}}
function tf(){fo=!fo;document.getElementById('bf').classList.toggle('on',fo);af()}
function af(){let f=D,lv=document.getElementById('lf').value,sv=document.getElementById('sf').value;
if(fo)f=f.filter(e=>e.flagged);if(lv)f=f.filter(e=>e.lang===lv);if(sv)f=f.filter(e=>e.src===sv);rs(f);rl(f)}
function rs(d){let t=d.length,fl=d.filter(e=>e.flagged).length,ss=new Set(d.map(e=>e.sid)).size,ls={};
d.forEach(e=>{ls[e.lang]=(ls[e.lang]||0)+1});let tl=Object.entries(ls).sort((a,b)=>b[1]-a[1])[0];
document.getElementById('ss').innerHTML=`<div class="sc"><div class="v">${t}</div><div class="l">Messages</div></div><div class="sc"><div class="v">${ss}</div><div class="l">Sessions</div></div><div class="sc"><div class="v" style="color:#e74c3c">${fl}</div><div class="l">⚠️ Gaps</div></div><div class="sc"><div class="v">${tl?FL[tl[0]]||tl[0]:'—'}</div><div class="l">Top lang${tl?' ('+tl[1]+')':''}</div></div>`}
function rl(d){if(!d.length){document.getElementById('ll').innerHTML='<div class="empty">No data</div>';return}
let s=[...d].sort((a,b)=>b.ts.localeCompare(a.ts));
document.getElementById('ll').innerHTML=s.map(e=>{let t=new Date(e.ts).toLocaleString(),f=e.flagged?'<span class="fb">⚠️ GAP</span>':'',
src='<span class="sb '+( SC[e.src]||'')+'">'+( SL[e.src]||e.src)+'</span>';
return'<div class="le'+(e.flagged?' fl':'')+'"><div class="lm"><span>'+t+'</span><span>'+(FL[e.lang]||'')+' '+e.lang+'</span>'+src+f+'</div><div class="lq"><strong>Q:</strong> '+eh(e.q)+'</div><div class="la"><strong>A:</strong> '+eh(e.a)+'</div></div>'}).join('')}
function eh(s){let d=document.createElement('div');d.textContent=s||'';return d.innerHTML}
function csv(){let r=[['ts','session','lang','source','flagged','question','answer']];
D.forEach(e=>r.push([e.ts,e.sid,e.lang,e.src,e.flagged?'YES':'','"'+(e.q||'').replace(/"/g,'""')+'"','"'+(e.a||'').replace(/"/g,'""')+'"']));
let b=new Blob([r.map(r=>r.join(',')).join('\\n')],{type:'text/csv'}),a=document.createElement('a');a.href=URL.createObjectURL(b);a.download='chatbot-logs.csv';a.click()}
async function rkb(){try{let r=await fetch('/kb/refresh?p='+encodeURIComponent(P),{method:'POST'});let d=await r.json();alert('KB refreshed! '+d.entries+' entries.')}catch(e){alert('Failed: '+e)}}
ld(7);
</script></body></html>"""


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
