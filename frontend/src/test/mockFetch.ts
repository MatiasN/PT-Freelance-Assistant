import { vi } from "vitest";

export interface MockResponse {
  status: number;
  statusText?: string;
  /** JSON body; pass an Error to make `response.json()` reject (non-JSON body). */
  body?: unknown;
}

export interface RecordedRequest {
  method: string;
  url: URL;
  headers: Headers;
  body: unknown;
}

export type FetchHandler = (request: RecordedRequest) => MockResponse;

/**
 * Replaces global fetch for one test. All HTTP goes through `handler`; every request is
 * recorded so tests can assert on what the UI sent.
 */
export function mockFetch(handler: FetchHandler): RecordedRequest[] {
  const requests: RecordedRequest[] = [];
  const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = new URL(String(input), "http://app.test");
    const request: RecordedRequest = {
      method: init?.method ?? "GET",
      url,
      headers: new Headers(init?.headers),
      body: typeof init?.body === "string" ? JSON.parse(init.body) : null,
    };
    requests.push(request);
    const { status, statusText = "", body } = handler(request);
    return {
      ok: status >= 200 && status < 300,
      status,
      statusText,
      json: async () => {
        if (body instanceof Error) {
          throw body;
        }
        return body;
      },
    } as unknown as Response;
  });
  vi.stubGlobal("fetch", fetchMock);
  return requests;
}
