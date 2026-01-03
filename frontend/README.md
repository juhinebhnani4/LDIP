# LDIP Frontend (Next.js)

Legal Document Intelligence Platform (LDIP) frontend built with **Next.js App Router**, **Tailwind CSS**, and **shadcn/ui**.

## Run locally

```bash
cd frontend
npm install
cp .env.local.example .env.local
npm run dev
```

App: `http://localhost:3000`

## Environment variables

Required:

- `NEXT_PUBLIC_SUPABASE_URL`
- `NEXT_PUBLIC_SUPABASE_ANON_KEY`
- `NEXT_PUBLIC_API_URL` (FastAPI backend; default `http://localhost:8000`)

## Useful commands

```bash
npm run lint
npm run build
```

## Notes

- Routing uses **App Router route groups** (`(auth)`, `(dashboard)`, `(matter)`), which do **not** appear in the URL.
- Supabase config is client-side only; never put service-role keys in the frontend.
