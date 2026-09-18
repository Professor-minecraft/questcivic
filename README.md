# CivicQuest: MPLADS Work Verification Portal

A platform where citizens verify MPLADS (Member of Parliament Local Area Development Scheme) works completed in their local constituency by uploading geo-tagged photos, which are then reviewed and approved by an auditor to award citizen XP.

---

## Backend Setup & Instructions

### 1. Prerequisites
- Python 3.11+
- Virtual environment (`venv`)

### 2. Installation
From the `backend/` directory:

```bash
cd backend
python -m venv venv

# On Windows (PowerShell):
.\venv\Scripts\Activate.ps1

# On macOS/Linux:
source venv/bin/activate

pip install -r requirements.txt
```

### 3. Environment Configuration
Copy the example environment file and customize it if needed:

```bash
cp .env.example .env
```

Key environment settings:
- `DATABASE_URL`: Database connection string (default: `sqlite:///./app.db`)
- `SECRET_KEY`: Secret key for JWT signing
- `FRONTEND_ORIGIN`: Allowed CORS origin (default: `http://localhost:5173`)
- `AUDITOR_ID`: Username for auditor login (default: `auditor`)
- `AUDITOR_PASSWORD`: Password for auditor login (default: `auditor123`)
- `ALLOWED_EMAIL_DOMAIN`: Allowed citizen email domain (default: `gmail.com`)
- `XP_PER_APPROVAL`: XP points awarded per approved work photo (default: `150`)

### 4. Running the CSV Data Import
The database needs to be populated with Lok Sabha and Rajya Sabha works data from the source CSV files:

```bash
cd backend
python -m scripts.import_csv
```

This will:
- Clean and normalize dataset records.
- Populate `works` table with ~35,475 Lok Sabha and ~10,129 Rajya Sabha rows.
- Index normalized location columns for fast matching.

### 5. Running the Backend Server
Start the development server with auto-reload:

```bash
cd backend
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

- **API Base URL:** `http://127.0.0.1:8000`
- **Interactive Swagger Documentation:** `http://127.0.0.1:8000/docs`
- **OpenAPI Schema:** `http://127.0.0.1:8000/openapi.json`
- **Health Check:** `http://127.0.0.1:8000/health`

### 6. Running Automated Tests
Run the comprehensive test suite with `pytest`:

```bash
cd backend
pytest
```

### 7. Running with Docker
Build and run using the backend Docker container:

```bash
cd backend
docker build -t civicquest-backend .
docker run -p 8000:8000 --env-file .env civicquest-backend
```

---

## Backend API Endpoints

| Method | Endpoint | Access | Description |
|---|---|---|---|
| `GET` | `/health` | Public | Server health status |
| `POST` | `/auth/request-otp` | Public | Send 6-digit TOTP code to user Gmail |
| `POST` | `/auth/verify-otp` | Public | Verify OTP and return JWT access token |
| `POST` | `/auth/auditor-login` | Public | Auditor credentials login |
| `GET` | `/me` | User | Get current citizen user profile & XP |
| `PUT` | `/me/location` | User | Update user saved location |
| `GET` | `/location/options` | User | Get distinct states, districts, and constituencies |
| `POST` | `/location/resolve` | User | Reverse-geocode coordinates to match dataset location |
| `GET` | `/works` | User | List works matching user location with pagination & search |
| `POST` | `/works/{work_id}/submissions` | User | Upload verification photo for a work |
| `GET` | `/auditor/submissions` | Auditor | List submitted works pending review |
| `GET` | `/auditor/submissions/{id}/image` | Auditor | Securely view uploaded photo |
| `POST` | `/auditor/submissions/{id}/approve` | Auditor | Approve submission and grant 150 XP |
| `POST` | `/auditor/submissions/{id}/reject` | Auditor | Reject submission with reason |

---

## Frontend Setup & Instructions

### 1. Prerequisites
- Node.js 18+
- npm (Node Package Manager)

### 2. Installation
From the `frontend/` directory:

```bash
cd frontend
npm install
```

### 3. Environment Configuration
Copy the example environment configuration:

```bash
cp .env.example .env
```

Key environment setting:
- `VITE_API_URL`: Backend API URL (default: `http://localhost:8000`)

### 4. Running the Development Server
Start the Vite development server:

```bash
cd frontend
npm run dev
```

Open your browser at `http://localhost:5173`.

### 5. Building for Production
Create an optimized production bundle:

```bash
cd frontend
npm run build
```

The production assets will be generated in `frontend/dist/`.

### 6. Frontend Pages & Features

- **Citizen Login (`/login`)**:
  - Two-step Gmail authentication with 6-digit TOTP verification.
  - Client-side validation ensuring only `@gmail.com` addresses are accepted.
  - 30-second cooldown timer for resending OTPs.
  - Direct link to the Auditor portal.

- **Location Setup (`/location`)**:
  - Automatically queries `navigator.geolocation` and reverse-geocodes coordinates to match dataset boundaries.
  - Manual fallback with cascading dropdowns: State &rarr; District &rarr; Lok Sabha Constituency.
  - Automatically skipped once a location is saved, with a "Change location" shortcut available in the header.

- **Works List (`/works`)**:
  - Displays MPLADS works matching the user's saved location.
  - Indian Rupee currency formatting (`₹X,XX,XXX`) and localized completion dates.
  - Debounced search bar filtering across project titles and descriptions.
  - "Load more" button for smooth pagination.
  - Submission status indicators: Pending (amber), Approved (green), Rejected (red).

- **Photo Upload Component (`UploadButton`)**:
  - Triggers mobile device back camera via `capture="environment"`.
  - Preview modal with "Send" and "Retake" actions.
  - Best-effort GPS tagging upon photo capture.
  - Upload progress indicator and duplicate submission prevention (HTTP 409 handling).

- **Auditor Portal (`/auditor/login` and `/auditor`)**:
  - Dedicated administrative dashboard with dark mode styling.
  - Protected image viewing via authenticated Bearer token blob requests.
  - One-click approval awarding 150 XP to the citizen.
  - Rejection modal requiring an audit reason.
  - Queue tabs for **Pending Review**, **Approved**, and **Rejected** submissions.

### 7. Responsive & Mobile-First Design
- Optimized for mobile viewports down to 360px width.
- Minimum 44px tap targets for buttons and input fields.
- Clean white card layout with accessible contrast, loading spinners, and error alerts.

