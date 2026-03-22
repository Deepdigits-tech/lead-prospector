#!/usr/bin/env python3
"""
Prospect Pipeline — Lead Prospector Plugin

Apollo + LeadMagic automation for the /prospect skill.

The QUALIFY step is done by Claude (web research). This script handles:
- search: Apollo contact search (free)
- reveal: Apollo contact reveal (1 credit/contact)
- enrich: LeadMagic enrichment (email validation, finder, profile, personal email, mobile)
- status: Show pipeline progress
- final: Generate clean final CSV with country filter and SDR context

Usage:
    python3 prospect_pipeline.py status --batch us-mi-1
    python3 prospect_pipeline.py search --batch us-mi-1
    python3 prospect_pipeline.py reveal --batch us-mi-1
    python3 prospect_pipeline.py enrich --batch us-mi-1
    python3 prospect_pipeline.py final --batch us-mi-1 [--country "United States"]
"""

import os
import sys
import argparse
import pandas as pd
import time
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables from .env in working directory
load_dotenv()

# Output directory — relative to current working directory
OUTPUT_DIR = Path(os.getcwd()) / "output" / "prospect"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Import from sibling modules in the same scripts/ directory
SCRIPT_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPT_DIR))

from apollo_contact_finder import (
    search_people_by_company,
    reveal_contact,
    format_contact,
    format_revealed_contact,
    TARGET_TITLES,
)
from enrich_leadmagic import (
    validate_email,
    find_email,
    profile_search,
    mobile_finder,
    role_finder,
    personal_email_finder,
    employee_finder,
)


def get_batch_files(batch: str) -> dict:
    """Get file paths for a batch."""
    return {
        "input": OUTPUT_DIR / f"{batch}_companies_input.csv",
        "qualified": OUTPUT_DIR / f"{batch}_companies_qualified.csv",
        "search": OUTPUT_DIR / f"{batch}_contacts_search.csv",
        "revealed": OUTPUT_DIR / f"{batch}_contacts_revealed.csv",
        "enriched": OUTPUT_DIR / f"{batch}_contacts_enriched.csv",
        "final": OUTPUT_DIR / f"{batch}_final.csv",
    }


def show_status(batch: str = None):
    """Show pipeline status for a batch or all batches."""
    print("=" * 60)
    print("PROSPECT PIPELINE STATUS")
    print("=" * 60)

    if batch:
        batches = [batch]
    else:
        # Find all batches by looking at files
        batches = set()
        for f in OUTPUT_DIR.glob("*_companies_*.csv"):
            batch_name = f.name.rsplit("_companies_", 1)[0]
            batches.add(batch_name)
        for f in OUTPUT_DIR.glob("*_contacts_*.csv"):
            batch_name = f.name.rsplit("_contacts_", 1)[0]
            batches.add(batch_name)
        for f in OUTPUT_DIR.glob("*_final.csv"):
            batch_name = f.name.rsplit("_final", 1)[0]
            batches.add(batch_name)
        batches = sorted(batches)

    if not batches:
        print("\nNo batches found in output/prospect/")
        return

    for b in batches:
        files = get_batch_files(b)
        print(f"\n--- Batch: {b} ---")

        if files["input"].exists():
            df = pd.read_csv(files["input"])
            print(f"  Input: {len(df)} companies")
        else:
            print(f"  Input: Not created")

        if files["qualified"].exists():
            df = pd.read_csv(files["qualified"])
            qualified = len(df[df["qualification_status"] == "QUALIFIED"]) if "qualification_status" in df.columns else 0
            not_qual = len(df[df["qualification_status"] == "NOT_QUALIFIED"]) if "qualification_status" in df.columns else 0
            review = len(df[df["qualification_status"] == "NEEDS_REVIEW"]) if "qualification_status" in df.columns else 0
            print(f"  Qualified: {qualified} qualified, {not_qual} not qualified, {review} needs review (total: {len(df)})")
        else:
            print(f"  Qualified: Not run (Claude research step)")

        if files["search"].exists():
            df = pd.read_csv(files["search"])
            companies = df["company_name"].nunique() if "company_name" in df.columns else 0
            print(f"  Contacts Found: {len(df)} contacts at {companies} companies")
        else:
            print(f"  Contacts Found: Not run")

        if files["revealed"].exists():
            df = pd.read_csv(files["revealed"])
            with_email = len(df[df["email"].notna() & (df["email"] != "")]) if "email" in df.columns else 0
            print(f"  Revealed: {len(df)} contacts ({with_email} with email)")
        else:
            print(f"  Revealed: Not run")

        if files["enriched"].exists():
            df = pd.read_csv(files["enriched"])
            deliverable = df["email_is_deliverable"].sum() if "email_is_deliverable" in df.columns else 0
            with_mobile = df["lm_mobile"].notna().sum() if "lm_mobile" in df.columns else 0
            print(f"  Enriched: {len(df)} contacts ({int(deliverable)} deliverable emails, {int(with_mobile)} with mobile)")
        else:
            print(f"  Enriched: Not run")

        if files["final"].exists():
            df = pd.read_csv(files["final"])
            print(f"  Final: {len(df)} verified contacts ready")
        else:
            print(f"  Final: Not generated")

    print()


def run_search(batch: str, limit_per_company: int = 5):
    """Run Apollo contact search for qualified companies."""
    files = get_batch_files(batch)

    if not files["qualified"].exists():
        print(f"Error: Qualified companies not found at {files['qualified']}")
        print("Run the 'qualify' step first (Claude research).")
        return False

    print(f"\n{'=' * 60}")
    print(f"SEARCHING APOLLO CONTACTS - Batch: {batch}")
    print(f"{'=' * 60}")

    df = pd.read_csv(files["qualified"])
    qualified = df[df["qualification_status"] == "QUALIFIED"] if "qualification_status" in df.columns else df
    print(f"Loaded {len(qualified)} qualified companies")
    print(f"Target titles: {', '.join(TARGET_TITLES[:5])}... (+{len(TARGET_TITLES)-5} more)")
    print(f"Cost: FREE (search only, no reveal)")
    print()

    all_contacts = []
    companies_with_contacts = 0

    for idx, row in qualified.iterrows():
        company_name = str(row.get("company_name", "")).strip()
        domain = str(row.get("domain", row.get("website", ""))).strip()

        # Clean domain
        if domain and domain != "nan":
            domain = domain.replace("www.", "").replace("https://", "").replace("http://", "").strip("/")
        else:
            domain = None

        print(f"[{idx + 1}/{len(qualified)}] {company_name} ({domain or 'no domain'})")

        result = search_people_by_company(company_name, domain, limit=limit_per_company)
        people = result.get("people", [])

        if people:
            companies_with_contacts += 1
            print(f"  Found {len(people)} contacts:")
            for person in people:
                contact = format_contact(person, company_name)
                all_contacts.append(contact)
                print(f"    - {contact['full_name']} | {contact['title']}")
        else:
            print(f"  No contacts found with target titles")

        time.sleep(0.3)  # Rate limit

    if all_contacts:
        contacts_df = pd.DataFrame(all_contacts)
        contacts_df.to_csv(files["search"], index=False)
        print(f"\n{'=' * 60}")
        print(f"SEARCH SUMMARY")
        print(f"{'=' * 60}")
        print(f"Companies searched: {len(qualified)}")
        print(f"Companies with contacts: {companies_with_contacts}")
        print(f"Total contacts found: {len(contacts_df)}")
        print(f"Saved to: {files['search']}")
    else:
        print("\nNo contacts found for any company.")

    return True


def run_reveal(batch: str):
    """Reveal contacts using Apollo credits."""
    files = get_batch_files(batch)

    if not files["search"].exists():
        print(f"Error: Search results not found at {files['search']}")
        return False

    df = pd.read_csv(files["search"])

    print(f"\n{'=' * 60}")
    print(f"REVEALING CONTACTS - Batch: {batch}")
    print(f"{'=' * 60}")
    print(f"Total contacts to reveal: {len(df)}")
    print(f"Estimated Apollo credits: {len(df)}")
    print()

    revealed_contacts = []
    total_credits = 0
    errors = 0

    for idx, row in df.iterrows():
        person_id = row.get("person_id", "")
        company = row.get("company_name", "")
        title = row.get("title", "")
        name = row.get("full_name", row.get("first_name", ""))

        print(f"[{idx + 1}/{len(df)}] {name} - {title} @ {company}...", end=" ")

        if not person_id or str(person_id) == "nan":
            print("SKIP (no person_id)")
            continue

        result = reveal_contact(person_id)

        if "error" not in result and result.get("person"):
            contact = format_revealed_contact(result["person"], company)
            revealed_contacts.append(contact)
            total_credits += result.get("credits_consumed", 1)
            email_display = contact.get("email", "no email")
            print(f"OK -> {email_display}")
        else:
            errors += 1
            print(f"FAILED: {result.get('error', 'Unknown')}")
            # Keep original data as fallback
            revealed_contacts.append({
                "person_id": person_id,
                "first_name": row.get("first_name", ""),
                "last_name": row.get("last_name", ""),
                "full_name": row.get("full_name", ""),
                "title": title,
                "headline": "",
                "email": "",
                "email_status": "",
                "direct_phone": "",
                "mobile_phone": "",
                "company_phone": "",
                "linkedin_url": row.get("linkedin_url", ""),
                "company_name": company,
                "company_domain": row.get("company_domain", ""),
                "company_linkedin": "",
                "seniority": row.get("seniority", ""),
                "departments": row.get("departments", ""),
                "city": row.get("city", ""),
                "state": row.get("state", ""),
                "country": row.get("country", ""),
                "revealed": False,
            })

        time.sleep(0.3)

    revealed_df = pd.DataFrame(revealed_contacts)
    revealed_df.to_csv(files["revealed"], index=False)

    with_email = len(revealed_df[revealed_df["email"].notna() & (revealed_df["email"] != "")]) if "email" in revealed_df.columns else 0

    print(f"\n{'=' * 60}")
    print(f"REVEAL SUMMARY")
    print(f"{'=' * 60}")
    print(f"Total processed: {len(revealed_contacts)}")
    print(f"Successful: {len(revealed_contacts) - errors}")
    print(f"Failed: {errors}")
    print(f"With email: {with_email}")
    print(f"Apollo credits used: {total_credits}")
    print(f"Saved to: {files['revealed']}")

    return True


def run_enrich(batch: str):
    """Run LeadMagic enrichment on revealed contacts."""
    files = get_batch_files(batch)

    if not files["revealed"].exists():
        print(f"Error: Revealed contacts not found at {files['revealed']}")
        return False

    df = pd.read_csv(files["revealed"])

    print(f"\n{'=' * 60}")
    print(f"ENRICHING CONTACTS - Batch: {batch}")
    print(f"{'=' * 60}")
    print(f"Total contacts: {len(df)}")

    with_email = df[df["email"].notna() & (df["email"] != "")]
    without_email = df[df["email"].isna() | (df["email"] == "")]
    with_linkedin = df[df["linkedin_url"].notna() & (df["linkedin_url"] != "")]

    print(f"  {len(with_email)} with email (will validate)")
    print(f"  {len(without_email)} missing email (will search)")
    print(f"  {len(with_linkedin)} with LinkedIn (will enrich + personal email + mobile)")

    est_credits = (len(with_email) * 0.05) + (len(without_email) * 1) + (len(with_linkedin) * 1) + (len(with_linkedin) * 2)
    print(f"\nEstimated LeadMagic credits: ~{est_credits:.0f}")
    print()

    # Initialize enrichment columns
    enrichment_cols = [
        "email_validated", "email_is_valid", "email_is_deliverable", "email_is_catch_all",
        "email_status_lm", "mx_provider",
        "lm_email", "lm_email_confidence",
        "personal_email",
        "lm_first_name", "lm_last_name", "lm_full_name", "lm_headline", "lm_bio",
        "lm_company_name", "lm_company_industry", "lm_company_website",
        "lm_location", "lm_country", "lm_followers", "lm_tenure_years",
        "lm_mobile", "mobile_found",
    ]
    for col in enrichment_cols:
        if col not in df.columns:
            df[col] = None

    total_credits = 0

    # Step 1: Validate existing emails
    print("=" * 40)
    print("STEP 1/6: Validating existing emails")
    print("=" * 40)

    for idx, row in df.iterrows():
        email = row.get("email")
        if pd.notna(email) and email:
            print(f"  [{idx+1}/{len(df)}] {email}...", end=" ")
            result = validate_email(str(email))
            if "error" not in result:
                df.at[idx, "email_validated"] = True
                df.at[idx, "email_is_valid"] = result.get("is_valid")
                df.at[idx, "email_is_deliverable"] = result.get("is_deliverable")
                df.at[idx, "email_is_catch_all"] = result.get("is_catch_all")
                df.at[idx, "email_status_lm"] = result.get("email_status", "unknown")
                df.at[idx, "mx_provider"] = result.get("mx_provider", "")
                total_credits += result.get("credits", 0.05)
                status = result.get("email_status", "unknown").upper()
                if result.get("is_catch_all"):
                    status += " (catch-all)"
                print(status)
            else:
                print(f"Error: {result.get('error')}")

    # Step 2: Find missing emails (Email Finder - 1 credit)
    print(f"\n{'=' * 40}")
    print("STEP 2/6: Finding missing emails")
    print("=" * 40)

    for idx, row in df.iterrows():
        email = row.get("email")
        domain = row.get("company_domain")
        first_name = row.get("first_name")
        last_name = row.get("last_name")

        if (pd.isna(email) or not email) and domain and first_name and last_name:
            domain = str(domain).strip()
            first_name = str(first_name).strip()
            last_name = str(last_name).strip()

            if domain == "nan" or not domain:
                continue

            print(f"  [{idx+1}/{len(df)}] {first_name} {last_name} @ {domain}...", end=" ")
            result = find_email(first_name, last_name, domain)

            if "error" not in result and result.get("email"):
                df.at[idx, "lm_email"] = result.get("email")
                df.at[idx, "lm_email_confidence"] = result.get("confidence")
                total_credits += result.get("credits", 1)
                print(f"FOUND: {result.get('email')}")

                # Validate the found email too
                val_result = validate_email(result.get("email"))
                if "error" not in val_result:
                    df.at[idx, "email_validated"] = True
                    df.at[idx, "email_is_valid"] = val_result.get("is_valid")
                    df.at[idx, "email_is_deliverable"] = val_result.get("is_deliverable")
                    df.at[idx, "email_is_catch_all"] = val_result.get("is_catch_all")
                    df.at[idx, "email_status_lm"] = val_result.get("email_status", "unknown")
                    total_credits += val_result.get("credits", 0.05)
            else:
                print("Not found")

    # Step 3: LinkedIn profile enrichment (1 credit)
    print(f"\n{'=' * 40}")
    print("STEP 3/6: LinkedIn profile enrichment")
    print("=" * 40)

    for idx, row in df.iterrows():
        linkedin_url = row.get("linkedin_url")
        if pd.notna(linkedin_url) and str(linkedin_url).startswith("http"):
            name = row.get("full_name", "Unknown")
            print(f"  [{idx+1}/{len(df)}] {name}...", end=" ")
            result = profile_search(str(linkedin_url))

            if "error" not in result:
                for key, value in result.items():
                    if key != "credits" and value:
                        df.at[idx, key] = value
                total_credits += result.get("credits", 1)
                print("OK")
            else:
                print(f"Error: {result.get('error')}")

    # Step 4: Personal email finder (2 credits, 0 if not found)
    print(f"\n{'=' * 40}")
    print("STEP 4/6: Finding personal emails")
    print("=" * 40)

    personal_found = 0
    for idx, row in df.iterrows():
        linkedin_url = row.get("linkedin_url")
        if pd.notna(linkedin_url) and str(linkedin_url).startswith("http"):
            name = row.get("full_name", "Unknown")
            print(f"  [{idx+1}/{len(df)}] {name}...", end=" ")
            result = personal_email_finder(str(linkedin_url))

            if "error" not in result and not result.get("not_found"):
                df.at[idx, "personal_email"] = result.get("personal_email")
                total_credits += result.get("credits", 2)
                print(f"FOUND: {result.get('personal_email')}")
                personal_found += 1
            else:
                print("Not found (0 credits)")

    print(f"\nPersonal emails found: {personal_found}/{len(with_linkedin)}")

    # Step 5: Mobile phone finder (5 credits, 0 if not found)
    print(f"\n{'=' * 40}")
    print("STEP 5/6: Finding mobile phones")
    print("=" * 40)

    mobiles_found = 0
    for idx, row in df.iterrows():
        linkedin_url = row.get("linkedin_url")
        if pd.notna(linkedin_url) and str(linkedin_url).startswith("http"):
            name = row.get("full_name", "Unknown")
            print(f"  [{idx+1}/{len(df)}] {name}...", end=" ")
            result = mobile_finder(str(linkedin_url))

            if "error" not in result:
                df.at[idx, "lm_mobile"] = result.get("lm_mobile")
                df.at[idx, "mobile_found"] = result.get("mobile_found")
                total_credits += result.get("credits", 0)
                if result.get("mobile_found"):
                    print(f"FOUND: {result.get('lm_mobile')}")
                    mobiles_found += 1
                else:
                    print("Not found (0 credits)")
            else:
                print(f"Error: {result.get('error')}")

    # Step 6: Summary & Save
    print(f"\n{'=' * 40}")
    print("STEP 6/6: Computing best email & saving")
    print("=" * 40)

    df["enriched_at"] = datetime.now().isoformat()

    # Compute best email
    def pick_best_email(r):
        if pd.notna(r.get("email")) and r.get("email"):
            return r["email"]
        if pd.notna(r.get("lm_email")) and r.get("lm_email"):
            return r["lm_email"]
        return ""

    df["best_email"] = df.apply(pick_best_email, axis=1)

    def compute_email_status(r):
        status = r.get("email_status_lm", "")
        if pd.notna(status) and status:
            return status
        if pd.notna(r.get("email_is_valid")) and r.get("email_is_valid"):
            return "valid"
        return "unknown"

    df["email_status_final"] = df.apply(compute_email_status, axis=1)

    # Save
    df.to_csv(files["enriched"], index=False)

    valid_count = len(df[df["email_status_final"] == "valid"]) if "email_status_final" in df.columns else 0
    catch_all_count = len(df[df["email_is_catch_all"] == True]) if "email_is_catch_all" in df.columns else 0

    print(f"\n{'=' * 60}")
    print("ENRICHMENT SUMMARY")
    print(f"{'=' * 60}")
    print(f"Total contacts: {len(df)}")
    print(f"Emails validated: {df['email_validated'].sum() if 'email_validated' in df.columns else 0:.0f}")
    print(f"  Valid: {valid_count}")
    print(f"  Catch-all: {catch_all_count}")
    print(f"New work emails found: {df['lm_email'].notna().sum()}")
    print(f"Personal emails found: {personal_found}")
    print(f"Mobile phones found: {mobiles_found}")
    print(f"LeadMagic credits used: {total_credits:.2f}")
    print(f"Saved to: {files['enriched']}")

    return True


def generate_final(batch: str, target_country: str = "United States"):
    """Generate clean final output CSV with country filter and SDR context."""
    files = get_batch_files(batch)

    # Use enriched if available, otherwise revealed
    if files["enriched"].exists():
        df = pd.read_csv(files["enriched"])
        source = "enriched"
    elif files["revealed"].exists():
        df = pd.read_csv(files["revealed"])
        source = "revealed"
    else:
        print(f"Error: No revealed or enriched data found for batch {batch}")
        return False

    print(f"\n{'=' * 60}")
    print(f"GENERATING FINAL OUTPUT - Batch: {batch}")
    print(f"{'=' * 60}")
    print(f"Source: {source} ({len(df)} contacts)")

    # Country filter
    if target_country and "country" in df.columns:
        before = len(df)
        df = df[df["country"].fillna("").str.strip().str.lower() == target_country.lower()]
        filtered = before - len(df)
        if filtered > 0:
            print(f"Country filter: removed {filtered} contacts not in {target_country}")
        print(f"Contacts after filter: {len(df)}")

    # Load qualification data for company info (including SDR context)
    qual_data = {}
    if files["qualified"].exists():
        qual_df = pd.read_csv(files["qualified"])
        for _, row in qual_df.iterrows():
            domain = str(row.get("domain", "")).strip()
            if domain and domain != "nan":
                qual_data[domain] = {
                    "qualification_reason": row.get("qualification_reason", ""),
                    "company_type": row.get("company_type", ""),
                    "employee_estimate": row.get("employee_estimate", ""),
                    "certifications": row.get("certifications", ""),
                    "sdr_context": row.get("sdr_context", ""),
                    "sdr_context_date": row.get("sdr_context_date", ""),
                    "pain_points": row.get("pain_points", ""),
                    "growth_signals": row.get("growth_signals", ""),
                }

    # Build final output
    final_rows = []
    for _, row in df.iterrows():
        domain = str(row.get("company_domain", "")).strip()
        qual_info = qual_data.get(domain, {})

        best_email = row.get("best_email", row.get("email", row.get("lm_email", "")))
        if pd.isna(best_email):
            best_email = ""

        email_status = row.get("email_status_final", "unknown")
        if source == "revealed" and not pd.isna(row.get("email")):
            email_status = row.get("email_status", "unknown")

        personal_email = row.get("personal_email", "")
        if pd.isna(personal_email):
            personal_email = ""

        phone = row.get("lm_mobile", row.get("mobile_phone", row.get("direct_phone", row.get("company_phone", ""))))
        if pd.isna(phone):
            phone = ""

        sdr_context = qual_info.get("sdr_context", "")
        if pd.isna(sdr_context):
            sdr_context = ""

        final_rows.append({
            "company_name": row.get("company_name", ""),
            "company_domain": domain,
            "company_type": qual_info.get("company_type", ""),
            "employee_estimate": qual_info.get("employee_estimate", ""),
            "qualification_reason": qual_info.get("qualification_reason", ""),
            "sdr_context": sdr_context,
            "sdr_context_date": qual_info.get("sdr_context_date", ""),
            "pain_points": qual_info.get("pain_points", ""),
            "growth_signals": qual_info.get("growth_signals", ""),
            "contact_name": row.get("full_name", ""),
            "title": row.get("title", ""),
            "seniority": row.get("seniority", ""),
            "best_email": best_email,
            "email_verified": email_status,
            "personal_email": personal_email,
            "linkedin_url": row.get("linkedin_url", ""),
            "phone": phone,
            "city": row.get("city", ""),
            "state": row.get("state", ""),
            "country": row.get("country", ""),
        })

    final_df = pd.DataFrame(final_rows)

    # Only keep contacts with at least email or LinkedIn
    final_df = final_df[
        (final_df["best_email"].notna() & (final_df["best_email"] != "")) |
        (final_df["linkedin_url"].notna() & (final_df["linkedin_url"] != ""))
    ]

    final_df.to_csv(files["final"], index=False)

    print(f"\nTotal contacts: {len(final_df)}")
    print(f"With email: {len(final_df[final_df['best_email'].notna() & (final_df['best_email'] != '')])}")
    print(f"With LinkedIn: {len(final_df[final_df['linkedin_url'].notna() & (final_df['linkedin_url'] != '')])}")
    print(f"With phone: {len(final_df[final_df['phone'].notna() & (final_df['phone'] != '')])}")
    print(f"With SDR context: {len(final_df[final_df['sdr_context'].notna() & (final_df['sdr_context'] != '')])}")
    print(f"\nSaved to: {files['final']}")

    return True


def main():
    parser = argparse.ArgumentParser(description="Prospect Pipeline - Apollo + LeadMagic automation")
    parser.add_argument("step", choices=["status", "search", "reveal", "enrich", "final"],
                        help="Pipeline step to run")
    parser.add_argument("--batch", "-b", type=str, required=False, default=None,
                        help="Batch name (e.g., us-mi-1, ontario-4)")
    parser.add_argument("--limit", "-l", type=int, default=5,
                        help="Max contacts per company for search (default: 5)")
    parser.add_argument("--country", "-c", type=str, default="United States",
                        help="Target country filter for final output (default: 'United States')")

    args = parser.parse_args()

    if args.step == "status":
        show_status(args.batch)
    elif args.step == "search":
        if not args.batch:
            print("Error: --batch is required")
            return
        run_search(args.batch, limit_per_company=args.limit)
    elif args.step == "reveal":
        if not args.batch:
            print("Error: --batch is required")
            return
        run_reveal(args.batch)
    elif args.step == "enrich":
        if not args.batch:
            print("Error: --batch is required")
            return
        run_enrich(args.batch)
    elif args.step == "final":
        if not args.batch:
            print("Error: --batch is required")
            return
        generate_final(args.batch, target_country=args.country)


if __name__ == "__main__":
    main()
