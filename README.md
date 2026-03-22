# Lead Prospector — Claude Code Plugin

B2B lead qualification and enrichment pipeline. Claude researches companies, Apollo finds contacts, LeadMagic verifies and enriches. Replaces Firecrawl + OpenAI with Claude-native research.

## What It Does

1. **Qualify** — Claude researches companies via web search to determine ICP fit
2. **Search** — Apollo finds decision-maker contacts at qualified companies (FREE)
3. **Reveal** — Apollo reveals contact details: email, phone, LinkedIn (1 credit/contact)
4. **Enrich** — LeadMagic validates emails, finds missing emails, enriches LinkedIn profiles, finds mobile phones and personal emails
5. **Final** — Generates clean CSV with SDR context for cold outreach

## Installation

### Prerequisites

- Python 3.8+
- `pip install requests pandas python-dotenv`
- Apollo.io API key
- LeadMagic API key

### Setup

1. Install the plugin in Claude Code
2. Create a `.env` file in your project directory:
   ```
   APOLLO_API_KEY=your_apollo_key
   LEADMAGIC_API_KEY=your_leadmagic_key
   ```
3. (Optional) Create `.claude/lead-prospector.local.md` to customize your ICP — see `skills/prospect/references/config-template.md`

## Usage

```
/prospect all --file companies.csv --batch us-mi-1
/prospect qualify --file companies.csv --batch us-mi-1
/prospect search --batch us-mi-1
/prospect reveal --batch us-mi-1
/prospect enrich --batch us-mi-1
/prospect status
```

### Input Modes

**CSV Input** — provide a list of companies:
```
/prospect all --file /path/to/companies.csv --batch my-batch
```
CSV requires: `company_name`, `website` (or `domain`)

**Discovery Mode** — find companies via Apollo:
```
/prospect all --discover --state MI --industry "food manufacturing" --batch us-mi-1
```

## Configuration

The plugin ships with a default ICP for Food & Beverage Manufacturing. To customize:

1. Copy the config template: `skills/prospect/references/config-template.md`
2. Save as `.claude/lead-prospector.local.md` in your project
3. Edit your ICP criteria, target titles, and settings

If no config file exists, the plugin asks at each step (progressive disclosure).

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

## Output

All outputs go to `output/prospect/` in the working directory:

```
output/prospect/
├── {batch}_companies_input.csv          # Input companies
├── {batch}_companies_qualified.csv      # After Claude qualification
├── {batch}_contacts_search.csv          # Apollo search results
├── {batch}_contacts_revealed.csv        # Revealed contacts
├── {batch}_contacts_enriched.csv        # Fully enriched contacts
└── {batch}_final.csv                    # Clean final output
```

## License

MIT
