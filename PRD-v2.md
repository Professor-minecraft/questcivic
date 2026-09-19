# PRD v2: Auditor Photo Viewer and Leaderboard Name Setting Removal

Read this whole file first. Then do ONLY the step you are asked to do (for example "Step A2"). Never start the next step by yourself.

This file builds on `PRD.md` and on the code as it exists today. It changes two things and nothing else. Part A and Part B are independent and can be done in either order.

---

## 0. Rules for the agent (follow always)

1. **Folders.** Backend files stay in `backend/`, frontend files in `frontend/`. Never create code files in the project root. Allowed root files: `PRD.md`, `PRD-v2.md`, `README.md`, `.gitignore` and the two CSV files.
2. **One step at a time.** Do only the step requested. When it is finished, run the "Done when" checks, print the result, and stop. No extra features, pages or endpoints.
3. **Stay inside the step's file list.** Each step has a "Touch only" list. Do not edit other files and do not refactor code you were not asked to change.
4. **No guessing.** If a detail is missing, choose the simplest option and write your choice in a "Decisions" list at the end of your reply.
5. **Secrets and data.** Never open, print or commit `.env` files, `backend/backups/` or `backend/uploads/`. The only allowed use of `backend/app.db` is the read-only count query in Step B1. Do not change the database schema or its data.
6. **Keep the API exactly as written in section 4.** Every endpoint not listed there stays as it is.
7. **Frontend style.** React function components, Tailwind 3 utility classes, no new npm packages, no icon libraries (use inline SVG). Match the dark slate look of the auditor dashboard and keep tap targets at least 44px.
8. **Verify before saying done.** Run the tests, lint and build named in the step and show the output. If a check needs a browser and you cannot run one, say so clearly and list the checks the owner must do by hand. Never claim a manual check passed if you did not do it. If a test fails for a reason unrelated to your change, report it and do not fix it.

**Prompt to use for each step:**
> Read PRD-v2.md. Do only Step `<ID>`. Follow the rules in section 0. Stop when the "Done when" checks pass and tell me what to run to verify.

---

## 1. What changes

1. **Auditor dashboard:** every photo the auditor sees can be opened fullscreen and downloaded. This covers work photos (Pending, Approved, Rejected tabs) and complaint photos (Pending, Accepted, Rejected tabs).
2. **Leaderboard:** remove the setting "Show my name on the leaderboard / When off, you appear as Anonymous". Everyone is shown by name.

---

## 2. How the code works today (checked in the code)

**Photos in the auditor dashboard**

| Where | File | Photo route | Notes |
|---|---|---|---|
| Work photos | `frontend/src/pages/AuditorDashboard.jsx`, local component `AuthenticatedImage` | `GET /auditor/submissions/{id}/image` | Loaded with the Bearer token as a blob URL. Shown as `h-56 object-cover`, so it is cropped in the card. |
| Complaint photos | `frontend/src/components/AuditorComplaintCard.jsx` | `GET /complaints/{id}/image` | Same blob approach. A status badge sits at the top-right of the photo. |

- Both routes are already limited on the server. A DB auditor only reaches photos in their assigned state and constituency (otherwise 404). The built-in auditor reaches all. Both routes return the raw image file with its real image type.
- The routes need the login token, so a plain `<a href>` link cannot download a photo. Downloads must be made from the blob the page has already loaded. **Part A needs no backend change.**
- The frontend has no test runner (only `npm run lint` and `npm run build`), so Part A checks are lint, build and manual.

**Leaderboard setting (every place it exists)**

| Layer | Where |
|---|---|
| API | `PUT /me/leaderboard-visibility` in `backend/app/routers/leaderboard_visibility.py`, registered in `backend/app/main.py` |
| API | `show_name` field in `MeResponse` and in `get_me` in `backend/app/routers/auth.py` |
| Logic | `_format_leaderboard_name` in `backend/app/routers/leaderboard.py` returns `"Anonymous"` when `show_name` is 0 |
| Database | `users.show_name` column (`backend/app/models.py`). Old databases got it from `backend/scripts/migrate_show_name.py`. |
| Tests | `backend/tests/test_leaderboard_show_name.py` |
| UI | The switch, its state, a `GET /me` read and a handler in `frontend/src/pages/Profile.jsx` |

**Data check (copy of `app.db` from 2026-09-19):** 43 users. One user has `show_name = 0`, and that user has 0 XP, so they are not on the leaderboard today.

---

## 3. Decisions (already made, do not re-decide)

| ID | Decision |
|---|---|
| D1 | "Fullscreen" means a full-viewport overlay (React portal), not the browser Fullscreen API, because iOS Safari does not support that API for images. |
| D2 | The viewer works on every photo card in both views and in all tabs. Server-side scope rules stay as they are. |
| D3 | Download uses the blob already loaded by the card. No extra network request, no backend change, original file bytes (no re-encoding). |
| D4 | Download file names: `civicquest-work-<submission id>.<ext>` and `civicquest-complaint-<complaint id>.<ext>`. `<ext>` comes from the blob type: `image/jpeg` gives `jpg`, `image/png` gives `png`, `image/webp` gives `webp`, anything else gives `jpg`. |
| D5 | The viewer is a reusable component with props only (no dashboard logic inside), so the admin dashboard can use it later. The admin dashboard is not changed now. |
| D6 | After the change the leaderboard shows the full name (trimmed, spaces collapsed, at most 60 characters). If the user has no name it shows the masked email (`ab***`). `"Anonymous"` is never produced. |
| D7 | **The `users.show_name` column stays** in the database and in `models.py`, unused. Reason: on databases created fresh by `create_all` the column is `NOT NULL` with no server default, so removing it from the model would break signup. Old databases also still need `migrate_show_name.py`, so do not delete that script. Dropping the column is a later, separate task. |
| D8 | *Default. The owner may change it before Part B starts.* Users who turned the setting off in the past will now appear by name once they have XP. If the owner wants old opt-outs to stay anonymous, the owner edits this decision and Steps B1 and B2 before Part B starts. Until then, follow the default. |

---

## 4. API changes

| Change | Detail |
|---|---|
| Removed | `PUT /me/leaderboard-visibility` (must return 404 afterwards) |
| Changed | `GET /me` no longer returns `show_name`. All other fields stay: `id, email, state, district, constituency, xp, location_locked_until` |
| Changed | `GET /leaderboard`: `name` is never `"Anonymous"`. Response shape stays `{items:[{rank,name,xp,is_me}], me:{rank,xp}}` |
| Unchanged | `GET /auditor/submissions/{id}/image`, `GET /complaints/{id}/image`, and every other route |

---

# PART A: AUDITOR PHOTO VIEWER (frontend only)

### Step A1: PhotoViewer component
**Touch only:** `frontend/src/components/PhotoViewer.jsx` (new file).

- Default export `PhotoViewer` with props: `src` (blob URL, required), `filename` (name without extension, for example `civicquest-work-12`), `title` (text for the top bar), `alt`, `onClose`.
- Named export `downloadPhoto(src, filename)`. It reads the blob with `fetch(src)` (a local blob URL, no network), picks the extension by D4, triggers the download through a temporary `<a download>` element, and removes that element. It must **not** revoke `src` (the card owns it).
- Render with `createPortal(..., document.body)`. Overlay: `fixed inset-0 z-[60]`, dark background (`bg-black/95`), `overscroll-contain`, height `h-dvh`. The existing modal and toast use `z-50`, so the viewer must sit above them.
- Top bar, left to right: the title, a **Download** button (icon and text), a **Close** button (X). Every button is at least 44 x 44 px, has a visible focus ring, and fits at 360px width. Pad the top and bottom with `env(safe-area-inset-*)` so phone notches do not cover the buttons.
- The photo fills the rest of the screen with `object-contain`, centered, never cropped and never stretched.
- Close on: the X button, the Escape key, a click or tap on the dark backdrop (not on the photo or the top bar).
- Accessibility: `role="dialog"`, `aria-modal="true"`, `aria-label` taken from `title`. On open, focus the Close button. On close, return focus to the element that was focused before.
- Lock page scrolling while open (`document.body.style.overflow = 'hidden'`) and restore the previous value on close or unmount.
- If a download fails, show a short message in the top bar ("Download failed. Try again.") and keep the viewer open.
- **Done when:** the file exists with both exports, and `npm run lint` and `npm run build` pass. (It is wired in during A2 and A3.)

### Step A2: Work photos in the auditor dashboard
**Touch only:** `frontend/src/pages/AuditorDashboard.jsx`.

- Inside `AuthenticatedImage`, keep the existing loading code. Once the image has loaded, wrap the `<img>` in a `<button type="button">` (full width, same rounded corners, `cursor-zoom-in`, visible focus ring, `aria-label="View photo fullscreen"`). Clicking it opens `PhotoViewer`. Add a small "expand" icon in the bottom-right corner of the photo as a hint (`pointer-events-none`).
- Use `filename = civicquest-work-${submissionId}` and `title = "Work photo #" + submissionId`. The card itself keeps its current look (`h-56 object-cover`).
- No viewer button while the image is loading or has failed.
- Opening or closing the viewer must never trigger Approve, Reject or any request.
- **Done when (manual, Photos view, Pending and Approved and Rejected tabs):** a click on a photo opens it fullscreen and uncropped. Download saves `civicquest-work-<id>.jpg` (or png or webp) that opens and looks identical to the photo. X, Escape and the backdrop all close it. The page behind does not scroll while it is open. Approve and Reject still work. `npm run lint` and `npm run build` pass.

### Step A3: Complaint photos in the auditor dashboard
**Touch only:** `frontend/src/components/AuditorComplaintCard.jsx`.

- Same as A2, for the complaint photo. The status badge is at the top-right, so put the expand icon at the bottom-right and wrap only the `<img>` in the button. The badge stays visible and is not covered.
- Use `filename = civicquest-complaint-${item.id}` and `title = "Complaint photo #" + item.id`.
- **Done when (manual, Complaints view, Pending and Accepted and Rejected tabs, including cards added with "Load more"):** the same checks as A2 pass. On a Pending card, typing a comment, opening the viewer and closing it leaves the comment text in place. `npm run lint` and `npm run build` pass.

---

# PART B: REMOVE "SHOW MY NAME ON THE LEADERBOARD"

### Step B1: Backend
**Touch only:** `backend/app/main.py`, `backend/app/routers/auth.py`, `backend/app/routers/leaderboard.py`, `backend/app/models.py` (one comment), and delete `backend/app/routers/leaderboard_visibility.py`.

0. **Preflight (read-only).** From `backend/`, run this and print the result in your reply. Do not act on it:
   `python -c "import sqlite3; c=sqlite3.connect('file:app.db?mode=ro', uri=True); print(c.execute('SELECT show_name, COUNT(*), SUM(xp>0) FROM users GROUP BY show_name').fetchall())"`
1. Delete `leaderboard_visibility.py`. Remove its import and its `app.include_router(...)` line from `main.py`.
2. In `auth.py`, remove `show_name` from `MeResponse` and from the `MeResponse(...)` call in `get_me`.
3. In `leaderboard.py`, delete the `show_name` check in `_format_leaderboard_name` and fix its docstring: full name (trimmed, spaces collapsed, at most 60 characters) when present, otherwise the masked email. Ranking, `limit` and the response shape do not change.
4. In `models.py`, keep `User.show_name` exactly as it is and add one comment above it: `# Deprecated: no longer read or written. Kept for database compatibility.`
5. Do not touch `scripts/migrate_show_name.py`, `signup.py`, `schemas.py` or any database file.
- **Done when:** the server starts. `http://localhost:8000/docs` no longer lists `PUT /me/leaderboard-visibility`. `GET /me` has no `show_name`. `GET /leaderboard` returns a normal name for a user whose `users.show_name` is 0. `grep -rn "show_name" backend/app` shows only `models.py`.

### Step B2: Backend tests
**Touch only:** `backend/tests/test_leaderboard_show_name.py`.

- Remove the `show_name` parameter from `make_user` and stop passing it. Delete `test_show_name_false_shows_anonymous` and the whole `TestLeaderboardVisibilityEndpoint` class. Change the module docstring to "Tests for user full name on the leaderboard and signup name validation."
- Keep every `TestSignupNameValidation` test and the other `TestLeaderboardNameFormatting` tests unchanged.
- Add three tests:
  1. `test_legacy_show_name_zero_is_ignored`: create a user named "Bob Builder" with 40 XP, set `u.show_name = 0`, commit, call `GET /leaderboard`, expect `items[0]["name"] == "Bob Builder"`.
  2. `test_me_response_has_no_show_name`: `GET /me` returns 200 and `"show_name"` is not in the JSON.
  3. `test_visibility_route_is_gone`: `PUT /me/leaderboard-visibility` with `{"show_name": false}` and a valid user token returns 404.
- **Done when:** `pytest tests/test_leaderboard_show_name.py tests/test_leaderboard.py -q` passes, and `pytest -q` from `backend/` shows no new failures.

### Step B3: Frontend
**Touch only:** `frontend/src/pages/Profile.jsx`.

- Delete: the `showName` and `visibilityError` state; the `useEffect` that calls `GET /me` only to read `show_name`; the `useEffect` that syncs `user?.show_name`; the `handleToggleShowName` function; the whole "Leaderboard Visibility Switch" block (the label, the text "When off, you appear as Anonymous.", the switch button); and the `visibilityError` paragraph under it.
- Keep: the counters grid, the closing tag of the card, the `refreshUser()` effect on mount, `fetchStats`, and everything else. Remove only imports or variables that become unused.
- **Done when:** `grep -rn "show_name\|showName\|leaderboard-visibility\|Anonymous" frontend/src` returns nothing. `npm run lint` and `npm run build` pass. The Profile page shows no switch, and no request to `/me/leaderboard-visibility` appears in the network tab. The Leaderboard page still lists names.

---

# PART C: FINISH

### Step C1: Final checks
- Run `pytest -q` in `backend/`, then `npm run lint` and `npm run build` in `frontend/`. Show all three outputs.
- Run `git status`. Only these files may have changed: `frontend/src/components/PhotoViewer.jsx` (new), `frontend/src/pages/AuditorDashboard.jsx`, `frontend/src/components/AuditorComplaintCard.jsx`, `frontend/src/pages/Profile.jsx`, `backend/app/main.py`, `backend/app/routers/auth.py`, `backend/app/routers/leaderboard.py`, `backend/app/models.py`, `backend/tests/test_leaderboard_show_name.py`, and `backend/app/routers/leaderboard_visibility.py` (deleted).
- **Done when:** all three commands pass and the file list matches.

### Step C2: End-to-end checklist (manual)
1. Log in as auditor. Photos view, Pending tab: click a photo. It opens fullscreen, complete and centered.
2. Download. The file has the right name, opens, and matches the photo.
3. Close with X, with Escape and with a tap on the backdrop. The page behind did not scroll or jump. Approve and Reject still work.
4. Repeat on the Approved and Rejected tabs.
5. Complaints view, all three tabs: same checks. A typed comment survives opening and closing the viewer.
6. Chrome device mode at 360px width, portrait and landscape: nothing is cut off and every button is easy to tap.
7. A DB auditor still cannot open a photo outside their constituency (404), and a citizen token still gets 403 on `/auditor/submissions/{id}/image`. The existing `test_scope.py` covers this.
8. As a citizen: the Profile page has no leaderboard switch, the Leaderboard still lists names, a user with no name shows as `ab***`, and nobody shows as "Anonymous".
9. `GET /me` has no `show_name`, and `PUT /me/leaderboard-visibility` returns 404.

---

## 5. Out of scope

Next and previous arrows between photos, zoom and pan controls, downloading many photos at once (ZIP), the admin dashboard viewer, logging downloads in the review log, dropping the `users.show_name` column, and any change to XP, the review flow or leaderboard ranking.
