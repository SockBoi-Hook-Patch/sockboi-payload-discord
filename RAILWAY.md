# SockBoi Bot — รันบน Railway

## 1. สิ่งที่ repo เตรียมไว้ให้แล้ว
- `Dockerfile` — python 3.12 + ffmpeg + libopus0 + non-root user + health endpoint `/livez`
- `railway.toml` — build จาก Dockerfile, 1 replica, restart อัตโนมัติ
- `.dockerignore` — กัน `.env` / state เข้า image

## 2. ขั้นตอน deploy
1. railway.app → New Project → **Deploy from GitHub** → เลือก `SockBoi-Hook-Patch/sockboi-payload-discord`
2. Variables:
   - `DISCORD_BOT_TOKEN` = token (หลัง Reset)
   - `GUILD_ID` = `1555677417518137354`
   - `OWN_DOMAINS` = `facebook.com,fb.com,youtube.com,youtu.be,telegram.me,t.me,github.com,mediafire.com,earnpaste.com,linkvertise.com,link-target.net,ezdn.app,buymeacoffee.com`
   - `WELCOME_VOICE` = `1`
   - `PORT` = `8080`
   - `DATA_DIR` = `/data`
3. Persistent Volume (optional แต่แนะนำ): สร้าง volume แล้ว attach ที่ `/data`
4. Deploy → รอ logs — ต้องเห็น:
   `[health] listening on 0.0.0.0:8080 (/livez, /readyz)`
   `Logged in as ... — automate ON`
5. ใน Discord พิมพ์ `!status` เช็ก
6. Auto-deploy: Railway redeploy เองทุกครั้งที่ push ขึ้น `main`

## 3. ข้อควรรู้
- เป็น **worker** ไม่ใช่เว็บ API — ไม่ต้องเปิด public domain
- Railway ไม่มี free tier ถาวรแล้ว — ใช้เครดิต หรือ $5/เดือน (Hobby)
- Token ใส่ใน Railway Variables เท่านั้น ห้ามใส่ในไฟล์หรือ Git
- ถ้าเห็น crashed ดู Deploy Logs ช่วงสีแดงแล้วส่งมา
