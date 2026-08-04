"""One-time backfill: applies address/zip_code (and refreshed about_text/
website_url/certification data) from the latest profiles_WITH_ADDRESS_*.json
snapshot onto existing Contractor rows. Does not touch scores/research/
insight — those are unaffected by this fix.

Usage: python -m scripts.apply_address_backfill
"""

import glob
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlmodel import Session, select

from app.database import engine
from app.models import Contractor

SNAP_DIR = Path(__file__).resolve().parent.parent / "data" / "snapshots"


def main() -> None:
    profile_files = sorted(glob.glob(str(SNAP_DIR / "profiles_WITH_ADDRESS_*.json")))
    if not profile_files:
        raise SystemExit("No profiles_WITH_ADDRESS_*.json snapshot found.")
    with open(profile_files[-1], encoding="utf-8") as f:
        profiles = json.load(f)

    updated, skipped = 0, 0
    with Session(engine) as session:
        for gaf_id, data in profiles.items():
            if "error" in data:
                skipped += 1
                continue
            contractor = session.exec(select(Contractor).where(Contractor.gaf_contractor_id == gaf_id)).first()
            if not contractor:
                skipped += 1
                continue
            contractor.address = data.get("address")
            contractor.zip_code = data.get("zip_code")
            session.add(contractor)
            updated += 1
        session.commit()

    print(f"Updated {updated} contractors with address/zip_code, skipped {skipped}")


if __name__ == "__main__":
    main()
