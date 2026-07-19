# ARCHITECTURE_PROMPT.md — First Codex Architecture Task

Read `PROJECT_SPEC.md` and `AGENTS.md` completely before answering.

This is a new hackathon repository. No implementation exists yet.

Your task is to design the architecture for the MVP. Do not write code, create files, install dependencies, or modify the repository during this task.

## Product to design

Design a Python 3.11+ MCP server that:

- uses the official MCP Python SDK
- supports SQLite as the only implemented database engine for the MVP
- isolates database access behind a `DatabaseConnector` abstraction
- does not prevent future PostgreSQL, Snowflake, Databricks SQL, MySQL, or SQL Server/Fabric connectors
- uses bounded pandas DataFrames for profiling and statistical analysis
- uses SciPy and statsmodels for test statistics and p-values
- uses Pydantic for structured public inputs and outputs where compatible with the MCP SDK
- uses pytest with deterministic seeded SQLite fixtures
- is read-only
- does not expose arbitrary SQL
- does not make server-side LLM calls

## Exact MVP tool surface

Expose exactly these three MCP tools:

### 1. `list_tables`

Lists tables available through the configured SQLite connection.

It must not expose credentials or a complete connection URL.

### 2. `profile_table`

Profiles one table using deterministic rule-based logic.

It should return bounded, structured metadata including:

- row and null information
- cardinality
- useful numeric summaries
- limited categorical frequencies
- safe example values
- suggested statistical roles
- extraction, sampling, and truncation metadata

Supported suggested roles:

- `continuous_outcome`
- `binary_outcome`
- `grouping_variable`
- `identifier`
- `datetime`
- `other`

The classification must use documented heuristics such as type, cardinality, uniqueness ratio, and null rate. It must not call an LLM.

### 3. `run_test`

Runs exactly one of these tests:

- `welch_t_test`
- `two_proportion_z_test`

The result must be structured and include, where applicable:

- test identifier and name
- null and alternative hypotheses
- statistic
- p-value
- alpha
- significance flag
- group summaries
- sample sizes
- effect-size name and value
- assumptions
- warnings
- rows examined
- null or invalid rows excluded
- extraction limit
- sampling or truncation metadata

For the two-proportion z-test, require the caller to provide the binary success value explicitly. Do not infer it.

## Required architecture properties

The proposed design must make these boundaries clear:

1. MCP transport and tool registration
2. configuration and environment loading
3. connector interface
4. SQLite connector
5. identifier validation
6. bounded data extraction
7. deterministic profiling
8. statistical calculations
9. Pydantic request and response models
10. domain exceptions and MCP error translation
11. fixture generation
12. unit and integration testing

Statistical modules must not import database drivers or MCP server objects.

Connector modules must not contain statistical calculations or test-selection logic.

Tool handlers should orchestrate services rather than contain substantial implementation logic.

The architecture must support future connectors without requiring changes to the statistical modules. It is acceptable for a future connector to require registration, optional dependencies, configuration, tests, and documentation.

## Questions you must resolve or flag

During the design, identify and discuss:

- whether to use synchronous or asynchronous connector interfaces for the SQLite MVP
- how the MCP SDK's preferred server API affects module structure
- how connection configuration should be represented without exposing secrets
- how table and column identifiers will be validated
- how hard extraction limits will be configured and enforced
- whether the MVP will use deterministic first-N-row limiting or reproducible sampling
- how null and invalid values will be counted and reported
- how the server will distinguish successful tool results from structured tool errors
- which effect size should accompany Welch's t-test
- which effect size should accompany the two-proportion z-test
- what minimum sample-size or approximation checks the proportion test should enforce
- how the seeded demo data will include both continuous and binary outcomes
- how the package will be launched locally through stdio
- which linting and type-checking tools are worth including without overbuilding the hackathon MVP

Do not silently decide an ambiguous item when multiple reasonable choices have meaningful tradeoffs. State the recommendation and rationale.

## Required response format

Return the architecture proposal in the following order.

### 1. Understanding of the product

Explain the product and its MVP boundary in plain English. Keep this section concise.

### 2. Contradictions, omissions, and risks

Identify any requirement that is contradictory, incomplete, statistically risky, insecure, or likely to cause rework. For each item, recommend a resolution.

### 3. Architecture decisions

List the major decisions and explain the tradeoff behind each one. Include recommendations for all questions listed above.

### 4. Proposed repository tree

Show the complete initial folder tree.

Do not create placeholder modules that have no clear near-term responsibility.

### 5. Module responsibilities

Describe the responsibility of every proposed module in one sentence.

If a module requires more than one clear responsibility, flag it for splitting.

### 6. Public interfaces

Sketch the expected public Python interfaces without implementing them. Include:

- the `DatabaseConnector` protocol or abstract base class
- bounded extraction request and metadata concepts
- tool input and output model names
- statistical test function signatures
- domain exception categories

Use concise pseudocode or signatures only. Do not provide full implementations.

### 7. Dependency proposal

List runtime and development dependencies separately.

For each package, state:

- why it is needed
- whether it is required for the MVP
- any concern about overlap or unnecessary complexity

Prefer `pyproject.toml` and an editable installation workflow unless there is a strong reason not to.

### 8. Implementation sequence

Propose small milestones in the order they should be built and tested.

The sequence should produce one complete vertical slice early rather than many empty abstractions.

For each milestone, include:

- behavior delivered
- files likely to change
- tests required
- exit criteria

### 9. Deliberately postponed work

List what should be deferred and explain why deferring it will not force a rewrite of the MVP.

### 10. First implementation prompt

End with a proposed follow-up prompt that would instruct Codex to create only the approved repository scaffold and first minimal validation tests.

## Final restrictions

Do not:

- write code
- create or edit files
- install packages
- initialize a virtual environment
- implement extra tools
- add extra statistical tests
- add extra database connectors
- add an LLM dependency
- introduce a web UI
- introduce deployment infrastructure

Stop after delivering the architecture proposal.
