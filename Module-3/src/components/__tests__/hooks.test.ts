import { renderHook, act } from "@testing-library/react";
import { useDwellTimer } from "../hooks/useDwellTimer";
import { useBannerSession } from "../hooks/useBannerSession";
import { useRiskScore } from "../hooks/useRiskScore";

// ---------- useDwellTimer ----------

describe("useDwellTimer", () => {
  beforeEach(() => {
    jest.useFakeTimers();
  });

  afterEach(() => {
    jest.useRealTimers();
  });

  it("returns approximately 5.0 after 5000 ms", () => {
    const { result } = renderHook(() => useDwellTimer());
    const getDwell = result.current;

    // Advance time by 5000 ms
    jest.advanceTimersByTime(5000);

    const elapsed = getDwell();
    expect(elapsed).toBeCloseTo(5.0, 0);
  });

  it("returns 0 immediately after mount", () => {
    const { result } = renderHook(() => useDwellTimer());
    const getDwell = result.current;

    const elapsed = getDwell();
    expect(elapsed).toBeCloseTo(0.0, 0);
  });
});

// ---------- useBannerSession ----------

describe("useBannerSession", () => {
  beforeEach(() => {
    sessionStorage.clear();
  });

  it("isDismissed returns false initially", () => {
    const { result } = renderHook(() => useBannerSession());

    expect(result.current.isDismissed("cust-1", "prod-1")).toBe(false);
  });

  it("after dismiss(), isDismissed returns true for same pair", () => {
    const { result } = renderHook(() => useBannerSession());

    act(() => {
      result.current.dismiss("cust-1", "prod-1");
    });

    expect(result.current.isDismissed("cust-1", "prod-1")).toBe(true);
  });

  it("after dismiss(), isDismissed returns false for different pair", () => {
    const { result } = renderHook(() => useBannerSession());

    act(() => {
      result.current.dismiss("cust-1", "prod-1");
    });

    expect(result.current.isDismissed("cust-1", "prod-2")).toBe(false);
    expect(result.current.isDismissed("cust-2", "prod-1")).toBe(false);
  });
});

// ---------- useRiskScore ----------

describe("useRiskScore", () => {
  beforeEach(() => {
    jest.useFakeTimers();
  });

  afterEach(() => {
    jest.useRealTimers();
    jest.restoreAllMocks();
  });

  it("populates data on successful fetch (200)", async () => {
    const mockResponse = {
      risk_score: 0.82,
      intervention_type: "SIZE_GUIDANCE",
      intervention_copy: "Your kept size is M.",
      taxonomy_miss: false,
    };

    global.fetch = jest.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(mockResponse),
    });

    const { result } = renderHook(() => useRiskScore());

    act(() => {
      result.current.fireRiskScore({
        customer_id: "cust-1",
        product_id: "prod-1",
        page_dwell_seconds: 5.0,
        is_buy_now: false,
      });
    });

    // Flush pending promises
    await act(async () => {
      await Promise.resolve();
      await Promise.resolve();
    });

    expect(result.current.data).toEqual(mockResponse);
    expect(result.current.error).toBe(false);
    expect(result.current.loading).toBe(false);
  });

  it("sets error=true on 3s timeout with no visible error message", async () => {
    // Mock fetch that never resolves (simulating timeout via AbortController)
    global.fetch = jest
      .fn()
      .mockImplementation((_url: string, options: { signal: AbortSignal }) => {
        return new Promise((_resolve, reject) => {
          options.signal.addEventListener("abort", () => {
            reject(
              new DOMException("The operation was aborted.", "AbortError"),
            );
          });
        });
      });

    const { result } = renderHook(() => useRiskScore());

    act(() => {
      result.current.fireRiskScore({
        customer_id: "cust-1",
        product_id: "prod-1",
        page_dwell_seconds: 5.0,
        is_buy_now: false,
      });
    });

    // Advance past the 3000 ms timeout
    await act(async () => {
      jest.advanceTimersByTime(3000);
      await Promise.resolve();
      await Promise.resolve();
    });

    expect(result.current.error).toBe(true);
    expect(result.current.data).toBeNull();
    expect(result.current.loading).toBe(false);
  });
});
