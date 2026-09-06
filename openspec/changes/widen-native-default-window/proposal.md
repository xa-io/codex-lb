# Widen the native default window

## Why
The native 1280-pixel client width constrains the dashboard's 1500 CSS-pixel page layout and requires manual widening.

## What Changes
- Request a 1525 CSS-pixel default client width with system DPI scaling.
- Retain the existing 840-pixel preferred client height.
- Center and clamp the outer window within the primary display work area.

## Impact
Only native initial window geometry changes. Dashboard column preferences, frontend layout, backend ownership, and running processes are unchanged.
