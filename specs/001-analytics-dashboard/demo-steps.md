# Smoke Test and Demo Steps: Analytics Dashboard

**Target Audience:** Product Owners, QA, and Development Team
**Feature:** `001-analytics-dashboard` (Coach Sophie Lin's Dashboard Demo)

## Overview

This guide provides the exact steps to generate the demo data, authenticate as Coach Sophie Lin, and verify the successful end-to-end rendering of the Coach Dashboard and its widgets.

## Step 1: Environment Setup & Data Generation

1. Ensure the Supabase (PostgreSQL) backend is running locally.
2. Run the updated Python data generation script to seed the database with the `SST` club, athletes, and **Coach Sophie Lin**. 

*Note: The script has been enhanced to automatically inject the exact generated database UUIDs into your frontend code (`auth.service.ts`), ensuring the mocked local login connects perfectly to the real database relationships!*

```bash
# From the project root, ensure dependencies are installed (e.g., psycopg2)
python generate_demo_data.py
```

**Expected Output:**
You should see a printout confirming the creation of the athletes, their predictive insights, their coaching recommendations, and the creation of Coach Sophie Lin:
```text
Successfully generated data for User Story 1, including Coach Sophie Lin.

--- Demo Data Generated ---
Athlete: Emma Johnson, Predicted Score: 62.45, Plateau Risk: False, Weakest Figure: Kip
...
```

## Step 2: Login as Coach Sophie Lin

*(Note: While external auth `001-multi-tenant-user-api` is mocked/stubbed for this local demo, use the following credentials/tokens to simulate the JWT claims.)*

1. Start the frontend Angular application:
   ```bash
   npm run start --prefix frontend
   ```
2. Open your browser and navigate to `http://localhost:4200/login`
3. Enter the demo credentials:
   - **Email:** `sophie.lin@sst.example.com`
   - **Password:** `demo123` (or use the designated local development bypass button "Login as SST Coach")
4. **Action:** Click **Login**.

**Expected Result:**
- The system successfully authenticates and routes you to the **Coach Dashboard** (`/dashboards/coach`).
- The JWT is stored in local storage, containing the `club_id` for Seattle Synchro (SST) and the role `Coach`.

## Step 3: Verify the Coach Dashboard Widgets

On the Coach Dashboard view, verify the following elements load correctly within 2 seconds:

### A. Team Overview Widget
- Ensure the widget lists the SST athletes (Emma Johnson, Olivia Davis, etc.).
- Verify the layout uses the requested extra-large typography (display-large) for easy reading on the pool deck.

### B. Figure Heatmap & Weaknesses
- Locate the Figure Heatmap widget.
- Verify it highlights the weakest figures (e.g., Kip, Swordfish) across the team, using the ECharts radar format.

### C. Predictive Insights
- Select an athlete (e.g., Emma Johnson) from the overview list.
- Verify the "Prediction Widget" updates to show her predicted next score (e.g., 62.45) and whether she has a "Plateau Risk."

### D. AI Coaching Recommendation
- With the athlete still selected, locate the AI Recommendation widget.
- Verify it displays the natural language suggestion (e.g., "Focus on vertical extension and control during the Kip...").

## Step 4: Logout

1. Locate the User Profile / Settings menu in the sticky navigation bar.
2. Click **Logout**.

**Expected Result:**
- The JWT is cleared from local storage.
- You are redirected back to the `/login` screen.
- Navigating back to `/dashboards/coach` via the browser's back button redirects you to the login screen (auth guard enforced).
