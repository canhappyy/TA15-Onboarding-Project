# Final Fixes Report

## Fixes

- `route-search-api.ts` parses JSON as `unknown`, validates failure codes against an exhaustive `ApiErrorCode` map, and converts unknown codes to `UPSTREAM_ERROR` with `Route search returned an invalid response.`
- `journey-filter.tsx` exposes Low and High active state with `aria-pressed`.
- `page.test.tsx` checks for links inside route `article` elements only.

## RED

Commands:

```sh
pnpm --filter web test -- src/lib/route-search-api.test.ts
pnpm --filter web test -- src/app/journey/page.test.tsx
```

Output: exit 1; 2 failed tests. The unknown-code test received `BOGUS` / `Unknown failure.`. The filter test received no `aria-pressed` attribute. Vitest ran the web test project, reporting 35 passed and 2 failed tests.

## GREEN

Commands:

```sh
pnpm --filter web test -- src/lib/route-search-api.test.ts
pnpm --filter web test -- src/app/journey/page.test.tsx
pnpm --filter web test
pnpm --filter web lint
pnpm --filter web exec tsc --noEmit
git diff --check
```

Output:

- Focused commands: exit 0; 6 files, 37 tests passed.
- Full frontend tests: exit 0; 6 files, 37 tests passed.
- Lint: exit 0; 2 pre-existing warnings in `use-geolocation.ts` and `use-quiet-spaces.ts`; no errors.
- Typecheck: exit 0.
- Diff check: exit 0.

## Self-review

- `Record<ApiErrorCode, true>` makes a new shared API error code a compile-time update requirement.
- Unknown error codes cannot enter `RouteSearchApiError`.
- Toggle test checks inactive, active, and toggle-off ARIA states.
- Route-link test does not inspect unrelated page links.
- Scope limited to review findings and report.
