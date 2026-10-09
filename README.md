# SockBoi's Payload — Discord Bot

Automate bot for SockBoi's Payload (TH/EN): token/webhook/nitro protection, link + APK filter,
anti-spam, anti-raid slowmode, verification gate + self-role buttons, welcome DM, logging to `#🚨・bot-logs`.

## Verification policy
- New members receive `Unverified` and can view only `#👋・welcome` and `#✅・verify`; all other categories/channels are hidden until verification. The bot enforces channel/category permission overwrites on startup and when new channels are created.
- Unverified members cannot send messages anywhere (the bot also removes messages as a fallback if channel permissions are misconfigured).
- Pressing the Verify button removes `Unverified` and grants `Member`.
- New members can press Verify after a 1-minute anti-raid grace period; the 1-hour kick deadline remains unchanged.
- Members who still have `Unverified` one hour after joining are kicked. Deadlines are saved in `sockboi_bot_data.json` and checked by the bot worker.
- Railway note: attach a persistent volume if you need verification deadlines/offense data to survive container replacement/redeploy. Without persistent storage, deadlines survive ordinary process restarts only while that filesystem remains intact.

## Run locally
```
pip install -r requirements.txt
copy .env.example .env   # then fill DISCORD_BOT_TOKEN + GUILD_ID
python sockboi_bot.py
```

## Deploy (Railway)
1. New Project → Deploy from GitHub (this repo)
2. Variables: `DISCORD_BOT_TOKEN`, `GUILD_ID=1555677417518137354`, `OWN_DOMAINS=`
3. Start command: `python sockboi_bot.py`

## One-time server setup
```
python setup_server.py     # roles + channels + topics
python update_thai_final.py  # TH migration + pins + forms
```

Admin in Discord: `!status` `!setup_verify` `!setup_roles` `!pinall`
