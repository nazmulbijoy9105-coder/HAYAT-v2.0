# HAYAT v2.0 — Deployment Guide

## Platform 1: Vercel (Frontend)

### Step 1: Prepare Frontend
```bash
cd frontend
npm install
npm run build
```

### Step 2: Deploy to Vercel
```bash
npm i -g vercel
vercel --prod
```

Or use GitHub integration:
1. Go to https://vercel.com/new
2. Import `nazmulbijoy9105-coder/HAYAT-2`
3. Set **Root Directory** to `frontend`
4. Framework Preset: `Vite`
5. Build Command: `npm run build`
6. Output Directory: `dist`
7. Add Environment Variable: `VITE_API_URL=https://hayat-api.onrender.com`
8. Deploy

---

## Platform 2: Render.com (Backend + Databases)

### Step 1: Push Latest Code
```bash
git add .
git commit -m "fix: add root Dockerfiles for Render deployment"
git push origin main
```

### Step 2: Deploy via Blueprint
1. Go to https://dashboard.render.com/blueprints
2. Click **New Blueprint Instance**
3. Connect GitHub repo: `nazmulbijoy9105-coder/HAYAT-2`
4. Render auto-detects `render.yaml`
5. Click **Apply**
6. Wait for all services to deploy (5-10 minutes)

### Step 3: Set Secrets
After deployment, go to each service and set:
- `OPENAI_API_KEY` — Your OpenAI API key
- `JWT_SECRET_KEY` — Auto-generated, or set your own

### Step 4: Run Migrations
```bash
# SSH into the API service on Render
# Or run locally pointing to Render database
export DATABASE_URL="your-render-postgres-url"
cd backend
alembic upgrade head
```

---

## Troubleshooting

### Error: "Dockerfile: no such file or directory"
**Fix**: The root `Dockerfile` must exist. We added it. Push to GitHub and redeploy.

### Error: "failed to solve: failed to read dockerfile"
**Fix**: Make sure `dockerfilePath` in `render.yaml` points to `./Dockerfile` (root level).

### Error: "Repository not found" on Render
**Fix**: Make sure the repo is public, or connect Render to GitHub with proper permissions.

---

## Environment Variables Reference

| Variable | Vercel | Render API | Render Worker |
|----------|--------|------------|---------------|
| `DATABASE_URL` | — | Auto | Auto |
| `REDIS_URL` | — | Auto | Auto |
| `JWT_SECRET_KEY` | — | Auto | — |
| `OPENAI_API_KEY` | — | Manual | Manual |
| `NEO4J_URI` | — | Auto | — |
| `NEO4J_PASSWORD` | — | Auto | — |
| `RABBITMQ_URL` | — | — | Auto |
| `ENVIRONMENT` | — | production | production |
| `VITE_API_URL` | Manual | — | — |
