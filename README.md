# SockBoi's Payload — Discord Bot

Automation bot for SockBoi's Payload (TH/EN): token/webhook/nitro protection, link + APK filter, anti-spam, anti-raid slowmode, verification gate + self-role buttons, welcome DM, logging, and optional voice greeting.

## Deploy on Railway

The repo re-includes `Dockerfile`, `railway.toml` and `.dockerignore` for Railway.

1. Railway → New Project → Deploy from GitHub → เลือก repo นี้
2. Variables (หรือ Secrets):
   - `DISCORD_BOT_TOKEN` = token ใหม่
   - `GUILD_ID` = `1555677417518137354`
   - `OWN_DOMAINS` = `facebook.com,fb.com,youtube.com,youtu.be,telegram.me,t.me,github.com,mediafire.com,earnpaste.com,linkvertise.com,link-target.net`
   - `WELCOME_VOICE` = `1`
   - `PORT` = `8080`
   - `DATA_DIR` = `/data`
3. Settings → Networking → ไม่ต้องเปิด public port (bot เป็น worker) — Railway ใช้ health check ภายในที่ `/livez`
4. ถ้าใช้ Persistent Volume: แนะนำสร้าง volume แล้ว mount ที่ `/data` (state จะอยู่ถาวร)
5. Deploy → ดู Logs: ต้องเห็น `Logged in as ... automate ON`

GitHub Actions ที่ `.github/workflows/ci.yml` (ถ้ามี) จะรัน CI; Railway Git integration จะ redeploy จาก branch `main` หลัง push.

อย่าใส่ token ใน Git — ใช้ Railway Variables เท่านั้น.

## Run locally (24/7 on this PC)

The bot runs as a persistent Discord Gateway worker. To keep it online, just leave `python sockboi_bot.py` running.

**Windows — start-on-boot (recommended):** create Task Scheduler entry that runs at logon:

- Program: `pythonw.exe` (or full path to your Python)
- Arguments: `sockboi_bot.py`
- Start in: this folder
- Trigger: At log on

**Manual run:**
```cmd
cd "C:\Users\SockBoi\Downloads\SockBoi Ai\sockboi-payload-discord"
python sockboi_bot.py
```

Hardware notes: bot uses ~150–250 MB RAM, almost no CPU. RAM/disk it needs is trivial; a mid-range PC is plenty.

Requirements: Windows Task Scheduler handles restarts automatically; no Docker/cloud required.

## Verification policy
- New members receive `Unverified` and can view only `#👋・welcome` and `#✅・verify`.
- Unverified members cannot send messages; the bot also removes messages as a fallback.
- Verify removes `Unverified` and grants `Member` after the one-minute anti-raid grace period.
- Unverified members receive one bilingual reminder after 30 minutes and are kicked after one hour.
- Verification deadlines and offense counters are persisted under `DATA_DIR`.

## Run locally
```bash
python -m venv .venv
pip install -r requirements.txt
cp .env.example .env
# Set DISCORD_BOT_TOKEN and GUILD_ID in .env
python sockboi_bot.py
```

## One-time server setup
```bash
python setup_server.py
python update_thai_final.py
```
Admin commands: `!status`, `!diag`, `!setup_verify`, `!setup_roles`, `!pinall`.
