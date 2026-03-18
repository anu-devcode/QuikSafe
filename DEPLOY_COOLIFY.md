# Deploy QuikSafe on DigitalOcean + Coolify

This guide deploys QuikSafe as a long-running Telegram bot service using only Coolify-managed resources.

## 1. Prepare DigitalOcean VM

1. Create an Ubuntu VM (2 GB RAM minimum recommended).
2. Install Coolify on the VM.
3. Add your Git repository to Coolify.

## 2. Create Coolify Resources

Create these resources inside the same Coolify project/environment:

1. PostgreSQL service
2. Optional Redis service (future session/cache scale-out)
3. App service from this repository (Dockerfile build)

## 3. Configure App Build in Coolify

1. Build method: Dockerfile
2. Base directory: /
3. Dockerfile path: ./Dockerfile
4. Build context: .
5. Start command: default from Dockerfile (python run.py)
6. Auto-deploy: enabled (optional)

If your repository is a monorepo, set Base directory to the folder that contains Dockerfile and run.py.

## 4. Set Environment Variables in Coolify

Set all of these on the app service:

- TELEGRAM_BOT_TOKEN
- BOT_USERNAME
- HUGGINGFACE_API_KEY
- ENCRYPTION_KEY
- DATABASE_URL
- DB_POOL_MIN_SIZE=1
- DB_POOL_MAX_SIZE=10
- DB_CONNECT_TIMEOUT=10
- DB_RUN_MIGRATIONS_ON_STARTUP=true
- DEBUG_MODE=false

For `DATABASE_URL`, use the internal Coolify connection string for your PostgreSQL service.

## 5. Telegram Integration Checklist

1. Create bot with BotFather.
2. Add token to `TELEGRAM_BOT_TOKEN`.
3. Set command list from BOTFATHER_SETUP.md.
4. Deploy app and open logs in Coolify.
5. Send `/start` to verify bot is live.

## 6. Production Recommendations

1. Keep DEBUG_MODE=false.
2. Restrict VM firewall to SSH and Coolify ingress only.
3. Enable daily PostgreSQL backups in Coolify.
4. Rotate TELEGRAM_BOT_TOKEN and HUGGINGFACE_API_KEY periodically.
5. Use Coolify health checks and restart policy (`always`).

## 7. Troubleshooting

- If app fails on startup, confirm `DATABASE_URL` and DB reachability.
- If Telegram commands do nothing, verify token and bot privacy settings.
- If AI calls fail, verify Hugging Face token permissions and quota.
- If build fails with "failed to read dockerfile: open Dockerfile: no such file or directory":
	- Ensure Dockerfile is committed and pushed to the same branch selected in Coolify.
	- Ensure Base directory points to the repository folder containing Dockerfile.
	- Ensure Dockerfile path is exactly ./Dockerfile.
