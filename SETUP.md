# localcontacts.biz — Setup (Supabase + Lemon Squeezy)

## 1) Supabase

### 1.1 Create project
- Create a Supabase project.
- Copy these values:
  - `Project URL` → `SUPABASE_URL` (backend) and `VITE_SUPABASE_URL` (frontend)
  - `anon public key` → `VITE_SUPABASE_ANON_KEY` (frontend)
  - Postgres connection string/password → `DATABASE_URL` (backend)

### 1.2 Enable Email/Password auth
- Supabase → Authentication → Providers → enable Email.

### 1.3 Auth URLs
- Supabase → Authentication → URL Configuration:
  - Add `http://localhost:5173`
  - Add your production domain later

## 2) Frontend env (local)

Create `frontend/.env.local`:

```
VITE_SUPABASE_URL=...
VITE_SUPABASE_ANON_KEY=...
```

Run:

```
cd frontend
npm install
npm run dev
```

Frontend runs at `http://127.0.0.1:5173/`.

## 3) Backend env (local)

Create `backend/.env`:

```
SUPABASE_URL=...
DATABASE_URL=...
FRONTEND_URL=http://localhost:5173

LEMONSQUEEZY_API_KEY=...
LEMONSQUEEZY_STORE_ID=...
LEMONSQUEEZY_WEBHOOK_SECRET=...
LEMONSQUEEZY_VARIANT_ENTRY=...
LEMONSQUEEZY_VARIANT_PRO=...
LEMONSQUEEZY_VARIANT_BUSINESS=...
LEMONSQUEEZY_VARIANT_TOPUP=...
```

Install backend deps:

```
cd backend
pip install -r requirements.txt
```

If using Supabase Postgres, ensure a Postgres driver is installed:

```
pip install psycopg2-binary
```

Run backend (loads env from file):

```
uvicorn main:app --reload --port 8000 --env-file .env
```

Backend runs at `http://127.0.0.1:8000/`.

## 4) Database schema (Alembic)

Run migrations against the DB configured by `DATABASE_URL`:

```
cd backend
alembic -c alembic.ini upgrade head
```

## 5) Lemon Squeezy

### 5.1 Products / variants
- Create three subscription variants:
  - Entry ($39/mo), Pro ($99/mo), Business ($199/mo)
- Create a Top-up variant.

Important: current top-up flow treats the “credits” input as Lemon checkout quantity.\nThat means the top-up variant should be priced as “price per 1 credit”, and quantity = credits.\nIf you want credit packs instead, update the backend to use a fixed quantity and compute credits from the pack.

### 5.2 Webhook
- Create a webhook pointing to:
  - `https://<your-backend-domain>/api/billing/webhook`
- Set a signing secret and put it in `LEMONSQUEEZY_WEBHOOK_SECRET`.
- Subscribe to at least:
  - `order_created`
  - `subscription_created`
  - `subscription_updated`
  - `subscription_payment_success`
  - `subscription_cancelled`
  - `subscription_expired`

The webhook signature is sent in `X-Signature` and must be verified using the raw request body.

## 6) Admin access

- Log in once so your profile row is created.
- Set `profiles.role = 'admin'` for your user id.
- Visit `/admin` in the frontend.

