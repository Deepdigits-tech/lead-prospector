#!/usr/bin/env python3
"""
Apollo.io Contact Finder — Lead Prospector Plugin

Finds decision-maker contacts at qualified companies using Apollo API.
Part of the lead-prospector pipeline.

Requires: APOLLO_API_KEY environment variable
"""

import os
import json
import requests
import pandas as pd
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables from .env in working directory
load_dotenv()

APOLLO_API_KEY = os.getenv("APOLLO_API_KEY")
APOLLO_BASE_URL = "https://api.apollo.io/v1"

# Default target titles — can be overridden by config
TARGET_TITLES = [
    "Plant Manager",
    "General Manager",
    "Operations Manager",
    "Production Manager",
    "Manufacturing Manager",
    "COO",
    "Chief Operations Officer",
    "VP Operations",
    "VP of Operations",
    "Director of Operations",
    "Director of Manufacturing",
    "VP Manufacturing",
    "Continuous Improvement",
    "Continuous Improvement Manager",
]


def search_people_by_company(company_name: str, domain: str = None, limit: int = 10, titles: list = None) -> dict:
    """
    Search for people at a company using Apollo API.

    Args:
        company_name: Name of the company
        domain: Company website domain (optional but recommended)
        limit: Max number of results
        titles: Custom list of job titles (defaults to TARGET_TITLES)

    Returns:
        API response with people data
    """
    url = f"{APOLLO_BASE_URL}/mixed_people/api_search"

    headers = {
        "Content-Type": "application/json",
        "Cache-Control": "no-cache",
        "X-Api-Key": APOLLO_API_KEY,
    }

    search_titles = titles or TARGET_TITLES

    payload = {
        "per_page": limit,
        "person_titles": search_titles,
    }

    # Add company filter
    if domain:
        payload["q_organization_domains"] = domain
    else:
        payload["q_organization_name"] = company_name

    try:
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error searching Apollo: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"Response: {e.response.text}")
        return {"error": str(e), "people": []}


def enrich_person(person_id: str) -> dict:
    """
    Get enriched data for a specific person (reveals email).
    Uses 1 credit per enrichment.
    """
    url = f"{APOLLO_BASE_URL}/people/match"

    headers = {
        "Content-Type": "application/json",
        "Cache-Control": "no-cache",
        "X-Api-Key": APOLLO_API_KEY,
    }

    payload = {
        "id": person_id,
        "reveal_personal_emails": False,
        "reveal_phone_number": True,
    }

    try:
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error enriching person: {e}")
        return {"error": str(e)}


def get_organization_contacts(domain: str) -> dict:
    """
    Alternative: Search for organization and get contacts.
    """
    url = f"{APOLLO_BASE_URL}/organizations/enrich"

    headers = {
        "Content-Type": "application/json",
        "Cache-Control": "no-cache",
        "X-Api-Key": APOLLO_API_KEY,
    }

    payload = {
        "domain": domain,
    }

    try:
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error: {e}")
        return {"error": str(e)}


def format_contact(person: dict, company_name: str) -> dict:
    """Format a person record into a contact dict."""
    org = person.get("organization", {}) or {}

    return {
        "person_id": person.get("id", ""),
        "first_name": person.get("first_name", ""),
        "last_name": person.get("last_name", person.get("last_name_obfuscated", "")),
        "full_name": f"{person.get('first_name', '')} {person.get('last_name', person.get('last_name_obfuscated', ''))}".strip(),
        "title": person.get("title", ""),
        "email": person.get("email", ""),
        "email_status": person.get("email_status", ""),
        "has_email": person.get("has_email", False),
        "has_phone": person.get("has_direct_phone", False),
        "phone": person.get("phone_numbers", [{}])[0].get("number", "") if person.get("phone_numbers") else "",
        "linkedin_url": person.get("linkedin_url", ""),
        "company_name": org.get("name", company_name),
        "company_domain": org.get("primary_domain", org.get("website_url", "")),
        "seniority": person.get("seniority", ""),
        "departments": ", ".join(person.get("departments", [])) if person.get("departments") else "",
        "city": person.get("city", ""),
        "state": person.get("state", ""),
        "country": person.get("country", ""),
        "needs_enrichment": True,
    }


def reveal_contact(person_id: str) -> dict:
    """
    Reveal full contact details using Apollo credits.
    Uses 1 credit per contact.

    Returns full name, email, phone, LinkedIn URL.
    """
    url = f"{APOLLO_BASE_URL}/people/bulk_match"

    headers = {
        "Content-Type": "application/json",
        "Cache-Control": "no-cache",
        "X-Api-Key": APOLLO_API_KEY,
    }

    payload = {
        "details": [{"id": person_id}]
    }

    try:
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        data = response.json()

        matches = data.get("matches", [])
        if matches:
            return {"person": matches[0], "credits_consumed": data.get("credits_consumed", 1)}
        return {"error": "No match found"}
    except requests.exceptions.RequestException as e:
        print(f"    Error revealing contact: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"    Response: {e.response.text[:200]}")
        return {"error": str(e)}


def format_revealed_contact(person: dict, company_name: str) -> dict:
    """Format a revealed person record with full details."""
    org = person.get("organization", {}) or {}

    # Get phone numbers
    phones = person.get("phone_numbers", [])
    direct_phone = ""
    mobile_phone = ""
    for phone in phones:
        if phone.get("type") == "direct":
            direct_phone = phone.get("number", "")
        elif phone.get("type") == "mobile":
            mobile_phone = phone.get("number", "")

    # If no personal phone, use company phone
    company_phone = org.get("phone", "") or ""
    if org.get("primary_phone"):
        company_phone = org.get("primary_phone", {}).get("number", "")

    return {
        "person_id": person.get("id", ""),
        "first_name": person.get("first_name", ""),
        "last_name": person.get("last_name", ""),
        "full_name": person.get("name", f"{person.get('first_name', '')} {person.get('last_name', '')}").strip(),
        "title": person.get("title", ""),
        "headline": person.get("headline", ""),
        "email": person.get("email", ""),
        "email_status": person.get("email_status", ""),
        "direct_phone": direct_phone,
        "mobile_phone": mobile_phone,
        "company_phone": company_phone,
        "linkedin_url": person.get("linkedin_url", ""),
        "company_name": org.get("name", company_name),
        "company_domain": org.get("primary_domain", ""),
        "company_linkedin": org.get("linkedin_url", ""),
        "seniority": person.get("seniority", ""),
        "departments": ", ".join(person.get("departments", [])) if person.get("departments") else "",
        "city": person.get("city", ""),
        "state": person.get("state", ""),
        "country": person.get("country", ""),
        "revealed": True,
    }


def find_contacts_for_companies(companies_df: pd.DataFrame, output_path: str = None, limit_per_company: int = 5, reveal: bool = False, titles: list = None) -> pd.DataFrame:
    """
    Find contacts for a list of companies.

    Args:
        companies_df: DataFrame with company_name and domain/website columns
        output_path: Path to save results
        limit_per_company: Max contacts per company
        reveal: If True, use Apollo credits to reveal full contact details
        titles: Custom title list (defaults to TARGET_TITLES)

    Returns:
        DataFrame with all contacts found
    """
    all_contacts = []
    credits_used = 0

    for idx, row in companies_df.iterrows():
        company_name = row.get("company_name", "")
        domain = row.get("domain", row.get("website", ""))

        # Clean domain
        if domain:
            domain = domain.replace("www.", "").replace("https://", "").replace("http://", "").strip("/")

        print(f"\n[{idx+1}/{len(companies_df)}] Searching: {company_name} ({domain})")

        result = search_people_by_company(company_name, domain, limit=limit_per_company, titles=titles)

        people = result.get("people", [])
        print(f"  Found {len(people)} contacts")

        for person in people:
            if reveal and person.get("id"):
                print(f"    Revealing: {person.get('first_name', '')} {person.get('title', '')}...")
                revealed = reveal_contact(person.get("id"))

                if "error" not in revealed and revealed.get("person"):
                    contact = format_revealed_contact(revealed["person"], company_name)
                    credits_used += 1
                    print(f"      -> {contact['full_name']} | {contact['email']} | {contact['direct_phone'] or contact['mobile_phone'] or 'No phone'}")
                else:
                    contact = format_contact(person, company_name)
                    print(f"      -> Failed to reveal, using basic info")
            else:
                contact = format_contact(person, company_name)
                print(f"    - {contact['full_name']} | {contact['title']}")

            all_contacts.append(contact)

        if not people:
            print(f"  No contacts found with target titles")

    # Create DataFrame
    contacts_df = pd.DataFrame(all_contacts)

    # Save if output path provided
    if output_path and len(contacts_df) > 0:
        contacts_df.to_csv(output_path, index=False)
        print(f"\nSaved {len(contacts_df)} contacts to {output_path}")

    if reveal:
        print(f"\nTotal Apollo credits used: {credits_used}")

    return contacts_df


if __name__ == "__main__":
    if not APOLLO_API_KEY:
        print("Error: APOLLO_API_KEY not set. Add it to your .env file.")
        exit(1)

    print("Apollo Contact Finder — Lead Prospector Plugin")
    print(f"API Key: {APOLLO_API_KEY[:8]}...{APOLLO_API_KEY[-4:]}")
    print(f"Target titles: {len(TARGET_TITLES)}")
    print("\nReady. Import this module or use prospect_pipeline.py to run.")
