# Task 3 Report: Journey Components and Page

## Changes

- Added `JourneySearchForm` for location selection and search submission.
- Added `JourneyRouteResults` for initial, loading, error/retry, empty, and successful route states.
- Replaced mock route fields with shared `Route` data in `RouteCard`.
- Reduced filters to `LOW` and `HIGH` shared-contract values.
- Simplified `JourneyPage` to compose `AppLogo`, `JourneySearchForm`, and `JourneyRouteResults` from `useJourney`.
- Deleted `apps/web/src/lib/mock-routes.ts`; no imports remain.
- Updated the page integration test. It uses real hook/components and mocks only location and route API calls with complete shared fixtures.

## RED evidence

Command:

```sh
pnpm --filter web test -- src/app/journey/page.test.tsx
```

Before implementation: exit 1, 5 page tests failed. Failures showed the old page lacked the `Searching…` button state, live route duration/distance fields, LOW/HIGH filtering, inline error/retry, and result clearing behavior.

Empty-results mutation check: temporarily removed the empty-route branch, then ran the same command. Exit 1; exactly 1 test failed because `No routes found for this journey.` was absent.

## GREEN evidence

```sh
pnpm --filter web test -- src/app/journey/page.test.tsx
# 6 files passed, 35 tests passed

pnpm --filter web test
# 6 files passed, 35 tests passed

pnpm --filter web exec tsc --noEmit
# exit 0

pnpm --filter web lint
# exit 0; 2 pre-existing warnings in use-geolocation.ts and use-quiet-spaces.ts
```

## Self-review

- Search button disables until both locations exist and changes to `Searching…` while loading.
- Results exposes an accessible loading status, inline `role="alert"` retry, initial instruction, empty message, count, filters, and articles.
- Route cards render shared fields: minutes, kilometres, LOW/HIGH indicator, recommended badge, explanation, and warning. They contain no route links, mock badge fields, via text, or chevron.
- Filter controls render only Low and High and send `LOW`/`HIGH`.
- Page tests cover disabled/loading, real fields, filtering, recommendation/warning, error/retry, empty results, clearing after a location change, and no route links.
- `git diff --check` passed. Existing lint warnings were not changed.
