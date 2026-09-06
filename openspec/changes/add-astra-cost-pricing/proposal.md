# Add Astra cost pricing

## Why
Recorded GPT-6 Astra requests have no matching price entry, so their token usage contributes no estimated API cost.

## What Changes
- Recognize the canonical Astra model and its suffixed aliases.
- Apply published Standard, Flex, and Fast/Priority rates, including long-context pricing.
- Keep existing model rates and stored historical costs unchanged.

## Impact
- Affected spec: api-keys.
- Affected code: app/core/usage/pricing.py and focused pricing tests.
- No runtime restart, native build, database migration, or historical backfill.
