"""India Code client for downloading act PDFs.

India Code (indiacode.nic.in) is the official government repository
of all Central and State Acts.
"""

import time
from pathlib import Path
from typing import Optional

import httpx
import structlog

from src.core.config import settings
from src.core.utils import safe_filename

logger = structlog.get_logger(__name__)


# Base URLs for India Code
INDIA_CODE_BASE = "https://www.indiacode.nic.in"
CENTRAL_ACTS_HANDLE = "123456789/1362"


class IndiaCodeClient:
    """Client for downloading acts from India Code.

    India Code provides:
    - Central Acts
    - State Acts
    - Subordinate Legislation
    - Constitutional amendments
    """

    def __init__(
        self,
        download_dir: Optional[Path] = None,
        rate_limit_delay: float = 1.0,
        timeout: float = 30.0,
    ):
        """Initialize India Code client.

        Args:
            download_dir: Directory to save downloaded PDFs
            rate_limit_delay: Seconds between requests
            timeout: Request timeout in seconds
        """
        self.download_dir = Path(download_dir or settings.data_path / "acts")
        self.download_dir.mkdir(parents=True, exist_ok=True)
        self.rate_limit_delay = rate_limit_delay
        self.timeout = timeout
        self.client = httpx.Client(timeout=timeout)

    def download_act(
        self,
        doc_id: str,
        filename: str,
        act_name: Optional[str] = None,
    ) -> Optional[Path]:
        """Download an act PDF from India Code.

        Args:
            doc_id: India Code document ID (e.g., "2189")
            filename: PDF filename (e.g., "1/a1881-26.pdf")
            act_name: Optional act name for local filename

        Returns:
            Path to downloaded file or None if failed
        """
        url = f"{INDIA_CODE_BASE}/bitstream/123456789/{doc_id}/{filename}"

        logger.info("downloading_act", doc_id=doc_id, url=url)

        try:
            response = self.client.get(url)
            response.raise_for_status()

            # Generate local filename
            if act_name:
                local_name = f"{safe_filename(act_name)}.pdf"
            else:
                local_name = f"act_{doc_id}.pdf"

            local_path = self.download_dir / local_name

            # Save PDF
            with open(local_path, "wb") as f:
                f.write(response.content)

            logger.info("act_downloaded", path=str(local_path), size=len(response.content))

            # Rate limiting
            time.sleep(self.rate_limit_delay)

            return local_path

        except httpx.HTTPError as e:
            logger.error("download_failed", doc_id=doc_id, error=str(e))
            return None

    def search_act(self, name: str, year: Optional[int] = None) -> list[dict]:
        """Search for an act on India Code.

        Args:
            name: Act name to search
            year: Optional year filter

        Returns:
            List of search results
        """
        search_url = f"{INDIA_CODE_BASE}/handle/{CENTRAL_ACTS_HANDLE}/simple-search"

        params = {
            "query": name,
            "filtername": "type",
            "filterquery": "Act",
        }

        if year:
            params["filter"] = f"year:{year}"

        try:
            response = self.client.get(search_url, params=params)
            response.raise_for_status()

            # Parse results (simplified - India Code returns HTML)
            # In production, you'd parse the HTML response
            logger.info("search_complete", query=name, year=year)
            return []

        except httpx.HTTPError as e:
            logger.error("search_failed", query=name, error=str(e))
            return []

    def close(self):
        """Close HTTP client."""
        self.client.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


# =============================================================================
# Known Acts Data (from Jaanch's known_acts.json)
# =============================================================================

KNOWN_ACTS = [
    {
        "normalized_name": "indian_penal_code_1860",
        "canonical_name": "Indian Penal Code, 1860",
        "india_code_doc_id": "1507",
        "india_code_filename": "1/a1860-45.pdf",
        "category": "criminal",
        "is_active": True,
    },
    {
        "normalized_name": "bharatiya_nyaya_sanhita_2023",
        "canonical_name": "Bharatiya Nyaya Sanhita, 2023",
        "india_code_doc_id": "20062",
        "india_code_filename": "1/202345.pdf",
        "category": "criminal",
        "is_active": True,
        "replaces": "indian_penal_code_1860",
    },
    {
        "normalized_name": "code_of_criminal_procedure_1973",
        "canonical_name": "Code of Criminal Procedure, 1973",
        "india_code_doc_id": "1517",
        "india_code_filename": "1/a1974-2.pdf",
        "category": "criminal",
        "is_active": True,
    },
    {
        "normalized_name": "bharatiya_nagarik_suraksha_sanhita_2023",
        "canonical_name": "Bharatiya Nagarik Suraksha Sanhita, 2023",
        "india_code_doc_id": "20061",
        "india_code_filename": "1/202346.pdf",
        "category": "criminal",
        "is_active": True,
        "replaces": "code_of_criminal_procedure_1973",
    },
    {
        "normalized_name": "indian_evidence_act_1872",
        "canonical_name": "Indian Evidence Act, 1872",
        "india_code_doc_id": "1470",
        "india_code_filename": "1/a1872-1.pdf",
        "category": "evidence",
        "is_active": True,
    },
    {
        "normalized_name": "bharatiya_sakshya_adhiniyam_2023",
        "canonical_name": "Bharatiya Sakshya Adhiniyam, 2023",
        "india_code_doc_id": "20063",
        "india_code_filename": "1/202347.pdf",
        "category": "evidence",
        "is_active": True,
        "replaces": "indian_evidence_act_1872",
    },
    {
        "normalized_name": "negotiable_instruments_act_1881",
        "canonical_name": "Negotiable Instruments Act, 1881",
        "india_code_doc_id": "2189",
        "india_code_filename": "1/a1881-26.pdf",
        "category": "banking",
        "is_active": True,
    },
    {
        "normalized_name": "companies_act_2013",
        "canonical_name": "Companies Act, 2013",
        "india_code_doc_id": "2114",
        "india_code_filename": "1/201318.pdf",
        "category": "corporate",
        "is_active": True,
    },
    {
        "normalized_name": "insolvency_and_bankruptcy_code_2016",
        "canonical_name": "Insolvency and Bankruptcy Code, 2016",
        "india_code_doc_id": "15440",
        "india_code_filename": "1/201631.pdf",
        "category": "insolvency",
        "is_active": True,
    },
    {
        "normalized_name": "income_tax_act_1961",
        "canonical_name": "Income Tax Act, 1961",
        "india_code_doc_id": "2435",
        "india_code_filename": "1/a1961-43.pdf",
        "category": "taxation",
        "is_active": True,
    },
    {
        "normalized_name": "code_of_civil_procedure_1908",
        "canonical_name": "Code of Civil Procedure, 1908",
        "india_code_doc_id": "1519",
        "india_code_filename": "1/a1908-5.pdf",
        "category": "civil",
        "is_active": True,
    },
    {
        "normalized_name": "indian_contract_act_1872",
        "canonical_name": "Indian Contract Act, 1872",
        "india_code_doc_id": "1504",
        "india_code_filename": "1/a1872-9.pdf",
        "category": "civil",
        "is_active": True,
    },
    {
        "normalized_name": "transfer_of_property_act_1882",
        "canonical_name": "Transfer of Property Act, 1882",
        "india_code_doc_id": "1533",
        "india_code_filename": "1/a1882-4.pdf",
        "category": "property",
        "is_active": True,
    },
    {
        "normalized_name": "arbitration_and_conciliation_act_1996",
        "canonical_name": "Arbitration and Conciliation Act, 1996",
        "india_code_doc_id": "1879",
        "india_code_filename": "1/a1996-26.pdf",
        "category": "civil",
        "is_active": True,
    },
    {
        "normalized_name": "consumer_protection_act_2019",
        "canonical_name": "Consumer Protection Act, 2019",
        "india_code_doc_id": "18903",
        "india_code_filename": "1/201935.pdf",
        "category": "consumer",
        "is_active": True,
    },
    {
        "normalized_name": "information_technology_act_2000",
        "canonical_name": "Information Technology Act, 2000",
        "india_code_doc_id": "1999",
        "india_code_filename": "1/a2000-21.pdf",
        "category": "technology",
        "is_active": True,
    },
    {
        "normalized_name": "motor_vehicles_act_1988",
        "canonical_name": "Motor Vehicles Act, 1988",
        "india_code_doc_id": "1798",
        "india_code_filename": "1/a1988-59.pdf",
        "category": "transport",
        "is_active": True,
    },
    {
        "normalized_name": "prevention_of_money_laundering_act_2002",
        "canonical_name": "Prevention of Money Laundering Act, 2002",
        "india_code_doc_id": "2020",
        "india_code_filename": "1/a2003-15.pdf",
        "category": "criminal",
        "is_active": True,
    },
    {
        "normalized_name": "protection_of_children_from_sexual_offences_act_2012",
        "canonical_name": "Protection of Children from Sexual Offences Act, 2012",
        "india_code_doc_id": "2100",
        "india_code_filename": "1/201232.pdf",
        "category": "criminal",
        "is_active": True,
    },
    {
        "normalized_name": "right_to_information_act_2005",
        "canonical_name": "Right to Information Act, 2005",
        "india_code_doc_id": "2052",
        "india_code_filename": "1/a2005-22.pdf",
        "category": "administrative",
        "is_active": True,
    },
]


def get_known_acts() -> list[dict]:
    """Get list of known acts with India Code IDs."""
    return KNOWN_ACTS


def download_all_known_acts(download_dir: Optional[Path] = None) -> dict[str, Path]:
    """Download all known acts from India Code.

    Args:
        download_dir: Directory to save PDFs

    Returns:
        Dict mapping act names to local paths
    """
    client = IndiaCodeClient(download_dir=download_dir)
    downloaded = {}

    for act in KNOWN_ACTS:
        if not act.get("india_code_doc_id") or not act.get("india_code_filename"):
            continue

        path = client.download_act(
            doc_id=act["india_code_doc_id"],
            filename=act["india_code_filename"],
            act_name=act["canonical_name"],
        )

        if path:
            downloaded[act["canonical_name"]] = path

    client.close()
    return downloaded
