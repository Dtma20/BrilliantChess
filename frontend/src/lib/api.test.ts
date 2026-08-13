import { afterEach, describe, expect, it, vi } from "vitest"

import { ApiError, api } from "@/lib/api"

function respond(body: unknown, status = 200) {
  return vi.fn().mockResolvedValue(
    new Response(JSON.stringify(body), {
      status,
      headers: { "Content-Type": "application/json" },
    }),
  )
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe("api", () => {
  it("hits the local endpoints with relative paths", async () => {
    const fetchMock = respond({ schema_version: "1", max_fullmoves: 100 })
    vi.stubGlobal("fetch", fetchMock)

    await api.lab()

    expect(fetchMock).toHaveBeenCalledWith("/api/lab", expect.anything())
  })

  it("escapes identifiers in the path", async () => {
    const fetchMock = respond({})
    vi.stubGlobal("fetch", fetchMock)

    await api.stepMatch("a b/c")

    expect(fetchMock.mock.calls[0][0]).toBe("/api/match/a%20b%2Fc/step")
  })

  it("surfaces the backend detail as the error message", async () => {
    vi.stubGlobal("fetch", respond({ detail: "Partida encerrada" }, 400))

    await expect(api.stepMatch("x")).rejects.toThrowError(
      expect.objectContaining({ message: "Partida encerrada", status: 400 }),
    )
  })

  it("explains a dead server instead of leaking a network error", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("failed to fetch")))

    const failure = await api.health().catch((cause: ApiError) => cause)

    expect(failure).toBeInstanceOf(ApiError)
    expect((failure as ApiError).message).toContain("brilliant-chess serve")
  })
})
