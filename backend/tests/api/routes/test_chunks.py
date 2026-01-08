"""Unit tests for chunk API routes."""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import jwt
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.core.config import Settings
from app.main import app
from app.models.chunk import Chunk, ChunkType, ChunkWithContent
from app.models.matter import MatterRole
from app.services.chunk_service import ChunkNotFoundError


# Test JWT secret
TEST_JWT_SECRET = "test-secret-key-for-testing-only-do-not-use-in-production"


def get_test_settings() -> Settings:
    """Create test settings with JWT secret configured."""
    settings = MagicMock(spec=Settings)
    settings.supabase_jwt_secret = TEST_JWT_SECRET
    settings.supabase_url = "https://test.supabase.co"
    settings.supabase_anon_key = "test-anon-key"
    settings.is_configured = True
    settings.debug = True
    return settings


def create_test_token(
    user_id: str = "test-user-id",
    email: str = "test@example.com",
) -> str:
    """Create a valid JWT token for testing."""
    payload = {
        "sub": user_id,
        "email": email,
        "role": "authenticated",
        "aud": "authenticated",
        "exp": datetime.now(timezone.utc) + timedelta(hours=1),
        "iat": datetime.now(timezone.utc),
        "session_id": "test-session",
    }
    return jwt.encode(payload, TEST_JWT_SECRET, algorithm="HS256")


class TestGetDocumentChunksEndpoint:
    """Tests for GET /api/documents/{document_id}/chunks endpoint."""

    @pytest.mark.anyio
    async def test_returns_chunks_on_success(self) -> None:
        """Should return chunks when authorized."""
        from app.core.config import get_settings
        from app.api.deps import get_matter_service
        from app.services.document_service import get_document_service
        from app.services.chunk_service import get_chunk_service

        document_id = "doc-123"
        chunk_id = "chunk-456"

        # Mock document
        mock_doc = MagicMock()
        mock_doc.matter_id = "matter-123"

        mock_doc_service = MagicMock()
        mock_doc_service.get_document.return_value = mock_doc

        # Mock matter access
        mock_matter_service = MagicMock()
        mock_matter_service.get_user_role.return_value = MatterRole.VIEWER

        # Mock chunk retrieval
        mock_chunks = [
            ChunkWithContent(
                id=chunk_id,
                document_id=document_id,
                content="Test content",
                chunk_type=ChunkType.PARENT,
                chunk_index=0,
                token_count=10,
                parent_chunk_id=None,
                page_number=1,
            ),
        ]
        mock_chunk_service = MagicMock()
        mock_chunk_service.get_chunks_for_document.return_value = (
            mock_chunks, 1, 0
        )

        app.dependency_overrides[get_settings] = get_test_settings
        app.dependency_overrides[get_matter_service] = lambda: mock_matter_service
        app.dependency_overrides[get_document_service] = lambda: mock_doc_service
        app.dependency_overrides[get_chunk_service] = lambda: mock_chunk_service

        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport,
            base_url="http://test",
        ) as client:
            token = create_test_token()
            response = await client.get(
                f"/api/documents/{document_id}/chunks",
                headers={"Authorization": f"Bearer {token}"},
            )

        app.dependency_overrides.clear()

        assert response.status_code == 200
        data = response.json()
        assert "data" in data
        assert "meta" in data
        assert data["meta"]["parent_count"] == 1

    @pytest.mark.anyio
    async def test_filters_by_chunk_type(self) -> None:
        """Should filter chunks by type when specified."""
        from app.core.config import get_settings
        from app.api.deps import get_matter_service
        from app.services.document_service import get_document_service
        from app.services.chunk_service import get_chunk_service

        document_id = "doc-123"

        mock_doc = MagicMock()
        mock_doc.matter_id = "matter-123"

        mock_doc_service = MagicMock()
        mock_doc_service.get_document.return_value = mock_doc

        mock_matter_service = MagicMock()
        mock_matter_service.get_user_role.return_value = MatterRole.VIEWER

        mock_chunk_service = MagicMock()
        mock_chunk_service.get_chunks_for_document.return_value = ([], 0, 0)

        app.dependency_overrides[get_settings] = get_test_settings
        app.dependency_overrides[get_matter_service] = lambda: mock_matter_service
        app.dependency_overrides[get_document_service] = lambda: mock_doc_service
        app.dependency_overrides[get_chunk_service] = lambda: mock_chunk_service

        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport,
            base_url="http://test",
        ) as client:
            token = create_test_token()
            response = await client.get(
                f"/api/documents/{document_id}/chunks?chunk_type=child",
                headers={"Authorization": f"Bearer {token}"},
            )

        app.dependency_overrides.clear()

        assert response.status_code == 200

        # Verify service was called with filter
        mock_chunk_service.get_chunks_for_document.assert_called_once()
        call_kwargs = mock_chunk_service.get_chunks_for_document.call_args
        assert call_kwargs.kwargs.get("chunk_type") == ChunkType.CHILD

    @pytest.mark.anyio
    async def test_returns_404_for_unauthorized_document(self) -> None:
        """Should return 404 when user has no access to document's matter."""
        from app.core.config import get_settings
        from app.api.deps import get_matter_service
        from app.services.document_service import get_document_service

        document_id = "doc-123"

        mock_doc = MagicMock()
        mock_doc.matter_id = "matter-123"

        mock_doc_service = MagicMock()
        mock_doc_service.get_document.return_value = mock_doc

        mock_matter_service = MagicMock()
        mock_matter_service.get_user_role.return_value = None  # No access

        app.dependency_overrides[get_settings] = get_test_settings
        app.dependency_overrides[get_matter_service] = lambda: mock_matter_service
        app.dependency_overrides[get_document_service] = lambda: mock_doc_service

        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport,
            base_url="http://test",
        ) as client:
            token = create_test_token()
            response = await client.get(
                f"/api/documents/{document_id}/chunks",
                headers={"Authorization": f"Bearer {token}"},
            )

        app.dependency_overrides.clear()

        assert response.status_code == 404


class TestGetChunkEndpoint:
    """Tests for GET /api/chunks/{chunk_id} endpoint."""

    @pytest.mark.anyio
    async def test_returns_chunk_on_success(self) -> None:
        """Should return chunk when authorized."""
        from app.core.config import get_settings
        from app.api.deps import get_matter_service
        from app.services.chunk_service import get_chunk_service

        chunk_id = "chunk-456"

        mock_chunk = Chunk(
            id=chunk_id,
            matter_id="matter-123",
            document_id="doc-123",
            content="Test content",
            chunk_type=ChunkType.PARENT,
            chunk_index=0,
            token_count=10,
            parent_chunk_id=None,
            page_number=1,
            bbox_ids=None,
            entity_ids=None,
            created_at=datetime.now(timezone.utc),
        )

        mock_chunk_service = MagicMock()
        mock_chunk_service.get_chunk.return_value = mock_chunk

        mock_matter_service = MagicMock()
        mock_matter_service.get_user_role.return_value = MatterRole.VIEWER

        app.dependency_overrides[get_settings] = get_test_settings
        app.dependency_overrides[get_matter_service] = lambda: mock_matter_service
        app.dependency_overrides[get_chunk_service] = lambda: mock_chunk_service

        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport,
            base_url="http://test",
        ) as client:
            token = create_test_token()
            response = await client.get(
                f"/api/chunks/{chunk_id}",
                headers={"Authorization": f"Bearer {token}"},
            )

        app.dependency_overrides.clear()

        assert response.status_code == 200
        data = response.json()
        assert data["data"]["id"] == chunk_id

    @pytest.mark.anyio
    async def test_returns_404_for_nonexistent_chunk(self) -> None:
        """Should return 404 when chunk doesn't exist."""
        from app.core.config import get_settings
        from app.api.deps import get_matter_service
        from app.services.chunk_service import get_chunk_service

        chunk_id = "nonexistent-chunk"

        mock_chunk_service = MagicMock()
        mock_chunk_service.get_chunk.side_effect = ChunkNotFoundError(chunk_id)

        mock_matter_service = MagicMock()

        app.dependency_overrides[get_settings] = get_test_settings
        app.dependency_overrides[get_matter_service] = lambda: mock_matter_service
        app.dependency_overrides[get_chunk_service] = lambda: mock_chunk_service

        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport,
            base_url="http://test",
        ) as client:
            token = create_test_token()
            response = await client.get(
                f"/api/chunks/{chunk_id}",
                headers={"Authorization": f"Bearer {token}"},
            )

        app.dependency_overrides.clear()

        assert response.status_code == 404


class TestGetChunkContextEndpoint:
    """Tests for GET /api/chunks/{chunk_id}/context endpoint."""

    @pytest.mark.anyio
    async def test_returns_context_for_child_chunk(self) -> None:
        """Should return parent and siblings for child chunk."""
        from app.core.config import get_settings
        from app.api.deps import get_matter_service
        from app.services.chunk_service import get_chunk_service

        chunk_id = "child-chunk"
        parent_id = "parent-chunk"

        mock_chunk = Chunk(
            id=chunk_id,
            matter_id="matter-123",
            document_id="doc-123",
            content="Child content",
            chunk_type=ChunkType.CHILD,
            chunk_index=0,
            token_count=10,
            parent_chunk_id=parent_id,
            page_number=1,
            bbox_ids=None,
            entity_ids=None,
            created_at=datetime.now(timezone.utc),
        )

        mock_parent = Chunk(
            id=parent_id,
            matter_id="matter-123",
            document_id="doc-123",
            content="Parent content",
            chunk_type=ChunkType.PARENT,
            chunk_index=0,
            token_count=50,
            parent_chunk_id=None,
            page_number=1,
            bbox_ids=None,
            entity_ids=None,
            created_at=datetime.now(timezone.utc),
        )

        mock_chunk_service = MagicMock()
        mock_chunk_service.get_chunk.return_value = mock_chunk
        mock_chunk_service.get_chunk_with_context.return_value = {
            "chunk": mock_chunk,
            "parent": mock_parent,
            "siblings": [],
        }

        mock_matter_service = MagicMock()
        mock_matter_service.get_user_role.return_value = MatterRole.VIEWER

        app.dependency_overrides[get_settings] = get_test_settings
        app.dependency_overrides[get_matter_service] = lambda: mock_matter_service
        app.dependency_overrides[get_chunk_service] = lambda: mock_chunk_service

        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport,
            base_url="http://test",
        ) as client:
            token = create_test_token()
            response = await client.get(
                f"/api/chunks/{chunk_id}/context",
                headers={"Authorization": f"Bearer {token}"},
            )

        app.dependency_overrides.clear()

        assert response.status_code == 200


class TestGetChunkParentEndpoint:
    """Tests for GET /api/chunks/{chunk_id}/parent endpoint."""

    @pytest.mark.anyio
    async def test_returns_parent_chunk(self) -> None:
        """Should return parent chunk for child."""
        from app.core.config import get_settings
        from app.api.deps import get_matter_service
        from app.services.chunk_service import get_chunk_service

        chunk_id = "child-chunk"
        parent_id = "parent-chunk"

        mock_child = Chunk(
            id=chunk_id,
            matter_id="matter-123",
            document_id="doc-123",
            content="Child content",
            chunk_type=ChunkType.CHILD,
            chunk_index=0,
            token_count=10,
            parent_chunk_id=parent_id,
            page_number=1,
            bbox_ids=None,
            entity_ids=None,
            created_at=datetime.now(timezone.utc),
        )

        mock_parent = Chunk(
            id=parent_id,
            matter_id="matter-123",
            document_id="doc-123",
            content="Parent content",
            chunk_type=ChunkType.PARENT,
            chunk_index=0,
            token_count=100,
            parent_chunk_id=None,
            page_number=1,
            bbox_ids=None,
            entity_ids=None,
            created_at=datetime.now(timezone.utc),
        )

        mock_chunk_service = MagicMock()
        mock_chunk_service.get_chunk.return_value = mock_child
        mock_chunk_service.get_parent_chunk.return_value = mock_parent

        mock_matter_service = MagicMock()
        mock_matter_service.get_user_role.return_value = MatterRole.VIEWER

        app.dependency_overrides[get_settings] = get_test_settings
        app.dependency_overrides[get_matter_service] = lambda: mock_matter_service
        app.dependency_overrides[get_chunk_service] = lambda: mock_chunk_service

        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport,
            base_url="http://test",
        ) as client:
            token = create_test_token()
            response = await client.get(
                f"/api/chunks/{chunk_id}/parent",
                headers={"Authorization": f"Bearer {token}"},
            )

        app.dependency_overrides.clear()

        assert response.status_code == 200
        data = response.json()
        assert data["data"]["id"] == parent_id

    @pytest.mark.anyio
    async def test_returns_404_for_parentless_chunk(self) -> None:
        """Should return 404 when chunk has no parent."""
        from app.core.config import get_settings
        from app.api.deps import get_matter_service
        from app.services.chunk_service import get_chunk_service

        chunk_id = "parent-chunk"

        mock_chunk = Chunk(
            id=chunk_id,
            matter_id="matter-123",
            document_id="doc-123",
            content="Parent content",
            chunk_type=ChunkType.PARENT,
            chunk_index=0,
            token_count=100,
            parent_chunk_id=None,
            page_number=1,
            bbox_ids=None,
            entity_ids=None,
            created_at=datetime.now(timezone.utc),
        )

        mock_chunk_service = MagicMock()
        mock_chunk_service.get_chunk.return_value = mock_chunk
        mock_chunk_service.get_parent_chunk.return_value = None

        mock_matter_service = MagicMock()
        mock_matter_service.get_user_role.return_value = MatterRole.VIEWER

        app.dependency_overrides[get_settings] = get_test_settings
        app.dependency_overrides[get_matter_service] = lambda: mock_matter_service
        app.dependency_overrides[get_chunk_service] = lambda: mock_chunk_service

        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport,
            base_url="http://test",
        ) as client:
            token = create_test_token()
            response = await client.get(
                f"/api/chunks/{chunk_id}/parent",
                headers={"Authorization": f"Bearer {token}"},
            )

        app.dependency_overrides.clear()

        assert response.status_code == 404


class TestGetChunkChildrenEndpoint:
    """Tests for GET /api/chunks/{chunk_id}/children endpoint."""

    @pytest.mark.anyio
    async def test_returns_child_chunks(self) -> None:
        """Should return children for parent chunk."""
        from app.core.config import get_settings
        from app.api.deps import get_matter_service
        from app.services.chunk_service import get_chunk_service

        parent_id = "parent-chunk"
        child_ids = ["child-1", "child-2", "child-3"]

        mock_parent = Chunk(
            id=parent_id,
            matter_id="matter-123",
            document_id="doc-123",
            content="Parent content",
            chunk_type=ChunkType.PARENT,
            chunk_index=0,
            token_count=100,
            parent_chunk_id=None,
            page_number=1,
            bbox_ids=None,
            entity_ids=None,
            created_at=datetime.now(timezone.utc),
        )

        mock_children = [
            Chunk(
                id=child_id,
                matter_id="matter-123",
                document_id="doc-123",
                content=f"Child {i} content",
                chunk_type=ChunkType.CHILD,
                chunk_index=i,
                token_count=30,
                parent_chunk_id=parent_id,
                page_number=1,
                bbox_ids=None,
                entity_ids=None,
                created_at=datetime.now(timezone.utc),
            )
            for i, child_id in enumerate(child_ids)
        ]

        mock_chunk_service = MagicMock()
        mock_chunk_service.get_chunk.return_value = mock_parent
        mock_chunk_service.get_child_chunks.return_value = mock_children

        mock_matter_service = MagicMock()
        mock_matter_service.get_user_role.return_value = MatterRole.VIEWER

        app.dependency_overrides[get_settings] = get_test_settings
        app.dependency_overrides[get_matter_service] = lambda: mock_matter_service
        app.dependency_overrides[get_chunk_service] = lambda: mock_chunk_service

        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport,
            base_url="http://test",
        ) as client:
            token = create_test_token()
            response = await client.get(
                f"/api/chunks/{parent_id}/children",
                headers={"Authorization": f"Bearer {token}"},
            )

        app.dependency_overrides.clear()

        assert response.status_code == 200
        data = response.json()
        assert len(data["data"]) == 3
        assert data["meta"]["child_count"] == 3
