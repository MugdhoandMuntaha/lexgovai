"""FastAPI application: REST + SSE endpoints consumed by the Next.js frontend."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import datetime, timedelta, timezone
import hashlib
import io
import json
import logging
import os
import secrets
import time
from typing import Any, Callable

from fastapi import APIRouter, Depends, FastAPI, File, Form, HTTPException, Request, Response, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response, StreamingResponse
from pydantic import BaseModel

from . import agents, auth, sop_pdf, starter
from .adapters import ConsoleNotifier
from .api_v1 import ApiKeyCreateRequest, VALID_SCOPES, create_api_v1_router
from .billing import BillingProvider, MockBillingProvider
from .collaboration import (
    CommentCreateRequest,
    FindingReviewRequest,
    InviteAcceptRequest,
    InviteCreateRequest,
    MemberRoleUpdateRequest,
    generate_invite_token,
    has_role_at_least,
    resolve_workspace_members_with_status,
)
from .config import Settings, get_settings
from .db import Database, LEGACY_WORKSPACE_ID, new_id, utcnow
from .documents import DocumentParseError, chunk_text, extract_text, extract_document_text
from .entitlements import AnalysisOptions, EntitlementService
from .feature_options import API_KEY_MAX_ACTIVE_PER_WORKSPACE, calculate_adjusted_impact_score
from .llm import GeminiClient, LLMClient, LLMError, LLMNotConfiguredError
from .pipeline import NotFoundError, load_inputs, run_pipeline
from .plans import CAPABILITIES, PLANS, PlanId, get_plan, next_plan_with_capability
from .regulations import load_regulation_pair, load_regulation_pair_by_id
from .report import render_markdown
from .support import SupportTicketCreateRequest, derive_ticket_priority
from .schemas import (
    ActionPlanResponse,
    AnalyzeRequest,
    AuthResponse,
    CapabilityDetail,
    ChecklistItemResponse,
    ChecklistUpdateRequest,
    CheckoutRequest,
    CheckoutResponse,
    CompanyProfile,
    CompanyProfileCreate,
    DocumentUploadResponse,
    FeatureGatedErrorDetail,
    HealthResponse,
    LoginRequest,
    MeResponse,
    QuotaExceededErrorDetail,
    RegulationChangeResponse,
    SampleDocumentRequest,
    SignupRequest,
    StarterGuideRequest,
    StarterGuideResponse,
    StarterPolicyItem,
    StarterSOPRequest,
    SubscriptionChangeRequest,
    SubscriptionResponse,
    UsageMeter,
    UserResponse,
    WorkspaceResponse,
    LawCoverageResponse,
    LawDetailResponse,
    LawRelationResponse,
    LawSearchHit,
    LawSectionResponse,
    LawSourceResponse,
    LawSummaryResponse,
    LawVersionResponse,
    ChangePasswordRequest,
    ForgotPasswordRequest,
    ForgotPasswordResponse,
    PasswordActionResponse,
    ResetPasswordRequest,
    ResetPasswordVerifyResponse,
)
from .legal_library.change import compute_section_diffs
from .legal_library.pipeline import LegalIngestionPipeline
from .ports import OcrEngine, SourceCrawler
from .services import Services
from .subscriptions import SubscriptionService
from .usage import QuotaExceededError, UsageService
from .vectorstore import VectorStore

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("complianceos.api")

SAMPLE_SOP_FILE = "apex_logistics_sop.txt"
_UNSET = object()


class AdminUserCreateRequest(BaseModel):
    email: str
    password: str
    full_name: str | None = None
    role: str = "owner"
    plan_id: str = "free"
    is_platform_admin: bool = False


class AdminUserUpdateRequest(BaseModel):
    full_name: str | None = None
    role: str | None = None
    plan_id: str | None = None
    is_platform_admin: bool | None = None


class AdminUserResetPasswordRequest(BaseModel):
    new_password: str


# ---------------------------------------------------------------------------
# Custom Exceptions
# ---------------------------------------------------------------------------


from .auth import UnauthenticatedException


class FeatureGatedException(HTTPException):
    def __init__(self, detail: str, capability: str, required_plan: str, current_plan: str):
        super().__init__(status_code=status.HTTP_403_FORBIDDEN, detail=detail)
        self.capability = capability
        self.required_plan = required_plan
        self.current_plan = current_plan


def _default_llm(settings: Settings) -> LLMClient | None:
    if not settings.gemini_api_key:
        logging.getLogger(__name__).warning("GEMINI_API_KEY not set - analysis endpoints will return 503.")
        return None
    return GeminiClient(
        settings.gemini_api_key, settings.gemini_model, settings.embedding_model, settings.embedding_dimensions
    )


def create_app(
    settings: Settings | None = None,
    llm: LLMClient | None | object = _UNSET,
    ocr: OcrEngine | None | object = _UNSET,
    crawler: SourceCrawler | None | object = _UNSET,
) -> FastAPI:
    settings = settings or get_settings()
    db = Database(settings.storage_dir / "compliance.db")
    store = VectorStore(settings.storage_dir / "chroma")
    entitlements = EntitlementService(db)
    usage = UsageService(db, entitlements)
    subscriptions = SubscriptionService(db)
    billing = MockBillingProvider(db, subscriptions, settings.app_env)

    resolved_llm = _default_llm(settings) if llm is _UNSET else llm

    if ocr is _UNSET:
        from .ocr import CompositeOcrEngine, GeminiVisionOcr, TesseractOcr
        resolved_ocr: OcrEngine = CompositeOcrEngine(
            primary=GeminiVisionOcr(resolved_llm),  # type: ignore[arg-type]
            fallback=TesseractOcr(),
        )
    else:
        resolved_ocr = ocr  # type: ignore[assignment]

    resolved_crawler = None if crawler is _UNSET else crawler  # type: ignore[assignment]

    svc = Services(
        settings=settings,
        db=db,
        store=store,
        llm=resolved_llm,  # type: ignore[arg-type]
        entitlements=entitlements,
        usage=usage,
        subscriptions=subscriptions,
        billing=billing,
        notifier=ConsoleNotifier(),
        ocr=resolved_ocr,
        crawler=resolved_crawler,
    )

    # Seed default platform admin and demo accounts if missing in this database instance
    def _seed_initial_accounts():
        admin_email = "admin@complianceos.com.bd"
        if not db.get_user_by_email(admin_email):
            salt = auth.generate_salt()
            pw_hash = auth.hash_password("AdminPassword123!", salt)
            u = db.create_user(email=admin_email, password_hash=pw_hash, salt=salt, full_name="LexGOV AI Admin")
            ws = db.create_workspace(name="LexGOV AI Operations")
            db.create_membership(user_id=u["id"], workspace_id=ws["id"], role="owner")
            subscriptions.ensure_free_subscription(ws["id"])
            subscriptions.change_plan(ws["id"], "professional")
            db.set_platform_admin(u["id"], is_admin=True)

        for p in ["free", "starter", "growth", "professional"]:
            email = f"demo_{p}@complianceos.com.bd"
            if not db.get_user_by_email(email):
                salt = auth.generate_salt()
                pw_hash = auth.hash_password("DemoPassword123!", salt)
                u = db.create_user(email=email, password_hash=pw_hash, salt=salt, full_name=f"Demo {p.capitalize()}")
                ws = db.create_workspace(name=f"Demo {p.capitalize()} Enterprise")
                db.create_membership(user_id=u["id"], workspace_id=ws["id"], role="owner")
                subscriptions.ensure_free_subscription(ws["id"])
                if p != "free":
                    subscriptions.change_plan(ws["id"], p)

    _seed_initial_accounts()

    # Seed foundational Bangladesh laws and ensure sources are enabled in production/dev
    if settings.app_env.lower() != "test":
        try:
            from .legal_library.seed import seed_foundational_laws
            seed_foundational_laws(db)
            db._execute("UPDATE law_sources SET enabled = 1 WHERE enabled = 0")
        except Exception as err:
            logger.warning(f"Could not auto-seed foundational Bangladesh laws: {err}")

    is_prod = settings.app_env.lower() == "production"
    app = FastAPI(
        title="LexGOV AI API",
        version="1.0.0",
        docs_url=None if is_prod else "/docs",
        redoc_url=None if is_prod else "/redoc",
        openapi_url=None if is_prod else "/openapi.json",
    )
    app.state.services = svc

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["Content-Disposition"],
    )

    # -----------------------------------------------------------------------
    # Request-ID & Structured Latency Logging Middleware
    # -----------------------------------------------------------------------
    @app.middleware("http")
    async def request_id_and_logging_middleware(request: Request, call_next):
        req_id = request.headers.get("x-request-id") or new_id()
        request.state.request_id = req_id
        start_time = time.perf_counter()
        response = await call_next(request)
        duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
        response.headers["x-request-id"] = req_id
        logger.info(
            "request_completed method=%s path=%s status=%d duration_ms=%s request_id=%s",
            request.method,
            request.url.path,
            response.status_code,
            duration_ms,
            req_id,
        )
        return response

    # -----------------------------------------------------------------------
    # CSRF Origin Verification Middleware
    # -----------------------------------------------------------------------
    @app.middleware("http")
    async def csrf_origin_middleware(request: Request, call_next):
        if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
            origin = request.headers.get("origin")
            if origin:
                allowed = False
                for allowed_origin in settings.cors_origins:
                    if allowed_origin == "*" or origin.rstrip("/") == allowed_origin.rstrip("/"):
                        allowed = True
                        break
                host = request.headers.get("host")
                if host and (origin.endswith(f"://{host}") or origin == f"http://{host}" or origin == f"https://{host}"):
                    allowed = True

                if not allowed:
                    return JSONResponse(
                        status_code=status.HTTP_403_FORBIDDEN,
                        content={"code": "CSRF_ERROR", "detail": f"Untrusted origin: {origin}"},
                    )
        return await call_next(request)

    # -----------------------------------------------------------------------
    # Error Mapping Handlers
    # -----------------------------------------------------------------------
    @app.exception_handler(UnauthenticatedException)
    async def _unauthenticated_handler(_: Request, exc: UnauthenticatedException):
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"code": "UNAUTHENTICATED", "detail": exc.detail},
        )

    @app.exception_handler(FeatureGatedException)
    async def _feature_gated_handler(_: Request, exc: FeatureGatedException):
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content={
                "code": "FEATURE_NOT_IN_PLAN",
                "detail": exc.detail,
                "capability": exc.capability,
                "required_plan": exc.required_plan,
                "current_plan": exc.current_plan,
            },
        )

    @app.exception_handler(QuotaExceededError)
    async def _quota_exceeded_handler(_: Request, exc: QuotaExceededError):
        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            content={
                "code": "QUOTA_EXCEEDED",
                "detail": str(exc),
                "metric": exc.metric,
                "limit": exc.limit,
                "used": exc.used,
                "resets_at": exc.resets_at,
                "upgrade_to": exc.upgrade_to,
            },
        )

    @app.exception_handler(LLMNotConfiguredError)
    async def _llm_missing(_: Request, exc: LLMNotConfiguredError):
        return JSONResponse(status_code=503, content={"detail": str(exc)})

    @app.exception_handler(LLMError)
    async def _llm_failed(_: Request, exc: LLMError):
        return JSONResponse(status_code=502, content={"detail": str(exc)})

    @app.exception_handler(NotFoundError)
    async def _not_found(_: Request, exc: NotFoundError):
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @app.exception_handler(DocumentParseError)
    async def _bad_document(_: Request, exc: DocumentParseError):
        return JSONResponse(status_code=422, content={"detail": str(exc)})

    # -----------------------------------------------------------------------
    # FastAPI Dependencies
    # -----------------------------------------------------------------------
    def get_current_user(request: Request) -> dict[str, Any]:
        token = auth.extract_session_token(request)
        if not token:
            raise UnauthenticatedException()

        # 1. Primary path: Supabase JWT verification
        try:
            payload = auth.verify_supabase_token(
                token,
                supabase_url=settings.supabase_url,
                supabase_jwt_secret=settings.supabase_jwt_secret,
            )
            sub = payload.get("sub")
            if not sub:
                raise UnauthenticatedException("Token missing subject (sub) claim.")
            email = payload.get("email") or f"{sub}@supabase.local"
            user_metadata = payload.get("user_metadata") or {}
            full_name = user_metadata.get("full_name") or payload.get("name")
            user, is_new = svc.db.get_or_create_supabase_user(sub, email, full_name)
            if is_new:
                ws_name = f"{user.get('full_name') or user['email'].split('@')[0]}'s Workspace"
                workspace = svc.db.create_workspace(ws_name)
                svc.db.create_membership(user["id"], workspace["id"], role="owner")
                svc.subscriptions.ensure_free_subscription(workspace["id"])
            return user
        except UnauthenticatedException as jwt_err:
            # 2. Check internal signed session token (stateless across all serverless instances)
            internal_payload = auth.decode_internal_token(token, secret=settings.supabase_jwt_secret)
            if internal_payload:
                sub = internal_payload["sub"]
                email = internal_payload.get("email") or f"{sub}@complianceos.local"
                full_name = internal_payload.get("full_name")
                user, is_new = svc.db.get_or_create_supabase_user(sub, email, full_name)
                if is_new:
                    ws_name = f"{user.get('full_name') or user['email'].split('@')[0]}'s Workspace"
                    workspace = svc.db.create_workspace(ws_name)
                    svc.db.create_membership(user["id"], workspace["id"], role="owner")
                    svc.subscriptions.ensure_free_subscription(workspace["id"])
                return user

            # 3. Fallback: check legacy session store (for transitional testing and backwards compatibility)
            session = svc.db.get_session(token)
            if not session:
                raise jwt_err

            # Check absolute lifetime (30 days) and sliding renewal (7 days)
            try:
                created_dt = datetime.fromisoformat(session["created_at"])
                now_dt = datetime.now(timezone.utc)
                if (now_dt - created_dt) > auth.ABSOLUTE_LIFETIME:
                    svc.db.delete_session(token)
                    raise UnauthenticatedException("Session expired.")

                # Extend sliding expiry
                new_expires = min(now_dt + auth.SLIDING_LIFETIME, created_dt + auth.ABSOLUTE_LIFETIME)
                svc.db.update_session_expiry(token, new_expires.isoformat(timespec="seconds"))
            except UnauthenticatedException:
                raise
            except Exception:
                pass

            user = svc.db.get_user_by_id(session["user_id"])
            if not user:
                raise UnauthenticatedException()
            return user

    def get_current_workspace(request: Request, user: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
        token = auth.extract_session_token(request)
        session = svc.db.get_session(token) if token else None
        ws = None
        if session and session.get("workspace_id"):
            ws = svc.db.get_workspace(session["workspace_id"])
        if not ws:
            ws = svc.db.get_user_workspace(user["id"])
        if not ws:
            # Auto-provision workspace if none exists for this user
            ws_name = f"{user.get('full_name') or user['email'].split('@')[0]}'s Workspace"
            new_ws = svc.db.create_workspace(ws_name)
            svc.db.create_membership(user["id"], new_ws["id"], role="owner")
            svc.subscriptions.ensure_free_subscription(new_ws["id"])
            ws = svc.db.get_user_workspace(user["id"])
        if not ws:
            raise HTTPException(status_code=404, detail="Workspace not found for this user.")

        # Annotate with effective role and freeze state according to plan seat limits
        members = svc.db.list_workspace_members(ws["id"])
        seat_limit = svc.entitlements.limit(ws["id"], "team_members")
        annotated = resolve_workspace_members_with_status(members, seat_limit)
        user_mem = next((m for m in annotated if m["user_id"] == user["id"]), None)

        if user_mem:
            ws["role"] = user_mem["effective_role"]
            ws["raw_role"] = user_mem["role"]
            ws["is_frozen"] = user_mem["is_frozen"]
        else:
            ws["role"] = ws.get("role", "member")
            ws["raw_role"] = ws.get("role", "member")
            ws["is_frozen"] = False
        return ws

    def require_workspace_role(min_role: str) -> Callable:
        def dependency(workspace: dict[str, Any] = Depends(get_current_workspace)) -> dict[str, Any]:
            if not has_role_at_least(workspace.get("role", "viewer"), min_role):
                if workspace.get("is_frozen"):
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Your account in this workspace is restricted to read-only due to plan seat limits. Contact the workspace owner.",
                    )
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Action requires at least '{min_role}' role.",
                )
            return workspace

        return dependency

    def require_capability(capability: str, min_level: str) -> Callable:
        def dependency(workspace: dict[str, Any] = Depends(get_current_workspace)) -> dict[str, Any]:
            ws_id = workspace["id"]
            if not svc.entitlements.has_at_least(ws_id, capability, min_level):
                cur_plan = svc.entitlements.get_workspace_plan_id(ws_id)
                req_plan = next_plan_with_capability(capability, min_level) or "professional"
                raise FeatureGatedException(
                    detail=f"Capability '{capability}' requires level '{min_level}'. Please upgrade to {req_plan.capitalize()}.",
                    capability=capability,
                    required_plan=req_plan,
                    current_plan=cur_plan,
                )
            return workspace

        return dependency

    def require_platform_admin(user: dict[str, Any] = Depends(get_current_user)) -> dict[str, Any]:
        if not user.get("is_platform_admin"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Platform administrator privileges required."
            )
        return user

    # -----------------------------------------------------------------------
    # Ingestion Helper (Workspace Scoped)
    # -----------------------------------------------------------------------
    def ingest(
        company_profile_id: str,
        filename: str,
        text: str,
        workspace_id: str,
        extraction_method: str = "text",
        ocr_confidence: float | None = None,
        ocr_notes: str | None = None,
    ) -> DocumentUploadResponse:
        company = svc.db.get_company(company_profile_id, workspace_id)
        if company is None:
            raise NotFoundError("Company profile not found in your workspace.")
        llm_client = svc.require_llm()
        chunks = chunk_text(text)
        embeddings = llm_client.embed([f"{c.section}\n{c.text}" for c in chunks], "RETRIEVAL_DOCUMENT")
        doc_id = new_id()
        svc.store.add_document(doc_id, chunks, embeddings)
        svc.db.create_document(
            company_profile_id,
            filename,
            text,
            len(chunks),
            doc_id,
            workspace_id=workspace_id,
            extraction_method=extraction_method,
            ocr_confidence=ocr_confidence,
            ocr_notes=ocr_notes,
        )
        return DocumentUploadResponse(
            document_id=doc_id,
            company_profile_id=company_profile_id,
            filename=filename,
            chunk_count=len(chunks),
            sections=list(dict.fromkeys(c.section for c in chunks)),
            extraction_method=extraction_method,
            ocr_confidence=ocr_confidence,
            ocr_notes=ocr_notes,
        )

    # -----------------------------------------------------------------------
    # Routers
    # -----------------------------------------------------------------------
    public_router = APIRouter(prefix="/api")
    protected_router = APIRouter(prefix="/api", dependencies=[Depends(get_current_user)])

    # =======================================================================
    # PUBLIC ROUTES
    # =======================================================================
    @public_router.post("/auth/signup", response_model=AuthResponse)
    def signup(body: SignupRequest, response: Response):
        try:
            auth.validate_password(body.password)
        except ValueError as err:
            raise HTTPException(status_code=400, detail=str(err))

        existing = svc.db.get_user_by_email(body.email)
        if existing:
            raise HTTPException(status_code=409, detail="An account with this email already exists.")

        salt = auth.generate_salt()
        pwd_hash = auth.hash_password(body.password, salt)
        user = svc.db.create_user(body.email, pwd_hash, salt, body.full_name)

        ws_name = body.company_name or f"{body.full_name or body.email.split('@')[0]}'s Workspace"
        workspace = svc.db.create_workspace(ws_name)
        svc.db.create_membership(user["id"], workspace["id"], role="owner")

        sub = svc.subscriptions.ensure_free_subscription(workspace["id"])

        session_id = auth.generate_session_token(
            user_id=user["id"],
            workspace_id=workspace["id"],
            email=user["email"],
            full_name=user.get("full_name"),
            secret=settings.supabase_jwt_secret,
        )
        expires_at = (auth.utcnow() + auth.SLIDING_LIFETIME).isoformat(timespec="seconds")
        svc.db.create_session(session_id, user["id"], workspace["id"], expires_at)

        auth.set_session_cookie(response, session_id, is_production=(settings.app_env.lower() == "production"))

        return AuthResponse(
            user=UserResponse(
                id=user["id"],
                email=user["email"],
                full_name=user["full_name"],
                created_at=user["created_at"],
                is_platform_admin=bool(user.get("is_platform_admin")),
            ),
            workspace=WorkspaceResponse(id=workspace["id"], name=workspace["name"], role="owner", created_at=workspace["created_at"]),
            subscription=SubscriptionResponse(
                id=sub["id"],
                plan_id=sub["plan_id"],
                status=sub["status"],
                period_start=sub["period_start"],
                period_end=sub["period_end"],
                cancel_at_period_end=bool(sub["cancel_at_period_end"]),
            ),
        )

    @public_router.post("/auth/login", response_model=AuthResponse)
    def login(body: LoginRequest, request: Request, response: Response):
        client_ip = request.client.host if request.client else "unknown"
        ip_key = f"ip:{client_ip}"
        email_key = f"email:{body.email.strip().lower()}"

        # Rate limiting check
        allowed_ip, retry_ip = auth.login_limiter.check(ip_key)
        if not allowed_ip:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Too many failed login attempts. Please try again in {retry_ip} seconds.",
                headers={"Retry-After": str(retry_ip)},
            )
        allowed_email, retry_email = auth.login_limiter.check(email_key)
        if not allowed_email:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Too many failed login attempts. Please try again in {retry_email} seconds.",
                headers={"Retry-After": str(retry_email)},
            )

        user = svc.db.get_user_by_email(body.email)
        if not user or not auth.verify_password(body.password, user["salt"], user["password_hash"]):
            auth.login_limiter.record_failure(ip_key)
            auth.login_limiter.record_failure(email_key)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email or password.",
            )

        # Reset rate limiting counters on successful authentication
        auth.login_limiter.reset(ip_key)
        auth.login_limiter.reset(email_key)

        mem = svc.db.get_user_workspace(user["id"])
        if not mem:
            workspace = svc.db.create_workspace(f"{user['email'].split('@')[0]}'s Workspace")
            svc.db.create_membership(user["id"], workspace["id"], role="owner")
            role = "owner"
        else:
            workspace = mem
            role = mem["role"]

        sub = svc.subscriptions.ensure_free_subscription(workspace["id"])

        session_id = auth.generate_session_token(
            user_id=user["id"],
            workspace_id=workspace["id"],
            email=user["email"],
            full_name=user.get("full_name"),
            secret=settings.supabase_jwt_secret,
        )
        expires_at = (auth.utcnow() + auth.SLIDING_LIFETIME).isoformat(timespec="seconds")
        svc.db.create_session(session_id, user["id"], workspace["id"], expires_at)

        auth.set_session_cookie(response, session_id, is_production=(settings.app_env.lower() == "production"))

        return AuthResponse(
            user=UserResponse(
                id=user["id"],
                email=user["email"],
                full_name=user["full_name"],
                created_at=user["created_at"],
                is_platform_admin=bool(user.get("is_platform_admin")),
            ),
            workspace=WorkspaceResponse(id=workspace["id"], name=workspace["name"], role=role, created_at=workspace["created_at"]),
            subscription=SubscriptionResponse(
                id=sub["id"],
                plan_id=sub["plan_id"],
                status=sub["status"],
                period_start=sub["period_start"],
                period_end=sub["period_end"],
                cancel_at_period_end=bool(sub["cancel_at_period_end"]),
            ),
        )

    @public_router.post("/auth/forgot-password", response_model=ForgotPasswordResponse)
    def forgot_password(body: ForgotPasswordRequest, request: Request):
        client_ip = request.client.host if request.client else "unknown"
        ip_key = f"reset_ip:{client_ip}"
        email_key = f"reset_email:{body.email.strip().lower()}"

        allowed_ip, retry_ip = auth.password_reset_limiter.check(ip_key)
        if not allowed_ip:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Too many password reset requests. Please wait {retry_ip} seconds.",
                headers={"Retry-After": str(retry_ip)},
            )
        allowed_email, retry_email = auth.password_reset_limiter.check(email_key)
        if not allowed_email:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Too many password reset requests for this email. Please wait {retry_email} seconds.",
                headers={"Retry-After": str(retry_email)},
            )

        user = svc.db.get_user_by_email(body.email.strip().lower())
        reset_token: str | None = None

        if user:
            auth.password_reset_limiter.record_failure(email_key)
            auth.password_reset_limiter.record_failure(ip_key)

            raw_token = auth.generate_password_reset_token()
            token_hash = auth.hash_token(raw_token)
            expires_at = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(timespec="seconds")
            svc.db.create_password_reset_token(user["id"], token_hash, expires_at)

            # In development/test environments, expose token for easy verification
            if settings.app_env.lower() != "production" or os.getenv("TESTING"):
                reset_token = raw_token

            base_url = os.getenv("APP_BASE_URL", "https://lexgov-ai-app.vercel.app")
            reset_url = f"{base_url.rstrip('/')}/reset-password?token={raw_token}"
            logger.info("[PASSWORD RESET] Reset link generated for %s: %s", user["email"], reset_url)

        return ForgotPasswordResponse(
            ok=True,
            message="If an account with that email exists, password reset instructions have been generated.",
            reset_token=reset_token,
        )

    @public_router.get("/auth/password-reset/verify", response_model=ResetPasswordVerifyResponse)
    def verify_password_reset(token: str):
        if not token or len(token) < 10:
            raise HTTPException(status_code=400, detail="Invalid password reset token format.")

        token_hash = auth.hash_token(token)
        record = svc.db.get_password_reset_token(token_hash)
        if not record:
            raise HTTPException(status_code=400, detail="Invalid or expired password reset link.")

        if record.get("used_at"):
            raise HTTPException(status_code=400, detail="This password reset link has already been used.")

        expires_at_str = record.get("expires_at")
        if expires_at_str and datetime.fromisoformat(expires_at_str) < datetime.now(timezone.utc):
            raise HTTPException(status_code=400, detail="This password reset link has expired.")

        user = svc.db.get_user_by_id(record["user_id"])
        if not user:
            raise HTTPException(status_code=400, detail="Associated user account not found.")

        email = user["email"]
        parts = email.split("@")
        masked = f"{parts[0][:2]}***@{parts[1]}" if len(parts) == 2 and len(parts[0]) >= 2 else email

        return ResetPasswordVerifyResponse(valid=True, email=masked)

    @public_router.post("/auth/reset-password", response_model=PasswordActionResponse)
    def reset_password(body: ResetPasswordRequest):
        try:
            auth.validate_password(body.new_password)
        except ValueError as err:
            raise HTTPException(status_code=400, detail=str(err))

        token_hash = auth.hash_token(body.token)
        record = svc.db.get_password_reset_token(token_hash)
        if not record:
            raise HTTPException(status_code=400, detail="Invalid or expired password reset token.")

        if record.get("used_at"):
            raise HTTPException(status_code=400, detail="This password reset link has already been used.")

        expires_at_str = record.get("expires_at")
        if expires_at_str and datetime.fromisoformat(expires_at_str) < datetime.now(timezone.utc):
            raise HTTPException(status_code=400, detail="This password reset link has expired.")

        user = svc.db.get_user_by_id(record["user_id"])
        if not user:
            raise HTTPException(status_code=400, detail="Associated user account not found.")

        new_salt = auth.generate_salt()
        new_hash = auth.hash_password(body.new_password, new_salt)

        success = svc.db.update_user_password(user["id"], new_hash, new_salt)
        if not success:
            raise HTTPException(status_code=500, detail="Failed to update password.")

        svc.db.mark_password_reset_token_used(record["id"])

        # Reset login brute-force limiter for this email
        auth.login_limiter.reset(f"email:{user['email'].lower()}")

        return PasswordActionResponse(
            ok=True,
            message="Your password has been successfully reset. Please log in with your new password.",
        )

    @public_router.get("/health", response_model=HealthResponse)
    def health():
        return HealthResponse(status="ok")

    # =======================================================================
    # PROTECTED ROUTES (Require get_current_user)
    # =======================================================================
    @protected_router.post("/auth/logout")
    def logout(request: Request, response: Response):
        token = auth.extract_session_token(request)
        if token:
            svc.db.delete_session(token)
        auth.clear_session_cookie(response, is_production=(settings.app_env.lower() == "production"))
        return {"ok": True}

    @protected_router.post("/auth/change-password", response_model=PasswordActionResponse)
    def change_password(body: ChangePasswordRequest, user: dict[str, Any] = Depends(get_current_user)):
        full_user = svc.db.get_user_by_id(user["id"])
        if not full_user or not auth.verify_password(body.current_password, full_user["salt"], full_user["password_hash"]):
            raise HTTPException(status_code=400, detail="Current password is incorrect.")

        try:
            auth.validate_password(body.new_password)
        except ValueError as err:
            raise HTTPException(status_code=400, detail=str(err))

        if body.current_password == body.new_password:
            raise HTTPException(status_code=400, detail="New password cannot be identical to the current password.")

        new_salt = auth.generate_salt()
        new_hash = auth.hash_password(body.new_password, new_salt)
        svc.db.update_user_password(user["id"], new_hash, new_salt)

        return PasswordActionResponse(ok=True, message="Password updated successfully.")

    @protected_router.get("/me", response_model=MeResponse)
    def get_me(user: dict[str, Any] = Depends(get_current_user), workspace: dict[str, Any] = Depends(get_current_workspace)):
        sub = svc.subscriptions.ensure_free_subscription(workspace["id"])
        plan_id = svc.entitlements.get_workspace_plan_id(workspace["id"])
        plan = svc.entitlements.get_workspace_plan(workspace["id"])

        capabilities = {}
        for k, cdef in CAPABILITIES.items():
            current_lvl = plan.capabilities.get(k, "off")
            capabilities[k] = CapabilityDetail(
                key=k,
                display_name=cdef.display_name,
                category=cdef.category,
                current_level=current_lvl,
                implemented=cdef.implemented,
                description=cdef.description,
            )

        usage_meters = [
            UsageMeter(**m) for m in svc.usage.get_usage_summary(workspace["id"])
        ]

        return MeResponse(
            user=UserResponse(
                id=user["id"],
                email=user["email"],
                full_name=user["full_name"],
                created_at=user["created_at"],
                is_platform_admin=bool(user.get("is_platform_admin")),
            ),
            workspace=WorkspaceResponse(id=workspace["id"], name=workspace["name"], role=workspace["role"], created_at=workspace["created_at"]),
            subscription=SubscriptionResponse(
                id=sub["id"],
                plan_id=sub["plan_id"],
                status=sub["status"],
                period_start=sub["period_start"],
                period_end=sub["period_end"],
                cancel_at_period_end=bool(sub["cancel_at_period_end"]),
            ),
            plan_id=plan_id,
            capabilities=capabilities,
            usage=usage_meters,
            llm_configured=svc.llm is not None,
        )

    @protected_router.get("/plans")
    def get_plans():
        """Single source of truth for plans, pricing, capabilities and limits."""
        res = []
        for pid in ["free", "starter", "growth", "professional"]:
            p = get_plan(pid)
            caps = []
            for k, cdef in CAPABILITIES.items():
                caps.append({
                    "key": k,
                    "display_name": cdef.display_name,
                    "category": cdef.category,
                    "level": p.capabilities.get(k, "off"),
                    "implemented": cdef.implemented,
                    "description": cdef.description,
                })
            res.append({
                "id": p.id,
                "name": p.name,
                "price_bdt_monthly": p.price_bdt_monthly,
                "personalization_label": p.personalization_label,
                "description": p.description,
                "badge": p.badge,
                "is_featured": p.is_featured,
                "audit_history_days": p.audit_history_days,
                "capabilities": caps,
                "limits": p.limits,
            })
        return res

    @protected_router.get("/usage", response_model=list[UsageMeter])
    def get_usage(workspace: dict[str, Any] = Depends(get_current_workspace)):
        return [UsageMeter(**m) for m in svc.usage.get_usage_summary(workspace["id"])]

    @protected_router.post("/billing/checkout", response_model=CheckoutResponse)
    def create_checkout(body: CheckoutRequest, workspace: dict[str, Any] = Depends(require_workspace_role("owner"))):
        raw_plan = body.plan_id or body.target_plan_id or ""
        plan_id = raw_plan.lower()
        if plan_id not in PLANS:
            raise HTTPException(status_code=400, detail=f"Invalid plan '{raw_plan}'.")
        result = svc.billing.create_checkout(workspace["id"], plan_id, body.return_url)  # type: ignore[arg-type]
        return CheckoutResponse(
            session_id=result["session_id"],
            checkout_url=result["checkout_url"],
            plan_id=result["plan_id"],
            amount_bdt=result["amount_bdt"],
            status=result["status"],
        )

    @protected_router.post("/billing/webhook")
    def billing_webhook(payload: dict[str, Any]):
        return svc.billing.handle_webhook(payload)

    @protected_router.post("/subscription/cancel", response_model=SubscriptionResponse)
    def cancel_subscription(workspace: dict[str, Any] = Depends(require_workspace_role("owner"))):
        sub = svc.subscriptions.cancel_subscription(workspace["id"])
        return SubscriptionResponse(
            id=sub["id"],
            plan_id=sub["plan_id"],
            status=sub["status"],
            period_start=sub["period_start"],
            period_end=sub["period_end"],
            cancel_at_period_end=bool(sub["cancel_at_period_end"]),
        )

    @protected_router.post("/subscription/change", response_model=SubscriptionResponse)
    def change_subscription(body: SubscriptionChangeRequest, workspace: dict[str, Any] = Depends(get_current_workspace)):
        plan_id = body.plan_id.lower()
        if plan_id not in PLANS:
            raise HTTPException(status_code=400, detail=f"Invalid plan '{body.plan_id}'.")
        sub = svc.subscriptions.upgrade_plan(workspace["id"], plan_id)  # type: ignore[arg-type]
        return SubscriptionResponse(
            id=sub["id"],
            plan_id=sub["plan_id"],
            status=sub["status"],
            period_start=sub["period_start"],
            period_end=sub["period_end"],
            cancel_at_period_end=bool(sub["cancel_at_period_end"]),
        )

    @protected_router.get("/checklist", response_model=list[ChecklistItemResponse])
    def get_checklist(workspace: dict[str, Any] = Depends(get_current_workspace)):
        items = svc.db.get_checklist_items(workspace["id"])
        return [
            ChecklistItemResponse(
                id=i["id"],
                company_profile_id=i["company_profile_id"],
                title=i["title"],
                tier=i["tier"],
                reason=i["reason"],
                done=bool(i["done"]),
                done_at=i["done_at"],
                created_at=i["created_at"],
            )
            for i in items
        ]

    @protected_router.patch("/checklist/{item_id}", response_model=ChecklistItemResponse)
    def update_checklist_item(
        item_id: str, body: ChecklistUpdateRequest, workspace: dict[str, Any] = Depends(get_current_workspace)
    ):
        updated = svc.db.update_checklist_item(item_id, workspace["id"], body.done)
        if not updated:
            raise NotFoundError("Checklist item not found.")
        return ChecklistItemResponse(
            id=updated["id"],
            company_profile_id=updated["company_profile_id"],
            title=updated["title"],
            tier=updated["tier"],
            reason=updated["reason"],
            done=bool(updated["done"]),
            done_at=updated["done_at"],
            created_at=updated["created_at"],
        )

    @protected_router.post("/company-profile", response_model=CompanyProfile)
    def create_company_profile(
        body: CompanyProfileCreate, workspace: dict[str, Any] = Depends(get_current_workspace)
    ):
        svc.usage.check_gauge_quota(workspace["id"], "business_profiles", 1)
        record = svc.db.create_company(
            body.company_name, body.industry, body.country, body.description, workspace_id=workspace["id"]
        )
        return record

    @protected_router.post("/documents/upload", response_model=DocumentUploadResponse)
    def upload_document(
        company_profile_id: str = Form(...),
        file: UploadFile = File(...),
        workspace: dict[str, Any] = Depends(require_capability("sop_upload", "on")),
    ):
        content = file.file.read(settings.max_upload_bytes + 1)
        if len(content) > settings.max_upload_bytes:
            raise HTTPException(status_code=413, detail="File exceeds the 10 MB limit.")

        idempotency_key = f"upload_{workspace['id']}_{company_profile_id}_{new_id()}"
        svc.usage.reserve(workspace["id"], "sop_documents", idempotency_key)

        filename = file.filename or "document.txt"
        text, method, confidence, notes = extract_document_text(filename, content, ocr_engine=svc.ocr)

        ocr_key = None
        if method.startswith("ocr"):
            if not svc.entitlements.has_at_least(workspace["id"], "document_ocr", "basic"):
                svc.usage.release(idempotency_key)
                raise FeatureGatedException(
                    capability="document_ocr",
                    required_plan="starter",
                    current_plan=svc.entitlements.get_workspace_plan_id(workspace["id"]),
                    detail="Scanned document OCR is available on Starter, Growth, and Professional plans.",
                )
            try:
                from pypdf import PdfReader
                reader = PdfReader(io.BytesIO(content))
                num_pages = min(len(reader.pages), 20)
            except Exception:
                num_pages = 1
            ocr_key = f"ocr_{workspace['id']}_{new_id()}"
            try:
                svc.usage.reserve(workspace["id"], "ocr_pages", ocr_key, amount=num_pages)
            except Exception:
                svc.usage.release(idempotency_key)
                raise

        try:
            res = ingest(
                company_profile_id,
                filename,
                text,
                workspace_id=workspace["id"],
                extraction_method=method,
                ocr_confidence=confidence,
                ocr_notes=notes,
            )
            svc.usage.commit(idempotency_key)
            if ocr_key:
                svc.usage.commit(ocr_key)
            return res
        except Exception:
            svc.usage.release(idempotency_key)
            if ocr_key:
                svc.usage.release(ocr_key)
            raise

    @protected_router.post("/documents/sample", response_model=DocumentUploadResponse)
    def upload_sample_document(
        body: SampleDocumentRequest, workspace: dict[str, Any] = Depends(require_capability("sop_upload", "on"))
    ):
        idempotency_key = f"sample_{workspace['id']}_{body.company_profile_id}_{new_id()}"
        svc.usage.reserve(workspace["id"], "sop_documents", idempotency_key)

        try:
            text = (settings.sample_dir / SAMPLE_SOP_FILE).read_text(encoding="utf-8").strip()
            res = ingest(body.company_profile_id, "Apex_Logistics_SOP.txt", text, workspace_id=workspace["id"])
            svc.usage.commit(idempotency_key)
            return res
        except Exception:
            svc.usage.release(idempotency_key)
            raise

    @protected_router.post("/starter-guide", response_model=StarterGuideResponse)
    def starter_guide(body: StarterGuideRequest, workspace: dict[str, Any] = Depends(get_current_workspace)):
        return starter.generate_starter_guide(svc, body, workspace_id=workspace["id"])

    @protected_router.post("/starter-guide/sop", response_model=DocumentUploadResponse)
    def starter_sop(
        body: StarterSOPRequest,
        workspace: dict[str, Any] = Depends(require_capability("sop_upload", "on")),
    ):
        if not svc.entitlements.has_at_least(workspace["id"], "policy_drafts", "basic"):
            cur_plan = svc.entitlements.get_workspace_plan_id(workspace["id"])
            raise FeatureGatedException(
                detail="Starter SOP drafting requires Starter plan or higher.",
                capability="policy_drafts",
                required_plan="starter",
                current_plan=cur_plan,
            )

        svc.usage.check_gauge_quota(workspace["id"], "business_profiles", 1)
        idempotency_key = f"starter_sop_{workspace['id']}_{new_id()}"
        svc.usage.reserve(workspace["id"], "sop_documents", idempotency_key)

        try:
            res = starter.create_starter_sop(svc, body, workspace_id=workspace["id"])
            svc.usage.commit(idempotency_key)
            return res
        except ValueError as err:
            svc.usage.release(idempotency_key)
            raise HTTPException(status_code=400, detail=str(err))
        except Exception:
            svc.usage.release(idempotency_key)
            raise

    @protected_router.post("/starter-guide/sop/pdf")
    def download_starter_sop_pdf(
        body: StarterSOPRequest,
        workspace: dict[str, Any] = Depends(get_current_workspace),
    ):
        """Generates and downloads a clean, highly formatted, formal PDF for the Starter SOP."""
        try:
            guide = starter.generate_starter_guide(svc, body, workspace_id=workspace["id"])
            pdf_bytes = sop_pdf.generate_starter_sop_pdf(body, body.company_name, guide=guide)
        except Exception as exc:
            logger.error("Failed to generate starter SOP PDF: %s", exc)
            raise HTTPException(status_code=500, detail="Failed to generate SOP PDF.")

        clean_name = body.company_name.strip() or "Company"
        safe_name = "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in clean_name)
        filename = f"{safe_name}_Standard_Operating_Procedure.pdf"

        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "Content-Type": "application/pdf",
            },
        )

    @protected_router.get("/documents/{document_id}/pdf")
    def download_document_pdf(
        document_id: str,
        workspace: dict[str, Any] = Depends(get_current_workspace),
    ):
        """Generates and downloads a formatted, formal PDF for any stored SOP document."""
        doc = svc.db.get_document(document_id, workspace_id=workspace["id"])
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found.")

        company = svc.db.get_company(doc["company_profile_id"])
        company_name = company["company_name"] if company else "Company"

        try:
            pdf_bytes = sop_pdf.generate_document_pdf(doc, company_name=company_name)
        except Exception as exc:
            logger.error("Failed to render document PDF: %s", exc)
            raise HTTPException(status_code=500, detail="Failed to render document PDF.")

        safe_name = "".join(c if c.isalnum() or c in ("-", "_") else "_" for c in company_name.strip() or "Company")
        filename = f"{safe_name}_SOP_{document_id[:8]}.pdf"

        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "Content-Type": "application/pdf",
            },
        )

    @protected_router.get("/regulations/current")
    def current_regulation():
        """Regulation texts, diff and hash - authenticated endpoint."""
        return agents.watcher_payload(load_regulation_pair(settings.regulation_dir))

    @protected_router.get("/regulations")
    def list_regulations_catalog():
        """List all statutory regulations in the catalog with metadata and version counts."""
        regs = svc.db.list_regulations()
        out = []
        for r in regs:
            versions = svc.db.list_regulation_versions(r["id"], status="published")
            changes = svc.db.list_regulatory_changes(r["id"])
            latest_change = changes[0] if changes else None
            obs_count = 0
            if latest_change and latest_change.get("obligations"):
                try:
                    obs_count = len(json.loads(latest_change["obligations"]))
                except Exception:
                    obs_count = 0
            out.append({
                "id": r["id"],
                "title": r["title"],
                "country": r.get("country", "Bangladesh"),
                "sector": r.get("sector"),
                "description": r.get("description"),
                "created_at": r["created_at"],
                "version_count": len(versions),
                "latest_version": versions[-1]["version_label"] if versions else None,
                "latest_summary": latest_change["summary"] if latest_change else None,
                "obligations_count": obs_count,
            })
        return out

    @protected_router.get("/regulations/{regulation_id}")
    def get_regulation_detail(regulation_id: str):
        """Get detail for a specific regulation including diff and version texts."""
        reg = svc.db.get_regulation(regulation_id)
        if not reg:
            raise HTTPException(status_code=404, detail="Regulation not found.")
        versions = svc.db.list_regulation_versions(regulation_id, status="published")
        pair = load_regulation_pair_by_id(svc.db, regulation_id, settings.regulation_dir)
        payload = agents.watcher_payload(pair)
        changes = svc.db.list_regulatory_changes(regulation_id)
        return {
            "regulation": reg,
            "versions": versions,
            "pair": payload,
            "latest_change": changes[0] if changes else None,
        }

    @protected_router.post("/regulations/detect-change", response_model=RegulationChangeResponse)
    def detect_regulation_change(
        workspace: dict[str, Any] = Depends(require_capability("impact_analysis", "basic"))
    ):
        result, _cached = agents.run_watcher(svc)
        return result

    @protected_router.post("/regulations/{regulation_id}/detect-change", response_model=RegulationChangeResponse)
    def detect_specific_regulation_change(
        regulation_id: str,
        workspace: dict[str, Any] = Depends(require_capability("impact_analysis", "basic")),
    ):
        """Runs Agent 1 Watcher for a specific regulation ID."""
        svc.require_llm()
        result, _cached = agents.run_watcher(svc, regulation_id=regulation_id)
        return result

    def _emit_analysis_alerts(plan_obj: dict[str, Any], ws_id: str, u_id: str = "") -> None:
        try:
            from .alerts.router import AlertRouter
            router = AlertRouter(db=svc.db)
            score = plan_obj.get("impact_score", 0)
            urgency = str(plan_obj.get("urgency", "low")).lower()
            plan_id = plan_obj.get("id", "")
            if score >= 70 or urgency in ("high", "critical"):
                router.dispatch_event(
                    workspace_id=ws_id,
                    event_type="high_risk_finding",
                    entity_type="action_plan",
                    entity_id=plan_id,
                    payload={
                        "finding_title": f"High Impact Non-Compliance ({score}/100, Urgency: {urgency})",
                        "impact_score": score,
                        "urgency": urgency,
                        "link": f"/action-plan/{plan_id}",
                    },
                )
            else:
                router.dispatch_event(
                    workspace_id=ws_id,
                    event_type="analysis_completed",
                    entity_type="action_plan",
                    entity_id=plan_id,
                    payload={
                        "document_title": f"Action Plan #{plan_id[:8]}",
                        "link": f"/action-plan/{plan_id}",
                        "user_id": u_id,
                    },
                )
        except Exception as e:
            logger.warning(f"Could not dispatch analysis alert: {e}")

    @protected_router.post("/analyze", response_model=ActionPlanResponse)
    def analyze(
        body: AnalyzeRequest, workspace: dict[str, Any] = Depends(require_capability("impact_analysis", "basic"))
    ):
        idempotency_key = f"analyze_{workspace['id']}_{body.company_profile_id}_{body.document_id}_{new_id()}"
        svc.usage.reserve(workspace["id"], "detailed_analyses", idempotency_key)

        try:
            company, document = load_inputs(svc, body.company_profile_id, body.document_id, workspace_id=workspace["id"])
            options = svc.entitlements.derive_analysis_options(workspace["id"])

            for event in run_pipeline(
                svc,
                company,
                document,
                options=options,
                workspace_id=workspace["id"],
                regulation_id=body.regulation_id,
            ):
                if event["type"] == "completed":
                    svc.usage.commit(idempotency_key)
                    _emit_analysis_alerts(event["plan"], workspace["id"])
                    return event["plan"]
                if event["type"] == "error":
                    svc.usage.release(idempotency_key)
                    raise HTTPException(status_code=502, detail=f"Agent {event['agent']} failed: {event['message']}")
            svc.usage.release(idempotency_key)
            raise HTTPException(status_code=500, detail="Pipeline ended without a result.")
        except Exception:
            svc.usage.release(idempotency_key)
            raise

    @protected_router.post("/analyze/stream")
    def analyze_stream(
        body: AnalyzeRequest, workspace: dict[str, Any] = Depends(require_capability("impact_analysis", "basic"))
    ):
        svc.require_llm()
        idempotency_key = f"analyze_stream_{workspace['id']}_{body.company_profile_id}_{body.document_id}_{new_id()}"
        svc.usage.reserve(workspace["id"], "detailed_analyses", idempotency_key)

        try:
            company, document = load_inputs(svc, body.company_profile_id, body.document_id, workspace_id=workspace["id"])
            options = svc.entitlements.derive_analysis_options(workspace["id"])
        except Exception:
            svc.usage.release(idempotency_key)
            raise

        def events() -> Iterator[str]:
            try:
                for event in run_pipeline(
                svc,
                company,
                document,
                options=options,
                workspace_id=workspace["id"],
                regulation_id=body.regulation_id,
            ):
                    if event["type"] == "completed":
                        svc.usage.commit(idempotency_key)
                        _emit_analysis_alerts(event.get("plan", {}), workspace["id"])
                    elif event["type"] == "error":
                        svc.usage.release(idempotency_key)
                    yield f"event: {event['type']}\ndata: {json.dumps(event)}\n\n"
            except Exception:
                svc.usage.release(idempotency_key)
                raise

        return StreamingResponse(
            events(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    @protected_router.get("/action-plans/{plan_id}", response_model=ActionPlanResponse)
    @protected_router.get("/analyses/{plan_id}", response_model=ActionPlanResponse)
    def get_action_plan(plan_id: str, workspace: dict[str, Any] = Depends(get_current_workspace)):
        plan = svc.db.get_action_plan(plan_id, workspace["id"])
        if plan is None:
            raise NotFoundError("Action plan not found in your workspace.")

        cutoff = svc.entitlements.retention_cutoff(workspace["id"])
        if cutoff and plan.get("created_at") and plan["created_at"] < cutoff:
            raise NotFoundError("This action plan has exceeded your plan's audit retention window.")

        return plan

    @protected_router.get("/action-plans/{plan_id}/report")
    def download_report(
        plan_id: str, workspace: dict[str, Any] = Depends(require_capability("report_download", "basic"))
    ):
        plan = svc.db.get_action_plan(plan_id, workspace["id"])
        if plan is None:
            raise NotFoundError("Action plan not found in your workspace.")

        cutoff = svc.entitlements.retention_cutoff(workspace["id"])
        if cutoff and plan.get("created_at") and plan["created_at"] < cutoff:
            raise NotFoundError("This action plan has exceeded your plan's audit retention window.")

        report_level = svc.entitlements.level(workspace["id"], "report_download")
        markdown_content = render_markdown(plan, level=report_level)

        try:
            from .alerts.events import AlertEvent, AlertSeverity
            from .alerts.router import AlertRouter
            ar = AlertRouter(db=svc.db)
            ev = AlertEvent(
                workspace_id=workspace["id"],
                event_type="export_ready",
                severity=AlertSeverity.INFO,
                entity_type="action_plan",
                entity_id=plan_id,
                payload={
                    "export_type": "markdown",
                    "plan_id": plan_id,
                    "title": plan.get("company_name", "Compliance Action Plan"),
                    "download_url": f"/api/action-plans/{plan_id}/report",
                },
            )
            ar.route_event(ev)
        except Exception:
            pass

        return Response(
            content=markdown_content,
            media_type="text/markdown; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="compliance-action-plan-{plan_id[:8]}.md"'},
        )

    # -----------------------------------------------------------------------
    # S1: Regulatory News & Notification Center
    # -----------------------------------------------------------------------
    @protected_router.get("/news")
    def get_news(
        sector: str | None = None,
        jurisdiction: str | None = None,
        tag: str | None = None,
        limit: int = 50,
        offset: int = 0,
        workspace: dict[str, Any] = Depends(require_capability("regulatory_news", "on")),
    ):
        items = svc.db.list_news_items(sector=sector, jurisdiction=jurisdiction, limit=limit, offset=offset)
        if tag:
            t = tag.lower()
            items = [item for item in items if t in item.get("title", "").lower() or t in item.get("content", "").lower()]
        return {"items": items, "total": len(items)}

    @protected_router.get("/notifications")
    def get_notifications(
        unread_only: bool = False,
        limit: int = 50,
        user: dict[str, Any] = Depends(get_current_user),
        workspace: dict[str, Any] = Depends(get_current_workspace),
    ):
        notifs = svc.db.list_notifications(workspace["id"], user["id"], unread_only=unread_only, limit=limit)
        unread_count = svc.db.get_unread_notification_count(workspace["id"], user["id"])
        return {"notifications": notifs, "unread_count": unread_count}

    @protected_router.patch("/notifications/{notification_id}/read")
    def mark_notification_read(
        notification_id: str,
        user: dict[str, Any] = Depends(get_current_user),
        workspace: dict[str, Any] = Depends(get_current_workspace),
    ):
        ok = svc.db.mark_notification_read(notification_id, user["id"])
        if not ok:
            raise HTTPException(status_code=404, detail="Notification not found.")
        return {"ok": True}

    @protected_router.post("/notifications/mark-all-read")
    def mark_all_notifications_read(
        user: dict[str, Any] = Depends(get_current_user),
        workspace: dict[str, Any] = Depends(get_current_workspace),
    ):
        count = svc.db.mark_all_notifications_read(workspace["id"], user["id"])
        return {"ok": True, "count": count}

    # -----------------------------------------------------------------------
    # S2: Continuous Monitoring & Subscriptions
    # -----------------------------------------------------------------------
    @protected_router.get("/monitoring/sources")
    def get_monitoring_sources(workspace: dict[str, Any] = Depends(get_current_workspace)):
        sources = svc.db.list_regulation_sources()
        regs = svc.db.list_regulations()
        reg_map = {r["id"]: r for r in regs}
        results = []
        for s in sources:
            reg = reg_map.get(s.get("regulation_id", ""), {})
            results.append({
                "id": s["id"],
                "name": s["name"],
                "regulation_id": s.get("regulation_id"),
                "regulation_title": reg.get("title", s["name"]),
                "sector": reg.get("sector", "General"),
                "jurisdiction": reg.get("country", "Bangladesh"),
                "kind": s["kind"],
                "url": s.get("url"),
                "enabled": bool(s.get("enabled")),
                "last_checked": s.get("last_checked"),
                "last_error": s.get("last_error"),
                "status": "healthy" if not s.get("last_error") else "failing",
            })
        return {"sources": results}

    @protected_router.get("/monitoring/subscriptions")
    def get_monitoring_subscriptions(
        workspace: dict[str, Any] = Depends(get_current_workspace),
    ):
        subs = svc.db.list_monitor_subscriptions(workspace["id"])
        return {"subscriptions": subs}

    @protected_router.post("/monitoring/subscriptions")
    def create_monitoring_subscription(
        body: dict[str, Any],
        workspace: dict[str, Any] = Depends(require_capability("personalized_alerts", "basic")),
    ):
        reg_id = body.get("regulation_id")
        if not reg_id:
            raise HTTPException(status_code=400, detail="regulation_id is required.")
        reg = svc.db.get_regulation(reg_id)
        if not reg:
            raise HTTPException(status_code=404, detail="Regulation not found.")

        # Check gauge limit for monitored_sources
        current_count = svc.db.count_monitored_sources(workspace["id"])
        limit = svc.entitlements.limit(workspace["id"], "monitored_sources")
        if current_count >= limit:
            raise QuotaExceededError(
                metric="monitored_sources",
                limit=limit,
                used=current_count,
                resets_at="next plan billing cycle or upon unsubscribing a source",
                upgrade_to="Growth or Professional plan",
            )

        sub = svc.db.subscribe_monitor(workspace["id"], reg_id)
        return sub

    @protected_router.delete("/monitoring/subscriptions/{regulation_id}")
    def delete_monitoring_subscription(
        regulation_id: str,
        workspace: dict[str, Any] = Depends(require_capability("personalized_alerts", "basic")),
    ):
        ok = svc.db.unsubscribe_monitor(workspace["id"], regulation_id)
        if not ok:
            raise HTTPException(status_code=404, detail="Subscription not found in your workspace.")
        return {"ok": True}

    @protected_router.post("/monitoring/sources/{source_id}/crawl")
    def trigger_source_crawl(
        source_id: str,
        workspace: dict[str, Any] = Depends(require_capability("portal_crawler", "on")),
    ):
        src = svc.db.get_regulation_source(source_id)
        if not src:
            raise HTTPException(status_code=404, detail="Source not found.")
        job = svc.db.enqueue_job(
            job_type="crawl_sources",
            payload={"source_id": source_id, "workspace_id": workspace["id"]},
            idempotency_key=f"crawl_{workspace['id']}_{source_id}_{int(time.time())}",
        )
        return {"ok": True, "message": "Portal crawl enqueued", "job": job}

    # -----------------------------------------------------------------------
    # Bangladesh Legal Library (Protected Endpoints)
    # -----------------------------------------------------------------------
    @protected_router.get("/laws")
    def list_legal_library_laws(
        q: str | None = None,
        law_type: str | None = None,
        domain_tag: str | None = None,
        status: str | None = None,
        year: int | None = None,
        language: str | None = None,
        issuing_body: str | None = None,
        limit: int = 50,
        offset: int = 0,
        user: dict[str, Any] = Depends(get_current_user),
        workspace: dict[str, Any] = Depends(require_capability("legal_library", "basic")),
    ):
        publish_state = None if user.get("is_platform_admin") else "published"
        laws = svc.db.list_laws(
            q=q,
            law_type=law_type,
            domain_tag=domain_tag,
            status=status,
            year=year,
            language=language,
            issuing_body=issuing_body,
            publish_state=publish_state,
            limit=limit,
            offset=offset,
        )
        total = svc.db.count_laws(publish_state=publish_state, law_type=law_type, domain_tag=domain_tag)
        return {"laws": laws, "total": total}

    @protected_router.get("/laws/coverage", response_model=LawCoverageResponse)
    def get_legal_library_coverage(
        workspace: dict[str, Any] = Depends(require_capability("legal_library", "basic")),
    ):
        return LawCoverageResponse(**svc.db.get_laws_coverage_stats())

    @protected_router.get("/laws/search")
    def search_legal_library(
        q: str,
        limit: int = 20,
        law_id: str | None = None,
        workspace: dict[str, Any] = Depends(require_capability("legal_library", "basic")),
    ):
        if not q or not q.strip():
            return {"hits": []}

        fts_hits = svc.db.search_law_sections_fts(query=q, limit=limit * 2, law_id=law_id)
        vec_hits: list[Any] = []
        if svc.llm:
            try:
                emb = svc.llm.embed([q], task="RETRIEVAL_QUERY")[0]
                vec_hits = svc.store.query_law_sections(embedding=emb, top_k=limit * 2, law_id=law_id)
            except Exception as e:
                logger.warning(f"Vector search failed: {e}")

        scores: dict[str, float] = {}
        items_map: dict[str, dict[str, Any]] = {}
        match_types: dict[str, set[str]] = {}

        for rank, hit in enumerate(fts_hits):
            sec_id = hit["section_id"]
            scores[sec_id] = scores.get(sec_id, 0.0) + (1.0 / (60.0 + rank))
            match_types.setdefault(sec_id, set()).add("fts")
            items_map[sec_id] = {
                "section_id": sec_id,
                "law_id": hit["law_id"],
                "version_id": hit["version_id"],
                "heading": hit.get("heading"),
                "text": hit["text"],
                "number_label": hit["number_label"],
            }
            if q.strip().lower() in hit["number_label"].lower():
                scores[sec_id] += 0.5

        for rank, hit in enumerate(vec_hits):
            sec_id = hit.section_id
            scores[sec_id] = scores.get(sec_id, 0.0) + (1.0 / (60.0 + rank))
            match_types.setdefault(sec_id, set()).add("vector")
            if sec_id not in items_map:
                items_map[sec_id] = {
                    "section_id": sec_id,
                    "law_id": hit.law_id,
                    "version_id": hit.version_id,
                    "heading": hit.heading,
                    "text": hit.text,
                    "number_label": hit.number_label,
                }
            if q.strip().lower() in hit.number_label.lower():
                scores[sec_id] += 0.5

        sorted_ids = sorted(scores.keys(), key=lambda sid: scores[sid], reverse=True)[:limit]
        law_ids = {items_map[sid]["law_id"] for sid in sorted_ids}
        laws_map = {lid: svc.db.get_law(lid) for lid in law_ids}

        hits = []
        for sid in sorted_ids:
            item = items_map[sid]
            law = laws_map.get(item["law_id"])
            if not law or law.get("publish_state") != "published":
                continue

            types = match_types.get(sid, set())
            match_source = "hybrid" if len(types) > 1 else ("fts" if "fts" in types else "vector")
            snippet = item["text"][:300] + ("..." if len(item["text"]) > 300 else "")

            hits.append(LawSearchHit(
                law_id=item["law_id"],
                version_id=item["version_id"],
                section_id=item["section_id"],
                law_title_en=law["canonical_title_en"],
                law_title_bn=law.get("canonical_title_bn"),
                law_type=law["law_type"],
                year=law.get("year"),
                number_label=item["number_label"],
                heading=item.get("heading"),
                snippet=snippet,
                match_source=match_source,
                score=round(scores[sid], 4),
            ))

        return {"hits": hits}

    @protected_router.get("/laws/recommended")
    def get_recommended_laws(
        workspace: dict[str, Any] = Depends(require_capability("legal_library", "standard")),
    ):
        profiles = svc.db.list_companies(workspace["id"])
        if not profiles:
            laws = svc.db.list_laws(publish_state="published", limit=6)
            return {"recommended": [{"law": l, "reason": "Fundamental statutory compliance baseline in Bangladesh."} for l in laws]}

        profile = profiles[0]
        industry = (profile.get("industry") or "").lower()
        tag_mappings = {
            "retail": ["tax_vat", "trade"],
            "manufacturing": ["tax_vat", "customs", "labor", "environment"],
            "tech": ["general_corporate", "tax_vat", "data_privacy"],
            "logistics": ["customs", "tax_vat", "trade"],
            "finance": ["banking", "company_law", "tax_vat"],
            "healthcare": ["general_corporate", "labor", "environment"],
        }
        relevant_tags = tag_mappings.get(industry, ["tax_vat", "general_corporate", "labor"])

        matched_laws: list[dict[str, Any]] = []
        seen_ids: set[str] = set()

        for tag in relevant_tags:
            laws = svc.db.list_laws(domain_tag=tag, publish_state="published", limit=4)
            for l in laws:
                if l["id"] not in seen_ids:
                    seen_ids.add(l["id"])
                    matched_laws.append({
                        "law": l,
                        "reason": f"Directly regulates corporate {tag.replace('_', ' ').upper()} obligations for the {industry.title()} sector.",
                    })

        if not matched_laws:
            fallback = svc.db.list_laws(publish_state="published", limit=6)
            matched_laws = [{"law": l, "reason": "Standard corporate compliance requirement."} for l in fallback]

        return {"recommended": matched_laws[:6]}

    @protected_router.get("/laws/watchlist")
    def get_law_watchlist(
        user: dict[str, Any] = Depends(get_current_user),
        workspace: dict[str, Any] = Depends(require_capability("legal_library", "standard")),
    ):
        return {"watchlist": svc.db.list_law_watchlist(workspace["id"], user["id"])}

    @protected_router.get("/laws/{law_id}", response_model=LawDetailResponse)
    def get_law_details(
        law_id: str,
        user: dict[str, Any] = Depends(get_current_user),
        workspace: dict[str, Any] = Depends(require_capability("legal_library", "basic")),
    ):
        law = svc.db.get_law(law_id)
        if not law:
            raise HTTPException(status_code=404, detail="Law not found.")
        if law["publish_state"] != "published" and not user.get("is_platform_admin"):
            raise HTTPException(status_code=404, detail="Law not found.")

        current_ver = svc.db.get_current_law_version(law_id)
        versions = svc.db.list_law_versions(law_id)
        relations = svc.db.list_law_relations(law_id)
        is_watched = svc.db.is_law_watched(workspace["id"], user["id"], law_id)

        return LawDetailResponse(
            law=LawSummaryResponse(**law),
            current_version=LawVersionResponse(**current_ver) if current_ver else None,
            versions=[LawVersionResponse(**v) for v in versions],
            relations=[LawRelationResponse(**r) for r in relations],
            is_watched=is_watched,
        )

    @protected_router.get("/laws/{law_id}/sections")
    def get_law_sections(
        law_id: str,
        version_id: str | None = None,
        workspace: dict[str, Any] = Depends(require_capability("legal_library", "basic")),
    ):
        law = svc.db.get_law(law_id)
        if not law:
            raise HTTPException(status_code=404, detail="Law not found.")

        target_ver_id = version_id
        if not target_ver_id:
            cur = svc.db.get_current_law_version(law_id)
            if not cur:
                return {"sections": []}
            target_ver_id = cur["id"]

        sections = svc.db.list_law_sections(target_ver_id)
        return {"sections": [LawSectionResponse(**s) for s in sections]}

    @protected_router.get("/laws/{law_id}/sections/{section_id}", response_model=LawSectionResponse)
    def get_law_section_by_id(
        law_id: str,
        section_id: str,
        workspace: dict[str, Any] = Depends(require_capability("legal_library", "basic")),
    ):
        sec = svc.db.get_law_section(section_id)
        if not sec:
            raise HTTPException(status_code=404, detail="Section not found.")
        return LawSectionResponse(**sec)

    @protected_router.get("/laws/{law_id}/versions")
    def get_law_versions(
        law_id: str,
        workspace: dict[str, Any] = Depends(require_capability("legal_library", "basic")),
    ):
        versions = svc.db.list_law_versions(law_id)
        return {"versions": [LawVersionResponse(**v) for v in versions]}

    @protected_router.get("/laws/{law_id}/diff")
    def get_law_version_diff(
        law_id: str,
        from_version_id: str,
        to_version_id: str,
        workspace: dict[str, Any] = Depends(require_capability("legal_library", "standard")),
    ):
        from_sections = svc.db.list_law_sections(from_version_id)
        to_sections = svc.db.list_law_sections(to_version_id)
        diff_items = compute_section_diffs(from_sections, to_sections)
        return {
            "law_id": law_id,
            "from_version_id": from_version_id,
            "to_version_id": to_version_id,
            "diffs": [
                {
                    "number_label": d.number_label,
                    "heading": d.heading,
                    "change_type": d.change_type,
                    "old_text": d.old_text,
                    "new_text": d.new_text,
                }
                for d in diff_items
            ],
        }

    @protected_router.post("/laws/{law_id}/watch")
    def watch_law(
        law_id: str,
        user: dict[str, Any] = Depends(get_current_user),
        workspace: dict[str, Any] = Depends(require_capability("legal_library", "standard")),
    ):
        law = svc.db.get_law(law_id)
        if not law:
            raise HTTPException(status_code=404, detail="Law not found.")
        svc.db.add_to_law_watchlist(workspace["id"], user["id"], law_id)
        return {"ok": True, "is_watched": True}

    @protected_router.delete("/laws/{law_id}/watch")
    def unwatch_law(
        law_id: str,
        user: dict[str, Any] = Depends(get_current_user),
        workspace: dict[str, Any] = Depends(require_capability("legal_library", "standard")),
    ):
        svc.db.remove_from_law_watchlist(workspace["id"], user["id"], law_id)
        return {"ok": True, "is_watched": False}

    @protected_router.post("/laws/{law_id}/analyze", response_model=ActionPlanResponse)
    def analyze_law_against_sop(
        law_id: str,
        body: dict[str, Any],
        workspace: dict[str, Any] = Depends(require_capability("legal_library", "full")),
    ):
        company_profile_id = body.get("company_profile_id")
        document_id = body.get("document_id")
        if not company_profile_id or not document_id:
            raise HTTPException(status_code=400, detail="company_profile_id and document_id are required.")

        law = svc.db.get_law(law_id)
        if not law:
            raise HTTPException(status_code=404, detail="Law not found.")

        reg_alias_id = f"law_{law_id}"
        reg = svc.db.get_regulation(reg_alias_id)
        if not reg:
            reg = svc.db.create_regulation(
                title=law["canonical_title_en"],
                country="Bangladesh",
                sector=law["domain_tags"][0] if law.get("domain_tags") else "General",
                description=law.get("summary_ai") or law["canonical_title_en"],
                regulation_id=reg_alias_id,
            )
            cur_ver = svc.db.get_current_law_version(law_id)
            if cur_ver:
                sections = svc.db.list_law_sections(cur_ver["id"])
                text = "\n\n".join(f"{s['number_label']}: {s['text']}" for s in sections)
                svc.db.create_regulation_version(
                    regulation_id=reg["id"],
                    version_label="Current Enacted Edition",
                    text=text,
                    effective_date=utcnow()[:10],
                    status="published",
                    is_sample=False,
                )

        req = AnalyzeRequest(
            company_profile_id=company_profile_id,
            document_id=document_id,
            regulation_id=reg["id"],
        )
        return analyze(req, workspace)

    @protected_router.post("/laws/ask")
    def ask_law(
        body: dict[str, Any],
        user: dict[str, Any] = Depends(get_current_user),
        workspace: dict[str, Any] = Depends(require_capability("legal_library", "full")),
    ):
        query = body.get("question") or body.get("query")
        law_id = body.get("law_id")
        if not query or not query.strip():
            raise HTTPException(status_code=400, detail="question is required.")

        svc.require_llm()
        idempotency_key = f"law_ask_{workspace['id']}_{new_id()}"
        svc.usage.reserve(workspace["id"], "general_ai_questions", idempotency_key)

        fts_hits = svc.db.search_law_sections_fts(query=query, limit=5, law_id=law_id)
        sections_context = []
        for h in fts_hits:
            sections_context.append(f"[{h['number_label']} - {h.get('heading') or ''}]\n{h['text']}")

        if not sections_context:
            svc.usage.release(idempotency_key)
            return {
                "answer": "I could not find any statutory clauses or sections in the Bangladesh Legal Library addressing your query. Please consult the official gazette text or an accredited legal practitioner.",
                "citations": [],
                "is_in_scope": False,
            }

        prompt = (
            "You are an authoritative legal intelligence system for Bangladesh statutory law. "
            "Answer the question using ONLY the provided official sections below. "
            "Do NOT speculate, assume, or invent legal obligations not present in the excerpt.\n\n"
            f"STATUTORY EXCERPTS:\n{chr(10).join(sections_context)}\n\n"
            f"QUESTION: {query}"
        )

        try:
            class AnswerOut(BaseModel):
                answer: str

            ans_obj = svc.llm.generate_json(
                prompt=prompt,
                schema=AnswerOut,
                system="You are an authoritative legal archivist in Bangladesh.",
            )
            svc.usage.commit(idempotency_key)

            citations = []
            for h in fts_hits[:2]:
                l_item = svc.db.get_law(h["law_id"])
                citations.append({
                    "law_id": h["law_id"],
                    "law_title": l_item["canonical_title_en"] if l_item else "Statutory Law",
                    "section_id": h["section_id"],
                    "section_number": h["number_label"],
                    "quote": h["text"][:150],
                    "similarity_score": 1.0,
                })

            return {
                "answer": ans_obj.answer,
                "citations": citations,
                "is_in_scope": True,
            }
        except Exception:
            svc.usage.release(idempotency_key)
            raise

    # -----------------------------------------------------------------------
    # S3: Statutory Deadline Reminders
    # -----------------------------------------------------------------------
    @protected_router.get("/deadlines")
    def get_deadlines(
        status: str | None = None,
        workspace: dict[str, Any] = Depends(get_current_workspace),
    ):
        deadlines = svc.db.list_deadlines(workspace["id"], status=status)
        return {"deadlines": deadlines}

    @protected_router.post("/deadlines")
    def create_deadline(
        body: dict[str, Any],
        workspace: dict[str, Any] = Depends(require_capability("deadline_reminders", "basic")),
    ):
        title = body.get("title")
        due_date = body.get("due_date")
        if not title or not due_date:
            raise HTTPException(status_code=400, detail="title and due_date are required.")
        return svc.db.create_deadline(
            workspace_id=workspace["id"],
            title=title,
            due_date=due_date,
            source_type=body.get("source_type", "manual"),
            regulation_id=body.get("regulation_id"),
            checklist_item_id=body.get("checklist_item_id"),
        )

    @protected_router.patch("/deadlines/{deadline_id}")
    def update_deadline(
        deadline_id: str,
        body: dict[str, Any],
        workspace: dict[str, Any] = Depends(require_capability("deadline_reminders", "basic")),
    ):
        updated = svc.db.update_deadline(
            deadline_id=deadline_id,
            workspace_id=workspace["id"],
            title=body.get("title"),
            due_date=body.get("due_date"),
            status=body.get("status"),
        )
        if not updated:
            raise HTTPException(status_code=404, detail="Deadline not found in your workspace.")
        return updated

    @protected_router.delete("/deadlines/{deadline_id}")
    def delete_deadline(
        deadline_id: str,
        workspace: dict[str, Any] = Depends(require_capability("deadline_reminders", "basic")),
    ):
        ok = svc.db.delete_deadline(deadline_id, workspace["id"])
        if not ok:
            raise HTTPException(status_code=404, detail="Deadline not found in your workspace.")
        return {"ok": True}

    # -----------------------------------------------------------------------
    # S4: AI Compliance Assistant
    # -----------------------------------------------------------------------
    @protected_router.post("/assistant/ask")
    def assistant_ask(
        body: dict[str, Any],
        user: dict[str, Any] = Depends(get_current_user),
        workspace: dict[str, Any] = Depends(require_capability("ai_assistant", "limited")),
    ):
        svc.require_llm()
        question = body.get("question", "").strip()
        if not question:
            raise HTTPException(status_code=400, detail="question is required.")
        thread_id = body.get("thread_id")

        # Entitlement & Metering
        level = svc.entitlements.level(workspace["id"], "ai_assistant")
        from .feature_options import AssistantOptions
        options = AssistantOptions.from_level(level)

        idempotency_key = f"assistant_{workspace['id']}_{user['id']}_{new_id()}"
        svc.usage.reserve(workspace["id"], "general_ai_questions", idempotency_key)

        from .assistant import run_assistant_stream

        def stream_events() -> Iterator[str]:
            committed = False
            try:
                for event in run_assistant_stream(
                    svc=svc,
                    user_id=user["id"],
                    workspace_id=workspace["id"],
                    question=question,
                    thread_id=thread_id,
                    options=options,
                ):
                    if event["type"] == "completed":
                        svc.usage.commit(idempotency_key)
                        committed = True
                    elif event["type"] == "error":
                        if not committed:
                            svc.usage.release(idempotency_key)
                    yield f"event: {event['type']}\ndata: {json.dumps(event)}\n\n"
            except Exception:
                if not committed:
                    svc.usage.release(idempotency_key)
                raise
            finally:
                if not committed:
                    try:
                        svc.usage.release(idempotency_key)
                    except Exception:
                        pass

        return StreamingResponse(
            stream_events(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    @protected_router.get("/assistant/threads")
    def get_assistant_threads(
        user: dict[str, Any] = Depends(get_current_user),
        workspace: dict[str, Any] = Depends(get_current_workspace),
    ):
        return {"threads": svc.db.list_assistant_threads(workspace["id"], user["id"])}

    @protected_router.get("/assistant/threads/{thread_id}/messages")
    def get_assistant_thread_messages(
        thread_id: str,
        user: dict[str, Any] = Depends(get_current_user),
        workspace: dict[str, Any] = Depends(get_current_workspace),
    ):
        th = svc.db.get_assistant_thread(thread_id, workspace["id"])
        if not th or th["user_id"] != user["id"]:
            raise HTTPException(status_code=404, detail="Assistant thread not found.")
        return {"messages": svc.db.list_assistant_messages(thread_id)}

    @protected_router.delete("/assistant/threads/{thread_id}")
    def delete_assistant_thread(
        thread_id: str,
        user: dict[str, Any] = Depends(get_current_user),
        workspace: dict[str, Any] = Depends(get_current_workspace),
    ):
        th = svc.db.get_assistant_thread(thread_id, workspace["id"])
        if not th or th["user_id"] != user["id"]:
            raise HTTPException(status_code=404, detail="Assistant thread not found.")
        svc.db.delete_assistant_thread(thread_id, workspace["id"])
        return {"ok": True}

    # -----------------------------------------------------------------------
    # Admin Router (Guarded by require_platform_admin)
    # -----------------------------------------------------------------------
    admin_router = APIRouter(prefix="/api/admin", dependencies=[Depends(require_platform_admin)], tags=["admin"])

    @admin_router.get("/queue")
    def get_admin_queue():
        return svc.db.get_queue_stats()

    @admin_router.get("/regulations/pending")
    def get_pending_regulations():
        versions = svc.db._fetchall(
            "SELECT v.*, r.title as regulation_title, r.country, r.sector "
            "FROM regulation_versions v "
            "JOIN regulations r ON r.id = v.regulation_id "
            "WHERE v.status IN ('pending_review', 'draft') "
            "ORDER BY v.created_at DESC"
        )
        return {"versions": versions}

    @admin_router.post("/regulations/versions/{version_id}/publish")
    def admin_publish_version(version_id: str, admin: dict[str, Any] = Depends(require_platform_admin)):
        v = svc.db.publish_regulation_version(version_id, published_by=admin["id"])
        if not v:
            raise HTTPException(status_code=404, detail="Regulation version not found.")
        chg = svc.db._fetchone("SELECT * FROM regulatory_changes WHERE to_version_id = ?", (version_id,))
        if chg:
            svc.db.enqueue_job(
                job_type="fan_out_alerts",
                payload={"change_id": chg["id"], "regulation_id": v["regulation_id"]},
                idempotency_key=f"fan_out_{chg['id']}",
            )
        return {"ok": True, "version": v}

    @admin_router.post("/regulations/versions/{version_id}/reject")
    def admin_reject_version(version_id: str):
        v = svc.db.reject_regulation_version(version_id)
        if not v:
            raise HTTPException(status_code=404, detail="Regulation version not found.")
        return {"ok": True, "version": v}

    @admin_router.get("/sources")
    def admin_list_sources():
        return svc.db.list_regulation_sources()

    @admin_router.post("/sources")
    def admin_create_source(body: dict[str, Any]):
        reg_id = body.get("regulation_id")
        name = body.get("name", "Regulation Source")
        kind = body.get("kind", "url_poll")
        url = body.get("url")
        poll_interval = int(body.get("poll_interval", 86400))
        enabled = bool(body.get("enabled", False))
        if not reg_id:
            raise HTTPException(status_code=400, detail="regulation_id is required")
        return svc.db.create_regulation_source(
            regulation_id=reg_id,
            name=name,
            kind=kind,
            url=url,
            poll_interval=poll_interval,
            enabled=enabled,
        )

    @admin_router.post("/sources/{source_id}/poll")
    def admin_trigger_source_poll(source_id: str):
        src = svc.db.get_regulation_source(source_id)
        if not src:
            raise HTTPException(status_code=404, detail="Source not found.")
        job = svc.db.enqueue_job(
            job_type="check_sources",
            payload={"source_id": source_id},
            idempotency_key=f"poll_{source_id}_{int(time.time())}",
        )
        return {"ok": True, "message": "Source check enqueued", "job": job}

    @admin_router.post("/sources/{source_id}/crawl")
    def admin_trigger_source_crawl(source_id: str):
        src = svc.db.get_regulation_source(source_id)
        if not src:
            raise HTTPException(status_code=404, detail="Source not found.")
        job = svc.db.enqueue_job(
            job_type="crawl_sources",
            payload={"source_id": source_id},
            idempotency_key=f"crawl_{source_id}_{int(time.time())}",
        )
        return {"ok": True, "message": "Source crawl enqueued", "job": job}

    @admin_router.post("/news")
    def admin_create_news(body: dict[str, Any]):
        title = body.get("title")
        content = body.get("content") or body.get("summary")
        if not title or not content:
            raise HTTPException(status_code=400, detail="title and content/summary are required")
        return svc.db.create_news_item(
            title=title,
            content=content,
            sector=body.get("sector"),
            jurisdiction=body.get("jurisdiction", "Bangladesh"),
            source_url=body.get("source_url"),
            regulation_id=body.get("regulation_id"),
        )

    @admin_router.get("/support/tickets")
    def admin_list_tickets(status: str | None = None):
        return svc.db.list_support_tickets(status=status)

    @admin_router.patch("/support/tickets/{ticket_id}")
    def admin_update_ticket(ticket_id: str, body: dict[str, Any]):
        new_status = body.get("status")
        if not new_status:
            raise HTTPException(status_code=400, detail="status is required")
        updated = svc.db.update_support_ticket(ticket_id, new_status)
        if not updated:
            raise HTTPException(status_code=404, detail="Support ticket not found.")
        return updated

    # -----------------------------------------------------------------------
    # Admin Bangladesh Legal Library Endpoints
    # -----------------------------------------------------------------------
    @admin_router.get("/laws/review-queue")
    def admin_list_law_review_queue(resolved: bool = False, limit: int = 50):
        return {"queue": svc.db.list_law_review_queue(resolved=resolved, limit=limit)}

    @admin_router.post("/laws/{law_id}/approve")
    def admin_approve_law(
        law_id: str,
        body: dict[str, Any] | None = None,
        admin: dict[str, Any] = Depends(require_platform_admin),
    ):
        law = svc.db.get_law(law_id)
        if not law:
            raise HTTPException(status_code=404, detail="Law not found.")
        svc.db.update_law(law_id, publish_state="published")
        queue_items = svc.db.list_law_review_queue(resolved=False)
        for item in queue_items:
            if item["law_id"] == law_id:
                svc.db.resolve_law_review(item["id"], resolved_by=admin["id"], resolution="approved")
        return {"ok": True, "law": svc.db.get_law(law_id)}

    @admin_router.post("/laws/{law_id}/reject")
    def admin_reject_law(
        law_id: str,
        body: dict[str, Any] | None = None,
        admin: dict[str, Any] = Depends(require_platform_admin),
    ):
        law = svc.db.get_law(law_id)
        if not law:
            raise HTTPException(status_code=404, detail="Law not found.")
        svc.db.update_law(law_id, publish_state="rejected")
        queue_items = svc.db.list_law_review_queue(resolved=False)
        for item in queue_items:
            if item["law_id"] == law_id:
                svc.db.resolve_law_review(item["id"], resolved_by=admin["id"], resolution="rejected")
        return {"ok": True, "law": svc.db.get_law(law_id)}

    @admin_router.patch("/laws/{law_id}")
    def admin_edit_law_metadata(law_id: str, body: dict[str, Any]):
        law = svc.db.get_law(law_id)
        if not law:
            raise HTTPException(status_code=404, detail="Law not found.")
        updated = svc.db.update_law(law_id, **body)
        return {"ok": True, "law": updated}

    @admin_router.get("/laws/sources")
    def admin_list_law_sources():
        return {"sources": svc.db.list_law_sources()}

    @admin_router.post("/laws/sources")
    def admin_create_law_source(body: dict[str, Any]):
        name = body.get("name")
        base_url = body.get("base_url")
        source_type = body.get("source_type", "acts_and_ordinances")
        if not name or not base_url:
            raise HTTPException(status_code=400, detail="name and base_url are required.")
        src = svc.db.create_law_source(
            name=name,
            base_url=base_url,
            source_type=source_type,
            enabled=bool(body.get("enabled", False)),
            crawl_config=body.get("crawl_config", {}),
            rate_limit=float(body.get("rate_limit", 1.0)),
        )
        return {"ok": True, "source": src}

    @admin_router.patch("/laws/sources/{source_id}")
    def admin_update_law_source(source_id: str, body: dict[str, Any]):
        src = svc.db.get_law_source(source_id)
        if not src:
            raise HTTPException(status_code=404, detail="Law source not found.")
        updated = svc.db.update_law_source(source_id, **body)
        return {"ok": True, "source": updated}

    @admin_router.post("/laws/ingest/run")
    def admin_trigger_law_ingest_run(source_id: str | None = None):
        job = svc.db.enqueue_job(
            job_type="ingest_law_source",
            payload={"source_id": source_id},
            idempotency_key=f"law_ingest_{source_id or 'all'}_{int(time.time())}",
        )
        return {"ok": True, "message": "Law ingestion run enqueued", "job": job}

    @admin_router.post("/laws/upload")
    async def admin_upload_law_document(
        file: UploadFile = File(...),
        existing_law_id: str | None = Form(None),
        source_url: str | None = Form(None),
    ):
        content = await file.read()
        if not content:
            raise HTTPException(status_code=400, detail="Uploaded file is empty.")

        pipeline = LegalIngestionPipeline(
            db=svc.db,
            vectorstore=svc.store,
            llm=svc.llm,
            ocr_engine=svc.ocr,
        )
        try:
            res = pipeline.ingest_document(
                filename=file.filename or "law.pdf",
                content=content,
                source_url=source_url,
                existing_law_id=existing_law_id,
            )
            return {
                "ok": True,
                "law_id": res.law_id,
                "version_id": res.version_id,
                "publish_state": res.publish_state,
                "is_new": res.is_new,
                "is_changed": res.is_changed,
                "is_unchanged": res.is_unchanged,
                "summary_verified": res.summary_verified,
                "review_reason": res.review_reason,
            }
        except Exception as e:
            raise HTTPException(status_code=422, detail=f"Legal ingestion failed: {e}")

    # -----------------------------------------------------------------------
    # Admin User Management
    # -----------------------------------------------------------------------
    @admin_router.get("/users")
    def admin_list_users():
        users = svc.db.list_all_users()
        return {"users": users, "total": len(users)}

    @admin_router.post("/users")
    def admin_create_user(body: AdminUserCreateRequest):
        try:
            auth.validate_password(body.password)
        except ValueError as err:
            raise HTTPException(status_code=400, detail=str(err))

        existing = svc.db.get_user_by_email(body.email)
        if existing:
            raise HTTPException(status_code=409, detail="A user with this email already exists.")

        salt = auth.generate_salt()
        pwd_hash = auth.hash_password(body.password, salt)
        user = svc.db.create_user(body.email, pwd_hash, salt, body.full_name)

        ws_name = f"{body.full_name or body.email.split('@')[0]}'s Workspace"
        ws = svc.db.create_workspace(ws_name)
        svc.db.create_membership(user["id"], ws["id"], role=body.role or "owner")
        svc.subscriptions.ensure_free_subscription(ws["id"])
        if body.plan_id and body.plan_id != "free":
            svc.subscriptions.change_plan(ws["id"], body.plan_id)

        if body.is_platform_admin:
            svc.db.set_platform_admin(user["id"], is_admin=True)

        return {
            "ok": True,
            "user": {
                "id": user["id"],
                "email": user["email"],
                "full_name": user["full_name"],
                "role": body.role or "owner",
                "plan_id": body.plan_id or "free",
                "is_platform_admin": bool(body.is_platform_admin),
                "created_at": user["created_at"],
            },
        }

    @admin_router.patch("/users/{user_id}")
    def admin_update_user(user_id: str, body: AdminUserUpdateRequest):
        user = svc.db.get_user_by_id(user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found.")

        if body.full_name is not None:
            svc.db._execute("UPDATE users SET full_name = ? WHERE id = ?", (body.full_name.strip() or None, user_id))

        if body.is_platform_admin is not None:
            svc.db.set_platform_admin(user_id, is_admin=bool(body.is_platform_admin))

        ws = svc.db.get_user_workspace(user_id)
        if ws:
            if body.role:
                svc.db.update_member_role(user_id, ws["id"], body.role)
            if body.plan_id:
                svc.subscriptions.change_plan(ws["id"], body.plan_id)

        return {"ok": True, "message": "User updated successfully."}

    @admin_router.post("/users/{user_id}/reset-password")
    def admin_reset_user_password(user_id: str, body: AdminUserResetPasswordRequest):
        user = svc.db.get_user_by_id(user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found.")

        try:
            auth.validate_password(body.new_password)
        except ValueError as err:
            raise HTTPException(status_code=400, detail=str(err))

        salt = auth.generate_salt()
        pwd_hash = auth.hash_password(body.new_password, salt)
        svc.db.update_user_password(user_id, pwd_hash, salt)
        return {"ok": True, "message": "Password reset successfully."}

    @admin_router.delete("/users/{user_id}")
    def admin_delete_user(user_id: str, current_admin: dict[str, Any] = Depends(require_platform_admin)):
        if user_id == current_admin["id"]:
            raise HTTPException(status_code=400, detail="Cannot delete your own admin account.")
        user = svc.db.get_user_by_id(user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found.")
        svc.db.delete_user(user_id)
        return {"ok": True, "deleted_user_id": user_id}

    # -----------------------------------------------------------------------
    # Team Collaboration & RBAC (Slice S5)
    # -----------------------------------------------------------------------
    @protected_router.get("/team/members")
    def list_team_members(workspace: dict[str, Any] = Depends(get_current_workspace)):
        members = svc.db.list_workspace_members(workspace["id"])
        seat_limit = svc.entitlements.limit(workspace["id"], "team_members")
        annotated = resolve_workspace_members_with_status(members, seat_limit)
        return {
            "members": annotated,
            "seat_limit": seat_limit,
            "active_count": len([m for m in annotated if not m.get("is_frozen")]),
            "total_count": len(annotated),
        }

    @protected_router.patch("/team/members/{target_user_id}")
    def update_team_member_role(
        target_user_id: str,
        body: MemberRoleUpdateRequest,
        user: dict[str, Any] = Depends(get_current_user),
        workspace: dict[str, Any] = Depends(require_workspace_role("admin")),
    ):
        target_mem = svc.db.get_membership(target_user_id, workspace["id"])
        if not target_mem:
            raise HTTPException(status_code=404, detail="Member not found in workspace.")
        if target_mem["role"] == "owner":
            raise HTTPException(status_code=400, detail="Cannot modify workspace owner role.")
        if workspace["role"] != "owner" and target_mem["role"] == "admin":
            raise HTTPException(status_code=403, detail="Only workspace owner can alter admin privileges.")

        svc.db.update_member_role(workspace["id"], target_user_id, body.role)
        return {"success": True, "user_id": target_user_id, "new_role": body.role}

    @protected_router.delete("/team/members/{target_user_id}")
    def remove_team_member(
        target_user_id: str,
        user: dict[str, Any] = Depends(get_current_user),
        workspace: dict[str, Any] = Depends(require_workspace_role("admin")),
    ):
        target_mem = svc.db.get_membership(target_user_id, workspace["id"])
        if not target_mem:
            raise HTTPException(status_code=404, detail="Member not found in workspace.")
        if target_mem["role"] == "owner":
            raise HTTPException(status_code=400, detail="Cannot remove workspace owner.")
        if workspace["role"] != "owner" and target_mem["role"] == "admin":
            raise HTTPException(status_code=403, detail="Only workspace owner can remove admins.")
        if target_user_id == user["id"]:
            raise HTTPException(status_code=400, detail="Cannot remove oneself. Please leave workspace instead.")

        svc.db.remove_member(workspace["id"], target_user_id)
        return {"success": True, "removed_user_id": target_user_id}

    @protected_router.get("/team/invites")
    def list_team_invites(workspace: dict[str, Any] = Depends(require_workspace_role("admin"))):
        return svc.db.list_invites(workspace["id"])

    @protected_router.post("/team/invites")
    def create_team_invite(
        body: InviteCreateRequest,
        user: dict[str, Any] = Depends(get_current_user),
        workspace: dict[str, Any] = Depends(require_capability("team_collaboration", "on")),
    ):
        if not has_role_at_least(workspace.get("role", "viewer"), "admin"):
            raise HTTPException(status_code=403, detail="Admin role required to invite team members.")

        # Fail-closed gauge quota enforcement for team_members (3 on Growth, 10 on Pro)
        svc.usage.check_gauge_quota(workspace["id"], "team_members", 1)

        clean_email = body.email.strip().lower()
        members = svc.db.list_workspace_members(workspace["id"])
        if any(m.get("email", "").lower() == clean_email for m in members):
            raise HTTPException(status_code=400, detail="User is already an active member of this workspace.")

        active_invites = svc.db.list_invites(workspace["id"])
        if any(i.get("email", "").lower() == clean_email for i in active_invites):
            raise HTTPException(status_code=400, detail="An active pending invite already exists for this email.")

        raw_token, token_hash, expires_at = generate_invite_token()
        inv = svc.db.create_invite(workspace["id"], clean_email, body.role, token_hash, expires_at)

        # Notify via transactional email
        svc.notifier.send_email(
            to=clean_email,
            subject=f"Invitation to join {workspace.get('name', 'LexGOV AI')}",
            body=f"You have been invited to join {workspace.get('name', 'LexGOV AI')} as {body.role}.\n\nInvitation link: /team/accept?token={raw_token}",
        )

        return {
            "id": inv["id"],
            "email": clean_email,
            "role": body.role,
            "expires_at": expires_at,
            "token": raw_token,
        }

    @protected_router.delete("/team/invites/{invite_id}")
    def revoke_team_invite(
        invite_id: str,
        workspace: dict[str, Any] = Depends(require_workspace_role("admin")),
    ):
        revoked = svc.db.revoke_invite(invite_id, workspace["id"])
        if not revoked:
            raise HTTPException(status_code=404, detail="Invite not found or already processed.")
        return {"success": True, "revoked_invite_id": invite_id}

    @protected_router.post("/team/invites/accept")
    def accept_team_invite(
        body: InviteAcceptRequest,
        request: Request,
        user: dict[str, Any] = Depends(get_current_user),
    ):
        token_hash = hashlib.sha256(body.token.strip().encode("utf-8")).hexdigest()
        inv = svc.db.get_invite_by_token_hash(token_hash)
        now = utcnow()
        if not inv or inv.get("accepted_at") or inv.get("revoked_at") or inv.get("expires_at", "") < now:
            raise HTTPException(status_code=404, detail="Invalid, expired, or already used invite token.")

        accepted = svc.db.accept_invite(inv["id"], user["id"])
        if not accepted:
            raise HTTPException(status_code=400, detail="Unable to accept invitation.")

        session_token = auth.extract_session_token(request)
        if session_token:
            svc.db.update_session_workspace(session_token, inv["workspace_id"])

        svc.db.create_activity_event(
            inv["workspace_id"],
            user["id"],
            "member_joined",
            f"{user.get('email')} joined workspace via invite as {inv['role']}.",
        )
        return {"status": "accepted", "workspace_id": inv["workspace_id"], "role": inv["role"]}

    # -----------------------------------------------------------------------
    # Discussions / Comments (Slice S5)
    # -----------------------------------------------------------------------
    @protected_router.get("/comments")
    def get_comments(
        resource_type: str,
        resource_id: str,
        workspace: dict[str, Any] = Depends(get_current_workspace),
    ):
        if resource_type not in ("finding", "checklist_item"):
            raise HTTPException(status_code=400, detail="resource_type must be 'finding' or 'checklist_item'.")
        return svc.db.list_comments(workspace["id"], resource_type, resource_id)

    @protected_router.post("/comments")
    def create_comment(
        body: CommentCreateRequest,
        user: dict[str, Any] = Depends(get_current_user),
        workspace: dict[str, Any] = Depends(require_workspace_role("member")),
    ):
        cmt = svc.db.create_comment(
            workspace["id"], body.resource_type, body.resource_id, user["id"], body.content
        )
        cmt["full_name"] = user.get("full_name")
        cmt["email"] = user.get("email")
        return cmt

    # -----------------------------------------------------------------------
    # Human-in-the-loop Finding Reviews (Slice S5)
    # -----------------------------------------------------------------------
    @protected_router.get("/finding-reviews")
    def get_finding_reviews(
        plan_id: str,
        workspace: dict[str, Any] = Depends(get_current_workspace),
    ):
        plan = svc.db.get_action_plan(plan_id, workspace["id"])
        if not plan:
            raise HTTPException(status_code=404, detail="Action plan not found.")
        reviews = svc.db.list_finding_reviews(workspace["id"], plan_id)
        rev_map = {r["finding_id"]: r["status"] for r in reviews}
        findings = plan.get("findings", [])
        orig_score = plan.get("impact_score", 0)
        adj_score = calculate_adjusted_impact_score(orig_score, findings, rev_map)
        return {
            "plan_id": plan_id,
            "original_impact_score": orig_score,
            "adjusted_impact_score": adj_score,
            "reviews": reviews,
        }

    @protected_router.post("/finding-reviews")
    def submit_finding_review(
        body: FindingReviewRequest,
        user: dict[str, Any] = Depends(get_current_user),
        workspace: dict[str, Any] = Depends(require_workspace_role("member")),
    ):
        plan = svc.db.get_action_plan(body.plan_id, workspace["id"])
        if not plan:
            raise HTTPException(status_code=404, detail="Action plan not found.")

        findings = plan.get("findings", [])
        if not any(f.get("id") == body.finding_id for f in findings):
            raise HTTPException(status_code=404, detail="Finding not found in specified plan.")

        review = svc.db.create_or_update_finding_review(
            workspace["id"],
            body.plan_id,
            body.finding_id,
            body.status,
            user["id"],
            body.note,
            body.edited_citation,
        )

        all_reviews = svc.db.list_finding_reviews(workspace["id"], body.plan_id)
        rev_map = {r["finding_id"]: r["status"] for r in all_reviews}
        adj_score = calculate_adjusted_impact_score(plan.get("impact_score", 0), findings, rev_map)

        return {
            "review": review,
            "adjusted_impact_score": adj_score,
        }

    # -----------------------------------------------------------------------
    # API Key Settings Management (Slice S6)
    # -----------------------------------------------------------------------
    @protected_router.get("/settings/api-keys")
    def list_settings_api_keys(workspace: dict[str, Any] = Depends(require_workspace_role("admin"))):
        return svc.db.list_api_keys(workspace["id"])

    @protected_router.post("/settings/api-keys")
    def create_settings_api_key(
        body: ApiKeyCreateRequest,
        workspace: dict[str, Any] = Depends(require_capability("api_integrations", "limited")),
    ):
        if not has_role_at_least(workspace.get("role", "viewer"), "admin"):
            raise HTTPException(status_code=403, detail="Admin role required to generate API keys.")

        active_cnt = svc.db.count_active_api_keys(workspace["id"])
        if active_cnt >= API_KEY_MAX_ACTIVE_PER_WORKSPACE:
            raise HTTPException(
                status_code=400,
                detail=f"Maximum of {API_KEY_MAX_ACTIVE_PER_WORKSPACE} active API keys reached. Revoke an existing key first.",
            )

        raw_secret = "cos_live_" + secrets.token_urlsafe(32)
        prefix = raw_secret[:16]
        key_hash = hashlib.sha256(raw_secret.encode("utf-8")).hexdigest()

        invalid_scopes = set(body.scopes) - VALID_SCOPES
        if invalid_scopes:
            raise HTTPException(status_code=400, detail=f"Invalid scopes: {list(invalid_scopes)}")

        record = svc.db.create_api_key(
            workspace["id"],
            name=body.name,
            prefix=prefix,
            key_hash=key_hash,
            scopes=body.scopes,
        )

        return {
            "id": record["id"],
            "name": record["name"],
            "prefix": record["prefix"],
            "secret_key": raw_secret,
            "scopes": record["scopes"],
            "created_at": record["created_at"],
        }

    @protected_router.delete("/settings/api-keys/{key_id}")
    def revoke_settings_api_key(
        key_id: str,
        workspace: dict[str, Any] = Depends(require_workspace_role("admin")),
    ):
        revoked = svc.db.revoke_api_key(key_id, workspace["id"])
        if not revoked:
            raise HTTPException(status_code=404, detail="API key not found or already revoked.")
        return {"success": True, "revoked_key_id": key_id}

    # -----------------------------------------------------------------------
    # Support Ticketing (Slice S7)
    # -----------------------------------------------------------------------
    @protected_router.get("/support/tickets")
    def list_support_tickets_endpoint(workspace: dict[str, Any] = Depends(get_current_workspace)):
        return svc.db.list_support_tickets(workspace_id=workspace["id"])

    @protected_router.post("/support/tickets")
    def create_support_ticket_endpoint(
        body: SupportTicketCreateRequest,
        user: dict[str, Any] = Depends(get_current_user),
        workspace: dict[str, Any] = Depends(get_current_workspace),
    ):
        plan_id = svc.entitlements.get_workspace_plan_id(workspace["id"])
        priority, sla_text = derive_ticket_priority(plan_id)

        ticket = svc.db.create_support_ticket(
            workspace["id"],
            user["id"],
            body.subject,
            body.message,
            priority=priority,
        )

        svc.db.create_notification(
            workspace_id=workspace["id"],
            user_id=user["id"],
            title=f"Support Ticket Logged: {body.subject}",
            body=f"Your ticket has been prioritized as {priority.capitalize()} (SLA: {sla_text}).",
            link="/support",
        )

        svc.notifier.send_email(
            to=user["email"],
            subject=f"[Support #{ticket['id'][:8]}] {body.subject}",
            body=f"Hello {user.get('full_name', 'Customer')},\n\nWe received your support ticket:\n\nSubject: {body.subject}\nPriority: {priority.capitalize()}\nSLA: {sla_text}\n\nOur team will review your inquiry shortly.",
        )

        return {
            "ticket": ticket,
            "priority": priority,
            "sla": sla_text,
        }

    # Attach routers
    from .alerts.api import create_alerts_router, create_alerts_webhook_router
    alerts_router = create_alerts_router(svc, get_current_user, get_current_workspace)
    alerts_webhook_router = create_alerts_webhook_router(svc)

    api_v1_router = create_api_v1_router(svc)
    app.include_router(public_router)
    app.include_router(alerts_webhook_router)
    app.include_router(protected_router)
    app.include_router(alerts_router)
    app.include_router(admin_router)
    app.include_router(api_v1_router)

    return app
