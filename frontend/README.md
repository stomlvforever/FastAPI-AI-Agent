# Frontend Workspace

This frontend turns the existing FastAPI backend into a blog-style web app with a separate Copilot route.

## What is included

- Authentication with the current `/api/v1/auth/login` and refresh flow
- Article list, detail, create, edit, and delete pages
- Favorite and follow interactions
- Profile and author pages
- A dedicated `/copilot` route wired to the streaming Agent API

## Local development

1. Start the FastAPI backend on `http://127.0.0.1:8000`
2. From this `frontend/` directory, install dependencies:

```bash
npm install
```

3. Start the frontend dev server:

```bash
npm run dev
```

The Vite dev server runs on `http://localhost:3000` and proxies `/api` and `/static` to the backend.

## Quality checks

```bash
npm run lint
npm run build
```
