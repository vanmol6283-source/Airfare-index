/**
 * api.js — Data access layer.
 *
 * When VITE_API_URL is set (pointing to the Python/FastAPI backend),
 * all calls go to the real API.
 *
 * When VITE_API_URL is not set (local dev without backend running),
 * falls back to mock JSON so the frontend always works standalone.
 *
 * To use the real backend:
 *   1. Start: cd backend && uvicorn app.main:app --reload --port 8000
 *   2. Create airfare-index/.env.local:
 *        VITE_API_URL=http://localhost:8000/api/v1
 *   3. Restart: npm run dev
 */

import mockData from "./mocks/airfareData.json";
import { aggregateByFrequency } from "./utils/aggregation";

const API_BASE = import.meta.env.VITE_API_URL;
const USE_MOCK = !API_BASE;

// Small artificial delay for mock mode so loading states are testable
const delay = (ms = 80) => new Promise((r) => setTimeout(r, ms));

// ── Generic fetch wrapper ─────────────────────────────────────────────────────

async function apiFetch(path) {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
  });
  if (!res.ok) {
    const detail = await res.text().catch(() => res.statusText);
    throw new Error(`API ${path} → ${res.status}: ${detail}`);
  }
  return res.json();
}

// ── Public API functions ──────────────────────────────────────────────────────

/**
 * GET /summary
 * Returns IndexSummary.
 */
export async function getSummary() {
  if (USE_MOCK) {
    await delay();
    return mockData.summary;
  }
  const data = await apiFetch("/summary");
  // Normalise backend camelCase aliases
  return {
    apixToday: data.apixToday,
    momChange: data.momChange,
    yoyChange: data.yoyChange,
    lastUpdated: data.lastUpdated,
    routesTracked: data.routesTracked,
    dataPointsToday: data.dataPointsToday,
  };
}

/**
 * GET /basket
 * Returns BasketItem[].
 */
export async function getBasketItems() {
  if (USE_MOCK) {
    await delay();
    return mockData.basketItems;
  }
  const data = await apiFetch("/basket");
  // Backend uses apWindow (camel); frontend expects apWindow too — pass through
  return data;
}

/**
 * GET /index-history?freq=daily|weekly|monthly
 * Returns IndexHistoryPoint[].
 */
export async function getIndexHistory(frequency = "daily") {
  if (USE_MOCK) {
    await delay();
    return aggregateByFrequency(mockData.indexHistory, frequency);
  }
  return apiFetch(`/index-history?freq=${frequency}`);
}

/**
 * GET /route/:id
 * Returns BasketItem[] for a single route.
 */
export async function getRouteDetail(routeId) {
  if (USE_MOCK) {
    await delay();
    return mockData.basketItems.filter((item) => item.route === routeId);
  }
  return apiFetch(`/route/${routeId}`);
}

/**
 * GET /data-quality
 * Returns DataQualityStats[].
 */
export async function getDataQuality() {
  if (USE_MOCK) {
    await delay();
    return [
      {
        source: "Airline booking portals",
        lastScraped: mockData.summary.lastUpdated,
        quotesCollected: mockData.summary.dataPointsToday * 48,
        quotesRejected: 12,
        backTestDeviationPct: 1.43,
      },
      {
        source: "Airline GDS feed",
        lastScraped: mockData.summary.lastUpdated,
        quotesCollected: mockData.summary.dataPointsToday * 24,
        quotesRejected: 4,
        backTestDeviationPct: 0.87,
      },
      {
        source: "DGCA traffic weight reference",
        lastScraped: "2026-04-01T00:00:00Z",
        quotesCollected: 8,
        quotesRejected: 0,
        backTestDeviationPct: 0,
      },
    ];
  }
  return apiFetch("/data-quality");
}

/**
 * POST /trigger-scrape/:type
 * Manually trigger scraping for 'web' or 'api'
 */
export async function triggerTargetedScrape(type) {
  if (USE_MOCK) {
    await delay(1000); // Simulate some delay
    return { message: "Mock scrape triggered." };
  }
  const res = await fetch(`${API_BASE}/trigger-scrape/${type}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
  });
  if (!res.ok) {
    throw new Error(`API error: ${res.status}`);
  }
  return res.json();
}