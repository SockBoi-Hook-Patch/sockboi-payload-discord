# Fly.io Deployment — SockBoi's Payload Discord Bot

This repo is already Fly.io-ready (Dockerfile + `/livez` health endpoint on port 8080).
Follow these steps once.

## 1. Install flyctl + login
```powershell
powershell -Command "iwr https://fly.io/install.ps1 -useb | iex"
fly auth signup   # or fly auth login
```

## 2. Create the app + volume (pick a unique app name)
```powershell
fly apps create sockboi-payload-discord
fly volumes create sockboi_data --region sin --size 1
```
> If the name is taken, use another, e.g. `sockboi-payload-bot2`. Change `app =` in fly.toml to match.

## 3. Set secrets
```powershell
fly secrets set DISCORD_BOT_TOKEN=<โทเคนใหม่> GUILD_ID=1555677417518137354
```

## 4. Deploy
```powershell
fly deploy
```

## 5. เช็กหลัง deploy
```powershell
fly logs               # ต้องเห็น "[health] listening on 0.0.0.0:8080" และ bot login สำเร็จ
fly status             # ต้องเป็น started
```
หรือ `fly proxy 8080` แล้วเปิด http://127.0.0.1:8080/livez ต้องตอบ 200

## Auto-deploy จาก GitHub (optional)
Fly ไม่มี auto-deploy จาก push ในแผนฟรีโดยตรงแบบ Northflank บาง platform ใช้ `fly deploy` มือ หรือผูก GitHub Actions เรียก `flyctl deploy --remote-only` โดยใช้ secret `FLY_API_TOKEN` (สร้างด้วย `fly tokens create deploy`)

## ข้อควรจำ
- เป็น worker ไม่ใช่เว็บ API — อย่าตั้ง auto-stop เป็น off เด็ดขาด
- ถ้าใช้ volume ต้อง mount ที่ `/data` เท่านั้น
- Token ให้ตั้งเป็น secret เท่านั้น ห้ามใส่ใน Git
