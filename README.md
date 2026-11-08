# SockBoi's Payload — Discord Bot

Automation bot for SockBoi's Payload (TH/EN): token/webhook/nitro protection, link + APK filter, anti-spam, anti-raid slowmode, verification gate + self-role buttons, welcome DM, logging, and optional voice greeting.

## Cloud deployment (Northflank)

This is a persistent Discord Gateway worker, not a request-driven web API. The repository includes Docker health endpoints, graceful shutdown, and persistent JSON state support.

**Deployment guide:** [RUN-24-7.md](RUN-24-7.md)

Recommended settings:
- Deployment Service from this GitHub repository, Dockerfile build
- One replica only
- Secrets: `DISCORD_BOT_TOKEN`, `GUILD_ID`
- Persistent Volume mounted at `/data`; set `DATA_DIR=/data`
- Liveness HTTP probe: port `8080`, path `/livez`
- Optional readiness probe: port `8080`, path `/readyz`
- Enable Northflank Continuous Deployment for the selected branch

GitHub Actions at `.github/workflows/ci.yml` runs compile checks, unit tests, and Docker build. Northflank Git integration performs the actual deployment after a push.

## Fly.io deployment

The repo includes `fly.toml` and [FLY-IO.md](FLY-IO.md). In short:
1. `fly apps create sockboi-payload-discord`
2. `fly volumes create sockboi_data --region sin --size 1`
3. `fly secrets set DISCORD_BOT_TOKEN=... GUILD_ID=1555677417518137354`
4. `fly deploy`

`auto_stop_machines` is **off** — the Discord Gateway must stay connected.

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
