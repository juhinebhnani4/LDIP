# Environment Variables Reference

Complete reference for all environment variables used in LDIP.

## Table of Contents

1. [Frontend Variables](#frontend-variables)
2. [Backend Variables](#backend-variables)
3. [Variable Sources](#variable-sources)
4. [Example Files](#example-files)

---

## Frontend Variables

### Required Variables

| Variable | Description | Example | Where to Get |
|----------|-------------|---------|--------------|
| `NEXT_PUBLIC_SUPABASE_URL` | Supabase project URL | `https://abc123.supabase.co` | Supabase Dashboard → Settings → API |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | Supabase anonymous/public key | `eyJhbGciOiJIUzI1NiIs...` | Supabase Dashboard → Settings → API |
| `NEXT_PUBLIC_API_URL` | Backend API URL | `https://ldip-backend.railway.app` | Railway Dashboard → Service → Settings → Domains |

### Optional Variables

| Variable | Description | Default | Notes |
|----------|-------------|---------|-------|
| `NEXT_PUBLIC_USE_MOCK_PROCESSING` | Use mock APIs for uploads | `false` | Set `true` for local dev without backend |

### Build-time vs Runtime

- All `NEXT_PUBLIC_*` variables are embedded at **build time**
- Changing them requires a new deployment
- Never put secrets in `NEXT_PUBLIC_*` variables

---

## Backend Variables

### Application Settings

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `DEBUG` | Enable debug mode | `false` | No |
| `API_VERSION` | API version prefix | `v1` | No |

### Supabase Configuration

| Variable | Description | Example | Required |
|----------|-------------|---------|----------|
| `SUPABASE_URL` | Project URL | `https://abc.supabase.co` | Yes |
| `SUPABASE_KEY` | Anonymous key (for client ops) | `eyJ...` | Yes |
| `SUPABASE_SERVICE_KEY` | Service role key (admin ops) | `eyJ...` | Yes |
| `SUPABASE_JWT_SECRET` | JWT secret for token validation | `super-secret...` | Yes |

**Getting Supabase Keys:**
1. Go to Supabase Dashboard
2. Navigate to Settings → API
3. Copy the appropriate keys

### Redis / Upstash Configuration

| Variable | Description | Example | Required |
|----------|-------------|---------|----------|
| `REDIS_URL` | Main Redis connection | `rediss://default:pass@host:6379` | Yes |
| `CELERY_BROKER_URL` | Celery message broker | `rediss://default:pass@host:6379/1` | Yes |
| `CELERY_RESULT_BACKEND` | Celery result storage | `rediss://default:pass@host:6379/2` | Yes |

**Important:** Use `rediss://` (with double 's') for TLS connections to Upstash.

### LLM API Keys

| Variable | Description | Purpose | Required |
|----------|-------------|---------|----------|
| `OPENAI_API_KEY` | OpenAI API key | GPT-4 for reasoning | Yes |
| `GOOGLE_API_KEY` | Google AI API key | Gemini for extraction | Yes |
| `GEMINI_API_KEY` | Gemini API key (may be same as Google) | OCR validation | Yes |
| `COHERE_API_KEY` | Cohere API key | Reranking search results | Yes |

### Google Cloud (Document AI)

| Variable | Description | Example | Required |
|----------|-------------|---------|----------|
| `GOOGLE_CLOUD_PROJECT_ID` | GCP project ID | `ldip-prod-123` | Yes |
| `GOOGLE_CLOUD_LOCATION` | Processing region | `us` | Yes |
| `GOOGLE_DOCUMENT_AI_PROCESSOR_ID` | OCR processor ID | `abc123def456` | Yes |

**Note:** For production, you may need to mount a service account JSON file or configure Workload Identity.

### Model Configuration

| Variable | Description | Default |
|----------|-------------|---------|
| `GEMINI_MODEL` | Gemini model for extraction | `gemini-3-flash` |
| `OPENAI_COMPARISON_MODEL` | GPT model for reasoning | `gpt-4-turbo-preview` |
| `OPENAI_INTENT_MODEL` | Model for query classification | `gpt-3.5-turbo` |
| `OPENAI_SAFETY_MODEL` | Model for safety checks | `gpt-4o-mini` |

### CORS Configuration

| Variable | Description | Example |
|----------|-------------|---------|
| `CORS_ORIGINS` | Allowed frontend origins | `https://ldip.vercel.app` |

**Format:** Single URL or comma-separated list (configured as Python list in code).

### Observability

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `AXIOM_TOKEN` | Axiom API token | `""` | No |
| `AXIOM_DATASET` | Axiom dataset name | `ldip-logs` | No |

### Rate Limiting

| Variable | Description | Default |
|----------|-------------|---------|
| `RATE_LIMIT_DEFAULT` | Standard endpoint limit/min | `100` |
| `RATE_LIMIT_CRITICAL` | LLM/export endpoints | `30` |
| `RATE_LIMIT_SEARCH` | Search endpoints | `60` |
| `RATE_LIMIT_READONLY` | Dashboard endpoints | `120` |
| `RATE_LIMIT_HEALTH` | Health check endpoints | `300` |
| `RATE_LIMIT_EXPORT` | Export generation | `20` |

### OCR Configuration

| Variable | Description | Default |
|----------|-------------|---------|
| `OCR_VALIDATION_GEMINI_THRESHOLD` | Trigger Gemini validation below | `0.85` |
| `OCR_VALIDATION_HUMAN_THRESHOLD` | Flag for human review below | `0.50` |
| `OCR_VALIDATION_BATCH_SIZE` | Words per Gemini request | `20` |

### Chunking Configuration

| Variable | Description | Default |
|----------|-------------|---------|
| `CHUNK_PARENT_SIZE` | Parent chunk size (tokens) | `1750` |
| `CHUNK_PARENT_OVERLAP` | Parent overlap (tokens) | `100` |
| `CHUNK_CHILD_SIZE` | Child chunk size (tokens) | `550` |
| `CHUNK_CHILD_OVERLAP` | Child overlap (tokens) | `75` |

### Verification Thresholds

| Variable | Description | Default |
|----------|-------------|---------|
| `VERIFICATION_THRESHOLD_OPTIONAL` | Above = optional verification | `90.0` |
| `VERIFICATION_THRESHOLD_SUGGESTED` | Above = suggested verification | `70.0` |
| `VERIFICATION_EXPORT_BLOCK_BELOW` | Below = block export | `70.0` |

### Feature Flags

| Variable | Description | Default |
|----------|-------------|---------|
| `SAFETY_LLM_ENABLED` | Enable LLM safety checks | `true` |
| `LANGUAGE_POLICING_ENABLED` | Enable output sanitization | `true` |
| `POLICING_LLM_ENABLED` | Enable LLM polish | `true` |

---

## Variable Sources

### Where to Find Each Value

| Service | Dashboard URL | What to Get |
|---------|---------------|-------------|
| Supabase | `supabase.com/dashboard` | URL, anon key, service key, JWT secret |
| Upstash | `console.upstash.com` | Redis URL, password |
| OpenAI | `platform.openai.com` | API key |
| Google Cloud | `console.cloud.google.com` | API key, project ID, processor ID |
| Cohere | `dashboard.cohere.com` | API key |
| Axiom | `app.axiom.co` | API token, dataset name |

---

## Example Files

### Frontend (.env.local)

```env
# Supabase
NEXT_PUBLIC_SUPABASE_URL=https://your-project.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...

# Backend API
NEXT_PUBLIC_API_URL=https://your-backend.railway.app

# Feature flags
NEXT_PUBLIC_USE_MOCK_PROCESSING=false
```

### Backend (.env)

```env
# Application
DEBUG=false
API_VERSION=v1

# Supabase
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
SUPABASE_SERVICE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
SUPABASE_JWT_SECRET=your-jwt-secret-here

# Upstash Redis (TLS)
REDIS_URL=rediss://default:password@region-redis.upstash.io:6379
CELERY_BROKER_URL=rediss://default:password@region-redis.upstash.io:6379/1
CELERY_RESULT_BACKEND=rediss://default:password@region-redis.upstash.io:6379/2

# LLM API Keys
OPENAI_API_KEY=sk-...
GOOGLE_API_KEY=AIza...
GEMINI_API_KEY=AIza...
COHERE_API_KEY=...

# Google Cloud
GOOGLE_CLOUD_PROJECT_ID=your-project-id
GOOGLE_CLOUD_LOCATION=us
GOOGLE_DOCUMENT_AI_PROCESSOR_ID=your-processor-id

# CORS
CORS_ORIGINS=https://your-frontend.vercel.app

# Observability (optional)
AXIOM_TOKEN=xaat-...
AXIOM_DATASET=ldip-logs
```

---

## Security Best Practices

1. **Never commit `.env` files** to version control
2. **Use platform secrets** (Vercel/Railway) in production
3. **Rotate keys regularly**, especially after suspected exposure
4. **Use separate keys** for development and production
5. **Limit service role key usage** to backend only
6. **Monitor API usage** for anomalies

---

*Last updated: 2026-01-16*
