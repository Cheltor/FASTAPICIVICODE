import re
from dataclasses import dataclass
from html import unescape
from typing import List, Optional

import requests


SDAT_BASE_URL = "https://sdat.dat.maryland.gov/RealProperty/Pages/viewdetails.aspx"


@dataclass
class SDATOwnerInfo:
    owner_name: Optional[str]
    owner_address: Optional[str]
    owner_city: Optional[str]
    owner_state: Optional[str]
    owner_zip: Optional[str]
    mailing_lines: List[str]
    premises_lines: List[str]
    rendered_district: Optional[str]
    rendered_account: Optional[str]
    source_url: str


_SPAN_PATTERN_CACHE: dict[str, re.Pattern[str]] = {}


def _extract_span_segment(source: str, id_fragment: str) -> Optional[str]:
    """
    Grab the inner HTML of a span whose id contains the provided fragment.
    """
    if id_fragment not in _SPAN_PATTERN_CACHE:
        # Capture any span where id contains the fragment (e.g., lblOwnerName_0)
        pattern = re.compile(
            rf'<span[^>]+id="[^"]*{re.escape(id_fragment)}[^"]*"[^>]*>(.*?)</span>',
            re.IGNORECASE | re.DOTALL,
        )
        _SPAN_PATTERN_CACHE[id_fragment] = pattern
    match = _SPAN_PATTERN_CACHE[id_fragment].search(source)
    return match.group(1) if match else None


def _extract_lines(segment: Optional[str]) -> List[str]:
    if not segment:
        return []
    # Replace <br> with newline then strip remaining tags.
    cleaned = re.sub(r"<br\s*/?>", "\n", segment, flags=re.IGNORECASE)
    cleaned = re.sub(r"<.*?>", "", cleaned, flags=re.DOTALL)
    cleaned = unescape(cleaned)
    return [line.strip() for line in cleaned.splitlines() if line.strip()]


def _parse_city_state_zip(line: str) -> tuple[Optional[str], Optional[str], Optional[str]]:
    normalized = re.sub(r"\s+", " ", line or "").strip(" ,")
    match = re.match(
        r"^(?P<city>.+?)\s*,?\s*(?P<state>[A-Z]{2})\s+(?P<zip>\d{5}(?:-\d{4})?)$",
        normalized,
    )
    if not match:
        return None, None, None
    city = match.group("city").strip(" ,")
    state = match.group("state").strip()
    zip_code = match.group("zip").strip()
    return city, state, zip_code


def fetch_owner_info(
    *,
    county: str,
    account_number: str,
    district: Optional[str] = None,
) -> SDATOwnerInfo:
    params: dict[str, str] = {
        "County": str(county),
        "SearchType": "ACCT",
        "AccountNumber": str(account_number),
    }
    if district:
        params["District"] = str(district)

    try:
        response = requests.get(SDAT_BASE_URL, params=params, timeout=30)
    except requests.RequestException as exc:
        raise RuntimeError("Could not reach SDAT") from exc

    if response.status_code >= 400:
        raise RuntimeError(f"SDAT returned HTTP {response.status_code}")

    html_source = response.text
    owner_name = _extract_span_segment(html_source, "lblOwnerName")
    mailing_lines = _extract_lines(_extract_span_segment(html_source, "lblMailingAddress"))
    premises_lines = _extract_lines(_extract_span_segment(html_source, "lblPremisesAddress"))
    header_text = _extract_span_segment(html_source, "lblDetailsStreetHeader") or ""

    rendered_district = None
    rendered_account = None
    if header_text:
        header_plain = unescape(re.sub(r"<.*?>", "", header_text))
        district_match = re.search(r"District\s*-\s*([^\s]+)", header_plain)
        if district_match:
            rendered_district = district_match.group(1).strip()
        account_match = re.search(r"Account Identifier\s*-\s*([A-Za-z0-9-]+)", header_plain)
        if account_match:
            rendered_account = account_match.group(1).strip()

    owner_address = None
    owner_city = None
    owner_state = None
    owner_zip = None

    if mailing_lines:
        city_candidate = mailing_lines[-1]
        city, state, zip_code = _parse_city_state_zip(city_candidate)
        if city and state and zip_code:
            owner_city, owner_state, owner_zip = city, state, zip_code
            street_lines = mailing_lines[:-1]
        else:
            street_lines = mailing_lines
        if street_lines:
            owner_address = ", ".join(street_lines)

    owner_name_text = None
    if owner_name:
        owner_name_text = unescape(re.sub(r"<.*?>", "", owner_name)).strip()

    return SDATOwnerInfo(
        owner_name=owner_name_text or None,
        owner_address=owner_address,
        owner_city=owner_city,
        owner_state=owner_state,
        owner_zip=owner_zip,
        mailing_lines=mailing_lines,
        premises_lines=premises_lines,
        rendered_district=rendered_district,
        rendered_account=rendered_account,
        source_url=str(response.url),
    )
