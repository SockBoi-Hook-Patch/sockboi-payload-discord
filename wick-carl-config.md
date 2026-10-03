# SockBoi's Payload — Wick / Carl-bot / MEE6 / Ticket Tool config
# Paste these into each bot dashboard after inviting them with Administrator (Wick) / Manage Server (others).

## 1. Invite order
1. Wick BOT — https://wickbot.com/invite — give Administrator, place Wick role ABOVE all custom roles, enable Anti-Nuke + Anti-Raid ON.
2. Carl-bot — https://carl.gg — Reaction roles + Automod + Logging.
3. MEE6 or Combot — leveling + welcome + slowmode triggers.
4. Ticket Tool — https://tickettool.xyz — private mod requests.

## 2. Wick — token protection + anti-raid
- Protection > Token Protection: ON, action = Delete + Mute, log to #🚨・bot-logs
- Custom regex (if Wick allows custom): `[MN][A-Za-z\d]{23}\.[\w-]{6}\.[\w-]{27}`
- DM message (ตั้ง 2 ภาษา): "Token sharing is prohibited. Contact SockBoi if this was a mistake. / ห้ามแชร์ token ถ้าเข้าใจผิดติดต่อ SockBoi"
- Anti-Raid: verification gate ON (new joins get Unverified only), flag accounts < 7 days old, join rate > 10/min → enable slowmode 30s in #💬・general + alert #🚨・bot-logs
- Whitelist roles for links: Verified Modder and up bypass link filter.

## 3. Carl-bot — automod + logging + reaction roles
### Automod (carl.gg/dashboard > Automod)
- Banned words (regex): `discord\.com/api/webhooks/\d+/[\w-]+`, `fre+\s*nitr[o0]`, `ฟรี.*ไนโตร|ไนโตร.*ฟรี|แจก.*ไนโตร|แจก.*nitro|ฟรี.*nitro` + คำไทย: ฟรีไนโตร, แจกไนโตร, สแกนรับ, แจกเพชรฟรี
- Invite/link filter: block all links in #💬・general and #❓・help except roles >= Verified Modder. Whitelist: `github.com/*`, `t.me/*`, `telegram.me/*` (+ add your own domains here: ________________)
- APK links: only allow in #📱・mod-releases by Core Dev+. Set rule: delete + warn elsewhere.
- Spam: same message 3x in 10s → delete, timeout 10 min first, 1h repeat. Punishment ladder in Carl: Warn > Mute 10m > Mute 1h > Kick.
- Token regex duplicate (defense in depth): `[MN][A-Za-z\d]{23}\.[\w-]{6}\.[\w-]{27}` → delete + mute + log to #🚨・bot-logs with user ID + timestamp (redact token).

### Logging (feed to #🚨・bot-logs)
- Log: message delete/edit, join/leave, role add/remove, mod actions, automod triggers.

### Reaction roles (for #✅・verify and #🎖️・role-select)
- #✅・verify: ✅ → add Member, remove Unverified. Mode: unique, allow re-verify.
  Command: `?rr add #✅・verify :white_check_mark: @Member` (then set remove Unverified in dashboard).
- #🎖️・role-select suggestions: game preference / platform (Android / Root / No-Root / Emulator). Create optionals as plain roles (no perms), self-assign only.

## 4. MEE6 (or Combot) — leveling + welcome + slowmode
- Welcome: DM + #💬・general (2 ภาษา): "ยินดีต้อนรับ {user} — ไปยืนยันที่ #✅・verify อ่าน #🗺️・server-guide เช็ก #🛡️・detection-log ก่อนเล่นแรงก์ / Welcome {user} — verify in #✅・verify, read guide, check detection-log before ranked."
- Leveling: enable in COMMUNITY only, disable XP in DROPS (avoid farm). Reward: Level 5 → Script Tester (manual approval by SockBoi/Core Dev).
- Slowmode trigger: if joins > 10/min → set #💬・general slowmode 30s (manual or via MEE6 custom command).

## 5. Ticket Tool — private mod requests
- Panel in #📥・request-mods: "Request a mod" → opens private ticket visible to Core Dev+.
- Required fields: Game name, version/code, Root? (Y/N), Mod features wanted, Screenshot of error.
- Close reason required; transcripts to #🛠️・mod-workshop.

## 6. Manual checklist Discord template CANNOT do (must click)
- [ ] Server Settings > Safety Setup > explicit filter ALL, verification MEDIUM (script already tries).
- [ ] Set #🚨・bot-logs as all bots' log channel.
- [ ] Pin welcome embed in #🗺️・server-guide.
- [ ] Lock #📣・announcements / #📱・mod-releases / #📜・script-releases to SockBoi/Core Dev send-only (script sets this).
- [ ] 2FA requirement for mods: Server Settings > Moderation > Require 2FA for mod actions ON.
- [ ] Vanity / widget / community onboarding as desired.
