/**
 * ApiDocs.jsx
 *
 * Clean institutional API documentation page.
 * Describes the planned interface contracts for statistical consumers.
 */

function EndpointCard({ method, path, description, params, response, note }) {
  return (
    <div className="border border-border bg-white mb-6">
      {/* Header */}
      <div className="flex items-center gap-3 border-b border-border px-5 py-4 bg-bg-alt">
        <span className="border border-gray-400 bg-[#20173f] px-2 py-0.5 font-mono text-[11px] font-bold text-white rounded-sm">
          {method}
        </span>
        <code className="font-mono text-[14px] font-semibold text-gray-900">
          {path}
        </code>
      </div>

      <div className="px-6 py-5 space-y-6">
        <p className="font-sans text-[14px] text-text-secondary leading-relaxed">{description}</p>

        {note && (
          <div className="border-l-4 border-amber-400 bg-amber-50 px-4 py-3 text-amber-800 font-sans text-[13px]">
            {note}
          </div>
        )}

        {params && params.length > 0 && (
          <div>
            <div className="mb-3 font-sans text-[12px] font-bold uppercase tracking-wider text-text-secondary">
              Parameters
            </div>
            <div className="overflow-x-auto">
              <table className="w-full border-collapse font-sans text-[13px]">
                <thead>
                  <tr className="border-b border-border text-[11px] uppercase tracking-wider text-text-secondary">
                    <th className="py-2 pr-4 text-left font-semibold">Name</th>
                    <th className="py-2 pr-4 text-left font-semibold">Type</th>
                    <th className="py-2 text-left font-semibold">Description</th>
                  </tr>
                </thead>
                <tbody>
                  {params.map(({ name, type, desc }) => (
                    <tr key={name} className="border-b border-gray-100">
                      <td className="py-2.5 pr-4 font-mono text-[12px] font-semibold text-gray-800">
                        {name}
                      </td>
                      <td className="py-2.5 pr-4 font-mono text-[11px] text-text-secondary">{type}</td>
                      <td className="py-2.5 text-text-secondary">{desc}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {response && (
          <div>
            <div className="mb-3 font-sans text-[12px] font-bold uppercase tracking-wider text-text-secondary">
              Example Response
            </div>
            <pre className="overflow-x-auto border border-border bg-gray-900 px-5 py-4 text-[12px] font-mono leading-relaxed text-gray-50 rounded-sm">
              {response}
            </pre>
          </div>
        )}
      </div>
    </div>
  );
}

const ENDPOINTS = [
  {
    method: "GET",
    path: "/summary",
    description:
      "Returns the current top-level index summary including the latest APIx value, month-on-month change, year-on-year change, number of routes tracked, and data points collected today.",
    params: [],
    response: `{
  "apixToday": 110.35,
  "momChange": 8.27,
  "yoyChange": 8.74,
  "lastUpdated": "2026-08-27T09:55:00Z",
  "routesTracked": 8,
  "dataPointsToday": 18
}`,
  },
  {
    method: "GET",
    path: "/basket",
    description:
      "Returns all basket items — one record per route × advance-purchase window combination. Includes base fare, current fare, price relative, weight, and recent change indicators.",
    params: [],
    response: `[
  {
    "route": "DEL-BOM",
    "origin": "DEL",
    "destination": "BOM",
    "apWindow": "T+1",
    "baseFare": 5200,
    "currentFare": 8137,
    "priceRelative": 1.5648,
    "weight": 7.1452,
    "change7d": 2.11,
    "change30d": -8.26,
    "dataPoints": 27,
    "history": [
      { "date": "2026-07-29", "fare": 7191.29 },
      ...
    ]
  },
  ...
]`,
  },
  {
    method: "GET",
    path: "/index-history",
    description:
      "Returns the daily APIx index history. Optionally aggregated to weekly or monthly frequency. Weekly and monthly values are arithmetic means of the constituent daily values.",
    params: [
      {
        name: "freq",
        type: "string",
        desc: 'Aggregation frequency. One of: "daily" (default), "weekly", "monthly".',
      },
    ],
    response: `[
  { "date": "2026-05-29", "apix": 100.12, "frequency": "daily" },
  { "date": "2026-05-30", "apix": 100.34, "frequency": "daily" },
  ...
  { "date": "2026-08-27", "apix": 110.35, "frequency": "daily" }
]`,
  },
  {
    method: "GET",
    path: "/route/:id",
    description:
      "Returns all basket entries for a specific route. The route identifier is the IATA code pair, e.g. DEL-BOM. Returns an array of basket items for each advance-purchase window observed on that route.",
    params: [
      {
        name: "id",
        type: "string",
        desc: "Route identifier in ORIG-DEST format, e.g. DEL-BOM.",
      },
    ],
    response: `[
  {
    "route": "DEL-BOM",
    "origin": "DEL",
    "destination": "BOM",
    "apWindow": "T+1",
    "baseFare": 5200,
    "currentFare": 8137,
    "priceRelative": 1.5648,
    "weight": 7.1452,
    "change7d": 2.11,
    "change30d": -8.26,
    "dataPoints": 27,
    "history": [...]
  },
  {
    "route": "DEL-BOM",
    "apWindow": "T+7",
    ...
  }
]`,
  },
  {
    method: "GET",
    path: "/data-quality",
    description:
      "Returns data provenance and quality statistics for each data source. Includes collection counts, rejection counts, and back-test deviation percentages.",
    params: [],
    response: `[
  {
    "source": "Airline booking portals",
    "lastScraped": "2026-08-27T09:55:00Z",
    "quotesCollected": 864,
    "quotesRejected": 12,
    "backTestDeviationPct": 1.43
  },
  ...
]`,
  },
];

export default function ApiDocs() {
  return (
    <div data-page="api" className="w-full max-w-[1000px] mx-auto space-y-8">
      <header className="rounded-2xl border border-border bg-gradient-to-br from-white to-[#f4eefb] px-6 py-6 shadow-[0_12px_35px_rgba(32,23,63,0.07)]">
        <div className="mb-2 text-[10px] font-bold uppercase tracking-[0.2em] text-accent">DEVELOPER ACCESS</div>
        <h1 className="font-sans text-[30px] sm:text-[36px] font-bold text-gray-900 tracking-tight">
          API Reference
        </h1>
        <p className="mt-2 font-sans text-[16px] text-text-secondary">
          Interface specification for the Airfare Price Index data API
        </p>
      </header>

      {/* Notice */}
      <section className="border border-border bg-white px-6 py-5 shadow-[0_8px_30px_rgba(32,23,63,0.055)]">
        <div className="space-y-4 font-sans text-[14px] text-text-secondary leading-relaxed">
          <div className="font-bold text-[16px] text-gray-900">About This Documentation</div>
          <p>
            This page documents the planned REST API interface for the Airfare Price Index
            system. The endpoints below represent the current interface contract and are
            subject to change as the backend implementation progresses.
          </p>
          <p>
            All responses are JSON. Date values are ISO 8601 strings. Fare values are
            in Indian Rupees (INR). The API is intended for use by statistical
            organisations, research institutions, and government agencies.
          </p>
          <div className="border-l-4 border-border bg-bg-alt px-4 py-3 text-gray-800 font-mono text-[12px] space-y-1">
            <div>Base URL (planned): <code className="font-semibold text-primary">https://api.airfareindex.in/v1</code></div>
            <div>Authentication: API key (header: <code className="bg-gray-200 px-1 rounded">X-API-Key</code>)</div>
            <div>Rate limit: 1,000 requests / hour per key</div>
          </div>
        </div>
      </section>

      {/* Data types */}
      <section className="border border-border bg-white shadow-[0_8px_30px_rgba(32,23,63,0.055)]">
        <div className="border-b border-border px-6 py-4 bg-bg-alt">
          <h2 className="font-sans text-[16px] font-bold text-gray-900">
            Data Types
          </h2>
        </div>
        <div className="px-6 py-5">
          <div className="grid gap-6 md:grid-cols-2">
            {[
              { type: "IndexSummary", fields: ["apixToday: number", "momChange: number", "yoyChange: number", "lastUpdated: ISO8601", "routesTracked: integer", "dataPointsToday: integer"] },
              { type: "BasketItem", fields: ["route: string", "origin: string (IATA)", "destination: string (IATA)", "apWindow: string", "baseFare: number (INR)", "currentFare: number (INR)", "priceRelative: number", "weight: number", "change7d: number (%)", "change30d: number (%)", "dataPoints: integer", "history: HistoryPoint[]"] },
              { type: "IndexHistoryPoint", fields: ["date: string (YYYY-MM-DD)", "apix: number", "frequency: string"] },
              { type: "DataQualityStats", fields: ["source: string", "lastScraped: ISO8601", "quotesCollected: integer", "quotesRejected: integer", "backTestDeviationPct: number (%)"] },
            ].map(({ type, fields }) => (
              <div key={type} className="border border-border px-5 py-4 bg-bg-alt">
                <div className="mb-3 font-mono text-[13px] font-bold text-gray-900">{type}</div>
                <ul className="space-y-1.5 font-sans text-[13px] text-text-secondary">
                  {fields.map((f) => (
                    <li key={f}>
                      <span className="text-gray-400 mr-2">•</span>
                      <span dangerouslySetInnerHTML={{ __html: f.replace(/(\w+):/, '<span class="font-mono text-[12px] font-semibold text-gray-800">$1:</span>') }} />
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Endpoint cards */}
      <div className="space-y-6">
        <h2 className="font-sans text-[20px] font-bold text-gray-900 pt-4">
          Endpoints
        </h2>
        {ENDPOINTS.map((ep) => (
          <EndpointCard key={ep.path} {...ep} />
        ))}
      </div>
    </div>
  );
}

