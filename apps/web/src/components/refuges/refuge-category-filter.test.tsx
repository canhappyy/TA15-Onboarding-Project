import { cleanup, render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, describe, expect, it, vi } from "vitest"

import { RefugeCategoryFilter } from "@/components/refuges/refuge-category-filter"

afterEach(cleanup)

describe("RefugeCategoryFilter", () => {
  it("renders every refuge category and reports the selected category", async () => {
    const onToggleFilter = vi.fn()
    const user = userEvent.setup()

    render(
      <RefugeCategoryFilter
        activeFilter="all"
        onToggleFilter={onToggleFilter}
      />
    )

    for (const label of ["All", "Park", "Garden", "Library", "Museum"]) {
      expect(screen.getByRole("button", { name: label })).toBeInTheDocument()
    }
    expect(screen.getByRole("button", { name: "All" })).toHaveAttribute(
      "aria-pressed",
      "true"
    )
    expect(screen.getByRole("button", { name: "Park" })).toHaveAttribute(
      "aria-pressed",
      "false"
    )

    await user.click(screen.getByRole("button", { name: "Museum" }))

    expect(onToggleFilter).toHaveBeenCalledWith("MUSEUM")
  })
})
