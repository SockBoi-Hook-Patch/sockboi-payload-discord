"""
SockBoi Bot — persistent automation for SockBoi's Payload (TH/EN)
Covers the whole spec without Wick/Carl/MEE6 (keep Wick only for anti-nuke if you want).

Features:
 1. Token protection: delete + mute + redacted log + TH/EN DM
 2. Anti-raid: Unverified gate, flag <7d accounts, slowmode #general if >10 joins/min
 3. Link filter: block links in #general/#help except Verified Modder+,
    whitelist github.com, t.me, telegram.me (+ OWN_DOMAINS),
    APK links only in #mod-releases by Core Dev+
 4. Spam: same msg 3x/10s -> timeout 10m first, 1h repeat
 5. Word filter: webhooks, free nitro EN+TH, invite spam
 6. Verify button in #verify (-> Member, remove Unverified), role-select buttons
 7. Welcome DM + general, logging to #bot-logs
 8. Admin: !setup_verify !setup_roles !pinall !status

Run 24/7: python sockboi_bot.py  (needs .env with DISCORD_BOT_TOKEN + GUILD_ID)
Required bot perms: Administrator (or Manage Messages + Moderate Members + Manage Channels + Manage Roles).
Role order: SockBoi Bot role ABOVE Member/Unverified (else timeout/role fails).
"""
import os, re, sys
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="ignore")
    sys.stderr.reconfigure(encoding="utf-8", errors="ignore")
except Exception:
    pass
import json
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
import discord
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("DISCORD_BOT_TOKEN")
GUILD_ID = int(os.getenv("GUILD_ID", "0") or 0)
assert TOKEN and GUILD_ID, "Set DISCORD_BOT_TOKEN and GUILD_ID in .env"

# ---------- CONFIG ----------
STAFF_ROLES = {"SockBoi", "Core Dev"}
BYPASS_LINK_ROLES = {"SockBoi", "Core Dev", "Verified Modder"}
APK_POST_ROLES = {"SockBoi", "Core Dev"}
LINK_BLOCK_CHANNELS = {"💬・general", "❓・help"}
WHITELIST_DOMAINS = {"github.com", "t.me", "telegram.me"}
OWN_DOMAINS = {d.strip().lower() for d in os.getenv("OWN_DOMAINS", "").split(",") if d.strip()}
ALLOWED_DOMAINS = WHITELIST_DOMAINS | OWN_DOMAINS

TOKEN_RE = re.compile(r"[MN][A-Za-z\d]{23}\.[\w-]{6}\.[\w-]{27}")
WEBHOOK_RE = re.compile(r"discord\.com/api/webhooks/\d+/[\w-]+", re.I)
NITRO_RE = re.compile(r"fre+\s*nitr[o0]", re.I)
THAI_SCAM_RE = re.compile(r"ฟรี.*ไนโตร|ไนโตร.*ฟรี|แจก.*ไนโตร|แจก.*nitro|ฟรี.*nitro|สแกน.*รับ|แจก.*เพชร.*ฟรี")
URL_RE = re.compile(r"https?://[^\s<>()\[\]]+", re.I)
INVITE_RE = re.compile(r"discord(?:\.gg|app\.com/invite)/[A-Za-z0-9-]+", re.I)
APK_RE = re.compile(r"\.apk(\?|$)|apkpure|apkmirror|mediafire.*\.apk", re.I)

DATA_FILE = "sockboi_bot_data.json"
def load_data():
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"offenses": {}}
def save_data(d):
    try:
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(d, f)
    except Exception:
        pass
DB = load_data()

# spam tracker: user_id -> deque[(content_hash, ts)]
recent_msgs = defaultdict(lambda: deque(maxlen=10))
# join tracker for raid: deque[ts]
join_times = deque(maxlen=50)

intents = discord.Intents.default()
intents.members = True
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

def is_staff(m: discord.Member):
    return any(r.name in STAFF_ROLES for r in m.roles)
def has_any_role(m, names):
    return any(r.name in names for r in m.roles)
def domain_of(url: str):
    m = re.search(r"https?://([^/\s:]+)", url, re.I)
    return m.group(1).lower() if m else ""

async def log_to_botlogs(guild, embed=None, text=None):
    ch = discord.utils.get(guild.text_channels, name="🚨・bot-logs")
    if not ch:
        return
    try:
        if embed is not None:
            await ch.send(embed=embed)
        elif text:
            await ch.send(text)
    except Exception:
        pass

def redact(s: str):
    # never log full token/webhook
    s = TOKEN_RE.sub("[REDACTED TOKEN]", s)
    s = re.sub(r"(discord\.com/api/webhooks/\d+/)[\w-]+", r"\1[REDACTED]", s, flags=re.I)
    return s[:1500]

# ---------- VERIFY VIEW ----------
VERIFY_WAIT = timedelta(minutes=5)

class VerifyView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
    @discord.ui.button(label="✅ ยืนยันตัวตน / Verify", style=discord.ButtonStyle.success, custom_id="sockboi_verify")
    async def verify(self, inter: discord.Interaction, button: discord.ui.Button):
        guild = inter.guild
        member = guild.get_member(inter.user.id)
        # new-join gate: must wait 5 min after joining
        joined = getattr(member, "joined_at", None)
        if joined is not None:
            left = VERIFY_WAIT - (datetime.now(timezone.utc) - joined)
            if left.total_seconds() > 0:
                m, s = divmod(int(left.total_seconds()), 60)
                await inter.response.send_message(
                    f"⏳ แอคใหม่รอ {m} นาที {s} วิ แล้วกดอีกทีนะ / Please wait {m}m {s}s after joining.",
                    ephemeral=True)
                return
        unver = discord.utils.get(guild.roles, name="Unverified")
        mem = discord.utils.get(guild.roles, name="Member")
        try:
            if unver and unver in member.roles:
                await member.remove_roles(unver, reason="verified")
            if mem and mem not in member.roles:
                await member.add_roles(mem, reason="verified")
            await inter.response.send_message("ยืนยันแล้ว! ห้องม็อดปลดล็อกแล้ว 🎮 / Verified — drops unlocked!", ephemeral=True)
        except discord.Forbidden:
            await inter.response.send_message("บอทติด permission — บอก SockBoi ขยับ role บอทขึ้นบนสุด / Bot needs higher role.", ephemeral=True)

class RoleView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
    async def toggle(self, inter, role_name):
        r = discord.utils.get(inter.guild.roles, name=role_name)
        if not r:
            # create plain self-assign role on demand
            try:
                r = await inter.guild.create_role(name=role_name, reason="self-assign")
            except Exception:
                await inter.response.send_message("สร้างยศไม่ได้ — ให้แอดมินสร้างก่อน", ephemeral=True)
                return
        m = inter.guild.get_member(inter.user.id)
        if r in m.roles:
            await m.remove_roles(r, reason="self unassign")
            await inter.response.send_message(f"เอา `{role_name}` ออกแล้ว", ephemeral=True)
        else:
            await m.add_roles(r, reason="self assign")
            await inter.response.send_message(f"รับยศ `{role_name}` แล้ว", ephemeral=True)
    @discord.ui.button(label="🤖 Android", style=discord.ButtonStyle.secondary, custom_id="role_android")
    async def b1(self, i, b): await self.toggle(i, "Android")
    @discord.ui.button(label="🔓 Root", style=discord.ButtonStyle.secondary, custom_id="role_root")
    async def b2(self, i, b): await self.toggle(i, "Root")
    @discord.ui.button(label="📵 No-Root", style=discord.ButtonStyle.secondary, custom_id="role_noroot")
    async def b3(self, i, b): await self.toggle(i, "No-Root")
    @discord.ui.button(label="🖥️ Emulator", style=discord.ButtonStyle.secondary, custom_id="role_emu")
    async def b4(self, i, b): await self.toggle(i, "Emulator")

@bot.event
async def on_ready():
    bot.add_view(VerifyView())
    bot.add_view(RoleView())
    print(f"Logged in as {bot.user} — guild {GUILD_ID} — automate ON")

@bot.event
async def on_member_join(member):
    if member.guild.id != GUILD_ID:
        return
    now = datetime.now(timezone.utc)
    # gate: give Unverified
    try:
        unver = discord.utils.get(member.guild.roles, name="Unverified")
        if unver:
            await member.add_roles(unver, reason="join gate")
    except Exception:
        pass
    # flag young accounts
    age = now - member.created_at
    if age < timedelta(days=7):
        await log_to_botlogs(member.guild, text=f"⚠️ แอคใหม่ <7วัน join: {member} (`{member.id}`) อายุ {age.days} วัน — รอตรวจสอบ")
    # raid: >10 joins in 60s -> slowmode general
    join_times.append(now.timestamp())
    recent = [t for t in join_times if now.timestamp() - t < 60]
    if len(recent) >= 10:
        ch = discord.utils.get(member.guild.text_channels, name="💬・general")
        if ch:
            try:
                await ch.edit(slowmode_delay=30, reason="anti-raid: join flood")
                await log_to_botlogs(member.guild, text=f"🚨 RAID MODE: {len(recent)} joins/60s — slowmode 30s ON ใน #💬・general")
            except Exception:
                pass
    # welcome DM
    try:
        await member.send("ยินดีต้อนรับสู่ SockBoi's Payload 🎮 ไปยืนยันที่ #✅・verify อ่าน #🗺️・server-guide เช็ก #🛡️・detection-log ก่อนเล่นแรงก์นะ / Verify in #✅・verify to unlock drops!")
    except Exception:
        pass

async def punish(msg, reason_en, reason_th, timeout_min):
    try:
        await msg.delete()
    except Exception:
        pass
    try:
        await msg.author.timeout(timedelta(minutes=timeout_min), reason=reason_en)
    except Exception:
        pass
    try:
        await msg.author.send(f"{reason_th}\n{reason_en}\nติดต่อ SockBoi ถ้าเข้าใจผิด / Contact SockBoi on false positive.")
    except Exception:
        pass
    em = discord.Embed(title=f"🛡️ Automod: {reason_en}", color=0xFF3333,
        timestamp=datetime.now(timezone.utc))
    em.add_field(name="User", value=f"{msg.author} (`{msg.author.id}`)", inline=False)
    em.add_field(name="Channel", value=f"#{msg.channel.name}", inline=True)
    em.add_field(name="Timeout", value=f"{timeout_min}m", inline=True)
    em.add_field(name="Content (redacted)", value=redact(msg.content) or "(embed/attach)", inline=False)
    await log_to_botlogs(msg.guild, embed=em)

@bot.event
async def on_message(msg):
    if msg.author.bot or not msg.guild or msg.guild.id != GUILD_ID:
        if msg.guild is None:
            pass
        else:
            return
    if msg.guild is None:
        return
    content = msg.content or ""
    member = msg.author
    staff_bypass = is_staff(member)

    # 1. token
    if TOKEN_RE.search(content):
        await punish(msg, "Token sharing prohibited", "ห้ามแชร์ token ในเซิร์ฟเวอร์", 60)
        return
    # 2. webhook
    if WEBHOOK_RE.search(content):
        await punish(msg, "Webhook URL blocked", "ห้ามโพสต์ webhook", 60)
        return
    # 3. nitro scam EN+TH
    if NITRO_RE.search(content) or THAI_SCAM_RE.search(content):
        key = f"nitro:{member.id}"
        n = DB["offenses"].get(key, 0) + 1
        DB["offenses"][key] = n
        save_data(DB)
        await punish(msg, "Free-nitro scam blocked", "ห้ามโพสต์ฟรีไนโตร/แจกของสแกม", 60 if n < 2 else 1440)
        return
    # 4. link filter
    urls = URL_RE.findall(content) + INVITE_RE.findall(content)
    if urls and msg.channel.name in LINK_BLOCK_CHANNELS and not staff_bypass:
        if not has_any_role(member, BYPASS_LINK_ROLES):
            await punish(msg, "Links blocked in this channel", "ห้องนี้ห้ามส่งลิงก์ (เฉพาะ Verified Modder+)", 10)
            return
        # even bypassers: only whitelisted domains
        bad = [u for u in urls if not any(d in domain_of(u) for d in ALLOWED_DOMAINS)]
        if bad:
            await punish(msg, f"Non-whitelisted link: {domain_of(bad[0])}", "ลิงก์นอก whitelist (github/t.me เท่านั้น)", 10)
            return
    # APK links only in mod-releases by Core Dev+
    if APK_RE.search(content) and not staff_bypass:
        if not (msg.channel.name == "📱・mod-releases" and has_any_role(member, APK_POST_ROLES)):
            await punish(msg, "APK links restricted", "ลิงก์ APK ลงได้แค่ #📱・mod-releases โดย Core Dev+", 10)
            return
    # 5. spam: same content 3x in 10s
    now = datetime.now(timezone.utc).timestamp()
    dq = recent_msgs[member.id]
    dq.append((content.strip().lower()[:200], now))
    same = [t for (c, t) in dq if c == content.strip().lower()[:200] and now - t < 10]
    if len(content.strip()) > 0 and len(same) >= 3 and not staff_bypass:
        key = f"spam:{member.id}"
        n = DB["offenses"].get(key, 0) + 1
        DB["offenses"][key] = n
        save_data(DB)
        await punish(msg, "Spam: duplicate 3x/10s", "ห้ามส่งข้อความซ้ำรัวๆ", 10 if n < 2 else 60)
        return

    await bot.process_commands(msg)

# ---------- ADMIN ----------
def admin_only():
    async def pred(ctx):
        return is_staff(ctx.author) or ctx.author.guild_permissions.administrator
    return commands.check(pred)

@bot.command()
@admin_only()
async def setup_verify(ctx):
    ch = discord.utils.get(ctx.guild.text_channels, name="✅・verify")
    await (ch or ctx.channel).send("**✅ ยืนยันตัวตน / Verify**\nกดปุ่มเพื่อรับ Member + ปลดล็อกห้องม็อด / Press to verify.", view=VerifyView())

@bot.command()
@admin_only()
async def setup_roles(ctx):
    ch = discord.utils.get(ctx.guild.text_channels, name="🎖️・role-select")
    await (ch or ctx.channel).send("**🎖️ เลือกยศ / Self roles**\nกดเพื่อรับ/เอาออก: Android / Root / No-Root / Emulator", view=RoleView())

@bot.command()
@admin_only()
async def status(ctx):
    g = ctx.guild
    n_rules = len(await g.fetch_automod_rules())
    await ctx.send(f"SockBoi Bot ON ✅ automod-native={n_rules} | whitelist={sorted(ALLOWED_DOMAINS)} | offenses-tracked={len(DB['offenses'])}")

@bot.command()
@admin_only()
async def pinall(ctx):
    """Pin latest bot msg in guide/rules/forms."""
    pinned = 0
    for name in ["🗺️・server-guide", "📜・rules", "📥・request-mods", "⚠️・ban-reports", "✅・verify"]:
        ch = discord.utils.get(ctx.guild.text_channels, name=name)
        if not ch:
            continue
        async for m in ch.history(limit=20):
            if m.author == bot.user and not m.pinned:
                try:
                    await m.pin(reason="SockBoi pinall")
                    pinned += 1
                except Exception:
                    pass
                break
    await ctx.send(f"Pinned {pinned} messages 📌")

if __name__ == "__main__":
    bot.run(TOKEN)
