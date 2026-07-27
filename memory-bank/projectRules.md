# Project Rules

## Rule 1: Never Guess

If a fact is not verified from code, tests, command output, or cited documentation, the agent must say it is unverified and inspect first.

## Rule 2: Read Bug History First

Before touching an area that has known defects or regressions, read `memory-bank/bugPatterns.md`.

## Rule 3: Preserve Memory After Fixes

Every resolved bug should leave behind a durable record:

- trigger
- root cause
- fix
- regression test or guardrail

## Rule 4: Match Existing Coding Style

When code exists, follow its:

- naming conventions
- file placement
- framework idioms
- validation patterns
- test structure

Do not introduce a new style unless the user explicitly asks for it or the existing pattern is demonstrably broken.

## Rule 4A: No Style Block In Vue SFC

Do not use `<style>` blocks in `.vue` files.

Frontend styles must live in the centralized `src/styles/` tree, preferably as `.scss` files with explicit class naming. Style isolation should come from structure and naming, not from Vue style blocks.

## Rule 5: Use Verified Tech Stack Only

The source of truth is `memory-bank/techContext.md`.

If the codebase proves the file wrong or incomplete, update the file instead of silently assuming.

## Rule 6: Prefer Reuse Over New Structure

Search for extension points before creating files, folders, services, or abstractions.

## Rule 7: Record Durable Project Knowledge

Update the Memory Bank when a task reveals:

- a recurring bug pattern
- a stable architectural rule
- a tech stack fact
- a workflow constraint

## Rule 8: Evidence Beats Confidence

Technical claims should be backed by:

- file references
- command output
- tests
- linked upstream sources

## Rule 9: Keep Dark/Light Theme Consistent

Dark/light mode is a system-wide style contract.

Buttons, menus, headers, data tables, form inputs, dialogs, cards, tabs, and notifications must use shared theme tokens and remain visually consistent across all pages.

Do not hardcode colors in page/component code. Add or reuse semantic tokens/classes instead.

Any UI change that affects shared components must be checked in both dark and light mode before completion.

## Rule 10: Enterprise Performance And Security

The boilerplate must be designed at enterprise level.

Do not load tens of thousands of rows into a normal API response or frontend store. Use server-side pagination/filter/sort, cursor pagination for large datasets, and virtual scrolling only where appropriate.

Heavy import/export must use async jobs, chunk/stream processing, progress tracking, audit log, error report, and permissions.

Security-sensitive endpoints must include RBAC, validation, rate limit where appropriate, audit logging, and tests.

Secrets must never be committed. Database access must use ORM/query builder safely or parameterized queries. Production must enforce HTTPS, secure headers, CORS by environment, and dependency/container scanning.

Production deployment is not acceptable without observability, backup/restore runbooks, secret management, SLO/alerts, and passing compliance gates or approved waivers.

## Rule 11: Mobile Responsive Is Mandatory

Admin UI must work on mobile, tablet, and desktop.

Shared layout pieces such as sidebar, topbar, breadcrumb, tables, forms, dialogs, cards, and action bars must degrade gracefully on smaller viewports.

Do not treat responsive behavior as a later polish task. It is part of the base acceptance criteria for frontend work.

## Rule 12: Typography Is A System Contract

The default UI font is `Be Vietnam Pro`.

Do not mix multiple body-font families across pages or modules unless the design system is intentionally revised. Shared layout, form, table, and dashboard views should inherit from one centralized font definition.

## Rule 13: Timezone Must Be Explicit

The default business timezone is `Asia/Ho_Chi_Minh` (`GMT+7`).

For user-facing dates and times:

- do not rely on the developer machine timezone
- do not rely on the browser locale alone to decide timezone
- do not mix naive and timezone-aware datetimes
- do not send ambiguous datetime strings between frontend and backend

When the system stores UTC internally, conversion to `Asia/Ho_Chi_Minh` must be explicit at display and date-filter boundaries.

## Rule 14: Strict Integration & Browser Verification

Never claim a bug is fixed based on static analysis, unit tests, or compile success alone if the issue involves browser security, CORS, cookies, local storage, network routing, or integration behavior. 

Such boundaries (like SameSite cookie rules, cross-origin restrictions, or docker network resolution) are heavily mocked in unit/store tests, which can lead to false-positive success reports.

For all integration or browser-facing bug fixes, the agent must perform at least one of:
1. **Automated E2E Verification**: Execute the actual browser-driven E2E tests (`make docker-test-e2e` or similar suite).
2. **Interactive Browser Verification**: Launch a `browser_subagent` to load the application, perform the action, and verify the console/network logs or page state.

The walkthrough must explicitly cite the E2E or browser verification steps performed to prove the fix.

## Rule 15: Cookie-Based Session Initialization

Client-side login state verification must rely exclusively on backend-provided cookie markers (e.g., `fastapivue_logged_in`). 

Do not write or check localStorage state flags to decide whether to trigger silent token refreshes. Because localStorage lacks expiration, it easily goes out-of-sync with actual cookie lifetime, resulting in redundant and failed `/auth/refresh` API calls that pollute the browser console with 401 errors.

Additionally, on any failed silent refresh (401/403 errors) or when logging out/clearing authentication state, the frontend application must actively clear the `fastapivue_logged_in` cookie by setting its expiration to `max-age=0`. This breaks the infinite loop of failed token refresh requests on subsequent page reloads.


## Rule 16: Automatic Database Migrations in Dev/Test Containers

To prevent database errors (such as `UndefinedTableError`) when client-side applications load and immediately hit backend endpoints on startup (e.g. during auto-refresh), all local Docker Compose and Docker Test backend targets must run database migrations (`alembic upgrade head`) and data seeding script (`seed_auth_rbac.py`) automatically in their container startup commands prior to launching the ASGI/Uvicorn server.

## Rule 17: No Response Object Returns in 204 No Content Endpoints

When designing endpoints in FastAPI that return `HTTP_204_NO_CONTENT` (or any status code with no response body), do not return the `response: Response` parameter directly. 

Returning a `Response` instance (which defaults to a 200 OK status) causes an ASGI protocol collision between the route's 204 expectation and the returned object's 200 status. This results in connection drops and a `502 Bad Gateway` error in proxy configurations. Instead, modify cookies/headers on the injected `response` parameter directly and return `None` (or omit the return statement).

## Rule 18: Safe Response Body Parsing in Frontend HTTP Client

When consuming API endpoints on the frontend, do not automatically parse response bodies with `response.json()` directly without safety checks, even if the response `content-type` header is `application/json`. Various successful endpoints (e.g. 204 No Content, 205 Reset Content, or empty 200 OK responses) do not contain a body, which triggers `SyntaxError: Unexpected end of JSON input`. The frontend HTTP utility (`frontend/src/api/http.ts`) must read the body as text (`response.text()`) first, verify that the string is non-empty before calling `JSON.parse(...)`, and wrap the parsing operation inside a robust try-catch block falling back to `null` to ensure the application does not crash.

## Rule 19: Full Feature Lifecycle Verification

When resolving any bug in a feature module (such as Authentication, File Storage, or User Administration), the agent must not limit verification to the modified line of code or specific function. The agent must verify the entire user journey/lifecycle of that feature in the browser environment.
For example, if the agent modifies the login or token refresh mechanism, it is mandatory to test the complete sequence: Login -> F5 Page Reload -> Navigate to protected routes -> Perform Logout -> Verify redirection back to the login page. The agent must verify the entire flow is fully operational before concluding the task.

## Rule 20: Required Fields Must Be Marked Visually

Any user-facing form field that is mandatory must display a visible red asterisk on its label.

Do not rely solely on placeholder text, runtime validation messages, or disabled submit behavior to communicate required input. The required-state visual marker is part of the base UI contract and must be added consistently across create, edit, filter, upload, and dialog forms whenever the field is truly required by the validation or business rule.

## Rule 21: Tài Liệu Tiếng Việt Phải Có Dấu

Mọi tài liệu dự án viết bằng tiếng Việt phải dùng đầy đủ dấu tiếng Việt.

Không viết tài liệu tiếng Việt theo dạng ASCII-only / không dấu. Quy tắc này áp dụng cho `docs/`, `memory-bank/`, runbook, implementation plan và mọi ghi chú bền vững của dự án. Code identifiers, commands, paths, environment variables và protocol examples phải được giữ nguyên chính xác theo code hoặc tooling.

