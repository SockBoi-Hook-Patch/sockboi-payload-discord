# Oracle Cloud Always Free — SockBoi's Payload Discord Bot

เป้าหมาย: รันบอท 24/7 **ฟรีถาวร** บน Oracle Cloud Always Free VM

## 1. สมัคร Oracle Cloud Always Free
1. เข้า https://cloud.oracle.com/ → Sign up
2. เลือก Home Region ที่ใกล้ไทย (เช่น Singapore/Tokyo/Australia)
3. สร้าง "Always Free" compute instance:
   - Image: Ubuntu 22.04/24.04
   - Shape: `VM.Standard.A1.Flex` (Ampere ARM) — Free สูงสุด 4 OCPU + 24 GB RAM
   - Boot volume: 200 GB (Always Free)
4. ดาวน์โหลด private key `.pem` แล้วจำพิกัด SSH
5. Networking: เปิดพอร์ต SSH (22) เท่านั้น — บอทไม่ต้องเปิด port สาธารณะ (health endpoint อยู่ใน container ไม่ต้อง expose)

## 2. SSH เข้าเครื่อง
```bash
ssh -i ~/key.pem ubuntu@<PUBLIC_IP>
# ถ้าเป็น user อื่นตาม image (opc, ubuntu) ใช้ให้ถูก
```

## 3. ติดตั้ง Docker + เอา repo มา
```bash
sudo apt-get update
sudo apt-get install -y docker.io git
sudo systemctl enable --now docker
sudo usermod -aG docker $USER
# ออก/เข้า SSH ใหม่ แล้ว:
git clone https://github.com/SockBoi-Hook-Patch/sockboi-payload-discord.git
cd sockboi-payload-discord
```

## 4. สร้าง .env (ห้าม commit)
```bash
cat > .env <<'EOF'
DISCORD_BOT_TOKEN=ใส่โทเคนใหม่
GUILD_ID=1555677417518137354
WELCOME_VOICE=1
PORT=8080
DATA_DIR=/data
EOF
```

## 5. รัน container (auto-start + restart เสมอ)
```bash
docker build -t sockboi-payload-bot .
docker volume create sockboi_data
docker run -d --name sockboi-payload-bot \
  --restart=always \
  --env-file .env \
  -v sockboi_data:/data \
  sockboi-payload-bot
```
ตรวจ: `docker logs -f sockboi-payload-bot` — ต้องเห็น bot login สำเร็จ

## 6. (ทางเลือก) Health check อัตโนมัติ
Dockerfile มี HEALTHCHECK ชี้ `127.0.0.1:8080/livez` แล้ว — Docker จะ restart container เองถ้าค้าง

## 7. อัปเดตจาก GitHub ครั้งต่อไป
```bash
cd ~/sockboi-payload-discord
git pull --ff-only
docker build -t sockboi-payload-bot .
docker rm -f sockboi-payload-bot
docker volume inspect sockboi_data   # เก็บ state เดิม
docker run -d --name sockboi-payload-bot --restart=always --env-file .env -v sockboi_data:/data sockboi-payload-bot
```

## ข้อควรจำ
- ใช้ VM.Standard.A1.Flex (ARM) — image `linux/arm64` รองรับทุก package ใน repo นี้
- Oracle Always Free ไม่มี expiry ถ้าไม่เกิน quota
- อย่าเปิด port 8080 ออกสู่สาธารณะ — ไม่จำเป็น
