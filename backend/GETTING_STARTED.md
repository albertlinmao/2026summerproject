# Getting Started: Backend Service

This guide explains how to start the FastAPI backend service so it can communicate with the Angular frontend.

## Prerequisites
- Python 3.11+ installed on your system.
- Ensure you are operating within the `backend` directory.

---

## 1. Create a Python Virtual Environment
It is highly recommended to use a virtual environment to manage your dependencies.
Open your terminal, navigate to the `backend` folder, and run:

```bash
cd backend
python -m venv venv
```

## 2. Activate the Virtual Environment
You need to activate the environment before installing packages.

**On Windows:**
```powershell
.\venv\Scripts\activate
```

**On Mac / Linux:**
```bash
source venv/bin/activate
```

## 3. Install Dependencies
Once the virtual environment is activated (you will see `(venv)` in your prompt), install the project requirements:

```bash
pip install -r requirements.txt
```

## 4. Start the FastAPI Server
The application uses `uvicorn` as the ASGI server. Start the server with the following command (must be run from the `backend` directory):

```bash
uvicorn src.main:app --reload --port 8080
```
*(Note: The `--reload` flag enables hot-reloading, so the server will automatically restart when you make changes to the code).*

> **Why 8080 and not 8000:** the Supabase stack is Docker Compose, and its Kong gateway binds host
> port `8000`. Use `8080` (or any free port) for a local backend run. The containerised path below
> avoids the clash by publishing `18081 -> 8000`.

---

## 5. Verification & Connecting to Frontend
1. **API Docs**: Open your browser and navigate to [http://localhost:8080/docs](http://localhost:8080/docs). You should see the interactive Swagger UI displaying your API endpoints (like `/api/analytics/dashboard`).
2. **Frontend Connection**: 
   - Open a separate terminal window.
   - Navigate to the `frontend` directory.
   - Run `npm start` (or `ng serve`).
   - The Angular app will now be able to successfully route calls from `/api/...` to your running FastAPI backend.
   - `frontend/src/environments/environment.ts` points `apiUrl` at `http://127.0.0.1:8080/api`; keep
     the two in step.

## Note on Database (Supabase & Redis)
If your endpoints require database access, ensure your local Supabase stack and Redis containers are running:

```bash
# To start Redis (this file's compose defines Redis only)
docker compose up -d

# To start the Supabase stack - it is the self-hosted Docker Compose project in
# ../supabase, NOT the Supabase CLI. Run it from that directory, because the
# compose file resolves .env and ./volumes/** relative to it.
cd ../supabase
docker compose up -d
docker compose ps      # wait until db and kong report healthy
```

The stack is reached at:

| Service | Host port | Value |
| --- | --- | --- |
| Kong (REST / auth / storage) | `8000` | `SUPABASE_URL=http://localhost:8000` |
| PostgreSQL | `5432` | `DATABASE_URL=postgresql://postgres:<password>@localhost:5432/postgres` |
| Supavisor pooler | `6543` | transaction mode |
| Studio | not published | no `ports:` in `supabase/docker-compose.yml` |
| Inbucket (mail) | absent | defined only in the dev overlay, which cannot build |

Project migrations are **not** applied automatically — the `db` service mounts only Supabase's own
init scripts. Apply the five files in `backend/supabase/migrations/` in timestamp order via the
container's `psql`; see step 2 of `IMPLEMENTATION_SUMMARY.md` for the exact commands.

Do not add `-f ./dev/docker-compose.dev.yml`: it rebuilds Studio from source
(`build.context: ..`, `dockerfile: apps/studio/Dockerfile`), and there is no `apps/` directory in
this repository, so the build fails.
