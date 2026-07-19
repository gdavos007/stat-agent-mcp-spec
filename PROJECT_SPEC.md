# PROJECT_SPEC.md — Database-Agnostic Statistical Testing MCP Server

## 1. Problem

Organizations often need to answer questions such as:

- Did one branch produce a meaningfully different average outcome than another?
- Did variant B convert at a higher rate than variant A?
- Is an observed difference likely to reflect a real signal or random variation?

Today, answering these questions usually requires a data scientist or an analyst who can extract the data, reshape it, select an appropriate statistical test, run the test correctly, and interpret the result.

Existing conversational statistical-agent examples often tie the analysis to one database platform and implement statistical calculations directly in SQL. That creates two problems:

1. The solution is difficult to reuse across PostgreSQL, Snowflake, Databricks, MySQL, SQL Server, Fabric, and other tabular systems.
2. Hand-written SQL implementations may rely on approximations when maintained Python libraries already provide tested statistical distributions and procedures.

## 2. Product vision

Build a read-only, database-agnostic MCP server that allows an MCP-compatible AI client to:

1. Discover available tables.
2. Inspect and profile a selected table.
3. Select columns relevant to a statistical question.
4. Run a statistically valid test in Python.
5. Receive a structured, auditable result that the host AI can explain to the user.

The database supplies the data. Python performs the statistical calculation. MCP exposes the capabilities to compatible AI clients.

## 3. Core differentiators

### Database-agnostic connector boundary

Database access is isolated behind a `DatabaseConnector` interface. The statistical layer receives pandas objects and does not know which database supplied the data.

The hackathon MVP supports SQLite, but the design must allow future connectors for PostgreSQL, Snowflake, Databricks SQL, MySQL, and Microsoft SQL Server/Fabric without rewriting the statistical test modules.

### Correct statistical computation in Python

Hypothesis-test statistics and p-values are calculated with maintained statistical libraries such as `scipy.stats` and `statsmodels`.

The server must not replace an available library implementation with a custom CDF approximation, a hand-derived p-value formula, or an LLM-generated calculation.

### Reusable MCP interface

The server exposes deterministic tools that can be called by different MCP-compatible hosts. The host model decides which tools to call and how to explain the returned structured result.

The server itself does not need an LLM call for the MVP. This keeps the statistical output reproducible, testable, and independent of model sampling behavior.

### Structured and auditable outputs

Every public tool returns structured data. Statistical results include the test used, test statistic, p-value, sample sizes, effect size, assumptions, warnings, excluded rows, and whether sampling or truncation occurred.

## 4. Target users

The primary users are analysts, operations teams, and business stakeholders who have access to organizational data but do not have a dedicated statistics or data-science resource.

Representative questions include:

- Did loan approval rates differ between two branches?
- Did a campaign increase conversion?
- Did two member groups have different average balances?
- Is the observed difference large enough to investigate further?

The system should help users perform valid statistical analysis. It must not imply that statistical significance proves causality or business importance.

## 5. Hackathon MVP scope

### In scope

- Python 3.11 or newer.
- Official MCP Python SDK.
- SQLite as the single implemented database engine.
- A connector abstraction that does not preclude future database engines.
- pandas for bounded in-memory analysis.
- SciPy and statsmodels for statistical computation.
- Pydantic models for public tool inputs and outputs.
- pytest unit and integration tests.
- A reproducible seeded SQLite demonstration database.
- Exactly three MCP tools:
  1. `list_tables`
  2. `profile_table`
  3. `run_test`
- Exactly two statistical tests:
  1. Welch's independent two-sample t-test
  2. Two-proportion z-test

### Explicitly out of scope for the MVP

- Arbitrary SQL supplied by a user or host model.
- Database writes of any kind.
- PostgreSQL, Snowflake, Databricks, MySQL, or SQL Server connectors.
- Cross-database or multi-schema discovery.
- Natural-language-to-SQL generation.
- Server-side LLM calls.
- Automatic causal inference.
- ANOVA, chi-square, Mann-Whitney U, regression, paired tests, and other additional procedures.
- A server-side `recommend_tests` tool.
- A server-side `explain_result` tool.
- Loading an entire unbounded table into memory.

These features may be added later, but the MVP architecture must not require their implementation now.

## 6. MCP tools

### 6.1 `list_tables`

Purpose: list the tables available through the configured SQLite connection.

The result should include:

- connection name or safe identifier
- table names
- table type when available
- non-secret metadata useful to the client

The result must never include passwords, tokens, or a complete connection string.

### 6.2 `profile_table`

Purpose: inspect a table and return deterministic metadata that helps the host model understand which columns may be useful for analysis.

For every column, return where applicable:

- column name
- database type
- inferred pandas type
- row count considered
- non-null count
- null count and null percentage
- unique count
- example values with safe limits
- numeric minimum, maximum, mean, median, and standard deviation
- top categorical values with counts
- a deterministic suggested role

Supported suggested roles:

- `continuous_outcome`
- `binary_outcome`
- `grouping_variable`
- `identifier`
- `datetime`
- `other`

Role classification must use documented rule-based heuristics such as data type, cardinality, uniqueness ratio, and null rate. It must not call an LLM.

The output must state when the profile is based on a limited or sampled set of rows.

### 6.3 `run_test`

Purpose: run one approved statistical test against explicitly selected columns and group values.

Supported test identifiers:

- `welch_t_test`
- `two_proportion_z_test`

The tool must validate the selected table, columns, group values, data types, sample sizes, and null-handling behavior before running the test.

#### Welch's independent two-sample t-test

Required inputs:

- table name
- numeric outcome column
- grouping column
- exactly two group values
- alpha level
- maximum rows or configured extraction limit

Requirements:

- Welch's unequal-variance form is the default and only independent t-test in the MVP.
- The two groups must be treated as independent samples.
- Non-numeric outcome values must be rejected or reported as excluded according to the validation contract.
- Null rows must be excluded explicitly and counted in result metadata.
- The result must include an effect size. A documented, tested implementation of Cohen's d or Hedges' g is acceptable.

#### Two-proportion z-test

Required inputs:

- table name
- grouping column
- exactly two group values
- binary outcome column
- explicit value representing success
- alpha level
- maximum rows or configured extraction limit

Requirements:

- The outcome must be validated as binary after null exclusion.
- The caller must explicitly identify the success value. The server must not guess which category represents success.
- The result must include successes and total observations for each group.
- The server must validate whether the normal approximation requirements are satisfied and return warnings or reject the request according to the documented rule.
- The result must include an effect-size measure appropriate for proportions, such as risk difference or Cohen's h.

## 7. Statistical result contract

A successful result should include, where applicable:

- test identifier
- human-readable test name
- null hypothesis
- alternative hypothesis
- alpha level
- test statistic
- p-value
- significance flag defined as `p_value < alpha`
- sample sizes
- group summaries
- effect-size name and value
- confidence interval when supported and implemented correctly
- assumptions
- assumption or data-quality warnings
- null rows excluded
- invalid rows excluded
- rows examined
- extraction limit
- whether truncation or sampling occurred
- reproducibility metadata such as a random seed when sampling is used

The server should return statistical evidence, not a causal conclusion. The host AI may explain the result but must not recalculate or invent statistical values.

## 8. Data-access and safety requirements

- The project is read-only.
- The MVP must not expose a general SQL execution tool.
- Database, table, and column identifiers must be validated before use.
- Queries must select only the columns required for the requested operation.
- Every extraction must apply a configurable hard row limit.
- No tool may load an unbounded table into a DataFrame.
- Query timeout support should be represented in the connector interface, even if SQLite support is limited.
- Sampling behavior must be explicit in the result metadata.
- Random sampling must be reproducible when the connector supports a seed.
- Credentials are loaded from environment variables or safe configuration.
- Secrets and complete connection URLs must never appear in logs, exceptions returned to clients, fixtures, or committed files.

## 9. Error-handling contract

Internal modules may raise specific typed exceptions for expected failure conditions, including:

- connection failure
- missing table
- missing column
- incompatible column type
- invalid group values
- insufficient sample size
- unsupported test
- unsafe identifier
- extraction limit violation

The MCP boundary must catch expected domain exceptions and convert them into structured, non-secret-bearing error responses.

Unexpected programming errors must not be silently presented as successful results. They should be logged safely and surfaced as generic internal errors without exposing credentials or sensitive query details.

## 10. Architecture boundaries

The implementation must keep these responsibilities separate:

1. MCP server creation and tool registration
2. configuration and secret loading
3. connector interface and SQLite implementation
4. metadata inspection and bounded data extraction
5. table profiling
6. statistical test implementations
7. public request and response models
8. domain exceptions
9. fixtures and tests

Statistical modules must accept pandas objects or ordinary Python values. They must not import database drivers or MCP server objects.

Connector modules must not contain statistical decision logic.

MCP tool handlers should orchestrate existing services rather than contain substantial database or statistical calculations directly.

## 11. Host-model role

The host AI is responsible for conversational orchestration. Based on a user's question, it may:

1. call `list_tables`
2. call `profile_table`
3. choose one of the supported tests
4. call `run_test` with explicit parameters
5. explain the structured result to the user

The MCP tool descriptions and schemas must clearly document:

- the question each test answers
- required variable types
- independence requirements
- important assumptions
- situations in which the test should not be used

The server must still validate every request. It must not assume that the host model selected a valid test or supplied compatible data.

In an OpenAI-hosted demonstration, the OpenAI model performs this orchestration. Other compatible hosts may use their own models while calling the same server tools.

## 12. MVP success criteria

The MVP is successful when:

1. A judge can clone the repository, create a virtual environment, run `pip install -e .`, generate or access the seeded SQLite database, and launch the documented MCP server command without external database credentials.
2. An MCP-compatible client can discover exactly the three MVP tools.
3. `list_tables` returns the seeded demonstration tables.
4. `profile_table` returns deterministic, bounded, structured metadata.
5. `run_test` correctly performs both supported tests.
6. Statistical values are validated in pytest against SciPy or statsmodels reference results.
7. Invalid requests return structured errors without crashing the MCP session.
8. Tests confirm that extraction limits are enforced and credentials are not exposed.
9. The README explains the architecture, setup, demo flow, limitations, and how Codex accelerated the build.

## 13. Demonstration scenario

The seeded SQLite database should include a simple experiment-style table containing:

- a record identifier
- a group or variant column with two values
- a continuous outcome
- a binary outcome
- a small amount of missing data to demonstrate explicit exclusion reporting

Example user questions:

- "Did variant B have a different average account balance than variant A?"
- "Did variant B convert at a higher rate than variant A?"

The demonstration should show the host model discovering the data, profiling the table, selecting an appropriate supported test, running it, and explaining the returned structured result without manually calculating the statistic or p-value.
