## ADDED Requirements

### Requirement: Default desktop width accommodates the dashboard layout
The native launcher SHALL request a default client width equivalent to 1525 CSS pixels at the system DPI. It SHALL retain the existing preferred client height of 840 physical pixels. The initial outer window SHALL be centered and constrained to the primary display work area.

#### Scenario: Display has sufficient room
- **WHEN** the desktop application starts on a sufficiently wide display
- **THEN** its preferred client width is 1525 pixels at 100 percent scaling, or the DPI-scaled equivalent
- **AND** the window is centered within the work area

#### Scenario: Display is narrower than the preferred window
- **WHEN** the preferred outer window exceeds the available work area
- **THEN** its initial dimensions are limited to the work area
