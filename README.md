# SockBoi's Payload — Discord Bot

Automation bot for SockBoi's Payload (TH/EN): token/webhook/nitro protection, link + APK filter, anti-spam, anti-raid slowmode, verification gate + self-role buttons, welcome DM, logging, and optional voice greeting.

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
