"""One-time TH migration: dedupe welcome/rules, post bilingual msgs + forms, update nitro automod."""
import os, sys
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="ignore")
    sys.stderr.reconfigure(encoding="utf-8", errors="ignore")
except Exception:
    pass
import discord
from dotenv import load_dotenv
from datetime import timedelta
load_dotenv()
TOKEN = os.getenv("DISCORD_BOT_TOKEN")
GUILD_ID = int(os.getenv("GUILD_ID", "0"))
assert TOKEN and GUILD_ID

NITRO = r"fre+\s*nitr[o0]"
THAI_NITRO = r"ฟรี.*ไนโตร|ไนโตร.*ฟรี|แจก.*ไนโตร|แจก.*nitro|ฟรี.*nitro"

WELCOME_TITLE = "👾 ยินดีต้อนรับสู่ SockBoi's Payload | Welcome"
WELCOME_DESC = (
    "นี่คือห้องแล็บม็อดส่วนตัวของ SockBoi\n"
    "This is SockBoi's personal modding lab.\n"
    "ม็อดลงที่นี่ สคริปต์ลงที่นี่ อะไรที่รันบน Android ทั้งที่เขาไม่ให้ทำ — มันเริ่มที่นี่\n\n"
    "✅ ยืนยันตัวตนที่ #✅・verify เพื่อปลดล็อกห้องดาวน์โหลด\n"
    "📦 ม็อดที่ #📱・mod-releases\n"
    "💉 สคริปต์ที่ #📜・script-releases\n"
    "🛡️ เช็ก #🛡️・detection-log ก่อนเอาไปเล่นแรงก์ทุกครั้ง\n\n"
    "พูดไทยได้ พิมพ์ไทยได้ ขอแค่สุภาพ | Thai & English welcome.\n"
    "อย่าแชร์ token อย่าดูดของไปปล่อยข้างนอก\n"
    "Stay clean. Don't share tokens. Don't leak drops.\n— SockBoi"
)
RULES_MSG = (
    "**📜 กฎเซิร์ฟเวอร์ / Server Rules**\n\n"
    "**1. ห้ามแชร์ token / webhook** — ลบ + mute ทันที | No token sharing = instant mute.\n"
    "**2. ห้ามดูดของไปปล่อยข้างนอก** — เจอ = แบน | No leaks outside.\n"
    "**3. เช็ก #🛡️・detection-log ก่อนเล่นแรงก์ทุกครั้ง** | Check detection before ranked.\n"
    "**4. ห้ามสแปม / ส่งซ้ำ / แท็กมั่ว** | No spam / duplicates / mass mentions.\n"
    "**5. ส่งลิงก์ได้เฉพาะ Verified Modder+ ใน #💬・general / #❓・help; ลิงก์ APK ลงได้แค่ #📱・mod-releases โดย Core Dev+**\n"
    "**6. ถามใน #❓・help ให้ระบุ: ชื่อเกม / เวอร์ชัน / root? / รูป error + log** | Game, version, root?, error log.\n"
    "**7. พูดไทยหรืออังกฤษก็ได้ ขอแค่สุภาพ** | Thai & English welcome, be respectful.\n"
    "โดนบอทเข้าใจผิด ติดต่อ SockBoi | False positive? Contact SockBoi."
)
VERIFY_MSG = (
    "**✅ ยืนยันตัวตน / Verify**\n\n"
    "กด ✅ ด้านล่างเพื่อรับยศ Member + ปลดล็อกห้องม็อด\n"
    "Press ✅ below to get Member + unlock drops.\n\n"
    "แอคใหม่ < 7 วัน รอตรวจสอบก่อนนะ\n"
    "New accounts (< 7 days) need manual review."
)
REQUEST_FORM = (
    "**📥 ฟอร์มขอม็อด / Mod Request Form (ก็อปไปใช้)**\n\n"
    "🎮 ชื่อเกม / Game:\n🔢 เวอร์ชัน / Version + code:\n📱 Root? (Y/N + Magisk/KernelSU):\n"
    "🛡️ กันโกง / Anti-cheat:\n✨ อยากได้อะไร / Features:\n📸 รูป error (ถ้ามี):"
)
BAN_FORM = (
    "**⚠️ ฟอร์มแจ้งแบน / Ban Report (ก็อปไปใช้)**\n\n"
    "📦 บิลด์ที่ใช้ / Build:\n🎮 เกม + เวอร์ชัน / Game + version:\n"
    "⏱️ เล่นกี่วันถึงโดน / Days until ban:\n🚫 แบนแบบไหน / Ban type:\n📸 หลักฐาน / Screenshot:"
)

intents = discord.Intents.default()
intents.members = True
intents.message_content = True
client = discord.Client(intents=intents)

async def purge_bot_msgs(ch):
    me = client.user
    deleted = 0
    async for m in ch.history(limit=50):
        if m.author == me:
            try:
                await m.delete()
                deleted += 1
            except Exception as e:
                print(f"delete failed in {ch.name}: {e}")
    print(f"purged {deleted} bot msgs in {ch.name}")
    return deleted

@client.event
async def on_ready():
    try:
        guild = client.get_guild(GUILD_ID) or await client.fetch_guild(GUILD_ID)
        print(f"Guild: {guild.name}")
        # 1. server-guide: purge + fresh welcome
        guide = discord.utils.get(guild.text_channels, name="🗺️・server-guide")
        if guide:
            await purge_bot_msgs(guide)
            await guide.send(embed=discord.Embed(title=WELCOME_TITLE, description=WELCOME_DESC, color=0x0A0A0A))
            print("welcome TH posted (pin it, delete old pins)")
        # 2. rules: purge + fresh bilingual
        rules = discord.utils.get(guild.text_channels, name="📜・rules")
        if rules:
            await purge_bot_msgs(rules)
            await rules.send(RULES_MSG)
            print("rules TH posted")
        # 3. verify form (only if no bot msg)
        verify = discord.utils.get(guild.text_channels, name="✅・verify")
        if verify:
            has = False
            async for m in verify.history(limit=20):
                if m.author == client.user and "ยืนยันตัวตน" in (m.content or ""):
                    has = True
                    break
            if not has:
                await verify.send(VERIFY_MSG)
                print("verify TH posted")
            else:
                print("verify TH already present")
        # 4. request-mods form
        req = discord.utils.get(guild.text_channels, name="📥・request-mods")
        if req:
            has = False
            async for m in req.history(limit=20):
                if m.author == client.user and "ฟอร์มขอม็อด" in (m.content or ""):
                    has = True
                    break
            if not has:
                await req.send(REQUEST_FORM)
                print("request form posted")
        # 5. ban-reports form
        ban = discord.utils.get(guild.text_channels, name="⚠️・ban-reports")
        if ban:
            has = False
            async for m in ban.history(limit=20):
                if m.author == client.user and "ฟอร์มแจ้งแบน" in (m.content or ""):
                    has = True
                    break
            if not has:
                await ban.send(BAN_FORM)
                print("ban form posted")
        # 6. update nitro automod to include Thai
        try:
            rules_list = await guild.fetch_automod_rules()
            old = next((r for r in rules_list if r.name == "Block free nitro scam"), None)
            if old:
                patterns = list(getattr(old.trigger, "regex_patterns", []) or [])
                print(f"old nitro patterns: {patterns}")
                if THAI_NITRO not in patterns:
                    await old.delete(reason="SockBoi TH update")
                    print("old nitro rule deleted, recreating with TH...")
                    bot_logs = discord.utils.get(guild.text_channels, name="🚨・bot-logs")
                    actions = [discord.AutoModRuleAction(type=discord.AutoModRuleActionType.block_message),
                               discord.AutoModRuleAction(type=discord.AutoModRuleActionType.timeout, duration=timedelta(seconds=600))]
                    if bot_logs:
                        actions.append(discord.AutoModRuleAction(type=discord.AutoModRuleActionType.send_alert_message, channel_id=bot_logs.id))
                    await guild.create_automod_rule(
                        name="Block free nitro scam",
                        event_type=discord.AutoModRuleEventType.message_send,
                        trigger=discord.AutoModTrigger(type=discord.AutoModRuleTriggerType.keyword, regex_patterns=[NITRO, THAI_NITRO]),
                        actions=actions, enabled=True, reason="SockBoi TH update")
                    print("nitro TH rule created")
                else:
                    print("nitro TH already present")
            else:
                print("no old nitro rule found")
        except Exception as e:
            print(f"nitro update failed: {e}")
        print("TH MIGRATION DONE")
    finally:
        await client.close()

client.run(TOKEN)
