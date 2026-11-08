import os, sys, discord
from dotenv import load_dotenv
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="ignore")
except Exception:
    pass
load_dotenv()
TOKEN = os.getenv("DISCORD_BOT_TOKEN")
GID = int(os.getenv("GUILD_ID"))
BODY = """Bypass CookieRun Classic
v26.10.02 (arm64-v8a)
Base: libfilepacker.so

[Detection]
[0x00913EC8]
01 60 00 39 -> 1F 20 03 D5
[0x00937460]
FD 7B BB A9 F9 0B 00 F9 -> 00 00 80 52 C0 03 5F D6

🛡️ เช็ก #detection-log ก่อนเล่นแรงก์ | อย่าดูดไปปล่อยข้างนอก
— SockBoi"""
intents = discord.Intents.default()
intents.members = True
c = discord.Client(intents=intents)
@c.event
async def on_ready():
    try:
        g = c.get_guild(GID) or await c.fetch_guild(GID)
        forums = [ch for ch in g.channels if isinstance(ch, discord.ForumChannel)]
        f = next((ch for ch in forums if ch.name == "🎁・giveaways"), None)
        if not f:
            raise RuntimeError("giveaways forum not found")
        atags = [t for t in f.available_tags if t.name in ("🆕 New", "🔧 Bypass")]
        res = await f.create_thread(
            name="Bypass CookieRun Classic v26.10.02 - SockBoi",
            content=BODY,
            applied_tags=atags,
            reason="drop v26.10.02",
        )
        th = res.thread if hasattr(res, "thread") else res
        print(f"created: {th.name} ({th.id})")
    finally:
        await c.close()
c.run(TOKEN)
