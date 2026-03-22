# Lead Prospector Configuration Template

Copy this file to `.claude/lead-prospector.local.md` in your project and customize.

---

## API Keys

Set these as environment variables in your `.env` file:
```
APOLLO_API_KEY=your_apollo_key
LEADMAGIC_API_KEY=your_leadmagic_key
```

## Target Country
United States

## Target Titles
- Plant Manager
- Production Manager
- VP Operations / Director of Operations
- Operations Manager
- General Manager
- COO / Chief Operating Officer
- Manufacturing Manager
- Director of Manufacturing

## ICP — Qualification Criteria

### QUALIFIED (target)
- [Describe your ideal customer]
- [Industry specifics]
- [Company size range]

### NOT QUALIFIED (skip)
- [What to exclude]
- [Industries to skip]

### KEY JUDGMENT RULE
[Any special rules for borderline cases]

## Enrichment Settings

### Email Validation
Enabled: yes

### Email Finder (for missing emails)
Enabled: yes

### Personal Email Finder
Enabled: yes

### LinkedIn Profile Enrichment
Enabled: yes

### Mobile Phone Finder
Enabled: yes

### Role Finder (Apollo backup)
Enabled: on-demand
