import os, discord
from dotenv import load_dotenv
load_dotenv()
TOKEN = os.getenv("DISCORD_BOT_TOKEN")
GID = int(os.getenv("GUILD_ID"))
intents = discord.Intents.default()
intents.members = True
intents.message_content = True
c = discord.Client(intents=intents)

@c.event
async def on_ready():
    try:
        g = c.get_guild(GID) or await c.fetch_guild(GID)
        print(f"GUILD: {g.name} ({g.id}) members={g.member_count}")
        print("=== CATEGORIES + CHANNELS ===")
        for cat in sorted(g.categories, key=lambda x: x.position):
            print(f"CAT: {cat.name}")
            for ch in sorted(cat.channels, key=lambda x: x.position):
                t = getattr(ch, "topic", None) or ""
                print(f"  {type(ch).__name__:10} {ch.name} | id={ch.id}" + (f" | topic={t}" if t else ""))
        no_cat = [ch for ch in g.channels if ch.category is None]
        if no_cat:
            print("NO CATEGORY")
            for ch in no_cat:
                print(f"  {type(ch).__name__:10} {ch.name} | id={ch.id}")
        print("=== PINS + ACTIVITY ===")
        for ch in sorted(g.text_channels, key=lambda x: (x.category.name if x.category else "", x.position)):
            try:
                pins = []
                async for p in ch.pins():
                    pins.append(p)
                last = None
                total = 0
                async for m in ch.history(limit=20):
                    total += 1
                    last = m
                ld = last.created_at.strftime("%Y-%m-%d") if last else "-"
                print(f"{ch.name} | pins={len(pins)} | recent_n={total} | last={ld}")
            except Exception as e:
                print(f"{ch.name} | ERROR {type(e).__name__}: {e}")
        print("=== FORUM/VOICE ===")
        for ch in g.channels:
            if isinstance(ch, discord.ForumChannel):
                print(f"forum {ch.name} threads={len(ch.threads)}")
            elif isinstance(ch, discord.VoiceChannel):
                print(f"voice {ch.name} members={len(ch.members)}")
    finally:
        await c.close()

c.run(TOKEN)
