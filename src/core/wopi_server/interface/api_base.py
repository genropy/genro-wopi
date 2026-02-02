# Copyright 2025 Softwell S.r.l. - SPDX-License-Identifier: Apache-2.0
"""FastAPI route generation from endpoint classes via introspection.

This module generates REST API routes automatically from endpoint classes
by introspecting method signatures and creating appropriate handlers.

Components:
    create_app: FastAPI application factory.
    register_endpoint: Register endpoint methods as FastAPI routes.
    verify_tenant_token: Token verification for tenant-scoped requests.
    require_admin_token: Admin-only endpoint protection.
    require_token: General authentication dependency.

Example:
    Create and run the API server::

        from core.wopi_server.interface import create_app
        from core.wopi_server.wopi_proxy import WopiProxy

        proxy = WopiProxy(db_path="/data/wopi.db")
        app = create_app(proxy, api_token="secret")

        # Run with uvicorn
        import uvicorn
        uvicorn.run(app, host="0.0.0.0", port=8000)

    Register custom endpoints::

        from fastapi import FastAPI
        from core.wopi_server.interface import register_endpoint

        app = FastAPI()
        endpoint = MyCustomEndpoint(table)
        register_endpoint(app, endpoint)

Note:
    Authentication uses X-API-Token header. Global token grants admin
    access to all tenants. Tenant tokens restrict access to own resources.
"""

from __future__ import annotations

import inspect
import logging
import secrets
from collections.abc import Callable
from collections.abc import Callable as CallableType
from contextlib import AbstractAsyncContextManager
from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Query, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.security import APIKeyHeader

from .endpoint_base import BaseEndpoint

if TYPE_CHECKING:
    from ..wopi_proxy import WopiProxy

logger = logging.getLogger(__name__)

# Authentication constants
API_TOKEN_HEADER_NAME = "X-API-Token"
api_key_scheme = APIKeyHeader(name=API_TOKEN_HEADER_NAME, auto_error=False)

# Global service reference (set by create_app)
_service: WopiProxy | None = None


def _get_http_method_fallback(method_name: str) -> str:
    """Infer HTTP method from method name prefix.

    Args:
        method_name: Name of the endpoint method.

    Returns:
        HTTP method string (GET, POST, DELETE, PATCH, PUT).
    """
    if method_name.startswith(("add", "create", "post", "run", "suspend", "activate")):
        return "POST"
    elif method_name.startswith(("delete", "remove")):
        return "DELETE"
    elif method_name.startswith(("update", "patch")):
        return "PATCH"
    elif method_name.startswith(("set", "put")):
        return "PUT"
    return "GET"


def _count_params_fallback(method: Callable) -> int:
    """Count non-self parameters for a method.

    Args:
        method: The method to introspect.

    Returns:
        Number of parameters excluding 'self'.
    """
    sig = inspect.signature(method)
    return sum(1 for p in sig.parameters if p != "self")


def _create_model_fallback(method: Callable, method_name: str) -> type:
    """Create Pydantic model from method signature.

    Args:
        method: The method to introspect.
        method_name: Name used for model class name.

    Returns:
        Dynamically created Pydantic model class.
    """
    from typing import get_type_hints

    from pydantic import create_model

    sig = inspect.signature(method)

    try:
        hints = get_type_hints(method)
    except Exception:
        hints = {}

    fields = {}
    for param_name, param in sig.parameters.items():
        if param_name == "self":
            continue

        annotation = hints.get(param_name, param.annotation)
        if annotation is inspect.Parameter.empty:
            annotation = Any

        if param.default is inspect.Parameter.empty:
            fields[param_name] = (annotation, ...)
        else:
            fields[param_name] = (annotation, param.default)

    model_name = f"{method_name.title().replace('_', '')}Request"
    return create_model(model_name, **fields)


def register_endpoint(app: FastAPI | APIRouter, endpoint: Any, prefix: str = "") -> None:
    """Register all methods of an endpoint as FastAPI routes.

    Introspects the endpoint to discover async methods and creates
    appropriate GET (query params) or POST (body) routes.

    Args:
        app: FastAPI app or APIRouter to register routes on.
        endpoint: Endpoint instance (BaseEndpoint or duck-typed).
        prefix: Optional URL prefix. Defaults to /{endpoint.name}.

    Example:
        ::

            endpoint = TenantEndpoint(db.table("tenants"))
            register_endpoint(app, endpoint)
            # Creates routes: GET /tenants/list, POST /tenants/add, etc.
    """
    name = getattr(endpoint, "name", endpoint.__class__.__name__.lower())
    base_path = prefix or f"/{name}"

    if isinstance(endpoint, BaseEndpoint):
        methods = endpoint.get_methods()
    else:
        methods = []
        for method_name in dir(endpoint):
            if method_name.startswith("_"):
                continue
            method = getattr(endpoint, method_name)
            if callable(method) and inspect.iscoroutinefunction(method):
                methods.append((method_name, method))

    for method_name, method in methods:
        if isinstance(endpoint, BaseEndpoint):
            http_method = endpoint.get_http_method(method_name)
            param_count = endpoint.count_params(method_name)
        else:
            http_method = _get_http_method_fallback(method_name)
            param_count = _count_params_fallback(method)

        path = f"{base_path}/{method_name}"
        doc = method.__doc__ or f"{method_name} operation"

        if http_method == "GET" or (http_method == "DELETE" and param_count <= 3):
            _register_query_route(app, path, method, http_method, doc, endpoint)
        else:
            _register_body_route(app, path, method, http_method, doc, method_name, endpoint)


def _register_query_route(
    app: FastAPI | APIRouter,
    path: str,
    method: Callable,
    http_method: str,
    doc: str,
    endpoint: Any = None,
) -> None:
    """Register route with query parameters."""
    sig = inspect.signature(method)

    params = []
    for param_name, param in sig.parameters.items():
        if param_name == "self":
            continue

        ann = param.annotation if param.annotation is not inspect.Parameter.empty else str
        default = param.default if param.default is not inspect.Parameter.empty else ...
        params.append((param_name, ann, default))

    async def handler(request: Request, **kwargs: Any) -> Any:
        # Propagate tenant_id from token authentication to endpoint
        if endpoint is not None:
            tenant_id = getattr(request.state, "token_tenant_id", None)
            if tenant_id:
                endpoint._current_tenant_id = tenant_id
            elif getattr(request.state, "is_admin", False):
                # Admin token - use default tenant unless specified in request
                endpoint._current_tenant_id = kwargs.get("tenant_id", "default")
            else:
                endpoint._current_tenant_id = "default"
        return await method(**kwargs)

    # Build signature with Request as first param + query params
    new_params = [
        inspect.Parameter(
            name="request",
            kind=inspect.Parameter.POSITIONAL_OR_KEYWORD,
            annotation=Request,
        )
    ] + [
        inspect.Parameter(
            name=p[0],
            kind=inspect.Parameter.KEYWORD_ONLY,
            default=Query(p[2]) if p[2] is not ... else Query(...),
            annotation=p[1],
        )
        for p in params
    ]
    handler.__signature__ = inspect.Signature(parameters=new_params)  # type: ignore
    handler.__doc__ = doc

    if http_method == "GET":
        app.get(path, summary=doc.split("\n")[0])(handler)
    elif http_method == "DELETE":
        app.delete(path, summary=doc.split("\n")[0])(handler)


def _make_body_handler(method: Callable, RequestModel: type, endpoint: Any = None) -> Callable:
    """Create handler that accepts body and calls method."""

    async def handler(request: Request, data: RequestModel) -> Any:  # type: ignore
        # Propagate tenant_id from token authentication to endpoint
        if endpoint is not None:
            tenant_id = getattr(request.state, "token_tenant_id", None)
            if tenant_id:
                endpoint._current_tenant_id = tenant_id
            elif getattr(request.state, "is_admin", False):
                # Admin token - use default tenant unless specified in body
                body_data = data.model_dump()
                endpoint._current_tenant_id = body_data.get("tenant_id", "default")
            else:
                endpoint._current_tenant_id = "default"
        return await method(**data.model_dump())

    handler.__signature__ = inspect.Signature(  # type: ignore
        parameters=[
            inspect.Parameter(
                "request",
                inspect.Parameter.POSITIONAL_OR_KEYWORD,
                annotation=Request,
            ),
            inspect.Parameter(
                "data",
                inspect.Parameter.POSITIONAL_OR_KEYWORD,
                annotation=RequestModel,
            ),
        ]
    )
    return handler


def _register_body_route(
    app: FastAPI | APIRouter,
    path: str,
    method: Callable,
    http_method: str,
    doc: str,
    method_name: str,
    endpoint: Any = None,
) -> None:
    """Register route with request body."""
    if isinstance(endpoint, BaseEndpoint):
        RequestModel = endpoint.create_request_model(method_name)
    else:
        RequestModel = _create_model_fallback(method, method_name)

    handler = _make_body_handler(method, RequestModel, endpoint)
    handler.__doc__ = doc

    if http_method == "POST":
        app.post(path, summary=doc.split("\n")[0])(handler)
    elif http_method == "PUT":
        app.put(path, summary=doc.split("\n")[0])(handler)
    elif http_method == "PATCH":
        app.patch(path, summary=doc.split("\n")[0])(handler)
    elif http_method == "DELETE":
        app.delete(path, summary=doc.split("\n")[0])(handler)


# =============================================================================
# Authentication functions
# =============================================================================


async def verify_tenant_token(
    tenant_id: str | None,
    api_token: str | None,
    global_token: str | None,
) -> None:
    """Verify API token for a tenant-scoped request.

    Args:
        tenant_id: The tenant ID from the request.
        api_token: The token from X-API-Token header.
        global_token: The configured global API token (admin).

    Raises:
        HTTPException: 401 if token is invalid or tenant_id mismatch.

    Note:
        - Global token grants access to any tenant
        - Tenant token grants access ONLY to own resources
        - No token configured = open access
    """
    if not api_token:
        if global_token is not None:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or missing API token")
        return

    if global_token is not None and secrets.compare_digest(api_token, global_token):
        return

    if _service and getattr(_service, "db", None):
        token_tenant = await _service.db.table("tenants").get_tenant_by_token(api_token)
        if token_tenant:
            if tenant_id and token_tenant["id"] != tenant_id:
                raise HTTPException(
                    status.HTTP_401_UNAUTHORIZED, "Token not authorized for this tenant"
                )
            return

    raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or missing API token")


async def require_admin_token(
    request: Request,
    api_token: str | None = Depends(api_key_scheme),
) -> None:
    """Require global admin token for admin-only endpoints.

    Admin-only endpoints include tenant management, API key operations,
    and instance configuration.

    Args:
        request: FastAPI request object.
        api_token: Token from X-API-Token header (via Depends).

    Raises:
        HTTPException: 401 if not global admin token, 403 if tenant token.
    """
    expected = getattr(request.app.state, "api_token", None)

    if not api_token:
        if expected is not None:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Admin token required")
        return

    if expected is not None and secrets.compare_digest(api_token, expected):
        return

    if _service and getattr(_service, "db", None):
        token_tenant = await _service.db.table("tenants").get_tenant_by_token(api_token)
        if token_tenant:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                "Admin token required, tenant tokens not allowed for this operation",
            )

    raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or missing API token")


async def require_token(
    request: Request,
    api_token: str | None = Depends(api_key_scheme),
) -> None:
    """Validate API token from X-API-Token header.

    Accepts global admin token (full access) or tenant token (own resources).
    Stores token info in request.state for downstream verification.

    Args:
        request: FastAPI request object.
        api_token: Token from X-API-Token header (via Depends).

    Raises:
        HTTPException: 401 if token is invalid.
    """
    request.state.api_token = api_token

    expected = getattr(request.app.state, "api_token", None)

    if not api_token:
        if expected is not None:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or missing API token")
        return

    if expected is not None and secrets.compare_digest(api_token, expected):
        request.state.is_admin = True
        return

    if _service and getattr(_service, "db", None):
        token_tenant = await _service.db.table("tenants").get_tenant_by_token(api_token)
        if token_tenant:
            request.state.token_tenant_id = token_tenant["id"]
            request.state.is_admin = False
            return

    raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or missing API token")


# Dependency shortcuts
admin_dependency = Depends(require_admin_token)
auth_dependency = Depends(require_token)


# =============================================================================
# Application factory
# =============================================================================


def create_app(
    svc: WopiProxy,
    api_token: str | None = None,
    lifespan: CallableType[[FastAPI], AbstractAsyncContextManager[None]] | None = None,
    tenant_tokens_enabled: bool = False,
) -> FastAPI:
    """Create and configure the FastAPI application.

    Args:
        svc: WopiProxy instance implementing business logic.
        api_token: Optional global token for X-API-Token authentication.
        lifespan: Optional lifespan context manager. If None, creates
            default that starts/stops the proxy service.
        tenant_tokens_enabled: When True, enables per-tenant API keys.

    Returns:
        Configured FastAPI application with all routes registered.

    Example:
        ::

            from core.wopi_server.wopi_proxy import WopiProxy
            from core.wopi_server.interface import create_app

            proxy = WopiProxy(db_path="/data/wopi.db")
            app = create_app(proxy, api_token="admin-secret")

            # Run with uvicorn
            import uvicorn
            uvicorn.run(app)
    """
    global _service
    _service = svc

    if lifespan is None:
        from collections.abc import AsyncGenerator
        from contextlib import asynccontextmanager

        @asynccontextmanager
        async def default_lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
            """Default lifespan: start and stop the WopiProxy service."""
            logger.info("Starting wopi-server service...")
            await svc.start()
            logger.info("Wopi-server service started")
            try:
                yield
            finally:
                logger.info("Stopping wopi-server service...")
                await svc.stop()
                logger.info("Wopi-server service stopped")

        lifespan = default_lifespan

    app = FastAPI(title="WOPI Server", lifespan=lifespan)
    app.state.api_token = api_token
    app.state.tenant_tokens_enabled = tenant_tokens_enabled

    # Enable CORS for development/demo
    from fastapi.middleware.cors import CORSMiddleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        """Handle FastAPI request validation errors with detailed logging."""
        body = await request.body()
        logger.error(f"Validation error on {request.method} {request.url.path}")
        logger.error(f"Request body: {body.decode('utf-8', errors='replace')}")
        logger.error(f"Validation errors: {exc.errors()}")
        return JSONResponse(status_code=422, content={"detail": exc.errors()})

    _register_entity_endpoints(app, svc)
    _register_instance_endpoints(app, svc)

    return app


def _register_entity_endpoints(app: FastAPI, svc: WopiProxy) -> None:
    """Register entity endpoints via autodiscovery."""
    router = APIRouter(dependencies=[auth_dependency])

    for endpoint_class in BaseEndpoint.discover():
        if endpoint_class.name == "instance":
            continue

        table = svc.db.table(endpoint_class.name)
        endpoint = endpoint_class(table)
        register_endpoint(router, endpoint)

    app.include_router(router)


def _register_instance_endpoints(app: FastAPI, svc: WopiProxy) -> None:
    """Register instance-level endpoints (health, status, operations)."""
    instance_class = None
    for endpoint_class in BaseEndpoint.discover():
        if endpoint_class.name == "instance":
            instance_class = endpoint_class
            break

    if not instance_class:
        logger.warning("InstanceEndpoint not found in discovery")
        return

    instance_table = svc.db.table("instance")
    instance_endpoint = instance_class(instance_table, proxy=svc)

    @app.get("/health")
    async def health() -> dict:
        """Health check endpoint for container orchestration."""
        return await instance_endpoint.health()

    router = APIRouter(dependencies=[auth_dependency])
    register_endpoint(router, instance_endpoint)
    app.include_router(router)

    # Register WOPI protocol endpoints (no auth dependency - uses access_token in query)
    _register_wopi_endpoints(app, svc)


def _register_wopi_endpoints(app: FastAPI, svc: WopiProxy) -> None:
    """Register WOPI protocol endpoints for document editing.

    These endpoints follow the WOPI protocol specification and use
    access_token in query string for authentication (not X-API-Token header).
    """
    from fastapi.responses import Response

    @app.get("/wopi/files/{file_id}")
    async def wopi_check_file_info(
        file_id: str,
        access_token: str = Query(..., description="WOPI access token"),
    ) -> dict:
        """WOPI CheckFileInfo: Return file metadata.

        Returns file information required by WOPI clients (Collabora, OnlyOffice, etc.)
        """

        logger.info(f"WOPI CheckFileInfo: file_id={file_id}")

        try:
            # Get session by file_id
            sessions_table = svc.db.table("sessions")
            session = await sessions_table.get_by_file_id(file_id)
            logger.info(f"WOPI CheckFileInfo: session={session}")

            if not session:
                raise HTTPException(status.HTTP_404_NOT_FOUND, "File not found")

            # Verify access token
            if session.get("access_token") != access_token:
                logger.warning("WOPI CheckFileInfo: token mismatch")
                raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid access token")

            # Check session expiration using UTC (same as SessionsTable)
            expires_at_str = session.get("expires_at")
            if expires_at_str:
                from datetime import datetime, timezone
                # Parse ISO datetime and compare with UTC now (all naive, all UTC)
                expires_dt = datetime.fromisoformat(expires_at_str)
                now_utc = datetime.now(timezone.utc).replace(tzinfo=None)
                if expires_dt <= now_utc:
                    logger.warning(f"WOPI CheckFileInfo: session expired (expires={expires_dt}, now={now_utc})")
                    raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Session expired")

            # Get file info from storage
            tenant_id = session.get("tenant_id", "default")
            storage_name = session.get("storage_name")
            file_path = session.get("file_path")
            logger.info(f"WOPI CheckFileInfo: tenant={tenant_id}, storage={storage_name}, path={file_path}")

            storages_table = svc.db.table("storages")
            manager = await storages_table.get_storage_manager(tenant_id)
            logger.info("WOPI CheckFileInfo: got storage manager")
            node = manager.node(f"{storage_name}:{file_path}")
        except HTTPException:
            raise
        except Exception as e:
            logger.exception(f"WOPI CheckFileInfo error: {e}")
            raise

        if not await node.exists():
            raise HTTPException(status.HTTP_404_NOT_FOUND, "File not found in storage")

        file_size = await node.size()
        basename = node.basename

        # WOPI CheckFileInfo response
        # See: https://docs.microsoft.com/en-us/microsoft-365/cloud-storage-partner-program/rest/files/checkfileinfo
        return {
            "BaseFileName": basename,
            "Size": file_size,
            "OwnerId": session.get("account", "unknown"),
            "UserId": session.get("user", "unknown"),
            "UserFriendlyName": session.get("user", "Unknown User"),
            "Version": str(int(await node.mtime())),
            "UserCanWrite": True,
            "UserCanNotWriteRelative": True,
            "SupportsUpdate": True,
            "SupportsLocks": False,  # Simplified - no locking for now
        }

    @app.get("/wopi/files/{file_id}/contents", response_class=Response)
    async def wopi_get_file(
        file_id: str,
        access_token: str = Query(..., description="WOPI access token"),
    ):
        """WOPI GetFile: Download file content."""
        logger.info(f"WOPI GetFile: file_id={file_id}")

        # Get session by file_id
        sessions_table = svc.db.table("sessions")
        session = await sessions_table.get_by_file_id(file_id)

        if not session:
            logger.warning(f"WOPI GetFile: session not found for file_id={file_id}")
            raise HTTPException(status.HTTP_404_NOT_FOUND, "File not found")

        # Verify access token
        if session.get("access_token") != access_token:
            logger.warning(f"WOPI GetFile: token mismatch for file_id={file_id}")
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid access token")

        # Get file from storage
        tenant_id = session.get("tenant_id", "default")
        storage_name = session.get("storage_name")
        file_path = session.get("file_path")
        logger.info(f"WOPI GetFile: tenant={tenant_id}, storage={storage_name}, path={file_path}")

        storages_table = svc.db.table("storages")
        manager = await storages_table.get_storage_manager(tenant_id)
        node = manager.node(f"{storage_name}:{file_path}")

        # Get actual filesystem path for debugging
        local_path = node._get_local_path()
        logger.info(f"WOPI GetFile: local_path={local_path}, exists={local_path.exists()}, is_file={local_path.is_file()}")

        if not await node.exists():
            logger.warning(f"WOPI GetFile: file not found in storage: {local_path}")
            raise HTTPException(status.HTTP_404_NOT_FOUND, "File not found in storage")

        if not await node.is_file():
            logger.warning(f"WOPI GetFile: path is not a file (is directory?): {local_path}")
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Path is not a file")

        try:
            content = await node.read_bytes()
            logger.info(f"WOPI GetFile: read {len(content)} bytes from {file_path}")
        except Exception as e:
            logger.exception(f"WOPI GetFile: failed to read file: {e}")
            raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, f"Failed to read file: {e}")

        return Response(
            content=content,
            media_type="application/octet-stream",
            headers={
                "X-WOPI-ItemVersion": str(int(await node.mtime())),
            }
        )

    @app.post("/wopi/files/{file_id}/contents")
    async def wopi_put_file(
        request: Request,
        file_id: str,
        access_token: str = Query(..., description="WOPI access token"),
    ) -> dict:
        """WOPI PutFile: Save edited file content."""
        # Get session by file_id
        sessions_table = svc.db.table("sessions")
        session = await sessions_table.get_by_file_id(file_id)

        if not session:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "File not found")

        # Verify access token
        if session.get("access_token") != access_token:
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid access token")

        # Get file content from request body
        content = await request.body()

        # Save to storage
        tenant_id = session.get("tenant_id", "default")
        storage_name = session.get("storage_name")
        file_path = session.get("file_path")

        storages_table = svc.db.table("storages")
        manager = await storages_table.get_storage_manager(tenant_id)
        node = manager.node(f"{storage_name}:{file_path}")

        await node.write_bytes(content)

        logger.info(f"WOPI PutFile: saved {len(content)} bytes to {storage_name}:{file_path}")

        return {
            "ItemVersion": str(int(await node.mtime())),
        }


__all__ = [
    "API_TOKEN_HEADER_NAME",
    "admin_dependency",
    "api_key_scheme",
    "auth_dependency",
    "create_app",
    "register_endpoint",
    "require_admin_token",
    "require_token",
    "verify_tenant_token",
]
