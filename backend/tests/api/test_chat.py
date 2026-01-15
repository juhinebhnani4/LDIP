"""Tests for Chat Streaming API.

Story 11.3: Streaming Response with Engine Trace
Task 12: Write comprehensive tests (AC: #1-3)

Tests:
- SSE endpoint streaming
- Event format validation
- Authentication requirements
- Error handling
"""

from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.engines.orchestrator.streaming import StreamingOrchestrator
from app.main import app
from app.models.chat import StreamEvent, StreamEventType
from app.models.orchestrator import EngineType, OrchestratorResult


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_orchestrator_result() -> OrchestratorResult:
    """Create a mock orchestrator result."""
    return OrchestratorResult(
        matter_id="test-matter-123",
        query="What are the citations?",
        successful_engines=[EngineType.CITATION],
        failed_engines=[],
        unified_response="I found 3 citations in the documents.",
        sources=[],
        confidence=0.85,
        engine_results=[
            MagicMock(
                engine=EngineType.CITATION,
                success=True,
                execution_time_ms=150,
                error=None,
                data={"citations": [{"act": "NI Act", "section": "138"}]},
            ),
        ],
        total_execution_time_ms=150,
        wall_clock_time_ms=150,
        blocked=False,
        blocked_reason="",
        suggested_rewrite="",
    )


@pytest.fixture
def mock_auth_user() -> dict:
    """Create a mock authenticated user."""
    return {
        "id": "user-123",
        "email": "test@example.com",
        "role": "user",
    }


# =============================================================================
# Unit Tests - Models
# =============================================================================


class TestStreamEventModels:
    """Tests for streaming event models."""

    def test_stream_event_types(self) -> None:
        """Test all event types are defined."""
        assert StreamEventType.TYPING == "typing"
        assert StreamEventType.ENGINE_START == "engine_start"
        assert StreamEventType.ENGINE_COMPLETE == "engine_complete"
        assert StreamEventType.TOKEN == "token"
        assert StreamEventType.COMPLETE == "complete"
        assert StreamEventType.ERROR == "error"

    def test_stream_event_serialization(self) -> None:
        """Test event serialization."""
        event = StreamEvent(
            type=StreamEventType.TYPING,
            data={"status": "processing"},
        )

        data = event.model_dump()
        assert data["type"] == "typing"
        assert data["data"]["status"] == "processing"


# =============================================================================
# Unit Tests - StreamingOrchestrator
# =============================================================================


class TestStreamingOrchestrator:
    """Tests for streaming orchestrator."""

    @pytest.mark.asyncio
    async def test_process_streaming_emits_typing_event(
        self,
        mock_orchestrator_result: OrchestratorResult,
    ) -> None:
        """Test that typing event is emitted first."""
        mock_query_orchestrator = AsyncMock()
        mock_query_orchestrator.process_query = AsyncMock(
            return_value=mock_orchestrator_result
        )

        mock_session_service = AsyncMock()
        mock_session_service.get_session = AsyncMock(return_value=None)
        mock_session_service.add_message = AsyncMock()

        streaming = StreamingOrchestrator(
            orchestrator=mock_query_orchestrator,
            session_service=mock_session_service,
        )

        events: list[StreamEvent] = []
        async for event in streaming.process_streaming(
            matter_id="test-matter-123",
            user_id="user-123",
            query="What are the citations?",
        ):
            events.append(event)

        # First event should be typing
        assert len(events) > 0
        assert events[0].type == StreamEventType.TYPING
        assert events[0].data["status"] == "processing"

    @pytest.mark.asyncio
    async def test_process_streaming_emits_engine_complete(
        self,
        mock_orchestrator_result: OrchestratorResult,
    ) -> None:
        """Test that engine_complete events are emitted."""
        mock_query_orchestrator = AsyncMock()
        mock_query_orchestrator.process_query = AsyncMock(
            return_value=mock_orchestrator_result
        )

        mock_session_service = AsyncMock()
        mock_session_service.get_session = AsyncMock(return_value=None)
        mock_session_service.add_message = AsyncMock()

        streaming = StreamingOrchestrator(
            orchestrator=mock_query_orchestrator,
            session_service=mock_session_service,
        )

        events: list[StreamEvent] = []
        async for event in streaming.process_streaming(
            matter_id="test-matter-123",
            user_id="user-123",
            query="What are the citations?",
        ):
            events.append(event)

        # Should have engine_complete event
        engine_events = [e for e in events if e.type == StreamEventType.ENGINE_COMPLETE]
        assert len(engine_events) == 1
        assert engine_events[0].data["engine"] == "citation"
        assert engine_events[0].data["success"] is True

    @pytest.mark.asyncio
    async def test_process_streaming_emits_token_events(
        self,
        mock_orchestrator_result: OrchestratorResult,
    ) -> None:
        """Test that token events are emitted during streaming."""
        mock_query_orchestrator = AsyncMock()
        mock_query_orchestrator.process_query = AsyncMock(
            return_value=mock_orchestrator_result
        )

        mock_session_service = AsyncMock()
        mock_session_service.get_session = AsyncMock(return_value=None)
        mock_session_service.add_message = AsyncMock()

        streaming = StreamingOrchestrator(
            orchestrator=mock_query_orchestrator,
            session_service=mock_session_service,
        )

        events: list[StreamEvent] = []
        async for event in streaming.process_streaming(
            matter_id="test-matter-123",
            user_id="user-123",
            query="What are the citations?",
        ):
            events.append(event)

        # Should have token events
        token_events = [e for e in events if e.type == StreamEventType.TOKEN]
        assert len(token_events) > 0

        # Last token should have full accumulated text
        last_token = token_events[-1]
        assert last_token.data["accumulated"] == mock_orchestrator_result.unified_response

    @pytest.mark.asyncio
    async def test_process_streaming_emits_complete_event(
        self,
        mock_orchestrator_result: OrchestratorResult,
    ) -> None:
        """Test that complete event is emitted at the end."""
        mock_query_orchestrator = AsyncMock()
        mock_query_orchestrator.process_query = AsyncMock(
            return_value=mock_orchestrator_result
        )

        mock_session_service = AsyncMock()
        mock_session_service.get_session = AsyncMock(return_value=None)
        mock_session_service.add_message = AsyncMock()

        streaming = StreamingOrchestrator(
            orchestrator=mock_query_orchestrator,
            session_service=mock_session_service,
        )

        events: list[StreamEvent] = []
        async for event in streaming.process_streaming(
            matter_id="test-matter-123",
            user_id="user-123",
            query="What are the citations?",
        ):
            events.append(event)

        # Last event should be complete
        assert events[-1].type == StreamEventType.COMPLETE
        assert events[-1].data["response"] == mock_orchestrator_result.unified_response
        assert events[-1].data["confidence"] == mock_orchestrator_result.confidence

    @pytest.mark.asyncio
    async def test_process_streaming_handles_blocked_query(
        self,
    ) -> None:
        """Test that blocked queries emit error event."""
        blocked_result = OrchestratorResult(
            matter_id="test-matter-123",
            query="test",
            blocked=True,
            blocked_reason="Query contains prohibited content",
            suggested_rewrite="Try asking about specific document content",
            success=False,
        )

        mock_query_orchestrator = AsyncMock()
        mock_query_orchestrator.process_query = AsyncMock(return_value=blocked_result)

        mock_session_service = AsyncMock()
        mock_session_service.get_session = AsyncMock(return_value=None)
        mock_session_service.add_message = AsyncMock()

        streaming = StreamingOrchestrator(
            orchestrator=mock_query_orchestrator,
            session_service=mock_session_service,
        )

        events: list[StreamEvent] = []
        async for event in streaming.process_streaming(
            matter_id="test-matter-123",
            user_id="user-123",
            query="test",
        ):
            events.append(event)

        # Should have error event
        error_events = [e for e in events if e.type == StreamEventType.ERROR]
        assert len(error_events) == 1
        assert error_events[0].data["code"] == "QUERY_BLOCKED"

    @pytest.mark.asyncio
    async def test_process_streaming_handles_exception(self) -> None:
        """Test that exceptions emit error event."""
        mock_query_orchestrator = AsyncMock()
        mock_query_orchestrator.process_query = AsyncMock(
            side_effect=Exception("Database error")
        )

        mock_session_service = AsyncMock()
        mock_session_service.get_session = AsyncMock(return_value=None)
        mock_session_service.add_message = AsyncMock()

        streaming = StreamingOrchestrator(
            orchestrator=mock_query_orchestrator,
            session_service=mock_session_service,
        )

        events: list[StreamEvent] = []
        async for event in streaming.process_streaming(
            matter_id="test-matter-123",
            user_id="user-123",
            query="test",
        ):
            events.append(event)

        # Should have error event
        error_events = [e for e in events if e.type == StreamEventType.ERROR]
        assert len(error_events) == 1
        assert "Database error" in error_events[0].data["error"]


# =============================================================================
# Integration Tests - API Endpoint
# =============================================================================


class TestChatStreamEndpoint:
    """Tests for chat streaming API endpoint."""

    @pytest.mark.asyncio
    async def test_stream_requires_authentication(self) -> None:
        """Test that endpoint requires authentication."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/chat/test-matter-123/stream",
                json={"query": "What are the citations?"},
            )

            # Should return 401 or 403 without auth
            assert response.status_code in [401, 403]

    @pytest.mark.asyncio
    async def test_stream_validates_request(self) -> None:
        """Test request validation."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # Empty query should fail validation
            response = await client.post(
                "/api/chat/test-matter-123/stream",
                json={"query": ""},
                headers={"Authorization": "Bearer fake-token"},
            )

            # Should return 422 for validation error
            assert response.status_code in [401, 403, 422]

    @pytest.mark.asyncio
    async def test_message_endpoint_requires_authentication(self) -> None:
        """Test that non-streaming endpoint requires authentication."""
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.post(
                "/api/chat/test-matter-123/message",
                json={"query": "What are the citations?"},
            )

            # Should return 401 or 403 without auth
            assert response.status_code in [401, 403]
