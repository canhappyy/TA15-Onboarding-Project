import { describe, expectTypeOf, it } from "vitest"

import type {
  ApiErrorCode,
  ApiResponse,
  RefugeCategory,
  Route,
  SensoryIndicator,
} from "@clearway/shared"

describe("shared API contract", () => {
  it("exposes only locked indicators, refuge categories, and error codes", () => {
    expectTypeOf<SensoryIndicator>().toEqualTypeOf<"LOW" | "HIGH">()
    expectTypeOf<RefugeCategory>().toEqualTypeOf<
      "LIBRARY" | "MUSEUM" | "GARDEN" | "PARK"
    >()
    expectTypeOf<ApiErrorCode>().toEqualTypeOf<
      | "INVALID_REQUEST"
      | "OUTSIDE_SERVICE_AREA"
      | "NOT_FOUND"
      | "UPSTREAM_TIMEOUT"
      | "UPSTREAM_ERROR"
      | "DATA_UNAVAILABLE"
      | "TOO_MANY_REQUESTS"
      | "INTERNAL_SERVER_ERROR"
    >()
  })

  it("wraps route data in the common response envelope", () => {
    expectTypeOf<ApiResponse<{ routes: Route[] }>>().toMatchTypeOf<
      | { success: true; data: { routes: Route[] } }
      | { success: false; error: { code: ApiErrorCode; message: string } }
    >()
  })
})
