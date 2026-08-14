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
    const fetchMock = respond({ schema_version: "1", max_fullmoves: 100, strict_policy: "strict_v2" })
    vi.stubGlobal("fetch", fetchMock)

    await api.lab()

    expect(fetchMock).toHaveBeenCalledWith("/api/lab", expect.anything())
  })

  it("accepts the versioned strict_v2 laboratory policy", async () => {
    const fetchMock = respond({
      schema_version: "2",
      match_id: "m1",
      white: { policy: "strict_v2" },
    })
    vi.stubGlobal("fetch", fetchMock)

    await api.createMatch({
      white: { strength_key: "maximo", policy: "strict_v2" },
      black: { strength_key: "iniciante", policy: "normal" },
    })

    expect(fetchMock.mock.calls[0][1]).toEqual(
      expect.objectContaining({
        body: JSON.stringify({
          white: { strength_key: "maximo", policy: "strict_v2" },
          black: { strength_key: "iniciante", policy: "normal" },
        }),
      }),
    )
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
