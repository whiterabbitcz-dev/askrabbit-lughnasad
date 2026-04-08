# White Rabbit AI Chatbot Template

Universal AI chatbot template by **White Rabbit** agency.  
One codebase, unlimited clients. First deployment: **Czech Beer Museum Prague**.

## Architecture

```
┌─ config.json ──────────┐     ┌─ Google Sheet ───────────┐
│ Branding, colors, fonts │     │ "Knowledge Base" tab     │
│ Languages, welcome msgs │     │ "Unanswered" tab         │
│ System prompt template  │     │ (auto-populated by bot)  │
└────────────┬────────────┘     └──────────┬───────────────┘
             │                             │
             ▼                             ▼
    ┌─────────────────────────────────────────┐
    │          server.py (FastAPI)             │
    │  • /chat — Claude API proxy + logging   │
    │  • /config.js — serves branding to FE   │
    │  • / — fullscreen chat (QR + iPad)      │
    │  • /widget.js — WP embed script         │
    │  • /admin — dashboard + stats           │
    └─────────────────────────────────────────┘
         ▲           ▲           ▲
    iPad kiosk    QR→mobile   WP widget
```

## New Client Deployment (15 min)

1. Fork/copy this repo
2. Replace `config.json` (branding, texts, system prompt)
3. Replace `static/img/logo.png`
4. Create Google Sheet + Service Account (see SETUP below)
5. Deploy to Railway with client's env vars
6. Add `<script src="https://bot-url.com/widget.js"></script>` to client's website

**That's it.** No code changes needed between clients.

## File Structure

```
├── server.py              # Backend (universal, don't change per client)
├── config.json            # ← CLIENT CONFIG — change this per client
├── requirements.txt
├── Dockerfile
├── .gitignore
├── static/
│   └── img/
│       └── logo.png       # ← CLIENT LOGO
└── templates/
    ├── index.html          # Frontend (reads config from /config.js)
    └── widget.js           # WordPress embed (auto-detects bot URL)
```

## Setup

### 1. Google Service Account (one-time, 5 min)

1. Go to https://console.cloud.google.com
2. Create project → Enable **Google Sheets API** + **Google Drive API**
3. Create **Service Account** → download JSON key
4. Share your Google Sheet with the service account email (as Editor)

### 2. Google Sheet

Create a sheet with two tabs:

**Tab "Knowledge Base"** (columns A + B):
| kategorie | obsah |
|---|---|
| Základní info | Address: ... |
| Vstupenky | Museum + Tasting: 390 CZK ... |
| Doprava | Metro Staroměstská — 3 min ... |

**Tab "Unanswered"** — created automatically by bot on first unanswered question.

### 3. Deploy to Railway

```bash
# Push to GitHub, then on railway.app:
# New Project → Deploy from GitHub → Add variables:
```

| Variable | Value |
|---|---|
| `ANTHROPIC_API_KEY` | `sk-ant-...` |
| `GOOGLE_SHEET_ID` | Sheet ID from URL |
| `GOOGLE_SA_JSON_CONTENT` | Entire JSON key file content |
| `ADMIN_PASSWORD` | Your admin password |

### 4. WordPress Integration

Add one line to your client's website footer:

```html
<script src="https://your-bot-url.railway.app/widget.js"></script>
```

Done. The widget auto-loads branding from the bot's config.

## URLs

| URL | What |
|---|---|
| `/` | Fullscreen chat (for QR codes + iPad kiosk) |
| `/widget.js` | WordPress/website embed script |
| `/admin?p=PASSWORD` | Admin dashboard with logs + stats |
| `/health` | Health check (API + Sheets status) |
| `/kb/refresh?p=PASSWORD` | Force KB refresh from Sheet |
| `/config.js` | Client config as JS (used by frontend) |

## Costs

| Service | Cost |
|---|---|
| Claude API (Sonnet) | ~$0.003–0.01/message → $2–5/mo at 200 msgs/day |
| Google Sheets API | Free |
| Google Cloud (SA) | Free |
| Railway | Starter free / $5/mo production |
