# SockBoi's Payload — Discord Bot

Automate bot for SockBoi's Payload (TH/EN): token/webhook/nitro protection, link + APK filter,
anti-spam, anti-raid slowmode, verify + self-role buttons, welcome DM, logging to `#🚨・bot-logs`.

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
