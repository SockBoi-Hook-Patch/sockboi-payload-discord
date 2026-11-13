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
import asyncio, json, os, re, signal, sys, time
from contextlib import suppress
from pathlib import Path
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="ignore")
    sys.stderr.reconfigure(encoding="utf-8", errors="ignore")
except Exception:
    pass
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
import discord
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()

def validate_environment(environ=None):
    """Fail fast when required runtime settings are missing or malformed."""
    env = os.environ if environ is None else environ
    token = (env.get("DISCORD_BOT_TOKEN") or "").strip()
    guild_raw = (env.get("GUILD_ID") or "").strip()
    if not token or token.lower() in {"paste_bot_token_here", "your_token_here", "changeme"}:
        raise ValueError("DISCORD_BOT_TOKEN is required; set it in platform secrets.")
    if not guild_raw.isdigit() or int(guild_raw) <= 0:
        raise ValueError("GUILD_ID must be a positive numeric Discord server ID.")
    port_raw = (env.get("PORT") or "8080").strip()
    if not port_raw.isdigit() or not 1 <= int(port_raw) <= 65535:
        raise ValueError("PORT must be an integer between 1 and 65535.")
    return {"token": token, "guild_id": int(guild_raw), "port": int(port_raw)}

CONFIG = validate_environment()
TOKEN = CONFIG["token"]
GUILD_ID = CONFIG["guild_id"]
PORT = CONFIG["port"]

# ---------- CONFIG ----------
STAFF_ROLES = {"SockBoi", "Core Dev"}
BYPASS_LINK_ROLES = {"SockBoi", "Core Dev", "Verified Modder", "💗・Supporter"}
APK_POST_ROLES = {"SockBoi", "Core Dev"}
LINK_BLOCK_CHANNELS = {"💬・general", "❓・help"}
WHITELIST_DOMAINS = {"github.com", "t.me", "telegram.me", "ezdn.app", "buymeacoffee.com"}
OWN_DOMAINS = {d.strip().lower() for d in os.getenv("OWN_DOMAINS", "").split(",") if d.strip()}
ALLOWED_DOMAINS = WHITELIST_DOMAINS | OWN_DOMAINS

TOKEN_RE = re.compile(r"[MN][A-Za-z\d]{23}\.[\w-]{6}\.[\w-]{27}")
WEBHOOK_RE = re.compile(r"discord\.com/api/webhooks/\d+/[\w-]+", re.I)
NITRO_RE = re.compile(r"fre+\s*nitr[o0]", re.I)
THAI_SCAM_RE = re.compile(r"ฟรี.*ไนโตร|ไนโตร.*ฟรี|แจก.*ไนโตร|แจก.*nitro|ฟรี.*nitro|สแกน.*รับ|แจก.*เพชร.*ฟรี")
URL_RE = re.compile(r"https?://[^\s<>()\[\]]+", re.I)
INVITE_RE = re.compile(r"discord(?:\.gg|app\.com/invite)/[A-Za-z0-9-]+", re.I)
APK_RE = re.compile(r"\.apk(\?|$)|apkpure|apkmirror|mediafire.*\.apk", re.I)

DATA_DIR = Path(os.getenv("DATA_DIR", ".")).expanduser()
DATA_FILE = os.getenv("DATA_FILE") or str(DATA_DIR / "sockboi_bot_data.json")

def empty_data():
    return {"offenses": {}, "verification_deadlines": {}, "verification_alerts": {}, "verification_reminders": {}}

def load_data():
    """Load persistent state and migrate older files by adding missing keys."""
    path = Path(DATA_FILE)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
        if not isinstance(data, dict):
            raise ValueError("root JSON value must be an object")
        for key, value in empty_data().items():
            data.setdefault(key, value)
        return data
    except FileNotFoundError:
        return empty_data()
    except (json.JSONDecodeError, OSError, ValueError) as exc:
        print(f"[storage] Could not load {path}: {type(exc).__name__}: {exc}", file=sys.stderr, flush=True)
        return empty_data()

def save_data(data):
    """Atomically save JSON state so termination cannot leave a partial file."""
    path = Path(DATA_FILE)
    tmp_path = path.with_name(path.name + ".tmp")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with tmp_path.open("w", encoding="utf-8") as handle:
            json.dump(data, handle, ensure_ascii=False, separators=(",", ":"))
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_path, path)
    except OSError as exc:
        print(f"[storage] Could not persist {path}: {type(exc).__name__}: {exc}", file=sys.stderr, flush=True)
DB = load_data()
DB.setdefault("offenses", {})
DB.setdefault("verification_deadlines", {})
DB.setdefault("verification_alerts", {})
DB.setdefault("verification_reminders", {})

VERIFY_TIMEOUT = timedelta(hours=1)
VERIFY_REMINDER_AFTER = timedelta(minutes=45)
VERIFY_ALLOWED_CATEGORIES = set()
VERIFY_ALLOWED_CHANNELS = {"👋・welcome", "✅・verify"}

# spam tracker: user_id -> deque[(content_hash, ts)]
recent_msgs = defaultdict(lambda: deque(maxlen=10))
# join tracker for raid: deque[ts]
join_times = deque(maxlen=50)
verification_worker_task = None
gateway_monitor_task = None
gateway_connected = False
gateway_reconnect_count = 0
last_gateway_event = None
verification_gate_configured = set()

intents = discord.Intents.default()
intents.members = True
intents.message_content = True
intents.voice_states = True
bot = commands.Bot(command_prefix="!", intents=intents)

WELCOME_VOICE = os.getenv("WELCOME_VOICE", "1") == "1"

# Member-facing copy approved in the Discord copy review.
WELCOME_DM_TEMPLATE = (
    "👾 HANDSHAKE ACCEPTED — ยินดีต้อนรับสู่ SockBoi's Payload!\n"
    "👾 HANDSHAKE ACCEPTED — Welcome to SockBoi's Payload!\n\n"
    "✅ ACCESS GATE: ไปที่ {verify_channel} แล้วกด Verify หลังเข้าร่วมครบ 1 นาที เพื่อรับ role Member และปลดล็อก member channels\n"
    "✅ ACCESS GATE: Go to {verify_channel} and press Verify 1 minute after joining to receive the Member role and unlock member channels.\n"
    "⏱️ TIMER: หากยังเป็น Unverified ครบ 1 ชั่วโมงหลังเข้าร่วม บอทจะ kick ออกจากเซิร์ฟเวอร์\n"
    "⏱️ TIMER: If you remain Unverified for 1 hour after joining, the bot will kick you from the server.\n"
    "🔔 REMINDER: หากยังไม่ Verify หลัง 45 นาที บอทจะส่ง DM เตือนหนึ่งครั้ง\n"
    "🔔 REMINDER: If you are still unverified after 45 minutes, the bot will send one reminder DM.\n"
    "📘 อ่าน {guide_channel} และตรวจ {detection_channel} ก่อนเล่นแรงก์\n"
    "📘 Read {guide_channel} and check {detection_channel} before ranked play."
)
WELCOME_PUBLIC_MESSAGE_TEMPLATE = "👾 {mention} เชื่อมต่อเข้า **SockBoi's Payload** แล้ว / jacked into **SockBoi's Payload**"
WELCOME_PUBLIC_TITLE = "[+] HANDSHAKE ACCEPTED // สมาชิกใหม่เชื่อมต่อ / NEW MEMBER CONNECTED"
WELCOME_PUBLIC_DESCRIPTION_TEMPLATE = (
    "ข้อมูลบัญชี / Account details:\n"
    "$ whoami\n> {username}\n"
    "$ uptime --account\n> {account_age_days} วัน / days\n"
    "$ grid --members\n> #{member_count} สมาชิก / members"
)
WELCOME_PUBLIC_FIELD_NAME = "// ACCESS GATE / จุดเริ่มต้นการเข้าใช้งาน"
WELCOME_PUBLIC_FIELD_VALUE = (
    "✅ กด Verify ที่ #✅・verify เพื่อรับ role Member และเข้าถึง member channels (สมาชิกใหม่ต้องรอ 1 นาทีหลังเข้าร่วม)\n"
    "✅ Click Verify in #✅・verify to receive the Member role and access member channels (new members must wait 1 minute after joining).\n"
    "⏱️ หากยังเป็น Unverified ครบ 1 ชั่วโมงหลังเข้าร่วม บอทจะ kick ออกจากเซิร์ฟเวอร์\n"
    "⏱️ If you remain Unverified for 1 hour after joining, the bot will kick you from the server.\n"
    "🔎 บัญชีที่อายุน้อยกว่า 7 วันอาจถูกระบบติด flag เพื่อตรวจเพิ่มเติม\n"
    "🔎 Accounts younger than 7 days may be flagged by the system for additional checks.\n"
    "🗺️ อ่าน #🗺️・server-guide เพื่อดูข้อมูลเซิร์ฟเวอร์\n"
    "🗺️ Read #🗺️・server-guide for server information.\n"
    "🛡️ ตรวจ #🛡️・detection-log ก่อนเล่นแรงก์\n"
    "🛡️ Check #🛡️・detection-log before ranked play.\n"
    "🔒 ห้ามแชร์ token หรือเผยแพร่ไฟล์ภายในเซิร์ฟเวอร์\n"
    "🔒 Do not share tokens or leak server-only files."
)
VERIFY_WAIT_RESPONSE_TEMPLATE = "⏳ กรุณารอ {m} นาที {s} วินาทีหลังเข้าร่วม แล้วกด Verify อีกครั้ง / Please wait {m}m {s}s after joining, then press Verify again."
VERIFY_SUCCESS_MESSAGE = "✅ ACCESS GATE OPEN: ยืนยันตัวตนสำเร็จ! คุณได้รับ role Member และเข้าถึง member channels แล้ว / Verification complete! You now have the Member role and access to member channels."
VERIFY_PERMISSION_ERROR_MESSAGE = "⚠️ บอทเปลี่ยน role ไม่ได้ กรุณาแจ้งแอดมินให้ตรวจ permission และลำดับ role / The bot could not update your role. Please ask an admin to check permissions and role hierarchy."
UNVERIFIED_CHAT_REMINDER = "🔒 ACCESS GATE: กรุณากด Verify ใน #✅・verify ก่อนส่งข้อความ / Please verify in #✅・verify before sending messages."
ROLE_ADDED_TEMPLATE = "🔗 DEVICE ROLE LOADED: รับ role {role_name} แล้ว / You now have the {role_name} role."
ROLE_REMOVED_TEMPLATE = "🔗 DEVICE ROLE CLEARED: เอา role {role_name} ออกแล้ว / The {role_name} role has been removed."
ROLE_CREATE_ERROR_TEMPLATE = "⚠️ สร้าง role {role_name} ไม่สำเร็จ กรุณาแจ้งแอดมินให้สร้างก่อน / Could not create {role_name}. Please ask an admin to create it first."
VERIFY_SETUP_MESSAGE = (
    "**✅ Access Gate / ยืนยันตัวตน**\n"
    "กดปุ่ม **Verify** เพื่อยืนยันตัวตน รับ role **Member** และปลดล็อก member channels / Press **Verify** to confirm your identity, receive the **Member** role, and unlock member channels.\n\n"
    "⏳ เข้าเซิร์ฟเวอร์ใหม่แล้ว รอ 1 นาทีก่อนกด Verify / After joining, wait 1 minute before pressing Verify.\n"
    "🕒 หากยังเป็น **Unverified** ครบ 1 ชั่วโมงหลังเข้าร่วม บอทจะ kick ออกจากเซิร์ฟเวอร์ / If you remain **Unverified** for 1 hour after joining, the bot will kick you from the server.\n"
    "🔔 หากยังไม่ Verify หลัง 45 นาที บอทจะส่ง DM เตือนหนึ่งครั้ง / If you are still unverified after 45 minutes, the bot will send one reminder DM.\n"
    "⚠️ บัญชีที่อายุน้อยกว่า 7 วันอาจถูก flag เพื่อการตรวจเพิ่มเติม / Accounts younger than 7 days may be flagged for additional checks."
)
ROLE_SETUP_MESSAGE = (
    "**🎖️ เลือกยศ / Self-Assignable Roles**\n"
    "ตั้งค่าโปรไฟล์อุปกรณ์ของคุณ / Set your device profile.\n"
    "กดเพื่อรับหรือเอายศออก / Click to add or remove a role: Android / Root / No-Root / Emulator"
)

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
        d.text((30, 190), "  $ verify: #verify (within 1 hour)  $ guide: #server-guide", fill=(0, 180, 60))
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

def verification_overwrite(current, can_view):
    """Preserve unrelated role permissions while enforcing the verification gate."""
    updated = discord.PermissionOverwrite.from_pair(*current.pair())
    updated.view_channel = can_view
    updated.read_message_history = can_view
    updated.send_messages = False
    updated.send_messages_in_threads = False
    updated.create_public_threads = False
    updated.create_private_threads = False
    updated.connect = False
    updated.speak = False
    return updated

async def enforce_verification_gate(guild, channel=None):
    """Deny Unverified access everywhere except the information/verification area."""
    role = discord.utils.get(guild.roles, name="Unverified")
    if not role:
        await log_to_botlogs(guild, text="⚠️ Verification gate not applied: role `Unverified` is missing.")
        return
    targets = [channel] if channel is not None else list(guild.channels)
    changed = 0
    for target in targets:
        if target is None:
            continue
        if isinstance(target, discord.CategoryChannel):
            allowed = target.name in VERIFY_ALLOWED_CATEGORIES
        else:
            parent = getattr(target, "category", None)
            parent_allowed = getattr(parent, "name", None) in VERIFY_ALLOWED_CATEGORIES
            allowed = parent_allowed or target.name in VERIFY_ALLOWED_CHANNELS
            # Synced channels already inherit the right setting. Break sync only for
            # the two explicitly allowed channels when their parent category is denied.
            if getattr(target, "permissions_synced", False) and allowed == parent_allowed:
                continue
        current = target.overwrites_for(role)
        expected = verification_overwrite(current, allowed)
        if current == expected:
            continue
        try:
            await target.set_permissions(
                role, overwrite=expected,
                reason="Verification gate: restrict Unverified access until /verify",
            )
            changed += 1
        except discord.Forbidden:
            await log_to_botlogs(guild, text=f"⚠️ Cannot apply verification gate to `{target.name}`: missing Manage Channels.")
        except discord.HTTPException as exc:
            await log_to_botlogs(guild, text=f"⚠️ Verification gate failed for `{target.name}`: {exc}")
    if changed:
        await log_to_botlogs(guild, text=f"🔒 Verification gate updated: {changed} channel/category permission overwrites; Unverified can only view information and verification areas.")

async def gateway_monitor():
    """Log gateway readiness while discord.py performs automatic reconnects."""
    while not bot.is_closed():
        if not bot.is_ready() or not gateway_connected:
            print(json.dumps({
                "event": "gateway_not_ready",
                "reconnect_attempts": gateway_reconnect_count,
                "last_gateway_event": last_gateway_event,
                "at": datetime.now(timezone.utc).isoformat(),
            }), flush=True)
        await asyncio.sleep(max(15, int(os.getenv("RECONNECT_MONITOR_INTERVAL", "60"))))

async def verification_timeout_worker():
    """DM unverified members once after 45 minutes, then kick at the 1-hour deadline."""
    await bot.wait_until_ready()
    while not bot.is_closed():
        now = datetime.now(timezone.utc)
        deadlines = DB.setdefault("verification_deadlines", {})
        alerts = DB.setdefault("verification_alerts", {})
        reminders = DB.setdefault("verification_reminders", {})
        changed = False
        for key, raw_deadline in list(deadlines.items()):
            try:
                deadline = datetime.fromisoformat(raw_deadline)
                if deadline.tzinfo is None:
                    deadline = deadline.replace(tzinfo=timezone.utc)
            except (TypeError, ValueError):
                deadlines.pop(key, None)
                alerts.pop(key, None)
                reminders.pop(key, None)
                changed = True
                continue
            try:
                guild_id, user_id = (int(part) for part in key.split(":", 1))
            except (ValueError, AttributeError):
                deadlines.pop(key, None)
                alerts.pop(key, None)
                reminders.pop(key, None)
                changed = True
                continue
            guild = bot.get_guild(guild_id)
            if guild is None:
                continue
            reminder_deadline = deadline - (VERIFY_TIMEOUT - VERIFY_REMINDER_AFTER)
            if now < reminder_deadline:
                continue
            try:
                member = await guild.fetch_member(user_id)
            except discord.NotFound:
                deadlines.pop(key, None)
                alerts.pop(key, None)
                reminders.pop(key, None)
                changed = True
                continue
            except discord.HTTPException as exc:
                await log_to_botlogs(guild, text=f"⚠️ Could not check verification deadline for user `{user_id}`: {exc}")
                continue
            unverified = discord.utils.get(guild.roles, name="Unverified")
            if not unverified or unverified not in member.roles:
                deadlines.pop(key, None)
                alerts.pop(key, None)
                reminders.pop(key, None)
                changed = True
                continue
            if key not in reminders:
                try:
                    await member.send(
                        "🔔 Verification reminder\n\n"
                        "You are still Unverified. Please press Verify in #✅・verify to unlock member channels.\n\n"
                        "⚠️ If you do not verify, you will be KICKED from the server.\n"
                        "⏱️ Kick happens 1 hour after you joined, so verify now to keep your access."
                    )
                    reminders[key] = {"at": now.isoformat(), "delivered": True}
                except (discord.Forbidden, discord.HTTPException) as exc:
                    # Record the one attempt so closed DMs do not trigger repeated failures.
                    reminders[key] = {"at": now.isoformat(), "delivered": False}
                    await log_to_botlogs(
                        guild,
                        text=f"⚠️ Could not DM the 45-minute verification reminder to `{member}` (`{member.id}`): {type(exc).__name__}.",
                    )
                changed = True
            if deadline > now:
                continue
            if key not in alerts:
                ch = discord.utils.get(guild.text_channels, name="🚨・bot-logs")
                if ch:
                    em = discord.Embed(
                        title="⚠️ Verification overdue — kick pending",
                        description=(f"{member} (`{member.id}`) still has `Unverified` after the 1-hour deadline. "
                                     "The bot will kick this member now."),
                        color=0xFFAA00,
                        timestamp=now,
                    )
                    try:
                        await ch.send(embed=em, allowed_mentions=discord.AllowedMentions.none())
                        alerts[key] = now.isoformat()
                        changed = True
                    except discord.HTTPException:
                        pass
            try:
                await member.kick(reason="Did not verify within 1 hour of joining")
                deadlines.pop(key, None)
                alerts.pop(key, None)
                reminders.pop(key, None)
                changed = True
                await member_log(
                    guild,
                    embed=discord.Embed(
                        title="👢 Verification timeout — member kicked",
                        description=f"{member} (`{member.id}`) still had `Unverified` after 1 hour.",
                        color=0xFFAA00,
                        timestamp=now,
                    ),
                )
            except discord.Forbidden:
                await log_to_botlogs(guild, text=f"⚠️ Could not kick `{member}` for verification timeout: role hierarchy or Kick Members permission.")
            except discord.HTTPException as exc:
                await log_to_botlogs(guild, text=f"⚠️ Kick failed for `{member}` at verification timeout: {exc}")
        if changed:
            save_data(DB)
        await asyncio.sleep(30)

@bot.event
async def on_member_remove(member):
    """Leave vs kick (via audit log) -> #member-log."""
    try:
        if member.guild.id != GUILD_ID:
            return
        DB.setdefault("verification_deadlines", {}).pop(f"{member.guild.id}:{member.id}", None)
        DB.setdefault("verification_alerts", {}).pop(f"{member.guild.id}:{member.id}", None)
        DB.setdefault("verification_reminders", {}).pop(f"{member.guild.id}:{member.id}", None)
        save_data(DB)
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
VERIFY_WAIT = timedelta(minutes=1)

class VerifyView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
    @discord.ui.button(label="✅ ยืนยันตัวตน / Verify", style=discord.ButtonStyle.success, custom_id="sockboi_verify")
    async def verify(self, inter: discord.Interaction, button: discord.ui.Button):
        guild = inter.guild
        member = guild.get_member(inter.user.id)
        # Brief anti-raid grace period: wait 1 min before verifying.
        joined = getattr(member, "joined_at", None)
        if joined is not None:
            left = VERIFY_WAIT - (datetime.now(timezone.utc) - joined)
            if left.total_seconds() > 0:
                m, s = divmod(int(left.total_seconds()), 60)
                await inter.response.send_message(
                    VERIFY_WAIT_RESPONSE_TEMPLATE.format(m=m, s=s),
                    ephemeral=True)
                return
        unver = discord.utils.get(guild.roles, name="Unverified")
        mem = discord.utils.get(guild.roles, name="Member")
        try:
            if unver and unver in member.roles:
                await member.remove_roles(unver, reason="verified")
            if mem and mem not in member.roles:
                await member.add_roles(mem, reason="verified")
            DB.setdefault("verification_deadlines", {}).pop(f"{guild.id}:{member.id}", None)
            DB.setdefault("verification_alerts", {}).pop(f"{guild.id}:{member.id}", None)
            DB.setdefault("verification_reminders", {}).pop(f"{guild.id}:{member.id}", None)
            save_data(DB)
            await inter.response.send_message(VERIFY_SUCCESS_MESSAGE, ephemeral=True)
        except discord.Forbidden:
            await inter.response.send_message(VERIFY_PERMISSION_ERROR_MESSAGE, ephemeral=True)

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
                await inter.response.send_message(ROLE_CREATE_ERROR_TEMPLATE.format(role_name=role_name), ephemeral=True)
                return
        m = inter.guild.get_member(inter.user.id)
        if r in m.roles:
            await m.remove_roles(r, reason="self unassign")
            await inter.response.send_message(ROLE_REMOVED_TEMPLATE.format(role_name=role_name), ephemeral=True)
        else:
            await m.add_roles(r, reason="self assign")
            await inter.response.send_message(ROLE_ADDED_TEMPLATE.format(role_name=role_name), ephemeral=True)
    @discord.ui.button(label="🤖 Android", style=discord.ButtonStyle.secondary, custom_id="role_android")
    async def b1(self, i, b): await self.toggle(i, "Android")
    @discord.ui.button(label="🔓 Root", style=discord.ButtonStyle.secondary, custom_id="role_root")
    async def b2(self, i, b): await self.toggle(i, "Root")
    @discord.ui.button(label="📵 No-Root", style=discord.ButtonStyle.secondary, custom_id="role_noroot")
    async def b3(self, i, b): await self.toggle(i, "No-Root")
    @discord.ui.button(label="🖥️ Emulator", style=discord.ButtonStyle.secondary, custom_id="role_emu")
    async def b4(self, i, b): await self.toggle(i, "Emulator")

@bot.event
async def on_connect():
    global gateway_connected, last_gateway_event
    gateway_connected = True
    last_gateway_event = time.time()
    print("[gateway] connected to Discord Gateway", flush=True)

@bot.event
async def on_disconnect():
    global gateway_connected, gateway_reconnect_count, last_gateway_event
    gateway_connected = False
    gateway_reconnect_count += 1
    last_gateway_event = time.time()
    print(json.dumps({"event":"gateway_disconnect","reconnect_attempts":gateway_reconnect_count,
                      "at":datetime.now(timezone.utc).isoformat()}), flush=True)

@bot.event
async def on_resumed():
    global gateway_connected, last_gateway_event
    gateway_connected = True
    last_gateway_event = time.time()
    print(json.dumps({"event":"gateway_resumed","reconnect_attempts":gateway_reconnect_count,
                      "at":datetime.now(timezone.utc).isoformat()}), flush=True)

@bot.event
async def on_ready():
    global verification_worker_task, gateway_monitor_task, gateway_connected, last_gateway_event
    gateway_connected = True
    last_gateway_event = time.time()
    bot.add_view(VerifyView())
    bot.add_view(RoleView())
    for guild in bot.guilds:
        if guild.id == GUILD_ID and guild.id not in verification_gate_configured:
            await enforce_verification_gate(guild)
            verification_gate_configured.add(guild.id)
    if verification_worker_task is None or verification_worker_task.done():
        verification_worker_task = asyncio.create_task(verification_timeout_worker(), name="verification-timeout-worker")
    if gateway_monitor_task is None or gateway_monitor_task.done():
        gateway_monitor_task = asyncio.create_task(gateway_monitor(), name="gateway-monitor")
    print(f"Logged in as {bot.user} — guild {GUILD_ID} — automate ON", flush=True)

@bot.event
async def on_guild_channel_create(channel):
    if channel.guild.id == GUILD_ID:
        await enforce_verification_gate(channel.guild, channel=channel)

@bot.event
async def on_member_join(member):
    if member.guild.id != GUILD_ID:
        return
    now = datetime.now(timezone.utc)
    # Gate: add Unverified and persist an expiry exactly one hour from join.
    try:
        unver = discord.utils.get(member.guild.roles, name="Unverified")
        if unver:
            await member.add_roles(unver, reason="join gate")
            deadline = now + VERIFY_TIMEOUT
            DB.setdefault("verification_deadlines", {})[f"{member.guild.id}:{member.id}"] = deadline.isoformat()
            DB.setdefault("verification_reminders", {}).pop(f"{member.guild.id}:{member.id}", None)
            save_data(DB)
            await log_to_botlogs(
                member.guild,
                text=f"⏳ Verification timer started for `{member}` (`{member.id}`); deadline <t:{int(deadline.timestamp())}:R>.",
            )
        else:
            await log_to_botlogs(member.guild, text="⚠️ New member joined, but role `Unverified` is missing; verification gate could not be assigned.")
    except Exception:
        await log_to_botlogs(member.guild, text=f"⚠️ Failed to assign `Unverified` to `{member}`; check Manage Roles and role hierarchy.")
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
        await member.send(WELCOME_DM_TEMPLATE.format(
            verify_channel="#✅・verify",
            guide_channel="#🗺️・server-guide",
            detection_channel="#🛡️・detection-log",
        ))
    except Exception:
        pass
    # public hacker-style welcome in #welcome (fallback #general)
    try:
        wch = welcome_channel(member.guild)
        if wch:
            age_days = max(age.days, 0)
            age_flag = "TRUSTED" if age > timedelta(days=30) else ("NEW" if age > timedelta(days=7) else "FRESH")
            em = discord.Embed(
                title=WELCOME_PUBLIC_TITLE,
                description=WELCOME_PUBLIC_DESCRIPTION_TEMPLATE.format(
                    username=member.name,
                    account_age_days=age_days,
                    member_count=member.guild.member_count,
                ),
                color=0x00FF41, timestamp=now)
            em.add_field(
                name=WELCOME_PUBLIC_FIELD_NAME,
                value=WELCOME_PUBLIC_FIELD_VALUE,
                inline=False)
            em.set_footer(text=f"node_id :: {member.id}")
            card = await make_welcome_card(member, age_days, age_flag, member.guild.member_count)
            if card:
                f = discord.File(card, filename="welcome.png")
                em.set_image(url="attachment://welcome.png")
                await wch.send(WELCOME_PUBLIC_MESSAGE_TEMPLATE.format(mention=member.mention), embed=em, file=f)
            else:
                await wch.send(WELCOME_PUBLIC_MESSAGE_TEMPLATE.format(mention=member.mention), embed=em)
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
            await log_to_botlogs(member.guild, text="⚠️ Voice greeting skipped: no ffmpeg found (system + bundled)")
            return
        from gtts import gTTS
        text = f"Welcome {member.display_name}"
        try:
            # clear natural English female voice, no pitch/rate shift
            import edge_tts
            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tf:
                path = tf.name
            await edge_tts.Communicate(text, "en-US-AriaNeural", rate="+0%", pitch="+0Hz").save(path)
        except Exception:
            try:
                with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tf:
                    gTTS(text=text, lang="en").save(tf.name)
                    path = tf.name
            except Exception as e:
                await log_to_botlogs(member.guild, text=f"⚠️ Voice greeting skipped: TTS failed ({type(e).__name__}: {e})")
                return
        try:
            # Force-clean any stale voice session first; a leftover voice websocket
            # from a previous connect is the usual cause of
            # "Cannot write to closing transport".
            old_vc = member.guild.voice_client
            if old_vc is not None:
                try:
                    await old_vc.disconnect(force=True)
                except Exception:
                    pass
                await asyncio.sleep(1)
            vc = await after.channel.connect(timeout=10, reconnect=False)
        except Exception as e:
            # One retry after a short delay: a just-closing voice websocket can
            # still reject the first connect attempt.
            try:
                await asyncio.sleep(2)
                vc = await after.channel.connect(timeout=10, reconnect=False)
            except Exception as e2:
                await log_to_botlogs(member.guild, text=f"⚠️ Voice greeting skipped: cannot join VC ({type(e2).__name__}: {e2})")
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
            await log_to_botlogs(member.guild, text=f"⚠️ Voice playback failed: {type(e).__name__}: {e!r}\n```{detail}```")
        finally:
            try:
                vc.stop()
            except Exception:
                pass
            try:
                await asyncio.sleep(0.5)
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

    unverified = discord.utils.get(msg.guild.roles, name="Unverified")
    if unverified and unverified in member.roles and not staff_bypass:
        try:
            await msg.delete()
        except discord.Forbidden:
            await log_to_botlogs(msg.guild, text=f"⚠️ Could not delete a message from Unverified member `{member}` in `#{msg.channel.name}`; check Manage Messages.")
        except discord.HTTPException:
            pass
        try:
            await member.send(UNVERIFIED_CHAT_REMINDER)
        except discord.HTTPException:
            pass
        return

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

DONOR_ROLE = "💗・Supporter"

CURRENCY_SYMBOLS = {
    "THB": "฿", "USD": "$", "EUR": "€", "GBP": "£", "JPY": "¥", "KRW": "₩",
    "SGD": "S$", "MYR": "RM", "CNY": "¥", "AUD": "A$", "PHP": "₱", "VND": "₫",
    "HKD": "HK$", "TWD": "NT$", "INR": "₹", "RUB": "₽",
}

DONOR_DM_TEMPLATE = (
    "💗 Thank you for supporting SockBoi's Payload!\n"
    "\n"
    "Your donation of **{display}** was received — you've been given the "
    "**💗・Supporter** role, including access to the private supporter lounge with "
    "early script access.\n"
    "\n"
    "— SockBoi\n"
    "\n"
    "*(automated message — no reply needed)*"
)

@bot.command()
@admin_only()
async def donate(ctx, member: discord.Member, amount: str, currency: str = "THB"):
    """ประกาศ donator ใหม่: ให้ Supporter + DM ขอบคุณ | !donate @user 100 THB"""
    role = discord.utils.get(ctx.guild.roles, name=DONOR_ROLE)
    if role is None:
        await ctx.send(f"ไม่พบ role `{DONOR_ROLE}` — สร้างก่อนใช้คำสั่งนี้")
        return
    cur = currency.upper()
    sym = CURRENCY_SYMBOLS.get(cur)
    display = f"{sym}{amount}" if sym else f"{amount} {cur}"
    try:
        if role not in member.roles:
            await member.add_roles(role, reason=f"donation {amount} {cur}")
        else:
            await ctx.send(f"ℹ️ {member.mention} มี role Supporter อยู่แล้ว — ส่ง DM ขอบคุณให้ใหม่")
    except discord.Forbidden:
        await ctx.send("ให้ role ไม่ได้ — role บอทต้องอยู่เหนือเป้าหมาย")
        return
    try:
        await member.send(DONOR_DM_TEMPLATE.format(display=display))
        dm_note = "DM ขอบคุณส่งแล้ว"
    except (discord.Forbidden, discord.HTTPException):
        dm_note = "ส่ง DM ไม่ได้ (ปิด DM ไว้)"
    await ctx.send(f"💗 {member.mention} รับ role `{DONOR_ROLE}` แล้ว · ยอด {display} · {dm_note}")
    await log_to_botlogs(ctx.guild, text=(
        f"💗 Donor added: `{member}` (`{member.id}`) — {display}, "
        f"role `{DONOR_ROLE}`, DM: {'sent' if 'ส่งแล้ว' in dm_note else 'failed'}"
    ))

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

ADMIN_STATUS = {
    "offshore": ("🛢️", "Offshore — ทำงานกลางทะเล", "ตอบช้าหน่อย เน็ตกลางทะเล 🌊", 0x3B82F6),
    "dayoff": ("🏖️", "Day Off", "พักผ่อน ตอบเมื่อว่าง", 0x00FF41),
    "gaming": ("🎮", "เล่นเกม", "ชวนจอยได้", 0x9B59B6),
    "online": ("🟢", "Online", "ว่างคุยได้", 0x00FF41),
}
ADMIN_ALIAS = {"ทะเล": "offshore", "พัก": "dayoff", "พักผ่อน": "dayoff",
               "เกม": "gaming", "ออนไลน์": "online", "ว่าง": "online"}

@bot.command()
@admin_only()
async def adminstatus(ctx, choice: str = "", *, note: str = ""):
    """ตั้งสถานะแอดมิน | !adminstatus offshore|dayoff|gaming|online [หมายเหตุ]"""
    key = ADMIN_ALIAS.get(choice, choice.lower())
    if key not in ADMIN_STATUS:
        await ctx.send("ใช้: `!adminstatus offshore|dayoff|gaming|online [หมายเหตุ]`\n(ไทย: ทะเล/พัก/เกม/ออนไลน์)")
        return
    emoji, title, desc, color = ADMIN_STATUS[key]
    if note:
        desc = f"{desc}\n💬 {note}"
    ch = discord.utils.get(ctx.guild.text_channels, name="🟢・admin-status")
    if not ch:
        await ctx.send("หาห้อง admin-status ไม่เจอ")
        return
    em = discord.Embed(title=f"{emoji} SockBoi Status: {title}", description=desc, color=color,
                       timestamp=datetime.now(timezone.utc))
    target = None
    async for m in ch.history(limit=20):
        if m.author == bot.user and m.embeds and "SockBoi Status" in (m.embeds[0].title or ""):
            target = m
            break
    if target:
        await target.edit(embed=em)
    else:
        target = await ch.send(embed=em)
        try:
            await target.pin(reason="admin status")
        except Exception:
            pass
    await ctx.send(f"✅ สถานะ: {emoji} {title}")

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
    await (ch or ctx.channel).send(VERIFY_SETUP_MESSAGE, view=VerifyView())

@bot.command()
@admin_only()
async def setup_roles(ctx):
    ch = discord.utils.get(ctx.guild.text_channels, name="🎖️・role-select")
    await (ch or ctx.channel).send(ROLE_SETUP_MESSAGE, view=RoleView())

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

async def health_http_handler(reader, writer):
    """Small internal HTTP server for platform probes; no web framework required."""
    try:
        request = await asyncio.wait_for(reader.readline(), timeout=5)
        parts = request.decode("latin-1", errors="replace").strip().split()
        path = parts[1].split("?", 1)[0] if len(parts) >= 2 else "/"
        while True:
            line = await asyncio.wait_for(reader.readline(), timeout=5)
            if line in (b"\r\n", b"\n", b""):
                break
        ready = bool(bot.is_ready() and gateway_connected)
        if path == "/livez":
            status, payload = 200, {"status": "alive"}
        elif path == "/readyz":
            status = 200 if ready else 503
            payload = {"status":"ready" if ready else "not_ready",
                       "discord_ready":bool(bot.is_ready()), "gateway_connected":gateway_connected,
                       "guild_available":bot.get_guild(GUILD_ID) is not None,
                       "latency_ms":round(bot.latency*1000,2) if bot.is_ready() else None,
                       "reconnect_attempts":gateway_reconnect_count,
                       "last_gateway_event":last_gateway_event}
        else:
            status, payload = 404, {"error":"not_found"}
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        reason = {200:"OK",404:"Not Found",503:"Service Unavailable"}[status]
        headers = (f"HTTP/1.1 {status} {reason}\r\n"
                   "Content-Type: application/json; charset=utf-8\r\n"
                   f"Content-Length: {len(body)}\r\n"
                   "Connection: close\r\n\r\n").encode("ascii")
        writer.write(headers + body)
        await writer.drain()
    except (asyncio.TimeoutError, ConnectionError, BrokenPipeError):
        pass
    finally:
        writer.close()
        with suppress(Exception):
            await writer.wait_closed()

async def run_bot():
    """Run the bot with signal-aware shutdown and a private health listener."""
    global gateway_monitor_task, verification_worker_task
    loop = asyncio.get_running_loop()
    shutdown_event = asyncio.Event()
    for sig in (signal.SIGINT, signal.SIGTERM):
        with suppress(NotImplementedError, RuntimeError):
            loop.add_signal_handler(sig, shutdown_event.set)
    health_server = await asyncio.start_server(health_http_handler, "0.0.0.0", PORT)
    print(f"[health] listening on 0.0.0.0:{PORT} (/livez, /readyz)", flush=True)
    bot_task = asyncio.create_task(bot.start(TOKEN, reconnect=True), name="discord-client")
    shutdown_task = asyncio.create_task(shutdown_event.wait(), name="shutdown-signal")
    try:
        done, _ = await asyncio.wait({bot_task, shutdown_task}, return_when=asyncio.FIRST_COMPLETED)
        if bot_task in done:
            await bot_task
        else:
            print("[shutdown] signal received; closing Discord client", flush=True)
            await bot.close()
            with suppress(asyncio.TimeoutError):
                await asyncio.wait_for(bot_task, timeout=20)
    finally:
        if not bot.is_closed():
            await bot.close()
        for task in (verification_worker_task, gateway_monitor_task):
            if task and not task.done():
                task.cancel()
                with suppress(asyncio.CancelledError):
                    await task
        if not bot_task.done():
            bot_task.cancel()
            with suppress(asyncio.CancelledError):
                await bot_task
        save_data(DB)
        shutdown_task.cancel()
        with suppress(asyncio.CancelledError):
            await shutdown_task
        health_server.close()
        await health_server.wait_closed()
        print("[shutdown] state saved; process stopped cleanly", flush=True)

if __name__ == "__main__":
    try:
        asyncio.run(run_bot())
    except KeyboardInterrupt:
        pass
