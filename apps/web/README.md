# Sailbase Web

Next.js portal: search, boat detail with price explanation, booking and customer portal.

```bash
npm install
API_URL=http://localhost:8000 npm run dev    # http://localhost:3000
```

The browser talks to `/api/*`, which a route handler proxies to the backend. So `API_URL` is a
runtime server setting and the same image works in every environment.
