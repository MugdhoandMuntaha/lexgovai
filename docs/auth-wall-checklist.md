# LexGOV AI Mandatory Authentication Wall Checklist

## 1. Architectural Principles Verified
- **Server-Side Enforcement**: Unauthenticated visitors receive HTTP 401 on backend API endpoints and HTTP 307 redirects to `/login?next=...` on frontend app routes.
- **Fail-Closed Default**: Backend separates routes into explicit `public_router` (only `/api/auth/signup`, `/api/auth/login`, and `/api/health`) and `protected_router` (`dependencies=[Depends(get_current_user)]`).
- **No Flash of Protected Content**: Next.js 16 App Router route groups `(public)` and `(app)` ensure zero protected HTML/JS payload or nav/footer markup is sent to signed-out visitors.
- **Cache-Control Defense**: Both edge `proxy.ts` and server layout emit `Cache-Control: no-store, max-age=0, must-revalidate` so back button after logout cannot render cached protected views (bfcache protection).
- **Anti-Enumeration & Throttling**: Generic login error message (`"Incorrect email or password."`) on both unknown emails and incorrect passwords. In-memory rate limiting enforces a 5-attempt sliding window per IP/email and locks out for 15 minutes returning HTTP 429 with `Retry-After`.
- **Zero Client `useEffect` State-Setting**: `AuthProvider` receives server-fetched `initialData: MeResponse` directly from the `(app)/layout.tsx` Server Component.

---

## 2. Verification Test Results

### Backend Automated Test Suite
- **Command**: `pytest -v` (30 tests)
- **Status**: 100% Passed (30 passed, 0 failed in 9.33s)
  - `test_route_enumerator_enforces_auth_fail_closed`: Reflects over all registered OpenAPI paths, verifying all non-allowlisted routes reject unauthenticated requests with 401.
  - `test_auth_unauthenticated_failure_modes`: Checks 401 on missing cookies, invalid cookies, expired sessions, and revoked sessions after logout.
  - `test_login_rate_limiting_defense`: 5 failed attempts trigger 429 Too Many Requests with `Retry-After` header.
  - `test_generic_login_error_prevents_user_enumeration`: Asserts identical generic error on missing vs bad password. Duplicate email returns 409 Conflict.
  - `test_password_validation_rules`: Rejects < 10 characters and common denylist with 400.
  - `test_health_check_privacy`: Confirms `/api/health` returns only `{"status": "ok"}` with zero LLM configuration leakage.
  - `test_cross_workspace_idor_isolation_returns_404`: Asserts cross-workspace resource access returns 404 (never 403 or data).
  - `test_csrf_origin_verification`: Blocks untrusted origins on state-changing requests with 403 `CSRF_ERROR`.
  - All 22 pre-existing subscription matrix, quota metering, SOP parsing, and pipeline tests passed.

### Frontend Quality & Build Verification
- **Lint**: `npm run lint` -> 0 errors, 0 warnings.
- **Build**: `npm run build` -> Clean compilation with Next.js 16 Turbopack.
- **Route Matrix**:
  - `(public)`: `/login`, `/signup`
  - `(app)`: `/`, `/upload`, `/regulations`, `/analysis`, `/action-plan/[id]`, `/pricing`, `/account`
  - Dynamic edge request interceptor: `proxy.ts` (formerly middleware)

