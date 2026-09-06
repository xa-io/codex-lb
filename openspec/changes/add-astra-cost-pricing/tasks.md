## Implementation
- [x] Add Astra rates and scoped Priority long-context support.
- [x] Add regression coverage for aliases, context boundary, tier rates, and aggregate costs.
- [x] Run focused pricing and native source tests, lint, and strict change validation.

Validation: 18 new pricing cases failed before the implementation. Final focused run passed 110 tests across pricing, usage-summary integration, request-log repository, and XA native source tests. Ruff and strict validation of this change passed. Tests used temporary data directories; no live database backfill was performed.

## Operator acceptance
- [ ] Operator rebuilds and restarts after CLI sessions finish; verify newly completed Astra requests show estimated cost.
