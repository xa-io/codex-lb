## ADDED Requirements

### Requirement: GPT-6 Astra estimated cost pricing is recognized
The system MUST recognize `gpt-6-astra` and suffixed Astra aliases when estimating request costs. Standard rates per million tokens SHALL be USD 10 input, USD 1 cached input, and USD 50 output. Flex SHALL use half those rates; Fast and Priority SHALL use twice those rates. Above 272,000 total input tokens, input and cached-input rates SHALL double and output rates SHALL increase by 50 percent for the full request, including Flex and Fast/Priority. Existing model pricing SHALL remain unchanged.

#### Scenario: Cached input is discounted
- **WHEN** a Standard Astra request uses 200,000 input tokens, including 100,000 cached tokens, and 10,000 output tokens
- **THEN** its estimated cost is USD 1.60

#### Scenario: Priority long-context pricing applies
- **WHEN** a Priority Astra request uses 300,000 input tokens, including 200,000 cached tokens, and 10,000 output tokens
- **THEN** its estimated cost is USD 6.30

#### Scenario: Threshold is exclusive
- **WHEN** an Astra request has exactly 272,000 input tokens
- **THEN** short-context pricing applies

#### Scenario: Snapshot alias resolves
- **WHEN** a suffixed `gpt-6-astra` model name is priced
- **THEN** it uses the canonical Astra entry
