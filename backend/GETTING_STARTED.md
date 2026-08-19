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
uvicorn src.main:app --reload --port 8000
```
*(Note: The `--reload` flag enables hot-reloading, so the server will automatically restart when you make changes to the code).*

---

## 5. Verification & Connecting to Frontend
1. **API Docs**: Open your browser and navigate to [http://localhost:8000/docs](http://localhost:8000/docs). You should see the interactive Swagger UI displaying your API endpoints (like `/api/analytics/dashboard`).
2. **Frontend Connection**: 
   - Open a separate terminal window.
   - Navigate to the `frontend` directory.
   - Run `npm start` (or `ng serve`).
   - The Angular app will now be able to successfully route calls from `/api/...` to your running FastAPI backend.

## Note on Database (Supabase & Redis)
If your endpoints require database access, ensure your local Supabase stack and Redis containers are running:
```bash
# To start Redis (if using docker-compose directly)
docker-compose up -d

# To start the local Supabase stack
npx supabase start
```
