# AVRIA
AVRIA AI Trading Platform — demo-only prototype.

## Current components
- `index.html`: browser interface for simulated trades.
- `app.py`: FastAPI backend with SQLite account and trade endpoints.
- `/health`: basic service health check.
- `/api/account` and `/api/trades`: account and demo-trade data.

## Backend configuration
Set these environment variables in the hosting provider's secret/environment settings:

- `TELEGRAM_BOT_TOKEN`: token for the AVRIA Telegram bot. Keep it secret; never commit it to Git.
- `DEV_MODE=false`: required for public deployment. The default is already false.

The API validates Telegram Mini App `initData` using Telegram's HMAC-SHA-256 procedure, checks the signature and rejects authentication data older than 24 hours. Authenticated requests must send the raw Telegram WebApp `initData` in the `X-Telegram-Init-Data` header.

For local development only, `DEV_MODE=true` enables the `X-Demo-User` header. Do not enable this on a public service.

## Run the backend
Install dependencies from `requirements.txt`, then start:

```bash
uvicorn app:app --host 0.0.0.0 --port 8000
```

The SQLite database is created as `avria.sqlite3` beside `app.py`. A production host must provide persistent storage for this file; otherwise accounts and trades may be lost when the service is redeployed or restarted.

## Important current limitations
- This is a simulated-trading prototype. It does not place orders with brokers or exchanges.
- The backend and static GitHub Pages frontend are not yet deployed as one integrated service.
- The frontend still stores demo activity locally in the browser; server-side account synchronization is not yet connected.
- Live crypto quotes are indicative public market data. Forex/stock live quotes and AI-generated signals are not implemented.
- Do not use real funds or treat demo output as investment advice.
