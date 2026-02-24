# CLAUDE.md - Project Configuration

## Deployment

**IMPORTANT**: When deploying, always deploy ALL services that have changes. Run commands from the repo root.

### Railway (Backend) — deploy BOTH services
- **Project**: trustworthy-passion
- **API service**: `railway up -s LDIP` (from repo root)
- **Worker service**: `railway up -s ldip-worker` (from repo root)
- **API URL**: jaanch-ai.up.railway.app
- **Always deploy both API and worker together** — they share the same codebase and must stay in sync.

### Vercel (Frontend)
- **Project**: ldip
- **Deploy command**: `cd frontend && vercel --prod`
- **Production URL**: https://www.jaanch-ai.in

### Full Deploy Sequence
When backend changes are involved, deploy everything:
```bash
# 1. Backend API (from repo root)
railway up -s LDIP
# 2. Backend Worker (from repo root)
railway up -s ldip-worker
# 3. Frontend (if frontend changes too)
cd frontend && vercel --prod
```
