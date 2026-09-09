# Settle Up — Production Vercel & PostgreSQL (Neon) Deployment Guide

This guide details how to configure, test, and deploy **Settle Up** to **Vercel** with a dual-database architecture:
* **Local Development:** SQLite (`settleup.db`)
* **Production (Vercel):** Hosted PostgreSQL (such as **Neon**)

---

## Architecture Overview

```
                               ┌────────────────────────────────┐
                               │       Vercel Edge / CDN        │
                               └───────────────┬────────────────┘
                                               │
                       ┌───────────────────────┴───────────────────────┐
                       ▼                                               ▼
         Static SPA Assets (HTML, CSS, JS)                API Routes (/api/*)
           Served directly by Vercel CDN                  api/index.py (Flask WSGI)
                                                                       │
                                                       ┌───────────────┴───────────────┐
                                                       ▼                               ▼
                                             Neon PostgreSQL Database       Persistent Object Storage
                                            (NullPool serverless pool)     (Vercel Blob / Cloudinary / S3)
```

---

## 1. Local SQLite Setup

By default, local development uses SQLite without requiring any complex configuration.

1. Create or verify your local `.env` file:
   ```bash
   cp .env.example .env
   ```
2. In `.env`, ensure the environment is set to development:
   ```ini
   FLASK_ENV=development
   FLASK_DEBUG=True
   DATABASE_URL=sqlite:///settleup.db
   STORAGE_PROVIDER=local
   UPLOAD_FOLDER=uploads/proofs
   SECRET_KEY=settleup-dev-secret-key-change-for-production
   ```
3. Run the development server:
   ```bash
   python server.py --host 127.0.0.1 --port 5000
   ```
4. Access the web application at `http://127.0.0.1:5000/?room=GOA2026`.

---

## 2. Production PostgreSQL Setup (Neon)

Vercel functions are serverless and have ephemeral filesystems. SQLite files cannot be written permanently on Vercel. A hosted PostgreSQL database is required.

### Setting up Neon PostgreSQL:
1. Sign up or log in at [neon.tech](https://neon.tech).
2. Create a new project (e.g., `settle-up-prod`).
3. Select your preferred region (choose a region close to your primary users or Vercel region, e.g., `us-east-1` or `eu-central-1`).
4. In the Neon Console Dashboard, copy your connection string.
5. Select the **Pooled connection** checkbox if available (recommended for serverless functions).
6. Your connection string will look like:
   ```
   postgresql://alex:AbC123dEf@ep-cool-fog-123456-pooler.us-east-2.aws.neon.tech/neondb?sslmode=require
   ```

---

## 3. Database Initialization & Data Migration

### Automatic Schema Initialization:
When your backend boots up on Vercel with `DATABASE_URL` configured, `init_database` automatically runs:
- Executes `db.create_all()` to create all tables (`users`, `rooms`, `members`, `expenses`, `expense_splits`, `settlements`, `join_requests`, `balance_records`, `room_invitations`).
- Checks and applies any missing column migrations non-destructively.
- Caches the initialized engine state in-memory so subsequent warm serverless invocations execute in $O(1)$ without database roundtrips.

### Optional: Migrating Existing Local SQLite Data:
If you want to copy your existing local SQLite data from `settleup.db` to Neon:
1. Preview the records to migrate (dry-run):
   ```bash
   python migrate_sqlite_to_postgres.py --dry-run
   ```
2. Execute the non-destructive migration:
   ```bash
   python migrate_sqlite_to_postgres.py --commit --target-url "postgresql://<user>:<password>@<neon-host>/neondb?sslmode=require"
   ```
> [!NOTE]
> The migration script reads `settleup.db` in read-only mode and checks existing IDs in PostgreSQL to avoid duplicates. It will never drop or modify your local SQLite file.

---

## 4. Required Environment Variables

Configure these variables in your **Vercel Project Settings → Environment Variables**:

| Variable Name | Required | Example / Format | Description |
|---|---|---|---|
| `FLASK_ENV` | **Yes** | `production` | Enables production mode and strict security checks. |
| `SECRET_KEY` | **Yes** | 64-char hex string | Cryptographic key for JWT/session security. |
| `DATABASE_URL` | **Yes** | `postgresql://...` | Neon PostgreSQL connection URI with `?sslmode=require`. |
| `STORAGE_PROVIDER` | **Yes** | `vercel_blob` / `cloudinary` / `s3` | Persistent object storage provider for payment proofs. |
| `CORS_ORIGINS` | No | `*` or `https://your-app.vercel.app` | Allowed CORS origins. |
| `AUTO_INIT_DB` | No | `True` (default) | Automatically creates tables and migrations on startup. |
| `SEED_SAMPLE_DATA`| No | `False` (default) | Prevents populating the sample Goa trip on production. |

### Generating a Secure SECRET_KEY:
Run this command in your terminal to generate a cryptographically strong key:
```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

---

## 5. Payment-Proof Storage Configuration

Because serverless runtimes discard local file changes upon container termination, local disk storage is blocked in production. Configure **ONE** of the following cloud storage options:

### Option A: Vercel Blob (Recommended for Vercel)
1. In your Vercel Project Dashboard, navigate to the **Storage** tab.
2. Click **Create Database** and select **Blob**.
3. Link the Blob store to your project.
4. Set the following environment variables:
   ```ini
   STORAGE_PROVIDER=vercel_blob
   BLOB_READ_WRITE_TOKEN=vercel_blob_rw_xxxxxxxxxxxxxxxxxxxxxxxx
   ```

### Option B: Cloudinary
1. Sign up at [cloudinary.com](https://cloudinary.com).
2. Retrieve your credentials from the Cloudinary Dashboard.
3. Configure in Vercel:
   ```ini
   STORAGE_PROVIDER=cloudinary
   CLOUDINARY_CLOUD_NAME=your_cloud_name
   CLOUDINARY_API_KEY=your_api_key
   CLOUDINARY_API_SECRET=your_api_secret
   ```

### Option C: AWS S3 or Cloudflare R2
1. Create an S3 Bucket or Cloudflare R2 bucket.
2. Configure in Vercel:
   ```ini
   STORAGE_PROVIDER=s3
   AWS_S3_BUCKET=settleup-proofs
   AWS_REGION=us-east-1
   AWS_ACCESS_KEY_ID=your_access_key
   AWS_SECRET_ACCESS_KEY=your_secret_key
   ```

---

## 6. Local Testing Before Deployment

### 1. Run the Full Test Suite:
Run all existing unit and integration tests:
```bash
python test_algorithm.py
python -m unittest test_invitations.py
python -m unittest test_payment_proof.py
python -m unittest test_server.py
```

### 2. Verify Vercel Serverless Function Loading:
Ensure Python can load the WSGI entrypoint without errors:
```bash
python -c "import api.index; print('Vercel entrypoint loaded successfully')"
```

### 3. Verify Remote PostgreSQL Connection (Optional):
Once you have your Neon `DATABASE_URL`, test connecting and initializing tables from your machine:
```bash
DATABASE_URL="postgresql://user:pass@host/neondb?sslmode=require" python server.py --init-db
```

---

## 7. Deployment Steps to Vercel

### Step 1: Connect Repository to Vercel
1. Push your code to your GitHub/GitLab repository (when you are ready).
2. Go to [vercel.com/new](https://vercel.com/new).
3. Import your Settle-Up repository.

### Step 2: Configure Build & Output Settings
Vercel automatically detects the project layout via `vercel.json`:
- **Framework Preset:** Other
- **Root Directory:** `./`
- **Build Command:** *(Leave blank or default)*
- **Output Directory:** *(Leave blank or default)*

### Step 3: Add Environment Variables
Add the production environment variables in the Vercel dashboard:
- `FLASK_ENV` = `production`
- `SECRET_KEY` = `(your generated 64-char hex key)`
- `DATABASE_URL` = `(your Neon PostgreSQL connection string)`
- `STORAGE_PROVIDER` = `vercel_blob` (or `cloudinary` / `s3`)
- Storage credentials for your selected provider (e.g. `BLOB_READ_WRITE_TOKEN`)

### Step 4: Deploy
Click **Deploy**. Vercel will:
1. Install dependencies from `requirements.txt` (including `psycopg2-binary`).
2. Package the static frontend (`index.html`, `src/`).
3. Build the serverless Python API function (`api/index.py`).

### Step 5: Verify Deployment
1. Visit `https://<your-project>.vercel.app/api/health`
   Expected response:
   ```json
   {
     "app": "Settle Up",
     "database": "PostgreSQL (SQLAlchemy)",
     "status": "ok",
     "version": "1.0.0"
   }
   ```
2. Visit `https://<your-project>.vercel.app/`
   Verify that the frontend loads, rooms can be created/opened, expenses added, and settlement workflows function smoothly.

---

## 8. Security Considerations

1. **No SQLite in Production:** `.vercelignore` blocks `settleup.db`, `*.sqlite`, `*.db`, `instance/`, and `uploads/`. The application will raise a fatal startup exception if SQLite is attempted in production mode.
2. **Never Commit Secrets:** `.gitignore` excludes `.env` and `.env.*`. Only `.env.example` with placeholders is tracked.
3. **Database SSL:** Neon requires `sslmode=require`. Ensure your `DATABASE_URL` retains `?sslmode=require`.
4. **Serverless Connection Pooling:** The application uses SQLAlchemy `NullPool` in production to prevent connection leaks across ephemeral serverless containers.
5. **Private Payment Proofs:** Uploaded payment proofs are validated with magic-byte format checks, given cryptographically random filenames, and served via authenticated routes or short-lived presigned URLs.
