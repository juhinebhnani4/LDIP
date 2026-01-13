"""Indian Legal Act abbreviation dictionary for citation extraction.

This module provides comprehensive mapping of abbreviated Act names
to their canonical forms, supporting the Citation Verification Engine.

Story 3-1: Act Citation Extraction (AC: #2)
"""

import re
from typing import Final

# =============================================================================
# Act Abbreviation Dictionary
# =============================================================================

# Maps abbreviated forms to canonical Act names
# Key: lowercase abbreviation pattern (can include variations)
# Value: (canonical_name, year if known)
ACT_ABBREVIATIONS: Final[dict[str, tuple[str, int | None]]] = {
    # -------------------------------------------------------------------------
    # Criminal Law
    # -------------------------------------------------------------------------
    "ipc": ("Indian Penal Code", 1860),
    "indian penal code": ("Indian Penal Code", 1860),
    "bns": ("Bharatiya Nyaya Sanhita", 2023),
    "bharatiya nyaya sanhita": ("Bharatiya Nyaya Sanhita", 2023),
    "crpc": ("Code of Criminal Procedure", 1973),
    "cr.p.c.": ("Code of Criminal Procedure", 1973),
    "cr.p.c": ("Code of Criminal Procedure", 1973),
    "cr pc": ("Code of Criminal Procedure", 1973),
    "code of criminal procedure": ("Code of Criminal Procedure", 1973),
    "criminal procedure code": ("Code of Criminal Procedure", 1973),
    "bnss": ("Bharatiya Nagarik Suraksha Sanhita", 2023),
    "bharatiya nagarik suraksha sanhita": ("Bharatiya Nagarik Suraksha Sanhita", 2023),
    "bsa": ("Bharatiya Sakshya Adhiniyam", 2023),
    "bharatiya sakshya adhiniyam": ("Bharatiya Sakshya Adhiniyam", 2023),
    "indian evidence act": ("Indian Evidence Act", 1872),
    "evidence act": ("Indian Evidence Act", 1872),
    "iea": ("Indian Evidence Act", 1872),
    "pocso": ("Protection of Children from Sexual Offences Act", 2012),
    "pocso act": ("Protection of Children from Sexual Offences Act", 2012),
    "ndps": ("Narcotic Drugs and Psychotropic Substances Act", 1985),
    "ndps act": ("Narcotic Drugs and Psychotropic Substances Act", 1985),
    "pmla": ("Prevention of Money Laundering Act", 2002),
    "prevention of money laundering act": ("Prevention of Money Laundering Act", 2002),
    "pota": ("Prevention of Terrorism Act", 2002),
    "uapa": ("Unlawful Activities (Prevention) Act", 1967),
    "unlawful activities prevention act": ("Unlawful Activities (Prevention) Act", 1967),
    # -------------------------------------------------------------------------
    # Civil and Commercial Law
    # -------------------------------------------------------------------------
    "cpc": ("Code of Civil Procedure", 1908),
    "c.p.c.": ("Code of Civil Procedure", 1908),
    "c.p.c": ("Code of Civil Procedure", 1908),
    "code of civil procedure": ("Code of Civil Procedure", 1908),
    "civil procedure code": ("Code of Civil Procedure", 1908),
    "ni act": ("Negotiable Instruments Act", 1881),
    "n.i. act": ("Negotiable Instruments Act", 1881),
    "n.i.act": ("Negotiable Instruments Act", 1881),
    "nia": ("Negotiable Instruments Act", 1881),
    "negotiable instruments act": ("Negotiable Instruments Act", 1881),
    "contract act": ("Indian Contract Act", 1872),
    "indian contract act": ("Indian Contract Act", 1872),
    "ica": ("Indian Contract Act", 1872),
    "sale of goods act": ("Sale of Goods Act", 1930),
    "soga": ("Sale of Goods Act", 1930),
    "transfer of property act": ("Transfer of Property Act", 1882),
    "tpa": ("Transfer of Property Act", 1882),
    "t.p. act": ("Transfer of Property Act", 1882),
    "specific relief act": ("Specific Relief Act", 1963),
    "sra": ("Specific Relief Act", 1963),
    "limitation act": ("Limitation Act", 1963),
    "arbitration act": ("Arbitration and Conciliation Act", 1996),
    "arbitration and conciliation act": ("Arbitration and Conciliation Act", 1996),
    "a&c act": ("Arbitration and Conciliation Act", 1996),
    # -------------------------------------------------------------------------
    # Banking and Finance
    # -------------------------------------------------------------------------
    "sarfaesi": ("Securitisation and Reconstruction of Financial Assets and Enforcement of Security Interest Act", 2002),
    "sarfaesi act": ("Securitisation and Reconstruction of Financial Assets and Enforcement of Security Interest Act", 2002),
    "securitisation act": ("Securitisation and Reconstruction of Financial Assets and Enforcement of Security Interest Act", 2002),
    "rbi act": ("Reserve Bank of India Act", 1934),
    "reserve bank of india act": ("Reserve Bank of India Act", 1934),
    "banking regulation act": ("Banking Regulation Act", 1949),
    "bra": ("Banking Regulation Act", 1949),
    "recovery of debts act": ("Recovery of Debts Due to Banks and Financial Institutions Act", 1993),
    "rddbfi act": ("Recovery of Debts Due to Banks and Financial Institutions Act", 1993),
    "drt act": ("Recovery of Debts Due to Banks and Financial Institutions Act", 1993),
    "insolvency and bankruptcy code": ("Insolvency and Bankruptcy Code", 2016),
    "ibc": ("Insolvency and Bankruptcy Code", 2016),
    "i&b code": ("Insolvency and Bankruptcy Code", 2016),
    # -------------------------------------------------------------------------
    # Corporate Law
    # -------------------------------------------------------------------------
    "companies act": ("Companies Act", 2013),
    "companies act 2013": ("Companies Act", 2013),
    "companies act 1956": ("Companies Act", 1956),
    "llp act": ("Limited Liability Partnership Act", 2008),
    "limited liability partnership act": ("Limited Liability Partnership Act", 2008),
    "sebi act": ("Securities and Exchange Board of India Act", 1992),
    "securities and exchange board of india act": ("Securities and Exchange Board of India Act", 1992),
    "securities contracts regulation act": ("Securities Contracts (Regulation) Act", 1956),
    "scra": ("Securities Contracts (Regulation) Act", 1956),
    "competition act": ("Competition Act", 2002),
    # -------------------------------------------------------------------------
    # Taxation
    # -------------------------------------------------------------------------
    "income tax act": ("Income Tax Act", 1961),
    "i.t. act": ("Income Tax Act", 1961),
    "it act": ("Income Tax Act", 1961),
    "income-tax act": ("Income Tax Act", 1961),
    "gst act": ("Goods and Services Tax Act", 2017),
    "cgst act": ("Central Goods and Services Tax Act", 2017),
    "central goods and services tax act": ("Central Goods and Services Tax Act", 2017),
    "igst act": ("Integrated Goods and Services Tax Act", 2017),
    "sgst act": ("State Goods and Services Tax Act", 2017),
    "customs act": ("Customs Act", 1962),
    "central excise act": ("Central Excise Act", 1944),
    "fema": ("Foreign Exchange Management Act", 1999),
    "foreign exchange management act": ("Foreign Exchange Management Act", 1999),
    "fera": ("Foreign Exchange Regulation Act", 1973),
    "black money act": ("Black Money (Undisclosed Foreign Income and Assets) and Imposition of Tax Act", 2015),
    "benami act": ("Prohibition of Benami Property Transactions Act", 1988),
    "prohibition of benami property transactions act": ("Prohibition of Benami Property Transactions Act", 1988),
    # -------------------------------------------------------------------------
    # Information Technology and Media
    # -------------------------------------------------------------------------
    "information technology act": ("Information Technology Act", 2000),
    "it act 2000": ("Information Technology Act", 2000),
    "copyright act": ("Copyright Act", 1957),
    "patents act": ("Patents Act", 1970),
    "trade marks act": ("Trade Marks Act", 1999),
    "designs act": ("Designs Act", 2000),
    "cinematograph act": ("Cinematograph Act", 1952),
    "cable television networks act": ("Cable Television Networks (Regulation) Act", 1995),
    # -------------------------------------------------------------------------
    # Labour and Employment
    # -------------------------------------------------------------------------
    "industrial disputes act": ("Industrial Disputes Act", 1947),
    "ida": ("Industrial Disputes Act", 1947),
    "factories act": ("Factories Act", 1948),
    "employees provident fund act": ("Employees' Provident Funds and Miscellaneous Provisions Act", 1952),
    "epf act": ("Employees' Provident Funds and Miscellaneous Provisions Act", 1952),
    "esic act": ("Employees' State Insurance Act", 1948),
    "payment of wages act": ("Payment of Wages Act", 1936),
    "minimum wages act": ("Minimum Wages Act", 1948),
    "payment of bonus act": ("Payment of Bonus Act", 1965),
    "payment of gratuity act": ("Payment of Gratuity Act", 1972),
    "contract labour act": ("Contract Labour (Regulation and Abolition) Act", 1970),
    "sexual harassment act": ("Sexual Harassment of Women at Workplace (Prevention, Prohibition and Redressal) Act", 2013),
    "posh act": ("Sexual Harassment of Women at Workplace (Prevention, Prohibition and Redressal) Act", 2013),
    # -------------------------------------------------------------------------
    # Property and Land Law
    # -------------------------------------------------------------------------
    "rera": ("Real Estate (Regulation and Development) Act", 2016),
    "real estate regulation act": ("Real Estate (Regulation and Development) Act", 2016),
    "registration act": ("Registration Act", 1908),
    "stamp act": ("Indian Stamp Act", 1899),
    "indian stamp act": ("Indian Stamp Act", 1899),
    "land acquisition act": ("Right to Fair Compensation and Transparency in Land Acquisition, Rehabilitation and Resettlement Act", 2013),
    "rfctlarr act": ("Right to Fair Compensation and Transparency in Land Acquisition, Rehabilitation and Resettlement Act", 2013),
    "easements act": ("Indian Easements Act", 1882),
    "indian easements act": ("Indian Easements Act", 1882),
    "partition act": ("Partition Act", 1893),
    # -------------------------------------------------------------------------
    # Family and Personal Law
    # -------------------------------------------------------------------------
    "hindu marriage act": ("Hindu Marriage Act", 1955),
    "hma": ("Hindu Marriage Act", 1955),
    "hindu succession act": ("Hindu Succession Act", 1956),
    "hsa": ("Hindu Succession Act", 1956),
    "hindu adoption act": ("Hindu Adoptions and Maintenance Act", 1956),
    "hama": ("Hindu Adoptions and Maintenance Act", 1956),
    "hindu minority act": ("Hindu Minority and Guardianship Act", 1956),
    "hmga": ("Hindu Minority and Guardianship Act", 1956),
    "special marriage act": ("Special Marriage Act", 1954),
    "sma": ("Special Marriage Act", 1954),
    "indian divorce act": ("Indian Divorce Act", 1869),
    "domestic violence act": ("Protection of Women from Domestic Violence Act", 2005),
    "pwdv act": ("Protection of Women from Domestic Violence Act", 2005),
    "dv act": ("Protection of Women from Domestic Violence Act", 2005),
    "maintenance and welfare of parents act": ("Maintenance and Welfare of Parents and Senior Citizens Act", 2007),
    "indian succession act": ("Indian Succession Act", 1925),
    "guardians and wards act": ("Guardians and Wards Act", 1890),
    # -------------------------------------------------------------------------
    # Constitutional and Administrative Law
    # -------------------------------------------------------------------------
    "constitution": ("Constitution of India", 1950),
    "constitution of india": ("Constitution of India", 1950),
    "indian constitution": ("Constitution of India", 1950),
    "administrative tribunals act": ("Administrative Tribunals Act", 1985),
    "rti act": ("Right to Information Act", 2005),
    "right to information act": ("Right to Information Act", 2005),
    "right to education act": ("Right of Children to Free and Compulsory Education Act", 2009),
    "rte act": ("Right of Children to Free and Compulsory Education Act", 2009),
    "consumer protection act": ("Consumer Protection Act", 2019),
    "cpa": ("Consumer Protection Act", 2019),
    "consumer protection act 2019": ("Consumer Protection Act", 2019),
    "consumer protection act 1986": ("Consumer Protection Act", 1986),
    "sc/st act": ("Scheduled Castes and Scheduled Tribes (Prevention of Atrocities) Act", 1989),
    "poa act": ("Scheduled Castes and Scheduled Tribes (Prevention of Atrocities) Act", 1989),
    "atrocities act": ("Scheduled Castes and Scheduled Tribes (Prevention of Atrocities) Act", 1989),
    # -------------------------------------------------------------------------
    # Environmental Law
    # -------------------------------------------------------------------------
    "environment protection act": ("Environment (Protection) Act", 1986),
    "epa": ("Environment (Protection) Act", 1986),
    "wildlife protection act": ("Wildlife (Protection) Act", 1972),
    "forest act": ("Indian Forest Act", 1927),
    "indian forest act": ("Indian Forest Act", 1927),
    "water act": ("Water (Prevention and Control of Pollution) Act", 1974),
    "air act": ("Air (Prevention and Control of Pollution) Act", 1981),
    "national green tribunal act": ("National Green Tribunal Act", 2010),
    "ngt act": ("National Green Tribunal Act", 2010),
    # -------------------------------------------------------------------------
    # Motor Vehicles and Transport
    # -------------------------------------------------------------------------
    "motor vehicles act": ("Motor Vehicles Act", 1988),
    "mv act": ("Motor Vehicles Act", 1988),
    "mva": ("Motor Vehicles Act", 1988),
    "carriage by road act": ("Carriage by Road Act", 2007),
    # -------------------------------------------------------------------------
    # Miscellaneous
    # -------------------------------------------------------------------------
    "arms act": ("Arms Act", 1959),
    "drugs and cosmetics act": ("Drugs and Cosmetics Act", 1940),
    "food safety act": ("Food Safety and Standards Act", 2006),
    "fssa": ("Food Safety and Standards Act", 2006),
    "electricity act": ("Electricity Act", 2003),
    "petroleum act": ("Petroleum Act", 1934),
    "explosives act": ("Explosives Act", 1884),
    "essential commodities act": ("Essential Commodities Act", 1955),
    "seeds act": ("Seeds Act", 1966),
    "legal metrology act": ("Legal Metrology Act", 2009),
    "lokpal act": ("Lokpal and Lokayuktas Act", 2013),
    "prevention of corruption act": ("Prevention of Corruption Act", 1988),
    "pc act": ("Prevention of Corruption Act", 1988),
    "whistleblowers protection act": ("Whistle Blowers Protection Act", 2014),
}


# =============================================================================
# Normalization Functions
# =============================================================================


def _normalize_key(text: str) -> str:
    """Normalize text for dictionary lookup.

    Converts to lowercase, removes extra spaces, and normalizes punctuation.
    """
    # Convert to lowercase
    text = text.lower().strip()

    # Replace multiple spaces with single space
    text = re.sub(r"\s+", " ", text)

    # Remove trailing comma and year (we handle year separately)
    text = re.sub(r",?\s*\d{4}$", "", text)

    # Normalize common punctuation variations
    text = text.replace("&", "and")

    return text


def normalize_act_name(raw_name: str) -> str:
    """Normalize an Act name to canonical form.

    Args:
        raw_name: The Act name as extracted from text.

    Returns:
        Normalized Act name suitable for database storage and matching.
        Format: lowercase_with_underscores_year (e.g., "negotiable_instruments_act_1881")
    """
    # First, try to get canonical name
    canonical = get_canonical_name(raw_name)
    if canonical:
        name, year = canonical
        # Convert to normalized form
        normalized = name.lower()
        normalized = re.sub(r"[^\w\s]", "", normalized)  # Remove punctuation
        normalized = re.sub(r"\s+", "_", normalized)  # Replace spaces with underscores
        if year:
            normalized = f"{normalized}_{year}"
        return normalized

    # Fallback: normalize the raw name directly
    normalized = raw_name.lower().strip()
    normalized = re.sub(r"[^\w\s]", "", normalized)
    normalized = re.sub(r"\s+", "_", normalized)

    # Try to extract year
    year = extract_year_from_name(raw_name)
    if year and str(year) not in normalized:
        normalized = f"{normalized}_{year}"

    return normalized


def get_canonical_name(abbreviated: str) -> tuple[str, int | None] | None:
    """Get the canonical name for an abbreviated Act name.

    Args:
        abbreviated: The abbreviated or informal Act name.

    Returns:
        Tuple of (canonical_name, year) if found, None otherwise.

    Examples:
        >>> get_canonical_name("NI Act")
        ("Negotiable Instruments Act", 1881)
        >>> get_canonical_name("SARFAESI")
        ("Securitisation and Reconstruction of Financial Assets...", 2002)
    """
    key = _normalize_key(abbreviated)

    # Direct lookup
    if key in ACT_ABBREVIATIONS:
        return ACT_ABBREVIATIONS[key]

    # Try partial matching for common patterns
    # Handle "the X act" -> "X act"
    if key.startswith("the "):
        key_without_the = key[4:]
        if key_without_the in ACT_ABBREVIATIONS:
            return ACT_ABBREVIATIONS[key_without_the]

    # Handle "X act of YYYY" -> "X act"
    key_without_year = re.sub(r"\s+of\s+\d{4}$", "", key)
    if key_without_year != key and key_without_year in ACT_ABBREVIATIONS:
        return ACT_ABBREVIATIONS[key_without_year]

    # Try fuzzy match for close variations
    for abbr_key, value in ACT_ABBREVIATIONS.items():
        # Check if the input contains the abbreviation
        if abbr_key in key or key in abbr_key:
            return value

    return None


def extract_year_from_name(act_name: str) -> int | None:
    """Extract the year from an Act name.

    Args:
        act_name: The Act name potentially containing a year.

    Returns:
        The year as an integer if found, None otherwise.

    Examples:
        >>> extract_year_from_name("Negotiable Instruments Act, 1881")
        1881
        >>> extract_year_from_name("NI Act")
        None
    """
    # Look for 4-digit year (1800-2099)
    year_match = re.search(r"\b(1[89]\d{2}|20\d{2})\b", act_name)
    if year_match:
        return int(year_match.group(1))
    return None


def get_display_name(normalized_name: str) -> str:
    """Get a display-friendly name from a normalized Act name.

    Args:
        normalized_name: Normalized name (e.g., "negotiable_instruments_act_1881")

    Returns:
        Display-friendly name (e.g., "Negotiable Instruments Act, 1881")
    """
    # Extract year if present
    year_match = re.search(r"_(\d{4})$", normalized_name)
    year = None
    if year_match:
        year = year_match.group(1)
        normalized_name = normalized_name[: -len(year) - 1]

    # Convert underscores to spaces and title case
    display = normalized_name.replace("_", " ").title()

    # Add year if present
    if year:
        display = f"{display}, {year}"

    return display
