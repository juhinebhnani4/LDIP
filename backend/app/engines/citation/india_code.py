"""India Code Client for searching and downloading Act PDFs.

This module provides a client for interacting with India Code (indiacode.nic.in)
to search for Acts and download their official PDF documents.

India Code is the official digital repository of all Central and State Acts
maintained by the Government of India, running on DSpace.

Part of Act Validation and Auto-Fetching feature.

References:
- India Code: https://www.indiacode.nic.in/
- Central Acts browse: https://www.indiacode.nic.in/handle/123456789/1362/browse
- PDF bitstream pattern: /bitstream/123456789/{doc_id}/1/{filename}.pdf
"""

import asyncio
import re
from dataclasses import dataclass
from typing import Final
from urllib.parse import quote, urljoin

import httpx
from bs4 import BeautifulSoup

from app.core.config import get_settings
from app.core.data_loader import get_known_acts, get_known_act_info
from app.core.logging import get_logger

logger = get_logger(__name__)


# =============================================================================
# Constants (non-configurable)
# =============================================================================

# Base URL for India Code
BASE_URL: Final[str] = "https://www.indiacode.nic.in"

# Central Acts handle ID
CENTRAL_ACTS_HANDLE: Final[str] = "123456789/1362"

# HTTP headers to mimic browser
DEFAULT_HEADERS: Final[dict[str, str]] = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
}


# =============================================================================
# Data Classes
# =============================================================================


@dataclass
class IndiaCodeSearchResult:
    """Result from India Code search."""

    act_name: str  # Full act name from search
    act_year: int | None  # Year if parsed
    doc_id: str  # DSpace document ID
    handle_url: str  # Full handle URL
    bitstream_url: str | None  # Direct PDF URL if available


@dataclass
class IndiaCodeDownloadResult:
    """Result from downloading an Act PDF."""

    success: bool
    doc_id: str
    pdf_bytes: bytes | None
    pdf_url: str
    error_message: str | None
    file_size: int


# =============================================================================
# India Code Client
# =============================================================================


class IndiaCodeClient:
    """Client for interacting with India Code website.

    This client provides methods to:
    1. Search for Acts by name
    2. Download Act PDFs
    3. Get direct PDF URLs

    The client implements rate limiting to avoid overwhelming the server.
    Configuration is loaded from settings (config.py).

    Example usage:
        async with IndiaCodeClient() as client:
            results = await client.search_act("Negotiable Instruments Act")
            if results:
                pdf = await client.download_pdf(results[0].doc_id)
                print(f"Downloaded {len(pdf.pdf_bytes)} bytes")
    """

    def __init__(self, request_delay: float | None = None):
        """Initialize the India Code client.

        Args:
            request_delay: Delay between requests in seconds.
                          If None, uses value from settings.
        """
        settings = get_settings()
        self.request_delay = request_delay if request_delay is not None else settings.india_code_request_delay
        self.request_timeout = settings.india_code_request_timeout
        self.enabled = settings.india_code_enabled
        self._client: httpx.AsyncClient | None = None
        self._last_request_time: float = 0
        self._known_acts: dict[str, tuple[str, str]] | None = None

    def _get_known_acts(self) -> dict[str, tuple[str, str]]:
        """Get known acts mapping, loading from JSON if needed."""
        if self._known_acts is None:
            self._known_acts = get_known_acts()
        return self._known_acts

    async def __aenter__(self):
        """Async context manager entry."""
        self._client = httpx.AsyncClient(
            headers=DEFAULT_HEADERS,
            timeout=self.request_timeout,
            follow_redirects=True,
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self._client:
            await self._client.aclose()
            self._client = None

    async def _rate_limit(self):
        """Apply rate limiting between requests."""
        import time

        now = time.time()
        elapsed = now - self._last_request_time
        if elapsed < self.request_delay:
            await asyncio.sleep(self.request_delay - elapsed)
        self._last_request_time = time.time()

    def _get_client(self) -> httpx.AsyncClient:
        """Get the HTTP client, creating if necessary."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                headers=DEFAULT_HEADERS,
                timeout=self.request_timeout,
                follow_redirects=True,
            )
        return self._client

    def get_known_pdf_url(self, normalized_act_name: str) -> str | None:
        """Get PDF URL for a known act from JSON mappings.

        Args:
            normalized_act_name: Normalized act name (e.g., "negotiable_instruments_act_1881")

        Returns:
            Direct PDF URL if known, None otherwise.
        """
        known_acts = self._get_known_acts()
        if normalized_act_name in known_acts:
            doc_id, filename = known_acts[normalized_act_name]
            return f"{BASE_URL}/bitstream/123456789/{doc_id}/1/{filename}"
        return None

    def get_known_doc_id(self, normalized_act_name: str) -> str | None:
        """Get document ID for a known act.

        Args:
            normalized_act_name: Normalized act name.

        Returns:
            Document ID if known, None otherwise.
        """
        known_acts = self._get_known_acts()
        if normalized_act_name in known_acts:
            return known_acts[normalized_act_name][0]
        return None

    async def search_act(
        self, act_name: str, year: int | None = None
    ) -> list[IndiaCodeSearchResult]:
        """Search for an Act on India Code.

        This method searches the India Code website for acts matching
        the given name and optional year.

        Args:
            act_name: Act name to search for.
            year: Optional year to filter results.

        Returns:
            List of search results, sorted by relevance.
        """
        if not self.enabled:
            logger.warning("India Code integration is disabled")
            return []

        client = self._get_client()
        await self._rate_limit()

        # Clean the search term
        search_term = act_name.strip()
        if year:
            search_term = f"{search_term} {year}"

        # URL encode the search term
        encoded_term = quote(search_term)

        # Search URL - using simple search on Central Acts handle
        search_url = f"{BASE_URL}/handle/{CENTRAL_ACTS_HANDLE}/simple-search"
        params = {
            "query": search_term,
            "filter_field_1": "type",
            "filter_type_1": "equals",
            "filter_value_1": "Act",
        }

        try:
            logger.info(f"Searching India Code for: {search_term}")
            response = await client.get(search_url, params=params)
            response.raise_for_status()

            # Parse HTML response
            soup = BeautifulSoup(response.text, "html.parser")
            results = []

            # Find search result items
            # DSpace typically uses table rows or list items for results
            result_items = soup.select("table.table tr") or soup.select(".ds-table-row")

            for item in result_items:
                # Try to extract act info from each result row
                link = item.select_one("a[href*='/handle/']")
                if not link:
                    continue

                title = link.get_text(strip=True)
                href = link.get("href", "")

                # Extract document ID from handle URL
                # Pattern: /handle/123456789/DOCID
                doc_id_match = re.search(r"/handle/123456789/(\d+)", href)
                if not doc_id_match:
                    continue

                doc_id = doc_id_match.group(1)

                # Try to extract year from title
                extracted_year = None
                year_match = re.search(r"\b(1[89]\d{2}|20\d{2})\b", title)
                if year_match:
                    extracted_year = int(year_match.group(1))

                # Build full URLs
                handle_url = urljoin(BASE_URL, href)

                results.append(
                    IndiaCodeSearchResult(
                        act_name=title,
                        act_year=extracted_year,
                        doc_id=doc_id,
                        handle_url=handle_url,
                        bitstream_url=None,  # Will be fetched separately if needed
                    )
                )

            # Sort by relevance (exact year match first)
            if year:
                results.sort(key=lambda x: (x.act_year != year, x.doc_id))

            logger.info(f"Found {len(results)} results for: {search_term}")
            return results

        except httpx.HTTPError as e:
            logger.error(f"HTTP error searching India Code: {e}")
            return []
        except Exception as e:
            logger.error(f"Error searching India Code: {e}")
            return []

    async def get_bitstream_url(self, doc_id: str) -> str | None:
        """Get the PDF bitstream URL for a document.

        This method fetches the document page and extracts the PDF link.

        Args:
            doc_id: DSpace document ID.

        Returns:
            Direct PDF URL if found, None otherwise.
        """
        if not self.enabled:
            logger.warning("India Code integration is disabled")
            return None

        client = self._get_client()
        await self._rate_limit()

        handle_url = f"{BASE_URL}/handle/123456789/{doc_id}"

        try:
            logger.info(f"Fetching bitstream URL for doc_id: {doc_id}")
            response = await client.get(handle_url)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, "html.parser")

            # Look for PDF links in various locations
            # 1. Direct bitstream link
            bitstream_link = soup.select_one("a[href*='/bitstream/'][href$='.pdf']")
            if bitstream_link:
                return urljoin(BASE_URL, bitstream_link.get("href", ""))

            # 2. Files section
            files_section = soup.select_one(".file-list, .files, .ds-table")
            if files_section:
                pdf_link = files_section.select_one("a[href*='.pdf']")
                if pdf_link:
                    return urljoin(BASE_URL, pdf_link.get("href", ""))

            # 3. Try common bitstream pattern
            # Many acts follow: /bitstream/123456789/{doc_id}/1/{filename}.pdf
            # We need to find the filename
            title_elem = soup.select_one("h1, .item-summary h2, .page-header")
            if title_elem:
                title = title_elem.get_text(strip=True)
                # Generate possible filename patterns
                year_match = re.search(r"\b(1[89]\d{2}|20\d{2})\b", title)
                if year_match:
                    year = year_match.group(1)
                    # Try common patterns
                    patterns = [
                        f"a{year}*.pdf",
                        f"{year}*.pdf",
                    ]
                    # For now, return the base pattern
                    # The actual filename would need to be discovered

            logger.warning(f"Could not find PDF URL for doc_id: {doc_id}")
            return None

        except Exception as e:
            logger.error(f"Error getting bitstream URL for {doc_id}: {e}")
            return None

    async def download_pdf(
        self, doc_id: str, bitstream_url: str | None = None
    ) -> IndiaCodeDownloadResult:
        """Download the PDF for an Act.

        Args:
            doc_id: DSpace document ID.
            bitstream_url: Optional direct PDF URL (will be fetched if not provided).

        Returns:
            Download result with PDF bytes if successful.
        """
        if not self.enabled:
            logger.warning("India Code integration is disabled")
            return IndiaCodeDownloadResult(
                success=False,
                doc_id=doc_id,
                pdf_bytes=None,
                pdf_url="",
                error_message="India Code integration is disabled",
                file_size=0,
            )

        client = self._get_client()

        # Get bitstream URL if not provided
        if not bitstream_url:
            bitstream_url = await self.get_bitstream_url(doc_id)
            if not bitstream_url:
                return IndiaCodeDownloadResult(
                    success=False,
                    doc_id=doc_id,
                    pdf_bytes=None,
                    pdf_url="",
                    error_message="Could not find PDF URL",
                    file_size=0,
                )

        await self._rate_limit()

        try:
            logger.info(f"Downloading PDF from: {bitstream_url}")
            response = await client.get(bitstream_url)
            response.raise_for_status()

            # Verify it's a PDF
            content_type = response.headers.get("content-type", "")
            if "pdf" not in content_type.lower() and not bitstream_url.endswith(".pdf"):
                return IndiaCodeDownloadResult(
                    success=False,
                    doc_id=doc_id,
                    pdf_bytes=None,
                    pdf_url=bitstream_url,
                    error_message=f"Unexpected content type: {content_type}",
                    file_size=0,
                )

            pdf_bytes = response.content
            logger.info(f"Downloaded {len(pdf_bytes)} bytes from: {bitstream_url}")

            return IndiaCodeDownloadResult(
                success=True,
                doc_id=doc_id,
                pdf_bytes=pdf_bytes,
                pdf_url=bitstream_url,
                error_message=None,
                file_size=len(pdf_bytes),
            )

        except httpx.HTTPError as e:
            logger.error(f"HTTP error downloading PDF: {e}")
            return IndiaCodeDownloadResult(
                success=False,
                doc_id=doc_id,
                pdf_bytes=None,
                pdf_url=bitstream_url,
                error_message=f"HTTP error: {str(e)}",
                file_size=0,
            )
        except Exception as e:
            logger.error(f"Error downloading PDF: {e}")
            return IndiaCodeDownloadResult(
                success=False,
                doc_id=doc_id,
                pdf_bytes=None,
                pdf_url=bitstream_url,
                error_message=f"Error: {str(e)}",
                file_size=0,
            )

    async def download_known_act(
        self, normalized_act_name: str
    ) -> IndiaCodeDownloadResult | None:
        """Download a PDF for a known act using JSON mappings.

        This method uses the known_acts.json mapping to directly download
        without needing to search first.

        Args:
            normalized_act_name: Normalized act name (e.g., "negotiable_instruments_act_1881")

        Returns:
            Download result if act is known, None otherwise.
        """
        known_acts = self._get_known_acts()
        if normalized_act_name not in known_acts:
            return None

        doc_id, filename = known_acts[normalized_act_name]
        bitstream_url = f"{BASE_URL}/bitstream/123456789/{doc_id}/1/{filename}"

        return await self.download_pdf(doc_id, bitstream_url)


# =============================================================================
# Module-level convenience functions
# =============================================================================


def is_india_code_enabled() -> bool:
    """Check if India Code integration is enabled.

    Returns:
        True if enabled, False otherwise.
    """
    return get_settings().india_code_enabled


async def search_india_code(
    act_name: str, year: int | None = None
) -> list[IndiaCodeSearchResult]:
    """Search for an Act on India Code.

    Convenience function that creates a client and searches.

    Args:
        act_name: Act name to search for.
        year: Optional year to filter results.

    Returns:
        List of search results.
    """
    async with IndiaCodeClient() as client:
        return await client.search_act(act_name, year)


async def download_act_pdf(doc_id: str) -> IndiaCodeDownloadResult:
    """Download an Act PDF from India Code.

    Convenience function that creates a client and downloads.

    Args:
        doc_id: DSpace document ID.

    Returns:
        Download result with PDF bytes if successful.
    """
    async with IndiaCodeClient() as client:
        return await client.download_pdf(doc_id)


def get_known_act_url(normalized_name: str) -> str | None:
    """Get PDF URL for a known act.

    Convenience function that checks JSON mappings.

    Args:
        normalized_name: Normalized act name.

    Returns:
        Direct PDF URL if known, None otherwise.
    """
    client = IndiaCodeClient()
    return client.get_known_pdf_url(normalized_name)
