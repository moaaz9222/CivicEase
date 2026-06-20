#!/usr/bin/env python3
"""
Populate CivicEase AI state deep-dive sections for all 50 U.S. states.

This script is intentionally deterministic: it does not ask an LLM to invent policy
facts. It uses a curated, source-attributed 50-state agency/portal registry and
federal baseline rules for SNAP, TANF, and Medicaid. It appends only missing
"## State Deep Dive" sections and creates a timestamped backup before writing.

Usage:
    python scripts/populate_states.py
    python scripts/populate_states.py --dry-run
    python scripts/populate_states.py --kb data/civicease_knowledge_base.md --validate-links
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable
from urllib.request import Request, urlopen

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_KB_PATH = PROJECT_ROOT / "data" / "civicease_knowledge_base.md"

SOURCE_REGISTRY = {
    "SNAP State Directory": "https://www.fns.usda.gov/snap/state-directory",
    "TANF State Contacts": "https://www.acf.hhs.gov/ofa/map/about/help-families",
    "Medicaid State Overviews": "https://www.medicaid.gov/state-overviews/index.html",
    "HHS Poverty Guidelines": "https://aspe.hhs.gov/topics/poverty-economic-mobility/poverty-guidelines",
    "Healthcare.gov Medicaid & CHIP": "https://www.healthcare.gov/medicaid-chip/",
}

# CivicEase 2026 monthly FPL anchors already used by the local KB.
# The KB notes Alaska at 125% and Hawaii at 115% of continental U.S. levels.
CONUS_FPL_2026_MONTHLY = {
    1: {100: 1330, 130: 1729, 138: 1835, 185: 2461, 200: 2660},
    2: {100: 1800, 130: 2340, 138: 2484, 185: 3330, 200: 3600},
    3: {100: 2265, 130: 2945, 138: 3126, 185: 4190, 200: 4530},
    4: {100: 2750, 130: 3575, 138: 3795, 185: 5088, 200: 5500},
    5: {100: 3235, 130: 4206, 138: 4464, 185: 5985, 200: 6470},
    6: {100: 3720, 130: 4836, 138: 5134, 185: 6882, 200: 7440},
}

NON_EXPANSION_STATES = {"AL", "FL", "GA", "KS", "MS", "SC", "TN", "TX", "WI", "WY"}

@dataclass(frozen=True)
class StateReference:
    code: str
    name: str
    agency: str
    portal_url: str
    gateway: str
    gateway_url: str

    @property
    def metadata_agency(self) -> str:
        acronym = re.findall(r"\(([A-Z]{2,})\)", self.agency)
        return acronym[-1] if acronym else self.agency.split(",")[0]


STATE_REFERENCES: tuple[StateReference, ...] = (
    StateReference("AL", "Alabama", "Alabama Department of Human Resources (DHR)", "https://dhr.alabama.gov", "myDHR", "https://mydhr.alabama.gov"),
    StateReference("AK", "Alaska", "Alaska Department of Health, Division of Public Assistance", "https://health.alaska.gov/dpa", "MyAlaska Benefits", "https://mybenefits.alaska.gov"),
    StateReference("AZ", "Arizona", "Arizona Department of Economic Security (DES)", "https://des.az.gov", "HEAplus", "https://www.healthearizonaplus.gov"),
    StateReference("AR", "Arkansas", "Arkansas Department of Human Services (DHS)", "https://humanservices.arkansas.gov", "Access Arkansas", "https://access.arkansas.gov"),
    StateReference("CA", "California", "California Department of Social Services (CDSS)", "https://www.cdss.ca.gov", "BenefitsCal", "https://benefitscal.com"),
    StateReference("CO", "Colorado", "Colorado Department of Human Services (CDHS)", "https://cdhs.colorado.gov", "Colorado PEAK", "https://peak.my.site.com"),
    StateReference("CT", "Connecticut", "Connecticut Department of Social Services (DSS)", "https://portal.ct.gov/dss", "ConneCT", "https://connect.ct.gov"),
    StateReference("DE", "Delaware", "Delaware Department of Health and Social Services (DHSS), Division of Social Services", "https://dhss.delaware.gov/dhss/dss", "ASSIST Delaware", "https://assist.dhss.delaware.gov"),
    StateReference("FL", "Florida", "Florida Department of Children and Families (DCF)", "https://www.myflfamilies.com", "ACCESS Florida", "https://www.myflorida.com/accessflorida"),
    StateReference("GA", "Georgia", "Georgia Division of Family and Children Services (DFCS)", "https://dfcs.georgia.gov", "Georgia Gateway", "https://gateway.ga.gov"),
    StateReference("HI", "Hawaii", "Hawaii Department of Human Services (DHS)", "https://humanservices.hawaii.gov", "Hawaii Benefits", "https://pais-benefits.dhs.hawaii.gov"),
    StateReference("ID", "Idaho", "Idaho Department of Health and Welfare", "https://healthandwelfare.idaho.gov", "Idaho Benefits", "https://idalink.idaho.gov"),
    StateReference("IL", "Illinois", "Illinois Department of Human Services (IDHS)", "https://www.dhs.state.il.us", "ABE Illinois", "https://abe.illinois.gov"),
    StateReference("IN", "Indiana", "Indiana Family and Social Services Administration (FSSA)", "https://www.in.gov/fssa", "FSSA Benefits Portal", "https://fssabenefits.in.gov"),
    StateReference("IA", "Iowa", "Iowa Department of Health and Human Services (Iowa HHS)", "https://hhs.iowa.gov", "Iowa HHS Benefits Portal", "https://hhsservices.iowa.gov"),
    StateReference("KS", "Kansas", "Kansas Department for Children and Families (DCF)", "https://www.dcf.ks.gov", "DCF Self-Service Portal", "https://cssp.kees.ks.gov"),
    StateReference("KY", "Kentucky", "Kentucky Cabinet for Health and Family Services (CHFS)", "https://chfs.ky.gov", "kynect benefits", "https://kynect.ky.gov/benefits"),
    StateReference("LA", "Louisiana", "Louisiana Department of Children and Family Services (DCFS)", "https://www.dcfs.la.gov", "LA CAFE", "https://cafe-cp.dcfs.la.gov"),
    StateReference("ME", "Maine", "Maine Department of Health and Human Services (DHHS)", "https://www.maine.gov/dhhs", "My Maine Connection", "https://www.mymaineconnection.gov"),
    StateReference("MD", "Maryland", "Maryland Department of Human Services (DHS)", "https://dhs.maryland.gov", "myMDTHINK", "https://mymdthink.maryland.gov"),
    StateReference("MA", "Massachusetts", "Massachusetts Executive Office of Health and Human Services (EOHHS)", "https://www.mass.gov/eohhs", "DTA Connect", "https://dtaconnect.eohhs.mass.gov"),
    StateReference("MI", "Michigan", "Michigan Department of Health and Human Services (MDHHS)", "https://www.michigan.gov/mdhhs", "MI Bridges", "https://www.michigan.gov/mibridges"),
    StateReference("MN", "Minnesota", "Minnesota Department of Human Services (DHS)", "https://mn.gov/dhs", "MNbenefits", "https://mnbenefits.mn.gov"),
    StateReference("MS", "Mississippi", "Mississippi Department of Human Services (MDHS)", "https://www.mdhs.ms.gov", "Mississippi Access", "https://access.ms.gov"),
    StateReference("MO", "Missouri", "Missouri Department of Social Services (DSS)", "https://dss.mo.gov", "myDSS", "https://mydss.mo.gov"),
    StateReference("MT", "Montana", "Montana Department of Public Health and Human Services (DPHHS)", "https://dphhs.mt.gov", "Apply for Assistance", "https://apply.mt.gov"),
    StateReference("NE", "Nebraska", "Nebraska Department of Health and Human Services (DHHS)", "https://dhhs.ne.gov", "ACCESSNebraska", "https://dhhs-access-neb-menu.ne.gov"),
    StateReference("NV", "Nevada", "Nevada Department of Health and Human Services (DHHS), Division of Welfare and Supportive Services", "https://dwss.nv.gov", "Access Nevada", "https://accessnevada.dwss.nv.gov"),
    StateReference("NH", "New Hampshire", "New Hampshire Department of Health and Human Services (DHHS)", "https://www.dhhs.nh.gov", "NH EASY", "https://nheasy.nh.gov"),
    StateReference("NJ", "New Jersey", "New Jersey Department of Human Services (DHS)", "https://www.nj.gov/humanservices", "NJHelps", "https://www.njhelps.gov"),
    StateReference("NM", "New Mexico", "New Mexico Health Care Authority (HCA)", "https://www.hca.nm.gov", "YES New Mexico", "https://www.yes.state.nm.us"),
    StateReference("NY", "New York", "New York State Office of Temporary and Disability Assistance (OTDA)", "https://otda.ny.gov", "myBenefits NY", "https://mybenefits.ny.gov"),
    StateReference("NC", "North Carolina", "North Carolina Department of Health and Human Services (NCDHHS)", "https://www.ncdhhs.gov", "ePASS", "https://epass.nc.gov"),
    StateReference("ND", "North Dakota", "North Dakota Health and Human Services (HHS)", "https://www.hhs.nd.gov", "Apply for Assistance", "https://www.hhs.nd.gov/applyforhelp"),
    StateReference("OH", "Ohio", "Ohio Department of Job and Family Services (ODJFS)", "https://jfs.ohio.gov", "Benefits.Ohio.gov", "https://benefits.ohio.gov"),
    StateReference("OK", "Oklahoma", "Oklahoma Department of Human Services (OKDHS)", "https://oklahoma.gov/okdhs.html", "OKDHSLive", "https://www.okdhslive.org"),
    StateReference("OR", "Oregon", "Oregon Department of Human Services (ODHS)", "https://www.oregon.gov/odhs", "ONE Oregon", "https://one.oregon.gov"),
    StateReference("PA", "Pennsylvania", "Pennsylvania Department of Human Services (DHS)", "https://www.dhs.pa.gov", "COMPASS", "https://www.compass.state.pa.us"),
    StateReference("RI", "Rhode Island", "Rhode Island Department of Human Services (DHS)", "https://dhs.ri.gov", "HealthyRhode / UHIP", "https://healthyrhode.ri.gov"),
    StateReference("SC", "South Carolina", "South Carolina Department of Social Services (DSS)", "https://dss.sc.gov", "SCMAPP / DSS Benefits Portal", "https://scmapp.sc.gov"),
    StateReference("SD", "South Dakota", "South Dakota Department of Social Services (DSS)", "https://dss.sd.gov", "DSS Benefits Portal", "https://benefits.sd.gov"),
    StateReference("TN", "Tennessee", "Tennessee Department of Human Services (TDHS)", "https://www.tn.gov/humanservices", "One DHS Customer Portal", "https://onedhs.tn.gov"),
    StateReference("TX", "Texas", "Texas Health and Human Services Commission (HHSC)", "https://www.hhs.texas.gov", "YourTexasBenefits", "https://www.yourtexasbenefits.com"),
    StateReference("UT", "Utah", "Utah Department of Workforce Services (DWS)", "https://jobs.utah.gov", "myCase", "https://jobs.utah.gov/mycase"),
    StateReference("VT", "Vermont", "Vermont Agency of Human Services (AHS), Department for Children and Families (DCF)", "https://dcf.vermont.gov", "MyBenefits Vermont", "https://mybenefits.ahs.state.vt.us"),
    StateReference("VA", "Virginia", "Virginia Department of Social Services (VDSS)", "https://www.dss.virginia.gov", "CommonHelp", "https://commonhelp.virginia.gov"),
    StateReference("WA", "Washington", "Washington State Department of Social and Health Services (DSHS)", "https://www.dshs.wa.gov", "Washington Connection", "https://www.washingtonconnection.org"),
    StateReference("WV", "West Virginia", "West Virginia Department of Human Services, Bureau for Family Assistance", "https://dhhr.wv.gov/bfa", "WV PATH", "https://www.wvpath.wv.gov"),
    StateReference("WI", "Wisconsin", "Wisconsin Department of Health Services (DHS)", "https://www.dhs.wisconsin.gov", "ACCESS Wisconsin", "https://access.wisconsin.gov"),
    StateReference("WY", "Wyoming", "Wyoming Department of Family Services (DFS)", "https://dfs.wyo.gov", "DFS Assistance Programs", "https://dfs.wyo.gov/services/assistance-programs"),
)

HEADER_RE = re.compile(r"^##\s+State Deep Dive\s+[—-]\s+(.+?)\s+\(([A-Z]{2})\)\s*$", re.MULTILINE)
DIRECTORY_ROW_RE = re.compile(r"^\|\s*([^|]+?)\s*\|\s*([^|]+?)\s*\|\s*(https?://[^|\s]+)\s*\|\s*([^|]+?)\s*\|\s*$", re.MULTILINE)


def money(value: int) -> str:
    return f"${value:,}/month"


def fpl_values_for(code: str, household_size: int = 4) -> dict[int, int]:
    multiplier = 1.25 if code == "AK" else 1.15 if code == "HI" else 1.0
    return {
        pct: int(round(amount * multiplier))
        for pct, amount in CONUS_FPL_2026_MONTHLY[household_size].items()
    }


def existing_state_codes(markdown: str) -> set[str]:
    return {match.group(2) for match in HEADER_RE.finditer(markdown)}


def directory_overrides(markdown: str) -> dict[str, tuple[str, str, str]]:
    by_name = {ref.name: ref.code for ref in STATE_REFERENCES}
    overrides: dict[str, tuple[str, str, str]] = {}
    for state_name, agency, portal, gateway in DIRECTORY_ROW_RE.findall(markdown):
        code = by_name.get(state_name.strip())
        if code:
            overrides[code] = (agency.strip(), portal.strip(), gateway.strip())
    return overrides


def with_local_overrides(ref: StateReference, overrides: dict[str, tuple[str, str, str]]) -> StateReference:
    override = overrides.get(ref.code)
    if not override:
        return ref
    agency, portal_url, gateway = override
    parsed_gateway_url = re.search(r"\(([^)]+\.[^)]+)\)", gateway)
    gateway_url = ref.gateway_url
    if parsed_gateway_url:
        host = parsed_gateway_url.group(1).strip()
        gateway_url = host if host.startswith("http") else f"https://{host}"
    return StateReference(ref.code, ref.name, agency, portal_url, gateway, gateway_url)


def source_lines() -> str:
    return "\n".join(f"  - {name}: {url}" for name, url in SOURCE_REGISTRY.items())


def render_state_deep_dive(ref: StateReference) -> str:
    h4 = fpl_values_for(ref.code, 4)
    h1 = fpl_values_for(ref.code, 1)
    expanded = ref.code not in NON_EXPANSION_STATES
    medicaid_status = "adopted ACA Medicaid expansion" if expanded else "has not adopted the full ACA adult Medicaid expansion"
    adult_medicaid = (
        f"Adults ages 19-64 are generally screened at 138% FPL ({money(h4[138])} for a household of 4 in this state's FPL region)."
        if expanded
        else "There is no broad ACA adult expansion group; parents, children, pregnant people, seniors, and people with disabilities must be screened under state categorical pathways."
    )
    metadata = {
        "state": ref.code,
        "state_name": ref.name,
        "type": "deep_dive",
        "agency": ref.metadata_agency,
        "portal": ref.gateway_url,
        "programs": [f"SNAP_{ref.code}", f"TANF_{ref.code}", f"Medicaid_{ref.code}"],
        "source_basis": "deterministic_2026_populator",
    }
    generated_at = datetime.now(timezone.utc).date().isoformat()
    return f"""
<!-- chunk: state_deep_dive:{ref.code} -->
<!-- metadata: {json.dumps(metadata, sort_keys=True)} -->
## State Deep Dive - {ref.name} ({ref.code})

- **Primary Human Services Agency:** {ref.agency}
- **Official State Portal:** {ref.portal_url}
- **Unified Application Gateway:** {ref.gateway} - {ref.gateway_url}
- **Generated/Validated By:** scripts/populate_states.py on {generated_at}
- **Primary Verification Sources:**
{source_lines()}

### {ref.name} - SNAP Baseline Mapping (2026)

- **Federal Parent Program:** SNAP, administered federally by USDA Food and Nutrition Service and locally by {ref.agency}.
- **Application Path:** Start at {ref.gateway} ({ref.gateway_url}) or the official state agency site ({ref.portal_url}).
- **Core Income Screen:** Standard federal SNAP screening uses 130% FPL gross income and 100% FPL net income after allowable deductions.
- **2026 Household-4 Screening Anchors:** 100% FPL {money(h4[100])}; 130% FPL {money(h4[130])}; 185% FPL {money(h4[185])}; 200% FPL {money(h4[200])}.
- **2026 Single-Person Screening Anchors:** 100% FPL {money(h1[100])}; 130% FPL {money(h1[130])}; 200% FPL {money(h1[200])}.
- **State Variation Watchpoints:** Broad-based categorical eligibility, asset-test waivers, ABAWD waivers, disaster SNAP, and EBT issuance schedules can vary by state and year.
- **RAG Safety Rule:** Treat these as screening anchors, not final eligibility determinations. Final SNAP decisions come from the state/local SNAP office.

### {ref.name} - TANF Baseline Mapping (2026)

- **Federal Parent Program:** Temporary Assistance for Needy Families (TANF), administered through the state human services system.
- **State Administrative Lead:** {ref.agency}.
- **Application Path:** {ref.gateway} ({ref.gateway_url}).
- **Core Federal Eligibility Frame:** TANF is for families with a child under 18, or a pregnant person, who meet state income/resource rules and citizenship/qualified-immigrant rules.
- **Income Standard:** TANF cash assistance does not have one federal income threshold. {ref.name} sets its own need standard, payment standard, countable-income rules, and disregards.
- **Federal Time Limit:** Up to 60 cumulative months of federally funded TANF assistance for adults, unless state rules or hardship exceptions apply.
- **Work Participation:** Adult recipients are generally screened for work, job search, training, education, or other approved activities.
- **RAG Safety Rule:** Never infer TANF approval from FPL alone. Use this section to route the applicant to the state agency and ask for household composition, earned/unearned income, pregnancy status, and child ages.

### {ref.name} - Medicaid Baseline Mapping (2026)

- **Federal Parent Program:** Medicaid (Title XIX), administered by the state Medicaid agency with CMS oversight.
- **State Expansion Posture:** {ref.name} {medicaid_status}.
- **Application Path:** {ref.gateway} ({ref.gateway_url}); Healthcare.gov can also route applicants to Medicaid/CHIP screening where appropriate.
- **Adult MAGI Screen:** {adult_medicaid}
- **Children/Pregnancy Screen:** Children and pregnant applicants often have higher Medicaid/CHIP thresholds than adults; route through the state gateway for official MAGI determination.
- **2026 Household-4 Reference Anchors:** 138% FPL {money(h4[138])}; 185% FPL {money(h4[185])}; 200% FPL {money(h4[200])}.
- **Non-MAGI Pathways:** Seniors, people with disabilities, SSI-linked applicants, long-term care applicants, and medically needy applicants may use different income/resource rules.
- **RAG Safety Rule:** Medicaid output should say "may qualify" or "should be screened," never "eligible" or "approved," unless an official state determination is present.
""".strip() + "\n"


def validate_references(refs: Iterable[StateReference]) -> list[str]:
    problems: list[str] = []
    for ref in refs:
        for label, url in (("portal", ref.portal_url), ("gateway", ref.gateway_url)):
            try:
                request = Request(url, method="HEAD", headers={"User-Agent": "CivicEase-KB-Populator/1.0"})
                with urlopen(request, timeout=10) as response:
                    if response.status >= 400:
                        problems.append(f"{ref.code} {label} returned HTTP {response.status}: {url}")
            except Exception as exc:
                problems.append(f"{ref.code} {label} could not be verified ({exc.__class__.__name__}): {url}")
    return problems


def populate(kb_path: Path, dry_run: bool = False, validate_links: bool = False) -> int:
    if not kb_path.exists():
        raise FileNotFoundError(f"Knowledge base file not found: {kb_path}")

    markdown = kb_path.read_text(encoding="utf-8")
    present = existing_state_codes(markdown)
    overrides = directory_overrides(markdown)
    refs = [with_local_overrides(ref, overrides) for ref in STATE_REFERENCES]
    missing = [ref for ref in refs if ref.code not in present]

    print(f"Knowledge base: {kb_path}")
    print(f"Existing state deep dives: {len(present)}")
    print(f"Missing state deep dives: {len(missing)}")
    if missing:
        print("Missing:", ", ".join(f"{ref.name} ({ref.code})" for ref in missing))

    if validate_links:
        print("Validating official portal/gateway links...")
        problems = validate_references(refs)
        if problems:
            print("Link validation warnings:")
            for problem in problems:
                print(f"  - {problem}")
        else:
            print("All checked links returned non-error HTTP statuses.")

    if not missing:
        return 0

    append_block = "\n\n---\n\n# Auto-Populated 50-State Deep Dives\n\n" + "\n---\n\n".join(
        render_state_deep_dive(ref) for ref in missing
    )

    if dry_run:
        print("Dry run only. No files changed.")
        print(f"Would append {len(append_block):,} characters.")
        return 0

    backup_path = kb_path.with_suffix(kb_path.suffix + f".bak-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}")
    shutil.copy2(kb_path, backup_path)
    kb_path.write_text(markdown.rstrip() + append_block + "\n", encoding="utf-8")
    print(f"Backup written: {backup_path}")
    print(f"Appended {len(missing)} state deep-dive section(s).")
    return 0


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Populate missing CivicEase 50-state KB deep dives.")
    parser.add_argument("--kb", type=Path, default=DEFAULT_KB_PATH, help="Path to CivicEase markdown KB file.")
    parser.add_argument("--dry-run", action="store_true", help="Report missing states without writing changes.")
    parser.add_argument("--validate-links", action="store_true", help="Best-effort HTTP HEAD validation for official URLs.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    return populate(args.kb.resolve(), dry_run=args.dry_run, validate_links=args.validate_links)


if __name__ == "__main__":
    raise SystemExit(main())
