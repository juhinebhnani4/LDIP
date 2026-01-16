# LDIP Deployment Runbook

This document provides step-by-step procedures for deploying LDIP to production.

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Pre-Deployment Checklist](#pre-deployment-checklist)
3. [Initial Setup](#initial-setup)
4. [Vercel Setup (Frontend)](#vercel-setup-frontend)
5. [Railway Setup (Backend)](#railway-setup-backend)
6. [Supabase Setup](#supabase-setup)
7. [Upstash Redis Setup](#upstash-redis-setup)
8. [Post-Deployment Verification](#post-deployment-verification)
9. [Rollback Procedures](#rollback-procedures)
10. [Troubleshooting](#troubleshooting)

---

## Architecture Overview

```
Production Architecture:

   [Vercel]           [Railway]              [Supabase]         [Upstash]
   Next.js 16         FastAPI                PostgreSQL         Redis
   Frontend           Backend                + pgvector         Serverless
       │                 │                       │                  │
       └─────────────────┼───────────────────────┼──────────────────┘
                         │                       │
                    [Railway]              [Supabase Storage]
                    Celery Worker          Documents, OCR Outputs
```

| Service | Provider | Purpose |
|---------|----------|---------|
| Frontend | Vercel | Next.js 16 application hosting |
| Backend | Railway | FastAPI server + Celery workers |
| Database | Supabase | PostgreSQL with pgvector, RLS |
| Cache | Upstash | Serverless Redis for sessions/cache |
| Storage | Supabase | Document storage with RLS |

---

## Pre-Deployment Checklist

### Code Quality

- [ ] All tests passing locally (`npm test` in frontend, `pytest` in backend)
- [ ] No TypeScript errors (`npm run type-check`)
- [ ] No linting errors (`npm run lint` and `ruff check .`)
- [ ] Security tests pass (`pytest tests/security/`)

### Configuration

- [ ] All environment variables documented in `.env.example` files
- [ ] No secrets committed to repository
- [ ] Migrations ready for production database

### External Services

- [ ] Supabase project created (production)
- [ ] Upstash Redis database created
- [ ] API keys obtained:
  - [ ] OpenAI API key
  - [ ] Google Cloud credentials (Document AI)
  - [ ] Cohere API key
  - [ ] Axiom token (optional, for logging)

---

## Initial Setup

### 1. Fork/Clone Repository

```bash
git clone <repository-url>
cd LDIP
```

### 2. Verify Local Development Works

```bash
# Frontend
cd frontend
npm install
npm run dev

# Backend (separate terminal)
cd backend
uv sync
uv run uvicorn app.main:app --reload
```

---

## Vercel Setup (Frontend)

### Step 1: Connect Repository

1. Go to [vercel.com](https://vercel.com) and sign in
2. Click "Add New Project"
3. Import your GitHub repository
4. Select the repository containing LDIP

### Step 2: Configure Build Settings

| Setting | Value |
|---------|-------|
| Framework Preset | Next.js |
| Root Directory | `frontend` |
| Build Command | `npm run build` |
| Output Directory | `.next` |
| Install Command | `npm ci` |

### Step 3: Environment Variables

Add these in Vercel Dashboard → Settings → Environment Variables:

| Variable | Description | Example |
|----------|-------------|---------|
| `NEXT_PUBLIC_SUPABASE_URL` | Supabase project URL | `https://abc123.supabase.co` |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | Supabase anonymous key | `eyJ...` |
| `NEXT_PUBLIC_API_URL` | Railway backend URL | `https://ldip-backend.railway.app` |
| `NEXT_PUBLIC_USE_MOCK_PROCESSING` | Use mock APIs | `false` (production) |

### Step 4: Domain Configuration (Optional)

1. Go to Settings → Domains
2. Add your custom domain
3. Configure DNS records as instructed

### Step 5: Deploy

- **Automatic**: Pushes to `main` branch trigger production deploys
- **Manual**: Use GitHub Actions workflow `deploy-production.yml`

---

## Railway Setup (Backend)

### Step 1: Create Project

1. Go to [railway.app](https://railway.app) and sign in
2. Click "New Project"
3. Select "Deploy from GitHub repo"
4. Choose your repository

### Step 2: Configure Main Backend Service

1. Service name: `ldip-backend`
2. Root Directory: `backend`
3. Builder: `Dockerfile`
4. Start Command: (uses Dockerfile CMD)

Railway will detect the `railway.toml` configuration automatically.

### Step 3: Create Celery Worker Service

1. Click "New Service" in your Railway project
2. Service name: `ldip-worker`
3. Root Directory: `backend`
4. Builder: `Dockerfile`
5. Start Command: `celery -A app.workers.celery:celery_app worker --loglevel=info --concurrency=4`

### Step 4: Environment Variables

Add to both `ldip-backend` and `ldip-worker` services:

```env
# Application
DEBUG=false
API_VERSION=v1

# Supabase
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-anon-key
SUPABASE_SERVICE_KEY=your-service-role-key
SUPABASE_JWT_SECRET=your-jwt-secret

# Upstash Redis (use rediss:// for TLS)
REDIS_URL=rediss://default:password@host:6379
CELERY_BROKER_URL=rediss://default:password@host:6379/1
CELERY_RESULT_BACKEND=rediss://default:password@host:6379/2

# LLM API Keys
OPENAI_API_KEY=sk-...
GOOGLE_API_KEY=AIza...
COHERE_API_KEY=...
GEMINI_API_KEY=AIza...

# Google Cloud (Document AI)
GOOGLE_CLOUD_PROJECT_ID=your-project-id
GOOGLE_CLOUD_LOCATION=us
GOOGLE_DOCUMENT_AI_PROCESSOR_ID=your-processor-id

# CORS (your Vercel frontend URL)
CORS_ORIGINS=https://your-app.vercel.app

# Axiom Logging (optional)
AXIOM_TOKEN=xaat-...
AXIOM_DATASET=ldip-logs

# Rate Limits (defaults are fine for start)
RATE_LIMIT_DEFAULT=100
RATE_LIMIT_CRITICAL=30
RATE_LIMIT_SEARCH=60
```

### Step 5: Health Check Configuration

Railway should detect health check from `railway.toml`:
- Path: `/api/health`
- Timeout: 10 seconds

### Step 6: Scaling Configuration

In Railway Dashboard → Service Settings:

| Setting | Recommended Value |
|---------|-------------------|
| Replicas | 1 (start), scale to 2-3 as needed |
| Memory | 512MB minimum |
| CPU | 0.5 vCPU minimum |

---

## Supabase Setup

### Step 1: Create Production Project

1. Go to [supabase.com](https://supabase.com)
2. Create new project (select region close to Railway)
3. Note your project URL and keys

### Step 2: Enable Required Extensions

Run in SQL Editor:

```sql
-- Enable pgvector for embeddings
CREATE EXTENSION IF NOT EXISTS vector;

-- Enable text similarity
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- Enable UUID generation
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
```

### Step 3: Run Migrations

Option A - Using Supabase CLI:

```bash
cd supabase
supabase link --project-ref your-project-ref
supabase db push
```

Option B - Manual execution:
1. Go to SQL Editor in Supabase Dashboard
2. Run each migration file in order from `supabase/migrations/`

### Step 4: Verify RLS Policies

Check that all tables with `matter_id` have RLS enabled:

```sql
SELECT tablename, rowsecurity
FROM pg_tables
WHERE schemaname = 'public';
```

All tables should show `rowsecurity = true`.

### Step 5: Configure Storage Buckets

1. Go to Storage in Supabase Dashboard
2. Create buckets:

| Bucket | Public | Purpose |
|--------|--------|---------|
| `documents` | No (Private) | Original uploaded PDFs |
| `ocr-outputs` | No (Private) | Processed OCR JSON |

3. Add RLS policies to each bucket (Storage → Policies)

### Step 6: Configure Authentication

1. Go to Authentication → URL Configuration
2. Set:
   - Site URL: `https://your-production-domain.com`
   - Redirect URLs:
     - `https://your-production-domain.com/*`
     - `https://your-production-domain.com/auth/callback`

3. Configure JWT settings:
   - JWT expiry: 3600 (1 hour)
   - Enable refresh token rotation

### Step 7: Connection Pooling

For serverless compatibility, use Supavisor pooler:

1. Go to Settings → Database
2. Copy the "Connection pooling" connection string
3. Use this for high-concurrency scenarios

Format: `postgresql://postgres.[project-ref]:[password]@aws-0-[region].pooler.supabase.com:5432/postgres`

---

## Upstash Redis Setup

### Step 1: Create Database

1. Go to [upstash.com](https://upstash.com)
2. Create Redis database
3. Select region close to Railway backend
4. Enable TLS (required for production)

### Step 2: Get Connection Details

Note these from Upstash dashboard:

| Field | Use |
|-------|-----|
| Endpoint | Host for connection |
| Password | Authentication |
| Port | Usually 6379 |

### Step 3: Configure Connection URLs

Format for `rediss://` (TLS):

```
REDIS_URL=rediss://default:{password}@{endpoint}:6379
CELERY_BROKER_URL=rediss://default:{password}@{endpoint}:6379/1
CELERY_RESULT_BACKEND=rediss://default:{password}@{endpoint}:6379/2
```

### Step 4: Verify Key Patterns

The application uses these Redis key patterns:

| Pattern | Purpose | TTL |
|---------|---------|-----|
| `session:{matter_id}:{user_id}:{type}` | Session memory | 7 days |
| `cache:query:{matter_id}:{hash}` | Query cache | 1 hour |
| `matter:{matter_id}:{type}` | Matter data | No expiration |
| `summary:{matter_id}` | Summary cache | 1 hour |
| `embedding:{hash}` | Embedding cache | 24 hours |
| `celery-*` | Celery queues | Varies |

---

## Post-Deployment Verification

### Automated Health Checks

```bash
# Backend health
curl https://your-backend.railway.app/api/health

# Expected response:
# {"status": "healthy", "services": {...}}
```

### Manual Verification Checklist

- [ ] Frontend loads at production URL
- [ ] Login/signup flow works
- [ ] File upload works
- [ ] Document processing completes
- [ ] Q&A chat returns responses
- [ ] Axiom logs appear (if configured)

### Security Verification

- [ ] CORS blocks requests from unauthorized origins
- [ ] RLS policies prevent cross-matter access
- [ ] Service role key not exposed in frontend

---

## Rollback Procedures

### Vercel Rollback

1. Go to Vercel Dashboard → Deployments
2. Find the previous working deployment
3. Click "..." → "Promote to Production"

### Railway Rollback

1. Go to Railway Dashboard → Service → Deployments
2. Click on previous deployment
3. Click "Rollback"

### Database Rollback

**CAUTION**: Database rollbacks can cause data loss.

1. Create backup before any changes
2. For schema changes, apply reverse migration
3. For data issues, restore from backup

---

## Troubleshooting

### Common Issues

#### Backend Not Starting

1. Check Railway logs for error messages
2. Verify all environment variables are set
3. Ensure Redis is accessible (check TLS settings)

#### Frontend Build Failing

1. Check Vercel build logs
2. Verify TypeScript errors are resolved
3. Check environment variables are available at build time

#### Database Connection Issues

1. Verify Supabase URL and keys
2. Check if using pooler URL for high-concurrency
3. Verify RLS policies don't block the service role

#### Redis Connection Timeout

1. Verify using `rediss://` (TLS) protocol
2. Check Upstash dashboard for connection status
3. Verify SSL configuration in Celery

### Getting Help

1. Check Vercel/Railway/Supabase status pages
2. Review application logs (Axiom or platform logs)
3. Contact platform support for infrastructure issues

---

## Security Reminders

1. **Never commit `.env` files** - only `.env.example`
2. **Rotate secrets regularly** - especially after any suspected breach
3. **Use platform secrets** - not environment files in production
4. **Monitor for anomalies** - check logs for unusual patterns
5. **Keep dependencies updated** - run `npm audit` and `pip audit` regularly

---

*Last updated: 2026-01-16*
