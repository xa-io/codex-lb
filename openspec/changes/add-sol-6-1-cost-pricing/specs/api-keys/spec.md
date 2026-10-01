## ADDED Requirements

### Requirement: GPT-6.1 Sol estimated cost pricing is recognized

The system MUST recognize `gpt-6.1-sol`, case variants, and suffixed aliases when estimating request costs. Standard rates per million tokens SHALL be USD 2 input, USD 0.10 cached input, and USD 10 output. Flex SHALL use half those rates; Fast and Priority SHALL use twice those rates. Above 272,000 total input tokens, input and cached-input rates SHALL double and output rates SHALL increase by 50 percent for the full request, including Flex and Fast/Priority. New persisted request costs, request-log cost breakdowns, and usage-summary totals MUST use the existing pricing path. Existing model pricing and stored historical costs SHALL remain unchanged.

#### Scenario: Cached input is discounted

- **WHEN** a Standard GPT-6.1 Sol request uses 200,000 input tokens, including 100,000 cached tokens, and 10,000 output tokens
- **THEN** its estimated cost is USD 0.31

#### Scenario: Priority long-context pricing applies

- **WHEN** a Priority GPT-6.1 Sol request uses 300,000 input tokens, including 200,000 cached tokens, and 10,000 output tokens
- **THEN** its estimated cost is USD 1.18

#### Scenario: Flex long-context pricing applies

- **WHEN** the same long-context request uses Flex
- **THEN** its estimated cost is USD 0.295

#### Scenario: Threshold is exclusive and includes cached input

- **WHEN** a Standard GPT-6.1 Sol request uses exactly 272,000 input tokens, including 100,000 cached tokens, and 10,000 output tokens
- **THEN** its estimated cost is USD 0.454
- **WHEN** the total input increases to 272,001 tokens with the same cached input and output
- **THEN** its estimated cost is USD 0.858004

#### Scenario: Aliases resolve to the canonical entry

- **WHEN** an uppercase or suffixed `gpt-6.1-sol` model name is priced
- **THEN** it uses the canonical `gpt-6.1-sol` entry and contributes to aggregate estimated cost

#### Scenario: Completed usage is persisted and displayed

- **WHEN** a newly completed GPT-6.1 Sol request is recorded
- **THEN** its persisted cost and displayed input, cached-input, output, and total cost reflect its billable service tier
- **AND** its persisted total contributes to the usage summary
