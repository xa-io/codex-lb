# Add GPT-6.1 Sol cost pricing

## Why

GPT-6.1 Sol requests currently have no matching price entry, so their recorded token usage contributes no estimated API cost.

## What Changes

- Recognize the canonical `gpt-6.1-sol` model, case variants, and suffixed aliases.
- Apply the published Standard, Flex, and Fast/Priority input, cached-input, and output rates, including long-context pricing above 272,000 total input tokens.
- Include those estimates in new persisted request logs, request-log cost breakdowns, and usage summaries using the existing calculation path.

## Impact

- Affected spec: api-keys.
- Affected code: app/core/usage/pricing.py and pricing/usage-summary tests.
- Existing model rates and stored historical costs remain unchanged; no database migration or historical backfill is required.
- Native rebuild and live acceptance remain operator-owned while the authenticated app is running.
