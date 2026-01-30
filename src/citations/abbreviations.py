"""Indian legal act abbreviations and canonical names.

Maps common abbreviations to full act names.
Includes both old acts and new Bharatiya codes (2023).
"""

from typing import Optional

# =============================================================================
# Act Abbreviation Mappings
# =============================================================================

ACT_ABBREVIATIONS: dict[str, str] = {
    # Criminal Law - Old
    "IPC": "Indian Penal Code, 1860",
    "Indian Penal Code": "Indian Penal Code, 1860",
    "CrPC": "Code of Criminal Procedure, 1973",
    "Cr.P.C.": "Code of Criminal Procedure, 1973",
    "Criminal Procedure Code": "Code of Criminal Procedure, 1973",
    "IEA": "Indian Evidence Act, 1872",
    "Evidence Act": "Indian Evidence Act, 1872",

    # Criminal Law - New (Bharatiya Codes 2023)
    "BNS": "Bharatiya Nyaya Sanhita, 2023",
    "Bharatiya Nyaya Sanhita": "Bharatiya Nyaya Sanhita, 2023",
    "BNSS": "Bharatiya Nagarik Suraksha Sanhita, 2023",
    "Bharatiya Nagarik Suraksha Sanhita": "Bharatiya Nagarik Suraksha Sanhita, 2023",
    "BSA": "Bharatiya Sakshya Adhiniyam, 2023",
    "Bharatiya Sakshya Adhiniyam": "Bharatiya Sakshya Adhiniyam, 2023",

    # Civil Law
    "CPC": "Code of Civil Procedure, 1908",
    "Civil Procedure Code": "Code of Civil Procedure, 1908",
    "ICA": "Indian Contract Act, 1872",
    "Contract Act": "Indian Contract Act, 1872",
    "TPA": "Transfer of Property Act, 1882",
    "Transfer of Property Act": "Transfer of Property Act, 1882",
    "SRA": "Specific Relief Act, 1963",
    "Specific Relief Act": "Specific Relief Act, 1963",
    "Limitation Act": "Limitation Act, 1963",

    # Commercial Law
    "NI Act": "Negotiable Instruments Act, 1881",
    "Negotiable Instruments Act": "Negotiable Instruments Act, 1881",
    "Companies Act": "Companies Act, 2013",
    "IBC": "Insolvency and Bankruptcy Code, 2016",
    "Insolvency and Bankruptcy Code": "Insolvency and Bankruptcy Code, 2016",
    "SARFAESI Act": "SARFAESI Act, 2002",
    "Arbitration Act": "Arbitration and Conciliation Act, 1996",
    "A&C Act": "Arbitration and Conciliation Act, 1996",

    # Banking & Finance
    "RBI Act": "Reserve Bank of India Act, 1934",
    "Banking Regulation Act": "Banking Regulation Act, 1949",
    "SEBI Act": "Securities and Exchange Board of India Act, 1992",
    "FEMA": "Foreign Exchange Management Act, 1999",

    # Taxation
    "IT Act": "Income Tax Act, 1961",
    "Income Tax Act": "Income Tax Act, 1961",
    "GST Act": "Central Goods and Services Tax Act, 2017",
    "CGST Act": "Central Goods and Services Tax Act, 2017",
    "IGST Act": "Integrated Goods and Services Tax Act, 2017",

    # Constitutional & Administrative
    "Constitution": "Constitution of India",
    "Indian Constitution": "Constitution of India",
    "RTI Act": "Right to Information Act, 2005",
    "CIC Act": "Central Information Commission Act",

    # Labour Law
    "ID Act": "Industrial Disputes Act, 1947",
    "Industrial Disputes Act": "Industrial Disputes Act, 1947",
    "Factories Act": "Factories Act, 1948",
    "EPF Act": "Employees' Provident Funds Act, 1952",
    "ESI Act": "Employees' State Insurance Act, 1948",
    "Payment of Wages Act": "Payment of Wages Act, 1936",
    "Minimum Wages Act": "Minimum Wages Act, 1948",

    # Consumer & Environment
    "Consumer Protection Act": "Consumer Protection Act, 2019",
    "CPA": "Consumer Protection Act, 2019",
    "EPA": "Environment Protection Act, 1986",
    "Environment Protection Act": "Environment Protection Act, 1986",

    # Property & Land
    "Registration Act": "Registration Act, 1908",
    "Stamp Act": "Indian Stamp Act, 1899",
    "Land Acquisition Act": "Right to Fair Compensation and Transparency in Land Acquisition Act, 2013",
    "RERA": "Real Estate (Regulation and Development) Act, 2016",

    # Technology & IT
    "IT Act 2000": "Information Technology Act, 2000",
    "Information Technology Act": "Information Technology Act, 2000",

    # Intellectual Property
    "Patents Act": "Patents Act, 1970",
    "Copyright Act": "Copyright Act, 1957",
    "Trademarks Act": "Trade Marks Act, 1999",

    # Family Law
    "HMA": "Hindu Marriage Act, 1955",
    "Hindu Marriage Act": "Hindu Marriage Act, 1955",
    "Hindu Succession Act": "Hindu Succession Act, 1956",
    "Special Marriage Act": "Special Marriage Act, 1954",
    "Muslim Personal Law": "Muslim Personal Law (Shariat) Application Act, 1937",
    "Guardians and Wards Act": "Guardians and Wards Act, 1890",
    "DV Act": "Protection of Women from Domestic Violence Act, 2005",
    "Domestic Violence Act": "Protection of Women from Domestic Violence Act, 2005",

    # Criminal Special Laws
    "NDPS Act": "Narcotic Drugs and Psychotropic Substances Act, 1985",
    "POCSO Act": "Protection of Children from Sexual Offences Act, 2012",
    "POCSO": "Protection of Children from Sexual Offences Act, 2012",
    "SC/ST Act": "Scheduled Castes and Scheduled Tribes (Prevention of Atrocities) Act, 1989",
    "PMLA": "Prevention of Money Laundering Act, 2002",
    "UAPA": "Unlawful Activities (Prevention) Act, 1967",
    "Arms Act": "Arms Act, 1959",
    "Motor Vehicles Act": "Motor Vehicles Act, 1988",
    "MV Act": "Motor Vehicles Act, 1988",
}


def resolve_abbreviation(name: str) -> str:
    """Resolve an act abbreviation to its canonical name.

    Args:
        name: Act name or abbreviation

    Returns:
        Canonical act name (or original if not found)
    """
    # Direct lookup
    if name in ACT_ABBREVIATIONS:
        return ACT_ABBREVIATIONS[name]

    # Case-insensitive lookup
    name_lower = name.lower().strip()
    for abbr, canonical in ACT_ABBREVIATIONS.items():
        if abbr.lower() == name_lower:
            return canonical

    # Partial match (for variations)
    for abbr, canonical in ACT_ABBREVIATIONS.items():
        if abbr.lower() in name_lower or name_lower in abbr.lower():
            return canonical

    # Not found, return original
    return name


def get_abbreviation(canonical_name: str) -> Optional[str]:
    """Get common abbreviation for an act.

    Args:
        canonical_name: Full act name

    Returns:
        Common abbreviation or None
    """
    # Reverse lookup
    for abbr, name in ACT_ABBREVIATIONS.items():
        if name == canonical_name:
            # Return shortest abbreviation
            if len(abbr) <= 6:
                return abbr

    return None


def normalize_act_name(name: str) -> str:
    """Normalize act name for matching.

    - Resolves abbreviations
    - Adds year if missing
    - Standardizes format
    """
    import re

    # Clean up
    name = name.strip()

    # Resolve abbreviation first
    canonical = resolve_abbreviation(name)

    # If we got a canonical name, use it
    if canonical != name:
        return canonical

    # Try to add "Act" if missing
    if not re.search(r'\b(Act|Code|Sanhita|Adhiniyam)\b', name, re.IGNORECASE):
        name = f"{name} Act"

    return name
