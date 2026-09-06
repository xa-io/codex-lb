# Pricing evidence and limits

Verified on 2026-09-06:
- https://developers.openai.com/api/docs/models/gpt-6-astra
- https://developers.openai.com/api/docs/pricing

USD per million tokens: Standard input 10, cached input 1, output 50; Flex is half; Fast/Priority is double. Above 272,000 input tokens, input/cache rates double and output rates multiply by 1.5 for the entire request. For example, 300,000 input tokens including 200,000 cached tokens and 10,000 output tokens cost 3.15 Standard, 1.575 Flex, or 6.30 Fast/Priority.

The published cache-write rate is 12.50 Standard before tier/context adjustments. Existing recorded usage does not distinguish cache-write tokens from other input tokens. This patch therefore retains the existing input/cached-input/output estimate and does not invent a cache-write count. It does not implement Batch billing or regional uplifts.

Explicit optional Priority long-context rates allow Astra's documented behavior without repricing other models. Compare this compatibility patch with upstream Astra support at the next sync.

Stored historical null costs are not rewritten. New completed requests use the new prices after the operator rebuilds and restarts. No live app or database is modified during implementation.
