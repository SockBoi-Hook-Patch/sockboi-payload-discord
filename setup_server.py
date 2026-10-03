"""
SockBoi's Payload - auto setup script
Run: pip install -r requirements.txt ; python setup_server.py
Needs: BOT with Administrator invited to the (empty) guild, intents ON.
What it does: creates roles, categories, channels, permission overwrites,
verification level, automod rules (token/webhook/nitro/links/spam).
Bots like Wick/Carl/MEE6/Ticket Tool still need 1-click invite + paste config
from wick-carl-config.md (Discord template cannot carry bots/automod).
"""
import os, asyncio, sys
import discord
from discord import PermissionOverwrite
from dotenv import load_dotenv
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="ignore")
    sys.stderr.reconfigure(encoding="utf-8", errors="ignore")
except Exception:
    pass

load_dotenv()
TOKEN = os.getenv("DISCORD_BOT_TOKEN")
GUILD_ID = int(os.getenv("GUILD_ID", "0"))
OWNER_USER_ID = int(os.getenv("OWNER_USER_ID", "0") or 0)

# ---------- SPEC ----------
ROLES_SPEC = [
    # name, color, hoist, mentionable, perms
    ("SockBoi", discord.Color.gold(), True, True, discord.Permissions(administrator=True)),
    ("Core Dev", discord.Color.red(), True, False, discord.Permissions(manage_messages=True, manage_channels=True, attach_files=True, embed_links=True, connect=True, speak=True)),
    ("Verified Modder", discord.Color.orange(), True, False, discord.Permissions(attach_files=True, embed_links=True, add_reactions=True)),
    ("Script Tester", discord.Color.gold(), True, False, discord.Permissions(attach_files=True, embed_links=True, add_reactions=True)),
    ("Member", discord.Color.green(), False, False, discord.Permissions(send_messages=True, read_messages=True, attach_files=True, embed_links=True, add_reactions=True, connect=True, speak=True)),
    ("Unverified", discord.Color.light_grey(), False, False, discord.Permissions(read_messages=True, read_message_history=True)),
]

CATEGORIES = {
    "📌 INFORMATION": [
        ("📜・rules", "กฎเซิร์ฟเวอร์ / Server rules — อ่านก่อนแชท | Read before chatting"),
        ("📣・announcements", "ประกาศสำคัญจาก SockBoi / Major drops — SockBoi only"),
        ("🗺️・server-guide", "วิธีใช้งานเซิร์ฟเวอร์ / How to navigate + ยศ + หาม็อดที่ไหน"),
        ("🔄・changelogs", "ประวัติเวอร์ชันม็อด/สคริปต์ / Version history"),
    ],
    "🎭 VERIFICATION & ROLES": [
        ("✅・verify", "ยืนยันตัวตนเพื่อปลดล็อกห้อง / Verify to unlock drops"),
        ("🎖️・role-select", "เลือกยศเอง: เกม / แพลตฟอร์ม / Self-assign roles"),
    ],
    "💬 COMMUNITY": [
        ("💬・general", "คุยทั่วไป (ไทย/Eng) / Main chat"),
        ("🧠・dev-talk", "คุยเทคนิค: RE / Frida / smali"),
        ("❓・help", "ถาม-ตอบปัญหาม็อด/สคริปต์ / Ask for help"),
        ("📸・showcase", "โชว์ผลงาน รูป/คลิป / Show results, screenshots, PoC"),
        ("🗳️・suggestions", "ขอฟีเจอร์/ขอม็อด / Feature & mod requests"),
    ],
    "📦 DROPS — ANDROID MODS": [
        ("📱・mod-releases", "ม็อด APK ตัวเต็ม ลงโดย SockBoi เท่านั้น / Full APK mods"),
        ("🔧・patch-notes", "แก้/บายพาสอะไรไปบ้าง / What was changed & bypassed"),
        ("📥・request-mods", "ขอม็อดเกม (ตามฟอร์ม) / Request a game mod"),
    ],
    "💉 DROPS — SCRIPTS": [
        ("📜・script-releases", "Frida / Xposed / Magisk modules"),
        ("🐍・python-tools", "เครื่องมือฝั่ง PC สำหรับแกะ APK / PC tooling"),
        ("📂・resource-dump", "สมาลี/offset/memory map / Smali snippets & offsets"),
    ],
    "🔒 SECURITY / ANTI-CHEAT WATCH": [
        ("🛡️・detection-log", "ม็อดไหนโดนจับแล้ว เช็กก่อนเล่นแรงก์ / Detection status"),
        ("⚠️・ban-reports", "แจ้งโดนแบน: ระบุบิลด์+เวอร์ชัน / Ban reports"),
    ],
    "🔐 PRIVATE / STAFF": [
        ("👑・sockboi-only", "ห้องส่วนตัว SockBoi / Owner private"),
        ("🛠️・mod-workshop", "ห้องทำบิลด์ทีมงาน/tester / Staff build channel"),
        ("🚨・bot-logs", "log บอท คนเข้า สแปม / Bot logs & alerts"),
    ],
}

# Who can VIEW each category (None = everyone verified+). Staff-only handled separately.
STAFF_ONLY = {"🔐 PRIVATE / STAFF"}
READONLY_DROPS = {"📱・mod-releases", "📜・script-releases", "📣・announcements", "🔄・changelogs", "🔧・patch-notes", "🛡️・detection-log"}

WELCOME_EMBED = {
    "title": "👾 ยินดีต้อนรับสู่ SockBoi's Payload | Welcome",
    "description": (
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
    ),
    "color": 0x0A0A0A,
}

TOKEN_REGEX = r"[MN][A-Za-z\d]{23}\.[\w-]{6}\.[\w-]{27}"
NITRO_REGEX = r"fre+\s*nitr[o0]"
THAI_NITRO_REGEX = r"ฟรี.*ไนโตร|ไนโตร.*ฟรี|แจก.*ไนโตร|แจก.*nitro|ฟรี.*nitro"
WEBHOOK_REGEX = r"discord\.com/api/webhooks/\d+/[\w-]+"

intents = discord.Intents.default()
intents.members = True
intents.message_content = True
client = discord.Client(intents=intents)

async def get_or_create_role(guild, name, color, hoist, mentionable, perms):
    r = discord.utils.get(guild.roles, name=name)
    if r:
        print(f"role exists: {name}")
        return r
    r = await guild.create_role(name=name, colour=color, hoist=hoist, mentionable=mentionable, permissions=perms, reason="SockBoi setup")
    print(f"role created: {name}")
    return r

async def setup(guild: discord.Guild):
    print(f"Guild: {guild.name} ({guild.id})")
    roles = {}
    for name, color, hoist, mentionable, perms in ROLES_SPEC:
        roles[name] = await get_or_create_role(guild, name, color, hoist, mentionable, perms)

    unverified = roles["Unverified"]
    member = roles["Member"]
    core = roles["Core Dev"]
    owner_role = roles["SockBoi"]
    everyone = guild.default_role

    # Assign SockBoi role to owner user ID
    if OWNER_USER_ID:
        try:
            owner_member = guild.get_member(OWNER_USER_ID) or await guild.fetch_member(OWNER_USER_ID)
            if owner_member:
                await owner_member.add_roles(owner_role, reason="SockBoi setup - owner")
                print(f"assigned SockBoi role to {owner_member} ({OWNER_USER_ID})")
            else:
                print(f"owner {OWNER_USER_ID} not found in guild (must join server first)")
        except Exception as e:
            print(f"assign owner role failed: {e}")

    # Verification level: medium (verified email) + explicit content filter all
    try:
        await guild.edit(verification_level=discord.VerificationLevel.medium, explicit_content_filter=discord.ContentFilter.all_members, reason="SockBoi setup")
        print("verification level set: medium + explicit filter all")
    except Exception as e:
        print(f"guild.edit failed: {e}")

    for cat_name, channels in CATEGORIES.items():
        cat = discord.utils.get(guild.categories, name=cat_name)
        if not cat:
            overwrites = {}
            if cat_name in STAFF_ONLY:
                # hide from everyone, allow Core Dev + owner role
                overwrites[everyone] = PermissionOverwrite(view_channel=False)
                overwrites[unverified] = PermissionOverwrite(view_channel=False)
                overwrites[member] = PermissionOverwrite(view_channel=False)
                overwrites[core] = PermissionOverwrite(view_channel=True, send_messages=True, read_messages=True)
                overwrites[owner_role] = PermissionOverwrite(view_channel=True, send_messages=True, read_messages=True)
            else:
                # Unverified can only see INFORMATION + VERIFICATION
                if cat_name not in ("📌 INFORMATION", "🎭 VERIFICATION & ROLES"):
                    overwrites[unverified] = PermissionOverwrite(view_channel=False)
            cat_kwargs = dict(reason="SockBoi setup")
            if overwrites:
                cat_kwargs["overwrites"] = overwrites
            cat = await guild.create_category(cat_name, **cat_kwargs)
            print(f"category created: {cat_name}")
        else:
            print(f"category exists: {cat_name}")

        for ch_name, topic in channels:
            existing = discord.utils.get(guild.text_channels, name=ch_name)
            if existing:
                print(f"  channel exists: {ch_name}")
                ch = existing
                try:
                    if (ch.topic or "") != topic:
                        await ch.edit(topic=topic, reason="SockBoi setup - TH update")
                        print(f"  topic updated: {ch_name}")
                except Exception as e:
                    print(f"  topic update failed {ch_name}: {e}")
            else:
                overwrites = None
                if ch_name in ("👑・sockboi-only",):
                    overwrites = {
                        everyone: PermissionOverwrite(view_channel=False),
                        unverified: PermissionOverwrite(view_channel=False),
                        member: PermissionOverwrite(view_channel=False),
                        core: PermissionOverwrite(view_channel=False),
                        owner_role: PermissionOverwrite(view_channel=True, send_messages=True, read_messages=True),
                    }
                elif ch_name in ("🛠️・mod-workshop", "🚨・bot-logs"):
                    overwrites = {
                        everyone: PermissionOverwrite(view_channel=False),
                        unverified: PermissionOverwrite(view_channel=False),
                        member: PermissionOverwrite(view_channel=False),
                        core: PermissionOverwrite(view_channel=True, send_messages=True, read_messages=True),
                        owner_role: PermissionOverwrite(view_channel=True, send_messages=True, read_messages=True),
                    }
                elif ch_name in READONLY_DROPS:
                    overwrites = {
                        everyone: PermissionOverwrite(send_messages=False),
                        unverified: PermissionOverwrite(view_channel=False) if cat_name not in ("📌 INFORMATION",) else PermissionOverwrite(send_messages=False),
                        core: PermissionOverwrite(view_channel=True, send_messages=True, read_messages=True),
                        owner_role: PermissionOverwrite(view_channel=True, send_messages=True, read_messages=True),
                    }
                ch_kwargs = dict(category=cat, topic=topic, reason="SockBoi setup", slowmode_delay=0)
                if overwrites:
                    ch_kwargs["overwrites"] = overwrites
                ch = await guild.create_text_channel(ch_name, **ch_kwargs)
                print(f"  channel created: {ch_name}")

            # slowmode for general to allow raid-mode toggling later
            if ch_name == "💬・general":
                try:
                    await ch.edit(slowmode_delay=0)
                except Exception:
                    pass

    # Post welcome embed to server-guide
    guide = discord.utils.get(guild.text_channels, name="🗺️・server-guide")
    if guide:
        em = discord.Embed(title=WELCOME_EMBED["title"], description=WELCOME_EMBED["description"], color=WELCOME_EMBED["color"])
        try:
            await guide.send(embed=em)
            print("welcome embed posted to server-guide (pin it manually)")
        except Exception as e:
            print(f"welcome post failed: {e}")

    # Post rules skeleton if empty
    rules = discord.utils.get(guild.text_channels, name="📜・rules")
    if rules:
        try:
            hist = [m async for m in rules.history(limit=1)]
            if not hist:
                await rules.send(
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
                print("rules skeleton posted")
        except Exception as e:
            print(f"rules post failed: {e}")

    # ---- AutoMod rules (native, works even before Wick/Carl) ----
    from datetime import timedelta
    bot_logs = discord.utils.get(guild.text_channels, name="🚨・bot-logs")
    alert_id = bot_logs.id if bot_logs else None
    automod_specs = [
        ("Block Discord tokens", [TOKEN_REGEX], ["block_message"], True),
        ("Block webhooks", [WEBHOOK_REGEX], ["block_message"], True),
        ("Block free nitro scam", [NITRO_REGEX, THAI_NITRO_REGEX], ["block_message", "timeout"], False),
    ]
    for name, patterns, actions, alert in automod_specs:
        try:
            existing_rules = await guild.fetch_automod_rules()
            if any(r.name == name for r in existing_rules):
                print(f"automod exists: {name}")
                continue
            act_list = [discord.AutoModRuleAction(type=discord.AutoModRuleActionType.block_message)]
            if actions and "timeout" in actions:
                act_list.append(discord.AutoModRuleAction(type=discord.AutoModRuleActionType.timeout, duration=timedelta(seconds=600)))
            if alert and alert_id:
                act_list.append(discord.AutoModRuleAction(type=discord.AutoModRuleActionType.send_alert_message, channel_id=alert_id))
            kwargs = dict(
                name=name, event_type=discord.AutoModRuleEventType.message_send,
                trigger=discord.AutoModTrigger(type=discord.AutoModRuleTriggerType.keyword, regex_patterns=patterns),
                actions=act_list,
                enabled=True, reason="SockBoi setup",
            )
            await guild.create_automod_rule(**kwargs)
            print(f"automod created: {name}")
        except Exception as e:
            print(f"automod {name} failed: {e} (need Manage Server perm + alerts channel)")

    print("DONE. Next: invite Wick + Carl-bot + MEE6 + Ticket Tool, paste configs from wick-carl-config.md")

@client.event
async def on_ready():
    try:
        guild = client.get_guild(GUILD_ID) or await client.fetch_guild(GUILD_ID)
        await setup(guild)
    finally:
        await client.close()

if __name__ == "__main__":
    assert TOKEN, "Missing DISCORD_BOT_TOKEN in .env"
    assert GUILD_ID, "Missing GUILD_ID in .env"
    client.run(TOKEN)
