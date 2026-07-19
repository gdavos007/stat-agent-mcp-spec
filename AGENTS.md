# AGENTS.md — Repository Instructions for Codex

These instructions apply to every change in this repository.

Read `PROJECT_SPEC.md` before proposing architecture, dependencies, public interfaces, statistical behavior, or scope changes. `PROJECT_SPEC.md` defines what the product should do. This file defines how work should be performed.

## 1. Working method

For any substantial task:

1. Inspect the relevant files before proposing changes.
2. Restate the task and the affected module's responsibility.
3. Identify contradictions, missing decisions, security risks, and statistical risks.
4. Propose the smallest coherent implementation plan.
5. Name the files expected to change.
6. Do not modify files when the user has requested planning or review only.
7. Implement only the approved scope.
8. Run the relevant tests and quality checks.
9. Report the exact commands run and whether each passed or failed.
10. Summarize changed behavior, remaining risks, and anything not verified.

Prefer small vertical slices over broad scaffolding followed by many incomplete modules.

Do not perform unrelated refactoring. Do not silently expand the MVP.

## 2. Architecture rules

Keep these concerns separate:

- MCP server setup and tool registration
- configuration and environment-variable loading
- database connector interfaces and implementations
- database metadata inspection
- bounded data extraction
- deterministic table profiling
- statistical test implementations
- Pydantic request and response models
- domain exceptions and MCP error translation
- fixtures and tests

### Connector boundary

All database access must go through a `DatabaseConnector` abstraction.

No module outside the connector package may import or call a database driver directly.

Statistical modules must receive pandas objects or ordinary Python values. They must not know which database produced the data.

MCP tool handlers should coordinate services. They should not contain substantial SQL, profiling algorithms, or statistical formulas.

When adding a future database engine, existing statistical modules and existing MCP tool behavior should not require modification. Expected connector work may include:

- a new connector implementation
- connector registration
- connector-specific tests
- optional dependencies
- configuration examples
- documentation

If a new connector requires changes to statistical calculations or tool-specific business logic, stop and review the abstraction before proceeding.

## 3. Statistical correctness

Hypothesis-test statistics, probability distributions, p-values, and library-supported confidence intervals must come from maintained statistical libraries such as `scipy.stats` and `statsmodels`.

Do not replace an available statistical-library implementation with:

- a custom CDF approximation
- a hand-derived p-value calculation
- SQL-based statistical approximations
- an LLM-generated number

Standard descriptive statistics and effect sizes may be implemented from established formulas only when:

- the formula is documented
- the implementation is isolated in a focused function
- deterministic tests validate it against a trusted reference

For the MVP:

- the independent two-sample test is Welch's unequal-variance t-test
- the proportion test requires an explicit success value
- null handling must be explicit
- sample sizes and exclusions must be reported
- statistical significance must not be presented as causality or business importance

Every statistical function must be deterministic for a fixed input.

## 4. Database and data safety

The project is read-only.

Do not implement or expose operations that perform:

- `INSERT`
- `UPDATE`
- `DELETE`
- `MERGE`
- `DROP`
- `ALTER`
- `CREATE`
- `TRUNCATE`
- other DDL or DML

Do not expose arbitrary SQL execution in the MVP.

Validate database identifiers before interpolation or execution.

Never load an unbounded table into pandas.

Every extraction must:

- apply a configurable hard row limit
- select only required columns
- report rows examined
- report rows excluded
- report whether truncation or sampling occurred
- use reproducible sampling when a seed is supported

Credentials and complete connection URLs must never be:

- hardcoded
- committed
- printed
- logged
- returned from an MCP tool
- included in exceptions sent to a client

Use environment variables or safe configuration objects. `.env.example` may contain placeholders only.

## 5. Structured tool contracts

Anything crossing an MCP tool boundary must use typed, structured models.

Use Pydantic models for public inputs and outputs unless the MCP SDK requires a different schema mechanism. Keep the resulting JSON schema explicit and understandable to a host model.

Do not return hand-formatted text when structured fields are appropriate.

Tool descriptions must explain:

- what question the tool answers
- required argument types
- important assumptions
- invalid-use cases
- row-limit behavior
- null-handling behavior

The host model may choose an incorrect test or invalid column. The server must validate all requests rather than trusting the host.

## 6. Error handling

Internal modules may raise specific typed domain exceptions.

Create focused exception types for expected failures such as:

- connection errors
- unsafe identifiers
- missing tables
- missing columns
- incompatible data types
- invalid group values
- insufficient observations
- unsupported tests

At the MCP boundary, catch expected domain exceptions and convert them into structured, non-secret-bearing error responses.

Do not use a broad `except Exception` to hide programming errors.

Unexpected failures should be logged safely and returned as a generic internal error without exposing secrets, raw connection strings, or sensitive query details.

Never claim a tool succeeded when part of the operation failed.

## 7. Python standards

- Use Python 3.11 or newer.
- Add type hints to public functions and methods.
- Use focused modules and small functions.
- Prefer clear names over abbreviations.
- Add docstrings to public interfaces and non-obvious statistical logic.
- Explain why a non-obvious decision exists rather than restating the code.
- Avoid global mutable state.
- Avoid adding dependencies without explaining their purpose.
- Keep dependency versions compatible and document any necessary lower or upper bounds.
- Do not introduce asynchronous complexity unless the MCP SDK or connector behavior requires it.

## 8. Testing requirements

Use pytest.

Tests must include:

- unit tests for every statistical calculation
- reference comparisons against SciPy or statsmodels
- tests for effect-size calculations
- tests for invalid statistical inputs
- tests for null and non-numeric handling
- tests for bounded extraction
- tests for unsafe or missing identifiers
- integration tests using a seeded SQLite fixture
- tests that tool errors do not crash the MCP session boundary
- tests that secrets and full connection URLs are not exposed

Use deterministic fixtures and fixed random seeds.

Do not write tests that only assert that code runs without raising. Assert meaningful values, schemas, exclusions, warnings, and error types.

A feature is not complete until its relevant tests pass.

## 9. Git and repository safety

- Do not commit or push unless explicitly asked.
- Do not rewrite Git history.
- Do not use destructive Git commands.
- Do not delete user-authored files without explicit approval.
- Do not modify real `.env` files or credentials.
- Keep generated caches, local databases, virtual environments, and secrets out of Git.
- Before a broad change, recommend a clean Git checkpoint when appropriate.

## 10. Scope discipline

The MVP scope is defined in `PROJECT_SPEC.md`.

If a task appears to require an out-of-scope feature, stop and explain:

- why it appears necessary
- whether the current design can defer it safely
- the smallest alternative that preserves the MVP

Do not add extra databases, statistical tests, LLM calls, arbitrary SQL, deployment infrastructure, or user interfaces merely because they might be useful later.

## 11. Codex contribution tracking

Maintain a concise development record in the README or another approved project log that identifies:

- architectural work proposed by Codex
- code generated or substantially edited by Codex
- tests generated by Codex
- corrections or decisions made by the human developer
- important prompts or session identifiers required by the hackathon submission

Do not store secrets, authentication tokens, or private Codex session transcripts in the repository.

## 12. Definition of done for an MCP tool

An MCP tool is complete only when:

- [ ] Its purpose and usage are documented.
- [ ] Its public input schema is explicit.
- [ ] Its successful output schema is explicit.
- [ ] Its structured error behavior is explicit.
- [ ] It validates table names, column names, values, and data types as applicable.
- [ ] It enforces bounded extraction.
- [ ] It reports exclusions, truncation, and sampling metadata.
- [ ] It has at least one successful integration test using the seeded SQLite fixture.
- [ ] It has at least one invalid-input test.
- [ ] Relevant unit, integration, lint, and type checks pass.
- [ ] The exact verification commands and results are reported.

## 13. Definition of done for a statistical test

A statistical test is complete only when:

- [ ] Its supported research question is documented.
- [ ] Its assumptions and invalid-use cases are documented.
- [ ] Its input validation is implemented.
- [ ] Its statistic and p-value come from an approved maintained library.
- [ ] Its sample sizes and exclusions are returned.
- [ ] Its effect size is returned and tested.
- [ ] Its result is validated against a trusted reference.
- [ ] Edge cases produce structured failures or warnings rather than misleading values.
