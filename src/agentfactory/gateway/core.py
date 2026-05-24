"""GatewayApp — Core gateway service for AgentFactory.

Manages adapter lifecycle, task dispatch, and integrates with the
SupervisorAgent for processing platform messages.
"""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Optional

from fastapi import FastAPI

from .session import SessionManager
from .adapters.base import BaseAdapter, ReplyFn

logger = logging.getLogger(__name__)


@dataclass
class ProviderConfig:
    """Configuration for the LLM provider used by the SupervisorAgent.

    Attributes:
        provider: Provider name (e.g. "openai", "anthropic", "openrouter").
        model: Model identifier (e.g. "gpt-4o", "claude-sonnet-4-20250514").
        base_url: Optional custom API base URL.
        api_key: Optional API key (falls back to env vars if not set).
        extra: Additional provider-specific configuration.
    """

    provider: str = "openai"
    model: str = "gpt-4o"
    base_url: Optional[str] = None
    api_key: Optional[str] = None
    extra: dict[str, Any] = None


class SupervisorAgent:
    """Minimal SupervisorAgent interface for the Gateway.

    In production, this would be replaced with the actual SupervisorAgent
    from the AgentFactory core. This stub provides the interface needed
    by the Gateway for task dispatch.
    """

    def __init__(self, provider_config: ProviderConfig) -> None:
        self.provider_config = provider_config
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize the supervisor (load models, connect to provider, etc.)."""
        logger.info(
            "Initializing SupervisorAgent: provider=%s model=%s",
            self.provider_config.provider,
            self.provider_config.model,
        )
        self._initialized = True

    async def process(
        self,
        user_id: str,
        channel_id: str,
        text: str,
        adapter_id: str = "default",
    ) -> str:
        """Process an incoming task and return a response.

        Args:
            user_id: The user who sent the message.
            channel_id: The channel/conversation ID.
            text: The message content.
            adapter_id: The originating adapter/platform ID.

        Returns:
            The response text to send back to the user.
        """
        if not self._initialized:
            await self.initialize()

        # TODO: Replace with actual SupervisorAgent logic.
        # This is a placeholder that echoes the input.
        logger.info(
            "SupervisorAgent processing: adapter=%s user=%s channel=%s text=%s",
            adapter_id,
            user_id,
            channel_id,
            text[:200],
        )

        # Simulate async processing delay
        await asyncio.sleep(0.1)

        return f"[{adapter_id}] Processed: {text}"

    async def shutdown(self) -> None:
        """Release supervisor resources."""
        logger.info("Shutting down SupervisorAgent.")
        self._initialized = False


class GatewayApp:
    """Main Gateway application.

    Manages:
    - FastAPI lifecycle
    - Adapter registration and lifecycle
    - Session tracking
    - Task dispatch to SupervisorAgent
    """

    def __init__(
        self,
        provider_config: Optional[ProviderConfig] = None,
        session_ttl: int = 3600,
    ) -> None:
        self.provider_config = provider_config or ProviderConfig()
        self.session_manager = SessionManager(ttl_seconds=session_ttl)
        self._adapters: dict[str, BaseAdapter] = {}
        self._supervisor: Optional[SupervisorAgent] = None
        self._app: Optional[FastAPI] = None
        self._shutdown_event = asyncio.Event()

    @property
    def app(self) -> FastAPI:
        """Get or create the FastAPI application instance."""
        if self._app is None:
            self._app = self._build_fastapi_app()
        return self._app

    def register_adapter(self, adapter: BaseAdapter) -> None:
        """Register an adapter with the gateway.

        Args:
            adapter: The adapter instance to register.
        """
        if adapter.adapter_id in self._adapters:
            logger.warning(
                "Adapter '%s' already registered — replacing.",
                adapter.adapter_id,
            )

        adapter.set_reply_fn(self._make_reply_fn(adapter.adapter_id))
        self._adapters[adapter.adapter_id] = adapter
        logger.info("Registered adapter: %s", adapter.adapter_id)

    def get_adapter(self, adapter_id: str) -> Optional[BaseAdapter]:
        """Get a registered adapter by ID."""
        return self._adapters.get(adapter_id)

    @property
    def adapters(self) -> dict[str, BaseAdapter]:
        """Get all registered adapters."""
        return dict(self._adapters)

    @property
    def supervisor(self) -> Optional[SupervisorAgent]:
        """Get the SupervisorAgent instance."""
        return self._supervisor

    async def dispatch_task(
        self,
        adapter_id: str,
        user_id: str,
        text: str,
        reply_fn: Optional[ReplyFn] = None,
    ) -> str:
        """Dispatch a task from an adapter to the SupervisorAgent.

        Args:
            adapter_id: The adapter that originated the task.
            user_id: The platform user ID.
            text: The message content.
            reply_fn: Optional override reply callback.

        Returns:
            The response from the SupervisorAgent.
        """
        adapter = self._adapters.get(adapter_id)
        if adapter is None:
            raise ValueError(f"Unknown adapter: {adapter_id}")

        # Get or create session
        session = self.session_manager.get_or_create(
            platform=adapter_id,
            user_id=user_id,
            channel_id="dispatch",  # Generic channel for dispatch
        )

        if self._supervisor is None:
            raise RuntimeError("SupervisorAgent not initialized")

        response = await self._supervisor.process(
            user_id=user_id,
            channel_id="dispatch",
            text=text,
            adapter_id=adapter_id,
        )

        # Use provided reply_fn or the adapter's registered one
        if reply_fn:
            await reply_fn(response)
        elif adapter._reply_fn:
            await adapter._reply_fn(response)

        return response

    async def start_adapters(self) -> None:
        """Start all registered adapters."""
        for adapter_id, adapter in self._adapters.items():
            try:
                await adapter.start()
            except Exception:
                logger.exception("Failed to start adapter: %s", adapter_id)

    async def stop_adapters(self) -> None:
        """Stop all registered adapters."""
        for adapter_id, adapter in self._adapters.items():
            try:
                await adapter.stop()
            except Exception:
                logger.exception("Failed to stop adapter: %s", adapter_id)

    def _make_reply_fn(self, adapter_id: str) -> ReplyFn:
        """Create a reply function bound to a specific adapter.

        Returns a callback that the adapter can use to send replies.
        """

        async def _reply(text: str, metadata: Optional[dict[str, Any]] = None) -> None:
            adapter = self._adapters.get(adapter_id)
            if adapter is None:
                logger.error("Adapter '%s' not found for reply.", adapter_id)
                return
            # The actual reply goes through the platform-specific adapter
            logger.info(
                "[reply] adapter=%s text=%s metadata=%s",
                adapter_id,
                text[:100],
                metadata,
            )

        return _reply

    def _build_fastapi_app(self) -> FastAPI:
        """Build the FastAPI application with lifespan management."""

        @asynccontextmanager
        async def lifespan(app: FastAPI):
            # Startup
            logger.info("Gateway starting up...")
            self._supervisor = SupervisorAgent(self.provider_config)
            await self._supervisor.initialize()

            # Inject supervisor into adapters that support it
            for adapter in self._adapters.values():
                if hasattr(adapter, "set_supervisor"):
                    adapter.set_supervisor(self._supervisor)

            await self.start_adapters()
            yield

            # Shutdown
            logger.info("Gateway shutting down...")
            await self.stop_adapters()
            if self._supervisor:
                await self._supervisor.shutdown()
            logger.info("Gateway shutdown complete.")

        api_app = FastAPI(
            title="AgentFactory Gateway",
            description="Plugin-based messaging gateway for AgentFactory",
            version="0.1.0",
            lifespan=lifespan,
        )

        # Health check endpoint
        @api_app.get("/health")
        async def health_check() -> dict:
            return {
                "status": "healthy",
                "adapters": list(self._adapters.keys()),
                "active_sessions": self.session_manager.active_count,
            }

        # Manual message injection endpoint (for testing / HTTP adapters)
        @api_app.post("/api/v1/message")
        async def inject_message(
            adapter_id: str,
            user_id: str,
            text: str,
            channel_id: str = "direct",
        ) -> dict:
            response = await self.dispatch_task(
                adapter_id=adapter_id,
                user_id=user_id,
                text=text,
            )
            return {"status": "processed", "response": response}

        return api_app
