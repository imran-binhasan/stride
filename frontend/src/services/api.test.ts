import { beforeEach, describe, expect, it, vi } from "vitest";
import { api } from "./api";

function makeJwt(payload: object): string {
  const seg = (o: object) => btoa(JSON.stringify(o));
  return `${seg({ alg: "HS256", typ: "JWT" })}.${seg(payload)}.sig`;
}

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

describe("ApiClient", () => {
  beforeEach(() => {
    localStorage.clear();
    api.clearAuth();
    vi.restoreAllMocks();
  });

  it("derives org id from the JWT claim on setAuth", () => {
    const token = makeJwt({ sub: "u1", org_id: "org-123" });
    api.setAuth(token, "refresh-1");
    expect(api.getOrgId()).toBe("org-123");
    expect(localStorage.getItem("stride_org_id")).toBe("org-123");
  });

  it("sends Authorization and X-Org-ID headers", async () => {
    const token = makeJwt({ sub: "u1", org_id: "org-9" });
    api.setAuth(token, "r");
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({ id: "u1" }));
    vi.stubGlobal("fetch", fetchMock);

    await api.getMe();
    const opts = fetchMock.mock.calls[0][1];
    expect(opts.headers["Authorization"]).toBe(`Bearer ${token}`);
    expect(opts.headers["X-Org-ID"]).toBe("org-9");
  });

  it("refreshes once on 401 and transparently retries", async () => {
    const oldToken = makeJwt({ sub: "u1", org_id: "o" });
    const newToken = makeJwt({ sub: "u1", org_id: "o" });
    api.setAuth(oldToken, "refresh-old");

    let apiCalls = 0;
    const fetchMock = vi.fn().mockImplementation((url: string) => {
      if (url.endsWith("/auth/refresh")) {
        return Promise.resolve(
          jsonResponse({ access_token: newToken, refresh_token: "refresh-new" })
        );
      }
      apiCalls++;
      return apiCalls === 1
        ? Promise.resolve(jsonResponse({}, 401))
        : Promise.resolve(jsonResponse({ id: "u1" }));
    });
    vi.stubGlobal("fetch", fetchMock);

    const me = await api.getMe();
    expect(me).toEqual({ id: "u1" });
    expect(fetchMock).toHaveBeenCalledTimes(3); // getMe(401) -> refresh -> getMe(200)
    expect(api.getToken()).toBe(newToken);
  });

  it("clears auth when refresh also fails", async () => {
    api.setAuth(makeJwt({ org_id: "o" }), "refresh-bad");
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse({}, 401));
    vi.stubGlobal("fetch", fetchMock);

    await expect(api.getMe()).rejects.toThrow();
    expect(api.getToken()).toBeNull();
  });
});
