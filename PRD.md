# PRD: MPLADS Work Verification Portal

Read this whole file first. Then do ONLY the step you are asked to do (for example "Step B3"). Never start the next step by yourself.

---

## 0. Rules for the agent (follow always)

1. **Folders.** Every backend file goes inside `backend/`. Every frontend file goes inside `frontend/`. Never create code files in the project root. The only root files allowed are `PRD.md`, `.gitignore` and `README.md`.
2. **One step at a time.** Do only the step requested. When it is finished, run the "Done when" checks, print the result, and stop. Do not add extra features, pages or endpoints.
3. **Stay inside the step's folder.** A backend step must not touch `frontend/`. A frontend step must not touch `backend/`.
4. **No guessing.** If a detail is missing, choose the simplest option, and write your choice in a "Decisions" list at the end of your reply.
5. **Secrets.** Never hardcode secrets, passwords or API keys in code. Use `backend/.env` (with a committed `backend/.env.example`) and `frontend/.env` (with `frontend/.env.example`). Both `.env` files go in `.gitignore`.
6. **Keep the API contract exactly as written in section 5.** Same paths, same field names, same status codes.
7. **Verify before saying done.** Run the server, the script or the build, and show the output.
8. **Do not modify the CSV files.** They are read-only inputs.

**Prompt to use for each step:**
> Read PRD.md. Do only Step `<ID>`. Follow the rules in section 0. Stop when the "Done when" checks pass and tell me what to run to verify.

---

## 1. Product summary

A website where citizens verify MPLADS (MP Local Area Development Scheme) works completed in their own area.

1. The user logs in with a Gmail address and an OTP (generated and checked with `pyotp`).
2. The site finds the user's location (state, district, constituency).
3. The user sees only the completed works from the two CSV files that match that location, each with its description.
4. On each work card the user can tap **Upload pic**. The phone's back camera opens, the user takes a photo, and it is uploaded.
5. Uploaded photos are visible **only to the auditor**.
6. The auditor logs in with a separate ID and password, then approves or rejects each photo.
7. On approval the user gets **150 XP**.

---

## 2. Tech stack (fixed, do not change)

| Part | Choice |
|---|---|
| Backend | Python 3.11+, FastAPI, Uvicorn |
| Database | SQLite through SQLAlchemy 2.x (file `backend/app.db`) |
| Auth | JWT (PyJWT), `pyotp` for OTP, `bcrypt` for the auditor password |
| CSV | `pandas` |
| Location matching | `rapidfuzz`, `httpx`, `shapely` |
| Images | `python-multipart`, `Pillow` |
| Frontend | React + Vite (JavaScript, not TypeScript), Tailwind CSS, `react-router-dom`, `axios` |

---

## 3. Folder structure (create exactly this)

```
project-root/
├── PRD.md
├── README.md
├── .gitignore
├── Loksova.csv              (input, do not edit)
├── RajyaSabha.csv           (input, do not edit)
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py
│   │   ├── config.py
│   │   ├── database.py
│   │   ├── models.py
│   │   ├── schemas.py
│   │   ├── security.py          (JWT, password hash, auth dependencies)
│   │   ├── routers/
│   │   │   ├── __init__.py
│   │   │   ├── auth.py
│   │   │   ├── location.py
│   │   │   ├── works.py
│   │   │   ├── submissions.py
│   │   │   └── auditor.py
│   │   └── services/
│   │       ├── __init__.py
│   │       ├── otp.py
│   │       ├── email_sender.py
│   │       ├── geo.py
│   │       └── csv_loader.py
│   ├── data/
│   │   ├── Loksova.csv          (copy)
│   │   ├── RajyaSabha.csv       (copy)
│   │   └── lok_sabha_constituencies.geojson   (optional, added by the team later)
│   ├── uploads/                 (photo storage, git-ignored)
│   ├── scripts/
│   │   └── import_csv.py
│   ├── tests/
│   ├── requirements.txt
│   ├── .env.example
│   └── Dockerfile
└── frontend/
    ├── index.html
    ├── package.json
    ├── vite.config.js
    ├── tailwind.config.js
    ├── postcss.config.js
    ├── .env.example
    └── src/
        ├── main.jsx
        ├── App.jsx
        ├── index.css
        ├── api/client.js
        ├── context/AuthContext.jsx
        ├── components/          (WorkCard, UploadButton, Header, ProtectedRoute, Loader)
        └── pages/
            ├── Login.jsx
            ├── LocationSetup.jsx
            ├── Works.jsx
            ├── AuditorLogin.jsx
            └── AuditorDashboard.jsx
```

---

## 4. Data facts (verified from the real files)

**Loksova.csv** (about 35,475 rows) columns, in this exact spelling:
`Sr. No.`, `Work Category`, `Work`, `State`, `IDA`, `Work Description`, `Hon'ble Members of Parliament`, `Constituency`, `Image`, `Completion Date`, `Amount Disbursed ( ₹ )`

**RajyaSabha.csv** (about 10,129 rows) has the same columns, except `Constituency` is replaced by `Elected/Nominated`. **Rajya Sabha rows have no constituency**, so they match on state and district only.

Cleaning rules (apply in Step B2):
- Read both files with `encoding="utf-8-sig"` (they start with a BOM).
- Each file has one junk footer row (non-breaking-space values). Drop any row where `Sr. No.` is not a number.
- **District** = the text before the first `(` in `IDA`, trimmed. Example: `ARARIA(DISTRICT PLANNING OFFICER ARARIA_IDA)` gives `ARARIA`.
- **Constituency** (Lok Sabha only): remove a trailing `(SC)` or `(ST)`. Example: `NAGINA(SC)` gives `NAGINA`.
- **Work code and work type**: the `Work` column looks like `WS/MP418/2024-2025/133409-Construction of roads...`. Split with the regex `^(WS/[^/]+/\d{4}-\d{4}/\d+)-(.*)$`. Group 1 is `work_code`, group 2 is `work_type`. If the regex fails, use the whole text as `work_type` and leave `work_code` empty.
- **Description**: about 79 rows are empty. Use `work_type` as the description when empty.
- **Amount**: about 80 rows are empty. Store as null.
- **Completion Date** format is `05-Sep-2024`. Parse with `%d-%b-%Y`.
- Ignore the `Image` column.
- For matching, also store upper-case, trimmed, single-spaced versions of state, district and constituency: `state_norm`, `district_norm`, `constituency_norm`.

---

## 5. Data model and API contract

### Tables

**works**: `id` (pk), `source` ("LS" or "RS"), `sr_no`, `work_code`, `work_type`, `category`, `state`, `district`, `constituency` (null for RS), `state_norm`, `district_norm`, `constituency_norm` (null for RS), `mp_name`, `description`, `amount` (float, null allowed), `completion_date` (date). Indexes on `state_norm`, `district_norm`, `constituency_norm`.

**users**: `id`, `email` (unique), `otp_secret`, `state`, `district`, `constituency`, `xp` (int, default 0), `created_at`.

**submissions**: `id`, `user_id`, `work_id`, `image_path`, `status` ("pending" | "approved" | "rejected"), `lat`, `lng` (both optional), `reject_reason` (optional), `created_at`, `reviewed_at`.

**xp_log**: `id`, `user_id`, `submission_id`, `points`, `created_at`.

### Endpoints

Auth header for protected routes: `Authorization: Bearer <token>`. The token has a `role` claim: `"user"` or `"auditor"`.

| Method and path | Who | Body / query | Response |
|---|---|---|---|
| `GET /health` | public | | `{"status":"ok"}` |
| `POST /auth/request-otp` | public | `{email}` | `{"message":"OTP sent"}` |
| `POST /auth/verify-otp` | public | `{email, otp}` | `{access_token, user}` |
| `POST /auth/auditor-login` | public | `{username, password}` | `{access_token}` |
| `GET /me` | user | | user object (email, state, district, constituency, xp) |
| `PUT /me/location` | user | `{state, district, constituency}` | user object |
| `GET /location/options` | user | `?state=&district=` | `{states:[], districts:[], constituencies:[]}` |
| `POST /location/resolve` | user | `{lat, lng}` | `{state, district, constituency, constituency_options:[]}` (values may be null) |
| `GET /works` | user | `?page=1&page_size=20&search=` | `{items:[...], total, page, page_size}` |
| `POST /works/{work_id}/submissions` | user | multipart: `photo`, optional `lat`, `lng` | submission object |
| `GET /auditor/submissions` | auditor | `?status=pending` | list of submissions with work details |
| `GET /auditor/submissions/{id}/image` | auditor | | image file |
| `POST /auditor/submissions/{id}/approve` | auditor | | submission object |
| `POST /auditor/submissions/{id}/reject` | auditor | `{reason}` | submission object |

Each item in `GET /works` contains: `id`, `source`, `work_code`, `work_type`, `description`, `mp_name`, `state`, `district`, `constituency`, `amount`, `completion_date`, `my_submission_status` (`null`, `"pending"`, `"approved"` or `"rejected"`).

Error status codes: 400 bad input, 401 not logged in, 403 wrong role, 404 not found, 409 conflict, 429 too many OTP attempts.

### Matching rule (used by `GET /works`)

- Lok Sabha works where `state_norm`, `district_norm` **and** `constituency_norm` equal the user's values.
- Plus Rajya Sabha works where `state_norm` and `district_norm` equal the user's values.
- If the user has no saved location, return 400 with `"Location not set"`.

---

# PART A: BACKEND (all work inside `backend/`)

### Step B0: Project scaffold
- Create the `backend/` folder structure from section 3, with empty `__init__.py` files.
- Create a virtual environment inside `backend/`. Write `requirements.txt` with: `fastapi`, `uvicorn[standard]`, `sqlalchemy`, `pydantic-settings`, `pandas`, `pyotp`, `PyJWT`, `bcrypt`, `python-multipart`, `Pillow`, `httpx`, `rapidfuzz`, `shapely`, `pytest`.
- `app/main.py` creates the FastAPI app and the `GET /health` route.
- Copy `Loksova.csv` and `RajyaSabha.csv` into `backend/data/`.
- Add the root `.gitignore` (venv, `__pycache__`, `.env`, `app.db`, `uploads/`, `node_modules`, `dist`).
- **Done when:** `uvicorn app.main:app --reload` starts from inside `backend/` and `GET /health` returns `{"status":"ok"}`.

### Step B1: Config, database and models
- `config.py` uses `pydantic-settings` to read `.env`. Settings: `SECRET_KEY`, `DATABASE_URL` (default `sqlite:///./app.db`), `FRONTEND_ORIGIN` (default `http://localhost:5173`), `AUDITOR_ID` (default `auditor`), `AUDITOR_PASSWORD` (default `auditor123`), `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `ALLOWED_EMAIL_DOMAIN` (default `gmail.com`), `XP_PER_APPROVAL` (default 150), `MAX_UPLOAD_MB` (default 8), `GEOJSON_PATH`.
- `database.py` creates the engine, `SessionLocal`, `Base` and a `get_db` dependency.
- `models.py` defines the four tables from section 5. Create all tables on app startup.
- Write `.env.example` listing every setting.
- **Done when:** the app starts, `app.db` is created, and the four tables exist (show them with a short Python or `sqlite3` command).

### Step B2: CSV import script
- Implement `services/csv_loader.py` and `scripts/import_csv.py` following the cleaning rules in section 4.
- The script clears the `works` table, loads both files, and prints row counts per source.
- Run it as `python -m scripts.import_csv` from inside `backend/`.
- **Done when:** the script prints roughly 35,475 LS rows and 10,129 RS rows; no LS row has an empty `district` or `constituency`; no RS row has a `constituency`. Print 3 sample rows of each source.

### Step B3: Location endpoints
- `services/geo.py`:
  - `reverse_geocode(lat, lng)` calls OpenStreetMap Nominatim (`https://nominatim.openstreetmap.org/reverse`, `format=jsonv2`) with `httpx`, a custom `User-Agent` header and a 10-second timeout. It returns raw state and district text.
  - `match_to_dataset(state_text, district_text, db)` finds the closest state, then the closest district within that state, from the distinct values in the `works` table, using `rapidfuzz` (minimum score 85). Return `None` for anything that does not match.
  - `find_constituency(lat, lng)` reads the file at `GEOJSON_PATH` if it exists and does a point-in-polygon check with `shapely`. If the file is missing, return `None`. Do not crash.
- `routers/location.py`:
  - `GET /location/options`: returns distinct states; districts for a given state; constituencies for a given state and district (constituencies come from Lok Sabha rows only).
  - `POST /location/resolve`: runs the three functions above. If the constituency is `None`, return `constituency_options` for the resolved state and district so the frontend can show a dropdown.
  - Both routes are user-only, but auth is added in Step B4. For now, leave them open and add the auth dependency in B4.
- **Done when:** `GET /location/options` returns the 35 or so states, and `POST /location/resolve` with `{"lat": 26.12, "lng": 87.47}` returns a state and district (or nulls if the network is unavailable, with no server crash).

### Step B4: User authentication with OTP
- `services/otp.py`:
  - Each user has a random base32 `otp_secret` (`pyotp.random_base32()`), created when the user first requests an OTP.
  - Generate with `pyotp.TOTP(secret, digits=6, interval=300).now()` and verify with `.verify(code, valid_window=0)`.
  - Keep an in-memory dictionary for limits: max 5 OTP requests per email per hour, max 5 wrong attempts then block that email for 15 minutes (return 429).
- `services/email_sender.py`: sends the OTP by SMTP (`smtplib`, STARTTLS). If `SMTP_USER` is empty, print the OTP to the server console instead (dev mode).
- Reject any email that does not end with `@` + `ALLOWED_EMAIL_DOMAIN`.
- `security.py`: `create_token(sub, role)` (expires in 24 hours), `get_current_user` and `require_auditor` dependencies.
- `routers/auth.py`: `POST /auth/request-otp` and `POST /auth/verify-otp` (creates the user if new, returns token and user).
- `routers/auth.py` also gets `GET /me` and `PUT /me/location`. Now add the user-auth dependency to the location routes from B3.
- **Done when:** request an OTP, read it in the console, verify it, receive a token, and `GET /me` works with that token. A wrong OTP returns 400. A request without a token returns 401.

### Step B5: Auditor authentication
- On startup, create an in-memory bcrypt hash of `AUDITOR_PASSWORD`. Do not store the plain password anywhere except `.env`.
- `POST /auth/auditor-login` compares `username` with `AUDITOR_ID` and the password with the hash, then returns a token with `role: "auditor"`.
- A user token must get 403 on auditor routes. An auditor token must get 403 on user routes.
- **Done when:** logging in with `auditor` / `auditor123` returns a token; a wrong password returns 401.

### Step B6: Works list endpoint
- `routers/works.py`: `GET /works` with the matching rule from section 5, pagination, and optional `search` (case-insensitive match on `description` or `work_type`).
- Include `my_submission_status` per work for the current user (the latest submission status, or null).
- Sort by `completion_date` descending.
- **Done when:** for a test user with location set to a real state, district and constituency from the data, `GET /works` returns only matching works. Show one LS example and one RS example. A user with no location gets 400.

### Step B7: Photo upload
- `routers/submissions.py`: `POST /works/{work_id}/submissions`.
- Accept only JPEG, PNG or WebP. Reject files larger than `MAX_UPLOAD_MB`. Open the file with Pillow to confirm it is a real image.
- Save to `backend/uploads/` with a random UUID filename. Never use the original filename. Store the relative path.
- The work must exist and must match the user's location (same rule as B6), otherwise 403.
- If the user already has a `pending` or `approved` submission for this work, return 409. A `rejected` one may be replaced by a new upload.
- The `uploads/` folder must not be served as static files.
- **Done when:** a valid upload returns a pending submission; a second upload for the same work returns 409; a `.txt` file renamed to `.jpg` is rejected with 400.

### Step B8: Auditor review and XP
- `routers/auditor.py`:
  - `GET /auditor/submissions?status=pending` returns submissions with work details (description, MP, district) and user email.
  - `GET /auditor/submissions/{id}/image` returns the file. Auditor only.
  - `POST .../approve`: in a single database transaction set `status="approved"`, set `reviewed_at`, add `XP_PER_APPROVAL` to `users.xp`, and insert an `xp_log` row. If the submission is not pending, return 409 (so XP can never be given twice).
  - `POST .../reject` with `{reason}`: set `status="rejected"`, save the reason and `reviewed_at`. No XP.
- **Done when:** approving a pending submission raises the user's `xp` by exactly 150; approving the same submission again returns 409 and XP does not change; a user token cannot open the image URL (403).

### Step B9: Backend finish
- Add CORS for `FRONTEND_ORIGIN` only.
- Add a `Dockerfile` (Python 3.11 slim, install requirements, run `uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}`).
- Write `backend/tests/test_flow.py` with `pytest` and FastAPI `TestClient` covering: OTP login, location set, works list, upload, approve, XP equals 150.
- Add a `README.md` section listing how to run the backend and the import script.
- **Done when:** `pytest` passes and `http://localhost:8000/docs` shows every endpoint from section 5.

---

# PART B: FRONTEND (all work inside `frontend/`)

Design rules for every page: mobile-first (most users will be on phones), clean white background, one accent colour, large tap targets (minimum 44px), clear loading and error messages, no external UI libraries beyond Tailwind.

### Step F0: Frontend scaffold
- Create the Vite React app inside `frontend/` (JavaScript template). Install `react-router-dom`, `axios`, and Tailwind CSS with its config.
- Create `.env.example` with `VITE_API_URL=http://localhost:8000`.
- Set up empty routes in `App.jsx`: `/login`, `/location`, `/works`, `/auditor/login`, `/auditor`.
- **Done when:** `npm run dev` shows a page for each route and `npm run build` succeeds.

### Step F1: API client and auth context
- `api/client.js`: an axios instance using `VITE_API_URL` that adds the token from `localStorage` to every request, and on a 401 response clears the token and redirects to the right login page.
- `context/AuthContext.jsx`: stores `token`, `role` and `user`; provides `login`, `logout` and `refreshUser`.
- `components/ProtectedRoute.jsx`: takes `role` and redirects to `/login` (user) or `/auditor/login` (auditor) when not allowed.
- **Done when:** visiting `/works` while logged out redirects to `/login`.

### Step F2: Login page (email and OTP)
- Step 1: an email input. Button "Send OTP" calls `POST /auth/request-otp`. Show an error if the email is not a Gmail address.
- Step 2: a 6-digit OTP input. Button "Verify" calls `POST /auth/verify-otp`, saves the token, then goes to `/location`. Show a "Resend OTP" button that is disabled for 30 seconds.
- Show a link at the bottom: "Auditor login" pointing to `/auditor/login`.
- **Done when:** with the backend running, the full login works and lands on `/location`. Wrong OTP shows a clear message.

### Step F3: Location setup page
- On load, ask for browser location with `navigator.geolocation.getCurrentPosition`. Call `POST /location/resolve` with the result.
- Show three dropdowns: State, District, Constituency, filled from `GET /location/options` and pre-selected with the resolved values. The user can change them.
- If permission is denied or the request fails, show the dropdowns empty with a short message "Select your location manually".
- Button "Confirm" calls `PUT /me/location`, then goes to `/works`.
- If the user already has a saved location, skip this page and go straight to `/works`, with a "Change location" link in the header.
- **Done when:** both the GPS path and the manual path save the location and open `/works`.

### Step F4: Works list page
- Header component: app name, the user's XP, "Change location", and "Logout".
- Call `GET /works` and show a `WorkCard` for each item: work type as the title, description, MP name, amount (formatted as ₹ with Indian digit grouping), completion date, district and constituency.
- Add a search box and "Load more" pagination.
- Show a status badge from `my_submission_status`: Pending (amber), Approved (green), Rejected (red).
- Show an empty state message when there are no works for the user's location.
- **Done when:** the list shows real works for the saved location, search works, and "Load more" adds the next page.

### Step F5: Photo upload from the work card
- `UploadButton.jsx`: a small "Upload pic" button in the **top-right corner** of each `WorkCard`.
- It triggers a hidden `<input type="file" accept="image/*" capture="environment">` so a phone opens the **back camera**.
- After the photo is taken, show a preview with "Send" and "Retake". On "Send", get the GPS position (best effort, optional) and call `POST /works/{id}/submissions` as multipart form data. Show upload progress.
- Hide the button when the status is `pending` or `approved`. Show it again (labelled "Retake") when the status is `rejected`.
- Show friendly messages for 409 and for files that are too large.
- **Done when:** on a phone (or Chrome device mode), tapping the button opens the camera or file picker, the upload succeeds, and the card badge changes to Pending.

### Step F6: Auditor login page
- Page `/auditor/login` with username and password fields, calling `POST /auth/auditor-login`. On success go to `/auditor`.
- Do not show the default credentials anywhere on the page.
- **Done when:** the auditor can log in and a user token cannot open `/auditor`.

### Step F7: Auditor dashboard
- Call `GET /auditor/submissions?status=pending`. Show each item as a card with: the photo (loaded with an authenticated request and shown through a blob URL, because the image route needs the token), work description, MP name, district, the user's email, and upload time.
- Buttons "Approve" and "Reject". Reject opens a small box that asks for a reason.
- After an action, remove the card from the list and show a short success message ("150 XP given").
- Add tabs for Pending, Approved and Rejected.
- **Done when:** approving from the dashboard raises the user's XP shown in the user's header after refresh.

### Step F8: Frontend finish
- Loading spinners on all requests, friendly error messages, no console errors.
- Check the layout at 360px width.
- Add the frontend section to `README.md`.
- **Done when:** `npm run build` succeeds with no warnings about missing files.

---

# PART C: INTEGRATION AND DEPLOY

### Step D1: Environment for deploy
- Confirm `frontend/.env.example` and `backend/.env.example` list every variable.
- Backend `FRONTEND_ORIGIN` must be settable to the deployed frontend URL.
- **Done when:** both apps run locally using only values from their `.env` files.

### Step D2: Deploy the backend (the `backend/` folder only)
- Deploy `backend/` as a web service (for example Render, with root directory `backend`, start command `uvicorn app.main:app --host 0.0.0.0 --port $PORT`), or use the Dockerfile.
- Set the environment variables from `.env.example`. Set a strong `SECRET_KEY`, a new `AUDITOR_PASSWORD`, and the SMTP settings.
- Note: SQLite and the `uploads/` folder are lost on free hosts that reset their disk. For a real deployment, use a hosted Postgres database and a persistent disk or object storage.
- Run the CSV import once on the server.
- **Done when:** `https://<backend-url>/health` returns ok.

### Step D3: Deploy the frontend (the `frontend/` folder only)
- Deploy `frontend/` (for example Vercel or Netlify, root directory `frontend`, build command `npm run build`, output `dist`).
- Set `VITE_API_URL` to the backend URL. Camera and location only work over HTTPS, and both hosts provide it.
- **Done when:** the deployed site loads and can reach the backend without CORS errors.

### Step D4: End-to-end test checklist
1. Log in with a Gmail address and OTP.
2. Location is detected (or chosen manually) and saved.
3. The works list shows only works for that location.
4. Upload a photo from a phone's back camera.
5. Log in as auditor and see the photo.
6. Approve it and confirm the user's XP is exactly 150.
7. Try to approve it again: it must fail and XP must not change.
8. Reject another photo, retake, and upload again.
9. A normal user must not be able to open any photo URL.

---

## 6. Out of scope for the first version

Push notifications, a leaderboard, multiple auditors, editing or deleting photos, admin analytics, and any changes to the CSV data.
