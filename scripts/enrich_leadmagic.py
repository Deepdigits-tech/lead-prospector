#!/usr/bin/env python3
"""
LeadMagic Enrichment — Lead Prospector Plugin

Enriches contacts with:
1. Email validation (20 validations per 1 credit)
2. Email finder for missing emails (1 credit per search)
3. LinkedIn profile enrichment (1 credit per profile)
4. Personal email finder (2 credits, 0 if not found)
5. Mobile phone finder (5 credits, 0 if not found)
6. Role finder — Apollo backup (2 credits, 0 if not found)
7. Employee finder (0.5 credits per 10 results)

Requires: LEADMAGIC_API_KEY environment variable
"""

import os
import pandas as pd
import requests
import time
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables from .env in working directory
load_dotenv()

LEADMAGIC_API_KEY = os.getenv("LEADMAGIC_API_KEY")
BASE_URL = "https://api.leadmagic.io/v1"

# Rate limiting
DELAY = 0.5  # seconds between requests


def make_request(endpoint: str, payload: dict) -> dict:
    """Make LeadMagic API request."""
    url = f"{BASE_URL}{endpoint}"
    headers = {
        "X-API-Key": LEADMAGIC_API_KEY,
        "Content-Type": "application/json"
    }

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=30)
        time.sleep(DELAY)

        if response.status_code == 200:
            data = response.json()
            return {"success": True, "data": data, "credits": data.get("credits_consumed", 0)}
        else:
            return {"success": False, "error": f"HTTP {response.status_code}", "response": response.text[:200]}
    except Exception as e:
        return {"success": False, "error": str(e)}


def validate_email(email: str) -> dict:
    """
    Validate an email address.
    Cost: 20 validations per 1 credit

    IMPORTANT: LeadMagic returns `email_status` (valid/invalid/unknown)
    and `is_domain_catch_all` — NOT is_valid/is_deliverable fields.
    This function maps those to is_valid/is_deliverable for convenience.

    Returns: email_status, is_valid, is_deliverable, is_catch_all, company data
    """
    result = make_request("/people/email-validation", {"email": email})
    if result["success"]:
        data = result["data"]
        email_status = data.get("email_status", "unknown")
        is_catch_all = data.get("is_domain_catch_all", False)
        return {
            "is_valid": email_status == "valid",
            "is_deliverable": email_status == "valid" and not is_catch_all,
            "is_catch_all": is_catch_all,
            "email_status": email_status,
            "mx_record": data.get("mx_record", ""),
            "mx_provider": data.get("mx_provider", ""),
            "company_name": data.get("company_name", ""),
            "company_industry": data.get("company_industry", ""),
            "company_size": data.get("company_size", ""),
            "credits": result.get("credits", 0.05)
        }
    return {"error": result.get("error"), "credits": 0}


def role_finder(company_name: str, job_title: str) -> dict:
    """
    Find a person by role at a company (Apollo backup).
    Cost: 2 credits (0 if not found)

    IMPORTANT: The parameter is `job_title`, NOT `role`.

    Returns: name, LinkedIn URL
    """
    result = make_request("/people/role-finder", {
        "company_name": company_name,
        "job_title": job_title
    })
    if result["success"]:
        data = result["data"]
        if data.get("message") == "Role Found":
            return {
                "name": data.get("name"),
                "first_name": data.get("first_name"),
                "last_name": data.get("last_name"),
                "profile_url": data.get("profile_url"),
                "company_name": data.get("company_name"),
                "company_website": data.get("company_website"),
                "credits": data.get("credits_consumed", 2)
            }
        return {"not_found": True, "credits": 0}
    return {"error": result.get("error"), "credits": 0}


def personal_email_finder(linkedin_url: str) -> dict:
    """
    Find personal email from LinkedIn profile URL.
    Cost: 2 credits (0 if not found)
    Returns: personal email
    """
    result = make_request("/people/personal-email-finder", {"profile_url": linkedin_url})
    if result["success"]:
        data = result["data"]
        credits = data.get("credits_consumed", 0)
        personal_email = data.get("email") or data.get("personal_email")
        if personal_email and credits > 0:
            return {
                "personal_email": personal_email,
                "credits": credits
            }
        return {"not_found": True, "credits": 0}
    return {"error": result.get("error"), "credits": 0}


def employee_finder(company_name: str, job_title: str = None) -> dict:
    """
    Find employees at a company.
    Cost: 0.5 credits per 10 results
    Returns: list of employees with name, title, company
    """
    payload = {"company_name": company_name}
    if job_title:
        payload["job_title"] = job_title
    result = make_request("/people/employee-finder", payload)
    if result["success"]:
        data = result["data"]
        return {
            "employees": data.get("data", []),
            "total_count": data.get("total_count", 0),
            "credits": data.get("credits_consumed", 0)
        }
    return {"error": result.get("error"), "credits": 0}


def find_email(first_name: str, last_name: str, domain: str) -> dict:
    """
    Find email by name and company domain.
    Cost: 1 credit
    Returns: email, confidence
    """
    result = make_request("/people/email-finder", {
        "first_name": first_name,
        "last_name": last_name,
        "domain": domain
    })
    if result["success"]:
        data = result["data"]
        return {
            "email": data.get("email"),
            "confidence": data.get("confidence"),
            "credits": result.get("credits", 1)
        }
    return {"error": result.get("error"), "credits": 0}


def profile_search(linkedin_url: str) -> dict:
    """
    Get profile data from LinkedIn URL.
    Cost: 1 credit
    Returns: full profile data (no phone — use mobile_finder for that)
    """
    result = make_request("/people/profile-search", {"profile_url": linkedin_url})
    if result["success"]:
        data = result["data"]
        return {
            "lm_first_name": data.get("first_name"),
            "lm_last_name": data.get("last_name"),
            "lm_full_name": data.get("full_name"),
            "lm_headline": data.get("professional_title") or data.get("headline"),
            "lm_bio": data.get("bio", "")[:200] if data.get("bio") else "",
            "lm_company_name": data.get("company_name"),
            "lm_company_industry": data.get("company_industry"),
            "lm_company_website": data.get("company_website"),
            "lm_location": data.get("location"),
            "lm_country": data.get("country"),
            "lm_followers": data.get("followers_range"),
            "lm_tenure_years": data.get("total_tenure_years"),
            "credits": result.get("credits", 1)
        }
    return {"error": result.get("error"), "credits": 0}


def mobile_finder(linkedin_url: str) -> dict:
    """
    Find mobile phone number from LinkedIn URL.
    Cost: 5 credits (0 if not found)
    Returns: mobile_number
    """
    result = make_request("/people/mobile-finder", {"profile_url": linkedin_url})
    if result["success"]:
        data = result["data"]
        mobile = data.get("mobile_number")
        return {
            "lm_mobile": mobile,
            "mobile_found": mobile is not None and mobile != "",
            "credits": result.get("credits", 0)
        }
    return {"error": result.get("error"), "credits": 0}


def enrich_contacts(input_path: str, output_path: str):
    """
    Enrich contacts from Apollo with LeadMagic data.
    Standalone function for direct usage outside the pipeline.
    """
    df = pd.read_csv(input_path)
    print(f"Loaded {len(df)} contacts from Apollo")

    with_email = df[df['email'].notna() & (df['email'] != '')].copy()
    without_email = df[df['email'].isna() | (df['email'] == '')].copy()
    with_linkedin = df[df['linkedin_url'].notna() & (df['linkedin_url'] != '')].copy()

    print(f"  - {len(with_email)} contacts have email (will validate)")
    print(f"  - {len(without_email)} contacts missing email (will search)")
    print(f"  - {len(with_linkedin)} contacts have LinkedIn (will enrich)")

    est_credits = (len(with_email) * 0.05) + (len(without_email) * 1) + (len(with_linkedin) * 1)
    print(f"\nEstimated credits needed: {est_credits:.1f}")

    enrichment_cols = [
        'email_validated', 'email_is_valid', 'email_is_deliverable', 'email_is_catch_all',
        'lm_email', 'lm_email_confidence',
        'lm_first_name', 'lm_last_name', 'lm_full_name', 'lm_headline', 'lm_bio',
        'lm_company_name', 'lm_company_industry', 'lm_company_website',
        'lm_location', 'lm_country', 'lm_followers', 'lm_tenure_years',
        'lm_mobile', 'mobile_found'
    ]
    for col in enrichment_cols:
        df[col] = None

    total_credits = 0

    # Step 1: Validate existing emails
    print("\n" + "="*60)
    print("STEP 1: Validating existing emails")
    print("="*60)

    for idx, row in df.iterrows():
        email = row.get('email')
        if pd.notna(email) and email:
            print(f"[{idx+1}/{len(df)}] Validating: {email}...", end=" ")
            result = validate_email(email)
            if 'error' not in result:
                df.at[idx, 'email_validated'] = True
                df.at[idx, 'email_is_valid'] = result.get('is_valid')
                df.at[idx, 'email_is_deliverable'] = result.get('is_deliverable')
                df.at[idx, 'email_is_catch_all'] = result.get('is_catch_all')
                total_credits += result.get('credits', 0.05)
                status = "VALID" if result.get('is_deliverable') else ("CATCH-ALL" if result.get('is_catch_all') else "INVALID")
                print(f"{status}")
            else:
                print(f"Error: {result.get('error')}")

    # Step 2: Find missing emails
    print("\n" + "="*60)
    print("STEP 2: Finding missing emails")
    print("="*60)

    for idx, row in df.iterrows():
        email = row.get('email')
        domain = row.get('company_domain')
        first_name = row.get('first_name')
        last_name = row.get('last_name')

        if (pd.isna(email) or not email) and domain and first_name and last_name:
            print(f"[{idx+1}/{len(df)}] Finding email for: {first_name} {last_name} @ {domain}...", end=" ")
            result = find_email(first_name, last_name, domain)
            if 'error' not in result and result.get('email'):
                df.at[idx, 'lm_email'] = result.get('email')
                df.at[idx, 'lm_email_confidence'] = result.get('confidence')
                total_credits += result.get('credits', 1)
                print(f"Found: {result.get('email')} ({result.get('confidence')})")
                # Validate the found email
                val_result = validate_email(result.get('email'))
                if 'error' not in val_result:
                    df.at[idx, 'email_validated'] = True
                    df.at[idx, 'email_is_valid'] = val_result.get('is_valid')
                    df.at[idx, 'email_is_deliverable'] = val_result.get('is_deliverable')
                    df.at[idx, 'email_is_catch_all'] = val_result.get('is_catch_all')
                    total_credits += val_result.get('credits', 0.05)
            else:
                print(f"Not found")

    # Step 3: Profile search via LinkedIn
    print("\n" + "="*60)
    print("STEP 3: LinkedIn profile enrichment")
    print("="*60)

    for idx, row in df.iterrows():
        linkedin_url = row.get('linkedin_url')
        if pd.notna(linkedin_url) and linkedin_url and linkedin_url.startswith('http'):
            name = row.get('full_name', 'Unknown')
            print(f"[{idx+1}/{len(df)}] Enriching: {name}...", end=" ")
            result = profile_search(linkedin_url)
            if 'error' not in result:
                for key, value in result.items():
                    if key != 'credits' and value:
                        df.at[idx, key] = value
                total_credits += result.get('credits', 1)
                print(f"OK")
            else:
                print(f"Error: {result.get('error')}")

    # Step 4: Mobile phone finder
    print("\n" + "="*60)
    print("STEP 4: Finding mobile phone numbers")
    print("="*60)

    mobiles_found = 0
    for idx, row in df.iterrows():
        linkedin_url = row.get('linkedin_url')
        if pd.notna(linkedin_url) and linkedin_url and linkedin_url.startswith('http'):
            name = row.get('full_name', 'Unknown')
            print(f"[{idx+1}/{len(df)}] Finding mobile for: {name}...", end=" ")
            result = mobile_finder(linkedin_url)
            if 'error' not in result:
                df.at[idx, 'lm_mobile'] = result.get('lm_mobile')
                df.at[idx, 'mobile_found'] = result.get('mobile_found')
                total_credits += result.get('credits', 0)
                if result.get('mobile_found'):
                    print(f"FOUND: {result.get('lm_mobile')}")
                    mobiles_found += 1
                else:
                    print("Not found (0 credits)")
            else:
                print(f"Error: {result.get('error')}")

    print(f"\nMobile phones found: {mobiles_found}/{len(with_linkedin)}")

    # Save enriched data
    df['enriched_at'] = datetime.now().isoformat()
    df.to_csv(output_path, index=False)

    # Summary
    print("\n" + "="*60)
    print("ENRICHMENT SUMMARY")
    print("="*60)
    print(f"Total contacts: {len(df)}")
    print(f"Total LeadMagic credits used: {total_credits:.2f}")

    validated = df['email_validated'].sum()
    deliverable = df['email_is_deliverable'].sum()
    found_new = df['lm_email'].notna().sum()
    with_mobile = df['lm_mobile'].notna().sum()

    print(f"\nEmail validation:")
    print(f"  - Validated: {validated}")
    print(f"  - Deliverable: {deliverable}")
    print(f"  - New emails found: {found_new}")
    print(f"\nMobile phones found: {with_mobile}")
    print(f"\nSaved to: {output_path}")

    return df


if __name__ == "__main__":
    if not LEADMAGIC_API_KEY:
        print("Error: LEADMAGIC_API_KEY not set. Add it to your .env file.")
        exit(1)

    print("LeadMagic Enrichment — Lead Prospector Plugin")
    print(f"API Key: {LEADMAGIC_API_KEY[:8]}...{LEADMAGIC_API_KEY[-4:]}")
    print("\nReady. Import this module or use prospect_pipeline.py to run.")
