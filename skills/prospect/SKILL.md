---
name: prospect
description: "Run the lead prospecting pipeline: qualify companies, find contacts via Apollo, enrich via LeadMagic. Use when user says /prospect, 'find leads', 'qualify companies', 'enrich contacts', 'prospect batch', or 'run pipeline'."
argument-hint: "[step] [options] — e.g., /prospect all --file companies.csv --batch us-1"
allowed-tools: ["Read", "Write", "Edit", "Bash", "Glob", "Grep", "WebFetch", "WebSearch", "Agent"]
---

# Lead Prospector Pipeline

Run a complete B2B lead qualification and enrichment pipeline. Claude researches companies (no Firecrawl/OpenAI needed), Apollo finds decision-maker contacts, LeadMagic verifies and enriches.

## Setup

Load API keys from environment or `.env` file in the working directory:

```python
from dotenv import load_dotenv
load_dotenv()
```

Required environment variables:
- `APOLLO_API_KEY` — Apollo.io API key
- `LEADMAGIC_API_KEY` — LeadMagic API key

Scripts are at: `$CLAUDE_PLUGIN_ROOT/scripts/`

## Steps

- `all` — Run complete pipeline (default)
- `qualify` — Step 1: Claude researches and qualifies companies
- `search` — Step 2: Apollo contact search (free)
- `reveal` — Step 3: Apollo contact reveal (1 credit/contact)
- `enrich` — Step 4: LeadMagic enrichment + email validation
- `status` — Show pipeline status and file counts

## Input Modes

### Mode 1: CSV Input (user has a list)
```
/prospect all --file /path/to/companies.csv --batch us-mi-1
```
CSV minimum columns: `company_name`, `website` (or `domain`)
Optional: `location`, `industry`, `size`

### Mode 2: Discovery (find companies via Apollo)
```
/prospect all --discover --state MI --industry "food manufacturing" --batch us-mi-1
```

## Options
- `--file FILE` — Input CSV path (Mode 1)
- `--discover` — Use Apollo to find companies (Mode 2)
- `--state XX` — US state or region (for discovery)
- `--industry TEXT` — Industry search term (for discovery)
- `--batch NAME` — Batch name for output files (e.g., `us-mi-1`)
- `--limit N` — Max companies to process (default: 50)

## Output Files

All outputs go to `output/prospect/` in the working directory:
```
output/prospect/
├── {batch}_companies_input.csv          # Input companies (raw)
├── {batch}_companies_qualified.csv      # After Claude qualification
├── {batch}_contacts_search.csv          # Apollo search results
├── {batch}_contacts_revealed.csv        # Revealed contacts
├── {batch}_contacts_enriched.csv        # Fully enriched contacts
└── {batch}_final.csv                    # Clean final output
```

## Credit Usage
| Service | Action | Cost |
|---------|--------|------|
| Apollo | Company Discovery | FREE |
| Apollo | Contact Search | FREE |
| Apollo | Contact Reveal | 1 credit/contact |
| LeadMagic | Email Validation | 20 per 1 credit |
| LeadMagic | Email Finder | 1 credit |
| LeadMagic | Profile Search | 1 credit |
| LeadMagic | Personal Email | 2 credits (0 if not found) |
| LeadMagic | Mobile Finder | 5 credits (0 if not found) |
| LeadMagic | Role Finder | 2 credits (0 if not found) |

## Configuration

Read user configuration from `.claude/lead-prospector.local.md` in the project directory if it exists. This file contains:
- ICP qualification criteria (what to qualify/disqualify)
- Target job titles for contact search
- Target country filter
- Any custom settings

If no config file exists, ask the user at each step (progressive disclosure).

## CRITICAL: Progressive Disclosure Pattern

**Every step MUST present its configuration to the user and wait for confirmation before executing.** This makes the pipeline flexible.

### Step 0: Discovery (if --discover)

Present to user:
> **Discovery Settings**
> - Geography: {state/region}
> - Industry: {industry}
>
> **Does this look right, or want to adjust?**

Wait for confirmation, then use Apollo or WebSearch to find companies.

### Step 1: Qualify

**BEFORE researching, present to user:**
> **Qualification Criteria**
> I'll research each company and check:
>
> **Qualify if:** [show criteria from config or defaults]
> **Disqualify if:** [show criteria from config or defaults]
>
> **Companies to process:** {N}
>
> **Does this look right? Want to change anything?**

Wait for confirmation. Then for each company:
1. **WebSearch** the company name + industry + location
2. **WebFetch** their website — check homepage, about, products pages
3. **Evaluate against ICP criteria**
4. **Score**: QUALIFIED / NOT_QUALIFIED / NEEDS_REVIEW
5. **Write qualification reason** (1-2 sentence summary)
6. **Write SDR context** — structured bullet points with everything useful for a cold call:
   - Products: what they make, key product lines
   - Scale: revenue, employees, production volume, # of plants
   - Locations: plant/facility cities and states
   - Certifications: industry certifications
   - Recent news: acquisitions, expansions, leadership changes
   - Pain signals: hiring patterns, manual processes, recalls
   - Growth signals: new markets, facility investments, partnerships
   - Source and date of research

Save to `output/prospect/{batch}_companies_qualified.csv` with columns:
```
company_name, domain, location, industry, employee_estimate,
qualification_status, qualification_reason, company_type,
certifications, is_copacker, pain_points, growth_signals,
sdr_context, sdr_context_date, qualified_at
```

**Process in mini-batches of 5-10, save progress after each.**

### Step 2: Search

**Present to user:**
> **Contact Search Settings**
> - Companies: {N} qualified
> - Titles: [list from config or defaults]
> - Max per company: 5
> - **Cost: FREE**
>
> **Want to add/remove any titles?**

Wait for confirmation. Then run:
```bash
python3 $CLAUDE_PLUGIN_ROOT/scripts/prospect_pipeline.py search --batch {BATCH}
```

### Step 3: Reveal

**Present to user:**
> **Reveal — Credit Confirmation**
> - Contacts to reveal: {N}
> - **Cost: ~{N} Apollo credits**
>
> **Continue? (This costs credits)**

**Do NOT proceed without explicit confirmation.**

```bash
python3 $CLAUDE_PLUGIN_ROOT/scripts/prospect_pipeline.py reveal --batch {BATCH}
```

### Step 4: Enrich

**Present to user:**
> **Enrichment — Credit Estimate**
> - Email validation: {X} emails (cheap)
> - Email finder: {Y} missing (1 credit each)
> - LinkedIn enrichment: {Z} profiles (1 credit each)
> - Personal email: {Z} profiles (2 credits, free if not found)
> - Mobile finder: {Z} profiles (5 credits, free if not found)
> - **Total: ~{total} LeadMagic credits**
>
> **Want to skip any sub-steps?**

Wait for confirmation.

```bash
python3 $CLAUDE_PLUGIN_ROOT/scripts/prospect_pipeline.py enrich --batch {BATCH}
```

### Step 5: Final Output

Auto-generate after enrichment:
```bash
python3 $CLAUDE_PLUGIN_ROOT/scripts/prospect_pipeline.py final --batch {BATCH}
```

Filters by target country (from config). Shows summary.

### For `status`
```bash
python3 $CLAUDE_PLUGIN_ROOT/scripts/prospect_pipeline.py status [--batch {BATCH}]
```

### For `all`
Run steps 0-5 sequentially with progressive disclosure at every gate. **Never skip a confirmation gate.**
