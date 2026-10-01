# GPT-6.1 Sol pricing evidence and limits

Verified on 2026-09-30 from the official model and pricing pages:

- https://developers.openai.com/api/docs/models/gpt-6.1-sol
- https://developers.openai.com/api/docs/pricing

Prices are USD per million tokens:

| Tier | Input | Cached input | Output | Long-context input | Long-context cached input | Long-context output |
| --- | --- | --- | --- | --- | --- | --- |
| Standard/default | 2.00 | 0.10 | 10.00 | 4.00 | 0.20 | 15.00 |
| Flex | 1.00 | 0.05 | 5.00 | 2.00 | 0.10 | 7.50 |
| Fast/Priority | 4.00 | 0.20 | 20.00 | 8.00 | 0.40 | 30.00 |

Long-context rates apply to the full request only above 272,000 input tokens, including cached input in the threshold. Exactly 272,000 input tokens retains short-context pricing. For 300,000 input tokens including 200,000 cached tokens and 10,000 output tokens, the estimates are USD 0.59 Standard, 0.295 Flex, and 1.18 Fast/Priority.

The published short-context cache-write rate is USD 2.50 Standard per million tokens. Recorded usage has no separate cache-write token count, so the app continues estimating from input, cached input, and output without inventing that count. Batch pricing and regional processing premiums also remain outside the existing recorded-usage contract.

The fetched canonical upstream built-in table and bundled pricing snapshot also lack this model; in-memory resolution of the canonical, uppercase, and suffixed names returns no price. Upstream now also supports independently refreshed third-party catalogs, whose live contents were not audited. The older Astra compatibility checker reports that upstream requires manual review because the pricing dependencies changed. This task does not synchronize those upstream changes. The XA addition reuses existing tier selection and optional Priority long-context fields; it introduces no separate calculation path or required configuration.

Newly completed requests use these rates after the operator rebuilds and restarts. Stored historical costs are not rewritten. These are API-equivalent estimates and do not represent ChatGPT subscription charges.
