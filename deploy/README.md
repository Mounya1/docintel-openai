# Deploying DocIntel for $0/month

```
Browser ──HTTPS──> Vercel (React static build)               free (Hobby)
   │
   └──HTTPS──> Oracle Cloud VM: Caddy (Let's Encrypt) ──> FastAPI container   free (Always Free)
                                                          ├──> Neon Postgres   free
                                                          └──> S3 bucket       ~cents
```

The only running cost is OpenAI usage. Set a monthly limit at
platform.openai.com → Settings → Limits.

## 1. Neon database

1. Sign up at neon.tech → create project `docintel`, region **AWS US East 1**.
2. Dashboard → **Connect** → turn **Connection pooling OFF** → copy the connection string.
   It looks like `postgresql://neondb_owner:...@ep-xxxx.us-east-1.aws.neon.tech/neondb?sslmode=require`.
   The host must **not** contain `-pooler`.

## 2. Oracle Cloud VM

1. Sign up at cloud.oracle.com (a card is needed for verification, but Always Free resources are never charged).
   Choose your home region carefully: Always Free compute only runs there.
2. Compute → Instances → **Create instance**:
   - Image: **Canonical Ubuntu 24.04**
   - Shape: **Ampere VM.Standard.A1.Flex**, 1 OCPU / 6 GB RAM (Always Free).
     If it says "out of capacity", retry later or use **VM.Standard.E2.1.Micro** (also free).
   - Networking: create a new VCN with a public subnet, **assign a public IPv4 address**
   - SSH keys: generate and download the private key
3. Instance → Subnet → **Security List** → Add Ingress Rules:
   source `0.0.0.0/0`, TCP, destination ports **80** and **443**.
4. Optional: make the IP permanent with Networking → **Reserved Public IPs**, and
   attach it to the instance. Otherwise the IP can change if the instance is recreated.

Your API hostname is the public IP with dashes + `.sslip.io`,
e.g. `129.146.20.15` → `129-146-20-15.sslip.io`.

## 3. Bootstrap the server

```bash
chmod 600 ssh-key.key
ssh -i ssh-key.key ubuntu@<public-ip>
curl -fsSL https://raw.githubusercontent.com/Mounya1/docintel-openai/main/deploy/setup-server.sh | bash
exit   # log back in so the docker group applies
```

```bash
cd ~/docintel-openai/deploy
cp .env.prod.example .env.prod
nano .env.prod      # API_DOMAIN, DATABASE_URL (Neon), OPENAI_API_KEY, secrets, S3 keys
```

## 4. Migrate the old Render database (optional, before first start)

Render dashboard → database → copy the **External Database URL**. On the server:

```bash
SOURCE_URL='postgresql://...render.com/docintel' \
TARGET_URL='<Neon connection string from step 1>' \
./migrate-db.sh
```

Skip this if the Render database has expired or you want a fresh start.
Uploaded files are already in S3, so they need no copying.

## 5. Start the API

```bash
./deploy.sh
curl https://<API_DOMAIN>/api/health
```

The first request may take ~30s while Caddy obtains the certificate. To ship
updates later: `git push`, then run `~/docintel-openai/deploy/deploy.sh` on the server.

## 6. Frontend on Vercel

vercel.com → Add New → Project → import `Mounya1/docintel-openai`:
- **Root Directory:** `frontend`
- Framework: Vite (auto-detected; `frontend/vercel.json` pins the settings)
- Environment variable: `VITE_API_BASE_URL` = `https://<API_DOMAIN>`

Deploy. Every push to `main` redeploys automatically. Put the resulting
`https://<project>.vercel.app` into `FRONTEND_URL` in `.env.prod` and rerun `./deploy.sh`.

## 7. After it works

- Log in and change the passwords of the seeded `admin@docintel.ai` / `reviewer@docintel.ai`
  accounts. Their defaults are public in the source and on `/docs`.
- Add a free UptimeRobot monitor on `https://<API_DOMAIN>/api/health` to get an
  email when the API goes down.
- Oracle can reclaim Always Free instances on free-trial accounts that stay
  nearly idle for 7 days. Upgrading the account to **Pay As You Go** avoids this,
  and Always Free resources stay free. Set a budget alert at $1 to be safe.
- Suspend the Render services so you aren't running two copies.

## Limits to know

- **Vercel Hobby** is for non-commercial use. Move to Pro once you charge customers.
- **Neon free** has 0.5 GB storage per project and suspends compute when idle
  (the first query after a pause takes ~1s).
- **Upgrading later** needs no code changes, only a different `DATABASE_URL` or server:
  the same `deploy/` files work on AWS EC2, Hetzner or DigitalOcean.
