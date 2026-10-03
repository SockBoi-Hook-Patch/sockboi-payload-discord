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
intents.voice_states = True
bot = commands.Bot(command_prefix="!", intents=intents)

WELCOME_VOICE = os.getenv("WELCOME_VOICE", "1") == "1"

# Preload opus explicitly (Debian libopus0) so voice never hits OpusNotLoaded.
try:
    if not discord.opus.is_loaded():
        discord.opus.load_opus("libopus.so.0")
except Exception:
    pass

def ffmpeg_path():
    """System ffmpeg first, else bundled static binary (imageio-ffmpeg, no apt needed)."""
    import shutil
    p = shutil.which("ffmpeg")
    if p:
        return p
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return None

def welcome_channel(guild):
    return (discord.utils.get(guild.text_channels, name="👋・welcome")
            or discord.utils.get(guild.text_channels, name="💬・general"))

async def make_welcome_card(member, age_days, age_flag, member_no):
    """Hacker-style welcome card (PIL). Returns BytesIO or None."""
    try:
        from PIL import Image, ImageDraw
        import io
        W, H = 900, 320
        img = Image.new("RGB", (W, H), (4, 10, 6))
        d = ImageDraw.Draw(img)
        for y in range(0, H, 4):  # scanlines
            d.line([(0, y), (W, y)], fill=(0, 30, 12))
        d.rectangle([4, 4, W - 5, H - 5], outline=(0, 255, 65), width=2)
        d.text((30, 24), "[+] ACCESS GRANTED", fill=(0, 255, 65))
        d.text((30, 52), "SOCKBOI'S PAYLOAD // NEW NODE", fill=(0, 200, 50))
        name = (member.display_name or str(member))[:24]
        d.text((30, 110), f"> {name}", fill=(220, 255, 220))
        d.text((30, 150), f"  node #{member_no} | acct {age_days}d [{age_flag}]", fill=(0, 255, 65))
        d.text((30, 190), "  $ verify: #verify (5 min)  $ guide: #server-guide", fill=(0, 180, 60))
        d.text((30, 230), "  stay clean. no tokens. no leaks. -- SockBoi", fill=(0, 160, 55))
        try:
            raw = await member.display_avatar.read()
            av = Image.open(io.BytesIO(raw)).convert("RGB").resize((150, 150))
            mask = Image.new("L", (150, 150), 0)
            ImageDraw.Draw(mask).ellipse([0, 0, 150, 150], fill=255)
            img.paste(av, (W - 190, 85), mask)
            ImageDraw.Draw(img).ellipse([W - 190, 85, W - 40, 235], outline=(0, 255, 65), width=2)
        except Exception:
            pass
        buf = io.BytesIO()
        img.save(buf, "PNG")
        buf.seek(0)
        return buf
    except Exception:
        return None

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

async def member_log(guild, embed=None, text=None):
    ch = (discord.utils.get(guild.text_channels, name="📤・member-log")
          or discord.utils.get(guild.text_channels, name="🚨・bot-logs"))
    if not ch:
        return
    try:
        if embed is not None:
            await ch.send(embed=embed)
        elif text:
            await ch.send(text)
    except Exception:
        pass

@bot.event
async def on_member_remove(member):
    """Leave vs kick (via audit log) -> #member-log."""
    try:
        if member.guild.id != GUILD_ID:
            return
        now = datetime.now(timezone.utc)
        action, by, reason = "leave", None, ""
        try:
            async for e in member.guild.audit_logs(limit=5, action=discord.AuditLogAction.kick):
                if e.target and e.target.id == member.id and (now - e.created_at).total_seconds() < 30:
                    action, by, reason = "kick", e.user, e.reason or ""
                    break
        except Exception:
            pass
        if action == "kick":
            em = discord.Embed(title="👢 KICK // node ejected", color=0xFFAA00, timestamp=now)
            em.add_field(name="User", value=f"{member} (`{member.id}`)", inline=False)
            em.add_field(name="By", value=str(by) if by else "-", inline=True)
            em.add_field(name="Reason", value=reason or "-", inline=True)
        else:
            joined = member.joined_at.strftime("%d/%m/%Y %H:%M") if getattr(member, "joined_at", None) else "-"
            em = discord.Embed(title="📤 LEAVE // connection closed", color=0x888888, timestamp=now)
            em.add_field(name="User", value=f"{member} (`{member.id}`)", inline=False)
            em.add_field(name="Joined", value=joined, inline=True)
            em.add_field(name="Members now", value=str(member.guild.member_count), inline=True)
        await member_log(member.guild, embed=em)
    except Exception:
        pass

@bot.event
async def on_member_ban(guild, user):
    try:
        if guild.id != GUILD_ID:
            return
        reason = ""
        try:
            e = await guild.fetch_ban(user)
            reason = e.reason or ""
        except Exception:
            pass
        em = discord.Embed(title="🔨 BAN // node terminated", color=0xFF3333,
                           timestamp=datetime.now(timezone.utc))
        em.add_field(name="User", value=f"{user} (`{user.id}`)", inline=False)
        em.add_field(name="Reason", value=reason or "-", inline=False)
        await member_log(guild, embed=em)
    except Exception:
        pass

@bot.event
async def on_member_unban(guild, user):
    try:
        if guild.id != GUILD_ID:
            return
        em = discord.Embed(title="✅ UNBAN // node restored", color=0x00FF41,
                           timestamp=datetime.now(timezone.utc))
        em.add_field(name="User", value=f"{user} (`{user.id}`)", inline=False)
        await member_log(guild, embed=em)
    except Exception:
        pass
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
VERIFY_WAIT = timedelta(minutes=2)

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
    # public hacker-style welcome in #welcome (fallback #general)
    try:
        wch = welcome_channel(member.guild)
        if wch:
            age_days = max(age.days, 0)
            age_flag = "TRUSTED" if age > timedelta(days=30) else ("NEW" if age > timedelta(days=7) else "FRESH")
            em = discord.Embed(
                title="[+] INCOMING CONNECTION // handshake accepted",
                description=(
                    "```\n"
                    f"$ whoami\n> {member}\n"
                    f"$ uptime --account\n> {age_days} days\n"
                    f"$ grid --members\n> #{member.guild.member_count} nodes online\n"
                    "```"
                ),
                color=0x00FF41, timestamp=now)
            em.add_field(
                name="// PAYLOAD BRIEF",
                value=("✅ กด verify ที่ #✅・verify (เข้าใหม่รอ 2 นาที)\n"
                       "🗺️ อ่าน #🗺️・server-guide ว่าของอยู่ไหน\n"
                       "🛡️ เช็ก #🛡️・detection-log ก่อนเล่นแรงก์\n"
                       "Stay clean. No tokens. No leaks."),
                inline=False)
            em.set_footer(text=f"node_id :: {member.id}")
            card = await make_welcome_card(member, age_days, age_flag, member.guild.member_count)
            if card:
                f = discord.File(card, filename="welcome.png")
                em.set_image(url="attachment://welcome.png")
                await wch.send(f"👾 {member.mention} jacked into **SockBoi's Payload**", embed=em, file=f)
            else:
                await wch.send(f"👾 {member.mention} jacked into **SockBoi's Payload**", embed=em)
    except Exception:
        pass

@bot.event
async def on_voice_state_update(member, before, after):
    """Voice greeting: bot joins VC briefly + TTS welcome (needs FFmpeg on host)."""
    try:
        if member.bot or not WELCOME_VOICE:
            return
        if member.guild.id != GUILD_ID:
            return
        if after.channel is None or (before.channel and before.channel.id == after.channel.id):
            return
        vc = member.guild.voice_client
        if vc and (vc.is_playing() or vc.is_connected()):
            return
        import tempfile
        ff = ffmpeg_path()
        if ff is None:
            await log_to_botlogs(member.guild, text="⚠️ Voice greeting skipped: ไม่มี ffmpeg (system + bundled)")
            return
        from gtts import gTTS
        text = f"ยินดีต้อนรับ {member.display_name} สู่ ซ็อกบอยเพย์โหลด น้า"
        try:
            # kawaii female voice: Premwadee + pitch/rate up
            import edge_tts
            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tf:
                path = tf.name
            await edge_tts.Communicate(text, "th-TH-PremwadeeNeural", rate="+12%", pitch="+22Hz").save(path)
        except Exception:
            try:
                with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tf:
                    gTTS(text=text, lang="th").save(tf.name)
                    path = tf.name
            except Exception as e:
                await log_to_botlogs(member.guild, text=f"⚠️ TTS ล้มเหลว: {e}")
                return
        try:
            vc = await after.channel.connect(timeout=10)
        except Exception as e:
            await log_to_botlogs(member.guild, text=f"⚠️ เข้าห้องเสียงไม่ได้: {e}")
            try:
                os.unlink(path)
            except Exception:
                pass
            return
        try:
            src = discord.FFmpegPCMAudio(path, executable=ff)
            vc.play(src)
            import asyncio as _aio
            while vc.is_playing():
                await _aio.sleep(1)
        except Exception as e:
            import traceback as _tb
            detail = _tb.format_exc(limit=5)[-800:]
            await log_to_botlogs(member.guild, text=f"⚠️ เล่นเสียงล้มเหลว: {type(e).__name__}: {e!r}\n```{detail}```")
        finally:
            try:
                await vc.disconnect()
            except Exception:
                pass
            try:
                os.unlink(path)
            except Exception:
                pass
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

async def kick_punish(msg, reason_en, reason_th):
    """Link violations = KICK (per SockBoi policy)."""
    try:
        await msg.delete()
    except Exception:
        pass
    try:
        await msg.author.send(f"{reason_th}\n{reason_en}\nโดนเตะออกเซิร์ฟเวอร์แล้ว อยากกลับเข้ามาอ่านกฎลิงก์ก่อน / Kicked. Read link rules before rejoining.")
    except Exception:
        pass
    try:
        await msg.author.kick(reason=reason_en)
    except Exception:
        pass
    em = discord.Embed(title=f"👢 Automod KICK: {reason_en}", color=0xFF3333,
        timestamp=datetime.now(timezone.utc))
    em.add_field(name="User", value=f"{msg.author} (`{msg.author.id}`)", inline=False)
    em.add_field(name="Channel", value=f"#{msg.channel.name}", inline=True)
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
            await kick_punish(msg, "Links blocked in this channel", "ห้องนี้ห้ามส่งลิงก์ (เฉพาะ Verified Modder+) — โดนเตะ")
            return
        # even bypassers: only whitelisted domains
        bad = [u for u in urls if not any(d in domain_of(u) for d in ALLOWED_DOMAINS)]
        if bad:
            await kick_punish(msg, f"Non-whitelisted link: {domain_of(bad[0])}", "ลิงก์นอก whitelist (github/t.me เท่านั้น) — โดนเตะ")
            return
    # APK links only in mod-releases by Core Dev+
    if APK_RE.search(content) and not staff_bypass:
        if not (msg.channel.name == "📱・mod-releases" and has_any_role(member, APK_POST_ROLES)):
            await kick_punish(msg, "APK links restricted", "ลิงก์ APK ลงได้แค่ #📱・mod-releases โดย Core Dev+ — โดนเตะ")
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

def mod_only():
    async def pred(ctx):
        return (is_staff(ctx.author)
                or ctx.author.guild_permissions.manage_messages
                or ctx.author.guild_permissions.administrator)
    return commands.check(pred)

@bot.command()
@mod_only()
async def clear(ctx, n: int = 10):
    """ลบแชท n ข้อความล่าสุด (1-200) | !clear 20"""
    n = max(1, min(n, 200))
    try:
        deleted = await ctx.channel.purge(limit=n + 1)
        msg = await ctx.send(f"🧹 ล้าง {len(deleted) - 1} ข้อความแล้ว")
        await msg.delete(delay=5)
    except discord.Forbidden:
        await ctx.send("บอทไม่มีสิทธิ์ Manage Messages")

@bot.command()
@mod_only()
async def timeout(ctx, member: discord.Member, minutes: int = 10, *, reason: str = ""):
    """mute ชั่วคราว | !timeout @user 30 สแปม"""
    try:
        await member.timeout(timedelta(minutes=minutes), reason=reason or "mod timeout")
        await ctx.send(f"⏳ {member.mention} โดน timeout {minutes} นาที {f'({reason})' if reason else ''}")
    except discord.Forbidden:
        await ctx.send("ทำไม่ได้ — role บอทต้องอยู่เหนือเป้าหมาย")

@bot.command()
@mod_only()
async def untimeout(ctx, member: discord.Member):
    try:
        await member.timeout(None, reason="unmuted")
        await ctx.send(f"✅ ปลด timeout {member.mention} แล้ว")
    except discord.Forbidden:
        await ctx.send("ทำไม่ได้ — เช็ก role บอท")

@bot.command()
@admin_only()
async def kick(ctx, member: discord.Member, *, reason: str = ""):
    await member.kick(reason=reason or "kicked")
    await ctx.send(f"👢 เตะ {member} แล้ว {f'({reason})' if reason else ''}")

@bot.command()
@admin_only()
async def ban(ctx, member: discord.Member, *, reason: str = ""):
    await member.ban(reason=reason or "banned", delete_message_days=1)
    await ctx.send(f"🔨 แบน {member} แล้ว {f'({reason})' if reason else ''}")

@bot.command()
@admin_only()
async def unban(ctx, user_id: int):
    try:
        u = await bot.fetch_user(user_id)
        await ctx.guild.unban(u)
        await ctx.send(f"✅ ปลดแบน {u} แล้ว")
    except Exception as e:
        await ctx.send(f"ปลดไม่ได้: {e}")

@bot.command()
@mod_only()
async def slowmode(ctx, seconds: int = 0):
    """!slowmode 30 เปิด / !slowmode 0 ปิด"""
    await ctx.channel.edit(slowmode_delay=max(0, min(seconds, 21600)), reason="mod slowmode")
    await ctx.send(f"🐢 slowmode {seconds}s ใน #{ctx.channel.name}")

@bot.command()
@mod_only()
async def lock(ctx):
    """ล็อกห้อง (เฉพาะทีมพิมพ์ได้)"""
    await ctx.channel.set_permissions(ctx.guild.default_role, send_messages=False, reason="locked")
    await ctx.send(f"🔒 ล็อก #{ctx.channel.name} แล้ว (`!unlock` เพื่อเปิด)")

@bot.command()
@mod_only()
async def unlock(ctx):
    await ctx.channel.set_permissions(ctx.guild.default_role, send_messages=None, reason="unlocked")
    await ctx.send(f"🔓 เปิด #{ctx.channel.name} แล้ว")

@bot.command()
@mod_only()
async def userinfo(ctx, member: discord.Member = None):
    """ดูข้อมูลสมาชิก (อายุแอค วันเข้าฯ ยศ) | !userinfo @user"""
    m = member or ctx.author
    now = datetime.now(timezone.utc)
    age = now - m.created_at
    flag = "🟢" if age > timedelta(days=30) else ("🟡" if age > timedelta(days=7) else "🔴")
    roles = ", ".join(r.name for r in m.roles if r.name != "@everyone") or "-"
    em = discord.Embed(title=f"{flag} {m}", color=0x00FF41, timestamp=now)
    em.add_field(name="ID", value=str(m.id), inline=True)
    em.add_field(name="อายุแอค", value=f"{age.days} วัน", inline=True)
    em.add_field(name="เข้าฯ", value=m.joined_at.strftime("%d/%m/%Y") if m.joined_at else "-", inline=True)
    em.add_field(name="Roles", value=roles[:1000], inline=False)
    if m.display_avatar:
        em.set_thumbnail(url=m.display_avatar.url)
    await ctx.send(embed=em)

@bot.command()
@admin_only()
async def detect(ctx, build: str, status: str, *, note: str = ""):
    """ลงสถานะม็อดใน detection-log | !detect v26.9.02 detected โดนแบน 3 วัน"""
    st = status.lower()
    color = {"safe": 0x00FF41, "risky": 0xFFAA00, "detected": 0xFF3333}.get(st, 0x888888)
    ch = discord.utils.get(ctx.guild.text_channels, name="🛡️・detection-log")
    if not ch:
        await ctx.send("หาห้อง detection-log ไม่เจอ")
        return
    em = discord.Embed(title=f"[{st.upper()}] {build}", description=note or "-", color=color,
                       timestamp=datetime.now(timezone.utc))
    em.set_footer(text=f"by {ctx.author}")
    await ch.send(embed=em)
    await ctx.send(f"✅ ลง {build} = {st} แล้ว")

@bot.command()
@admin_only()
async def announce(ctx, *, text: str):
    """ประกาศในห้อง announcements | !announce ..."""
    ch = discord.utils.get(ctx.guild.text_channels, name="📣・announcements")
    if not ch:
        await ctx.send("หาห้อง announcements ไม่เจอ")
        return
    em = discord.Embed(title="📣 ประกาศจาก SockBoi", description=text, color=0x0A0A0A,
                       timestamp=datetime.now(timezone.utc))
    await ch.send(embed=em)
    await ctx.send("✅ ประกาศแล้ว")

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
async def diag(ctx):
    """Self-check: version, ffmpeg, voice, config — paste output to SockBoi's AI."""
    import shutil, platform
    commit = os.getenv("RAILWAY_GIT_COMMIT_SHA", "")[:7] or "local"
    ff = shutil.which("ffmpeg") or "NOT FOUND"
    try:
        n_rules = len(await ctx.guild.fetch_automod_rules())
    except Exception as e:
        n_rules = f"err: {e}"
    vc = ctx.guild.voice_client
    await ctx.send(
        f"```\ncommit={commit} | py={platform.python_version()} | dpy={discord.__version__}\n"
        f"ffmpeg={ff} | voice_client={vc} | latency={round(bot.latency*1000)}ms\n"
        f"verify_wait={VERIFY_WAIT} | welcome_voice={WELCOME_VOICE}\n"
        f"automod_native={n_rules} | whitelist={sorted(ALLOWED_DOMAINS)}\n```")

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
