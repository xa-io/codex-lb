## Implementation
- [x] Increase preferred native client width and constrain initial geometry to the work area.
- [x] Validate the source diff and strict OpenSpec change.

Validation: git diff --check and strict change validation passed; all 14 existing native source tests passed. Native compilation and visual acceptance remain operator-owned. No build or process restart was run.

## Operator acceptance
- [ ] Rebuild after CLI sessions finish and verify the opening width visually at the operator's display scaling.
