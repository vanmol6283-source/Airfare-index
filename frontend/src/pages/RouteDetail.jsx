import { useParams, Link, useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
} from "recharts";
import { getRouteDetail } from "../api";

const ROUTE_LABELS = {
  "DEL-BOM": { origin: "Delhi (DEL)", destination: "Mumbai (BOM)", dist: "1,148 km", carriers: 4, competition: "High", season: "Business/Corporate" },
  "DEL-BLR": { origin: "Delhi (DEL)", destination: "Bengaluru (BLR)", dist: "1,740 km", carriers: 4, competition: "High", season: "Tech/Corporate" },
  "BOM-BLR": { origin: "Mumbai (BOM)", destination: "Bengaluru (BLR)", dist: "842 km", carriers: 3, competition: "High", season: "Business" },
  "DEL-CCU": { origin: "Delhi (DEL)", destination: "Kolkata (CCU)", dist: "1,305 km", carriers: 3, competition: "Medium", season: "Mixed" },
  "BLR-HYD": { origin: "Bengaluru (BLR)", destination: "Hyderabad (HYD)", dist: "500 km", carriers: 2, competition: "Low", season: "Commuter" },
  "MAA-DEL": { origin: "Chennai (MAA)", destination: "Delhi (DEL)", dist: "1,753 km", carriers: 3, competition: "Medium", season: "Mixed" },
  "DEL-HYD": { origin: "Delhi (DEL)", destination: "Hyderabad (HYD)", dist: "1,253 km", carriers: 3, competition: "High", season: "Tech" },
  "BOM-CCU": { origin: "Mumbai (BOM)", destination: "Kolkata (CCU)", dist: "1,652 km", carriers: 2, competition: "Medium", season: "Mixed" },
};

function CustomTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null;
  return (
    <div className="border border-border bg-white px-3 py-2 shadow-[0_8px_30px_rgba(32,23,63,0.055)] rounded-none">
      <div className="font-mono text-[10px] text-text-secondary">{label}</div>
      <div className="mt-1 font-mono text-[14px] font-semibold tabular-nums text-gray-900">
        ₹{Math.round(payload[0].value).toLocaleString("en-IN")}
      </div>
    </div>
  );
}

export default function RouteDetail() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [apFilter, setApFilter] = useState("all");

  const { data, isLoading, isError } = useQuery({
    queryKey: ["route", id],
    queryFn: () => getRouteDetail(id),
    enabled: !!id,
  });

  const label = ROUTE_LABELS[id] || { origin: "Unknown", destination: "Unknown", dist: "N/A", carriers: "N/A", competition: "N/A", season: "N/A" };

  if (isLoading) {
    return (
      <div className="flex h-64 items-center justify-center font-sans text-[12px] text-gray-400">
        Loading route data…
      </div>
    );
  }

  if (isError || !data || data.length === 0) {
    return (
      <div className="flex h-64 items-center justify-center font-sans text-[12px] text-danger">
        Unable to load route data for {id}.
      </div>
    );
  }

  // Calculate aggregates for KPI Strip
  const avgBase = data.reduce((acc, curr) => acc + curr.baseFare, 0) / data.length;
  const avgCurrent = data.reduce((acc, curr) => acc + curr.currentFare, 0) / data.length;
  const avg7d = data.reduce((acc, curr) => acc + curr.change7d, 0) / data.length;
  const avg30d = data.reduce((acc, curr) => acc + curr.change30d, 0) / data.length;

  const kpis = [
    { label: "BASE FARE (AVG)", value: `₹${Math.round(avgBase).toLocaleString("en-IN")}` },
    { label: "CURRENT FARE (AVG)", value: `₹${Math.round(avgCurrent).toLocaleString("en-IN")}` },
    { label: "7D CHG.", value: `${avg7d > 0 ? '▲ +' : avg7d < 0 ? '▼ ' : ''}${avg7d.toFixed(2)}%`, isChange: true, raw: avg7d },
    { label: "30D CHG.", value: `${avg30d > 0 ? '▲ +' : avg30d < 0 ? '▼ ' : ''}${avg30d.toFixed(2)}%`, isChange: true, raw: avg30d },
  ];

  // Chart data: use data[0] history as representative for demo, or merge if multiple
  const activeData = apFilter === "all" ? data[0] : data.find(d => d.apWindow === apFilter) || data[0];
  const historyData = activeData.history ?? [];

  return (
    <div data-page="route-detail" className="space-y-6">
      {/* Header */}
      <div className="rounded-2xl border border-border bg-gradient-to-br from-white to-[#f4eefb] px-6 py-5 shadow-[0_12px_35px_rgba(32,23,63,0.07)]">
        <button 
          onClick={() => navigate(-1)}
          className="text-primary hover:underline font-sans text-[12px] font-medium flex items-center gap-1 mb-4"
        >
          &larr; Back
        </button>
        <div className="mb-2 text-[10px] font-bold uppercase tracking-[0.2em] text-accent">ROUTE INTELLIGENCE</div>
        <h1 className="font-sans text-[34px] font-bold text-gray-900 tracking-tight leading-none">
          {id}
        </h1>
        <p className="mt-2 font-sans text-[14px] text-text-secondary">
          {label.origin} to {label.destination}
        </p>
      </div>

      {/* KPI Strip */}
      <section className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 gap-3">
        {kpis.map((kpi) => {
          let color = "text-gray-900";
          if (kpi.isChange) {
            color = kpi.raw > 0 ? "text-danger" : kpi.raw < 0 ? "text-success" : "text-gray-900";
          }
          return (
            <div key={kpi.label} className="rounded-xl bg-white border border-border p-4 shadow-[0_8px_24px_rgba(32,23,63,0.05)]">
              <div className="font-sans text-[10px] uppercase font-semibold text-text-secondary tracking-[0.05em]">
                {kpi.label}
              </div>
              <div className={`mt-1 font-mono text-[24px] font-bold tabular-nums leading-tight ${color}`}>
                {kpi.value}
              </div>
            </div>
          );
        })}
      </section>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Main Chart Column */}
        <div className="lg:col-span-2 space-y-6">
          <section className="overflow-hidden rounded-2xl bg-white border border-border shadow-[0_10px_32px_rgba(32,23,63,0.06)]">
            <div className="flex items-center justify-between border-b border-border p-4 pb-3">
              <div>
                <h2 className="font-sans text-[14px] font-semibold uppercase tracking-[0.05em] text-text-secondary">
                  FARE HISTORY
                </h2>
                <h3 className="font-sans text-[13px] font-medium text-text-secondary mt-0.5">
                  30-day observed fare series
                </h3>
              </div>
              <select 
                value={apFilter}
                onChange={(e) => setApFilter(e.target.value)}
                className="font-sans text-[12px] border border-border rounded-sm px-2 py-1 bg-bg-alt text-text-secondary focus:outline-none"
              >
                <option value="all">Default AP Window</option>
                {data.map(d => (
                  <option key={d.apWindow} value={d.apWindow}>{d.apWindow}</option>
                ))}
              </select>
            </div>

            <div className="p-4">
              {historyData.length === 0 ? (
                <div className="flex h-[320px] items-center justify-center font-sans text-[12px] text-gray-400">
                  No fare history available.
                </div>
              ) : (
                <ResponsiveContainer width="100%" height={320}>
                  <LineChart
                    data={historyData}
                    margin={{ top: 8, right: 24, bottom: 8, left: 8 }}
                  >
                    <CartesianGrid stroke="var(--color-border)" strokeDasharray="3 3" vertical={false} />
                    <XAxis
                      dataKey="date"
                      tick={{ fontFamily: "IBM Plex Mono", fontSize: 10, fill: "var(--color-text-secondary)" }}
                      tickLine={false}
                      axisLine={{ stroke: "var(--color-border)" }}
                      interval={4}
                    />
                    <YAxis
                      tickFormatter={(v) => `₹${Math.round(v / 1000)}k`}
                      tick={{ fontFamily: "IBM Plex Mono", fontSize: 10, fill: "var(--color-text-secondary)" }}
                      tickLine={false}
                      axisLine={false}
                      width={52}
                    />
                    <Tooltip content={<CustomTooltip />} />
                    <Line
                      type="monotone"
                      dataKey="fare"
                      stroke="var(--color-accent)"
                      strokeWidth={1.5}
                      dot={{ r: 3, fill: "var(--color-accent)", strokeWidth: 0 }}
                      activeDot={{ r: 5, fill: "var(--color-accent)", strokeWidth: 0 }}
                      isAnimationActive={false}
                    />
                  </LineChart>
                </ResponsiveContainer>
              )}
            </div>
            
            <div className="border-t border-border px-4 py-3 bg-bg-alt">
              <p className="font-sans text-[10px] text-text-secondary">
                Data reflects minimum available economy direct fares.
              </p>
            </div>
          </section>

          {/* AP Windows Table */}
          <section className="overflow-hidden rounded-2xl bg-white border border-border shadow-[0_10px_32px_rgba(32,23,63,0.06)]">
            <div className="border-b border-border p-4 pb-3">
              <h2 className="font-sans text-[14px] font-semibold uppercase tracking-[0.05em] text-text-secondary">
                ADVANCE PURCHASE WINDOWS
              </h2>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full text-left font-sans text-[12px]">
                <thead className="bg-bg-alt border-b border-border">
                  <tr>
                    <th className="py-2 px-4 font-semibold text-text-secondary uppercase tracking-wide text-[10px]">AP Window</th>
                    <th className="py-2 px-4 font-semibold text-text-secondary uppercase tracking-wide text-[10px] text-right">Base Fare</th>
                    <th className="py-2 px-4 font-semibold text-text-secondary uppercase tracking-wide text-[10px] text-right">Current Fare</th>
                    <th className="py-2 px-4 font-semibold text-text-secondary uppercase tracking-wide text-[10px] text-right">7D Chg</th>
                    <th className="py-2 px-4 font-semibold text-text-secondary uppercase tracking-wide text-[10px] text-right">Weight</th>
                  </tr>
                </thead>
                <tbody>
                  {data.map((item, i) => {
                    const c7 = item.change7d;
                    const c7Color = c7 > 0 ? "text-danger" : c7 < 0 ? "text-success" : "text-gray-900";
                    return (
                      <tr key={item.apWindow} className={`border-b border-border ${i % 2 === 1 ? 'bg-bg-alt/40' : 'bg-white'}`}>
                        <td className="py-2.5 px-4 font-semibold text-gray-800">{item.apWindow}</td>
                        <td className="py-2.5 px-4 text-right font-mono tabular-nums text-text-secondary">₹{item.baseFare.toLocaleString()}</td>
                        <td className="py-2.5 px-4 text-right font-mono tabular-nums text-gray-900 font-medium">₹{item.currentFare.toLocaleString()}</td>
                        <td className={`py-2.5 px-4 text-right font-mono tabular-nums ${c7Color}`}>
                          {c7 > 0 ? '▲ +' : c7 < 0 ? '▼ ' : ''}{Math.abs(c7).toFixed(2)}%
                        </td>
                        <td className="py-2.5 px-4 text-right font-mono tabular-nums text-text-secondary">{item.weight?.toFixed(4)}</td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          </section>
        </div>

        {/* Metadata Panel Column */}
        <div className="lg:col-span-1">
          <section className="bg-white border border-border sticky top-[80px]">
            <div className="border-b border-border p-4 pb-3 bg-bg-alt">
              <h2 className="font-sans text-[14px] font-semibold uppercase tracking-[0.05em] text-text-secondary">
                ROUTE CHARACTERISTICS
              </h2>
            </div>
            <div className="p-4">
              <dl className="space-y-4 font-sans text-[12px]">
                <div>
                  <dt className="text-[10px] font-semibold text-text-secondary uppercase tracking-wide mb-1">Distance</dt>
                  <dd className="text-gray-900 font-medium">{label.dist}</dd>
                </div>
                <hr className="border-border" />
                <div>
                  <dt className="text-[10px] font-semibold text-text-secondary uppercase tracking-wide mb-1">Carrier Count</dt>
                  <dd className="text-gray-900 font-medium">{label.carriers} Active Carriers</dd>
                </div>
                <hr className="border-border" />
                <div>
                  <dt className="text-[10px] font-semibold text-text-secondary uppercase tracking-wide mb-1">Competition Index</dt>
                  <dd className="text-gray-900 font-medium">{label.competition}</dd>
                </div>
                <hr className="border-border" />
                <div>
                  <dt className="text-[10px] font-semibold text-text-secondary uppercase tracking-wide mb-1">Seasonal Factors</dt>
                  <dd className="text-gray-900 font-medium">{label.season}</dd>
                </div>
              </dl>
            </div>
            <div className="border-t border-border bg-bg-alt p-4">
              <a href="#" className="font-sans text-[12px] font-medium text-primary hover:underline flex items-center justify-between">
                <span>View Methodology</span>
                <span>→</span>
              </a>
            </div>
          </section>
        </div>
      </div>
    </div>
  );
}

