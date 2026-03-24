# Cloudflare Tunnel + Zero Trust Access Setup

## What This Does

Your server never opens any inbound ports. `cloudflared` creates an outbound-only
encrypted tunnel to Cloudflare's global network:

```
User's browser → Cloudflare Edge → cloudflared tunnel → your Docker container
```

No IP address is exposed. No port scanning is possible.

## Prerequisites

- A domain on Cloudflare DNS (free plan works)
- Cloudflare Zero Trust account (free for up to 50 users)
- Docker and docker-compose installed

## Step 1: Create the Tunnel

1. Log into [dash.cloudflare.com](https://dash.cloudflare.com)
2. Go to **Zero Trust → Networks → Tunnels**
3. Click **"Create a tunnel"** → choose **Cloudflared**
4. Name it `trading-assistant`
5. Copy the tunnel token → paste into `CLOUDFLARE_TUNNEL_TOKEN` in your `.env`
6. In **"Public Hostname"**:
   - Subdomain: `trading` (or your preference)
   - Domain: your domain (must be on Cloudflare DNS)
   - Service: `http://nginx:80`
7. Save the tunnel

## Step 2: Configure Cloudflare Access

1. Go to **Zero Trust → Access → Applications**
2. Click **"Add an application"** → **Self-hosted**
3. Application name: `Trading Assistant`
4. Application domain: `trading.yourdomain.com`
5. Session duration: **8 hours** (matches JWT expiry)
6. Under **"Policies"** → Add a policy:
   - Policy name: `Owner only`
   - Action: **Allow**
   - Rule: **Emails** → `your-email@example.com`
7. Save

Only your specific email address can pass the Cloudflare Access gate.

## Step 3: Enable One-Time PIN Auth

1. Go to **Zero Trust → Settings → Authentication**
2. Confirm **"One-time PIN"** is in Login methods
3. No further IdP setup needed for personal use

## Step 4: Verify

1. Start the stack:
   ```bash
   docker-compose up -d
   ```
2. Visit `trading.yourdomain.com`
3. You should see Cloudflare Access login screen
4. Enter your email → receive OTP → enter OTP
5. You are now past **Layer 1** (Cloudflare)
6. You should see the app's own login screen (**Layer 2**)
7. Enter your app credentials → JWT issued
8. Dashboard loads

## Security Notes

- **Tunnel token** is a secret — treat it like a password
- If compromised: Zero Trust → Tunnels → **Revoke token** immediately
- A new token can be issued without changing anything else
- Cloudflare Access is **free** for personal use (up to 50 users)

## Recommended Cloudflare Settings

In your Cloudflare dashboard for the domain:

- SSL/TLS → Overview → **Full (strict)**
- SSL/TLS → Edge Certificates → Always Use HTTPS: **ON**
- SSL/TLS → Edge Certificates → HSTS: **Enable** (max-age 6 months, include subdomains)
- Security → Settings → Security Level: **Medium**
- Security → WAF → Managed Rules: **Enable Cloudflare Managed Ruleset**
- Security → Bots → Bot Fight Mode: **ON**
