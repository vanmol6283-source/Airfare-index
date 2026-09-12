import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { getDataQuality, triggerTargetedScrape } from "../api";
import ProvenancePanel from "../components/data-quality/ProvenancePanel";

function StatBox({ label, value, sub }) {
  return (
    <div className="rounded-xl border border-border bg-white px-5 py-4 shadow-[0_8px_24px_rgba(32,23,63,0.05)]">
      <div className="font-sans text-[11px] font-bold uppercase tracking-wider text-text-secondary mb-2">
        {label}
      </div>
      <div className="font-mono text-[28px] font-bold tabular-nums text-gray-900 leading-none">
        {value}
      </div>
      {sub && (
        <div className="mt-2 font-sans text-[12px] text-gray-400">{sub}</div>
      )}
    </div>
  );
}

export default function DataQuality() {
  const [triggerStatus, setTriggerStatus] = useState({ web: false, api: false });
  const { data, isLoading, isError } = useQuery({
    queryKey: ["dataQuality"],
    queryFn: getDataQuality,
  });

  const handleTrigger = async (type) => {
    setTriggerStatus(prev => ({ ...prev, [type]: "loading" }));
    try {
      await triggerTargetedScrape(type);
      setTriggerStatus(prev => ({ ...prev, [type]: "success" }));
      setTimeout(() => setTriggerStatus(prev => ({ ...prev, [type]: false })), 3000);
    } catch (e) {
      console.error(e);
      setTriggerStatus(prev => ({ ...prev, [type]: "error" }));
      setTimeout(() => setTriggerStatus(prev => ({ ...prev, [type]: false })), 3000);
    }
  };

  const totalCollected = data?.reduce((s, r) => s + r.quotesCollected, 0);
  const totalRejected = data?.reduce((s, r) => s + r.quotesRejected, 0);
  const overallRejRate =
    totalCollected > 0
      ? ((totalRejected / totalCollected) * 100).toFixed(2)
      : "0.00";
  const avgDeviation =
    data?.length > 0
      ? (
          data.reduce((s, r) => s + r.backTestDeviationPct, 0) /
          data.length
        ).toFixed(2)
      : "—";

  return (
    <div data-page="quality" className="w-full max-w-[1200px] mx-auto space-y-8">
      <header className="relative overflow-hidden rounded-2xl border border-border bg-gradient-to-br from-white to-[#f4eefb] px-6 py-6 shadow-[0_12px_35px_rgba(32,23,63,0.07)]">
        <div className="flex flex-col sm:flex-row justify-between items-start sm:items-end">
          <div>
            <div className="mb-2 text-[10px] font-bold uppercase tracking-[0.2em] text-primary">TRUST & PROVENANCE</div>
            <h1 className="font-sans text-[36px] font-bold text-gray-900 tracking-tight">
              Data Quality
            </h1>
            <p className="mt-2 font-sans text-[16px] text-text-secondary">
              Provenance, collection statistics and quality indicators
            </p>
          </div>
          
          <div className="mt-4 sm:mt-0 flex gap-3">
            <button 
              onClick={() => handleTrigger('web')}
              disabled={triggerStatus.web}
              className="bg-primary hover:bg-primary-dark text-white px-4 py-2 rounded-lg font-sans text-[13px] font-semibold transition disabled:opacity-50"
            >
              {triggerStatus.web === 'loading' ? 'Triggering...' : 
               triggerStatus.web === 'success' ? 'Triggered!' :
               triggerStatus.web === 'error' ? 'Error' : 'Web Scrape'}
            </button>
            <button 
              onClick={() => handleTrigger('api')}
              disabled={triggerStatus.api}
              className="bg-primary hover:bg-primary-dark text-white px-4 py-2 rounded-lg font-sans text-[13px] font-semibold transition disabled:opacity-50"
            >
              {triggerStatus.api === 'loading' ? 'Triggering...' : 
               triggerStatus.api === 'success' ? 'Triggered!' :
               triggerStatus.api === 'error' ? 'Error' : 'API Fetch'}
            </button>
          </div>
        </div>
      </header>

      {/* Summary stats */}
      {data && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <StatBox
            label="Total Quotes Collected"
            value={totalCollected?.toLocaleString("en-IN")}
            sub="All sources combined"
          />
          <StatBox
            label="Total Quotes Rejected"
            value={totalRejected?.toLocaleString("en-IN")}
            sub="Failed validation checks"
          />
          <StatBox
            label="Overall Rejection Rate"
            value={`${overallRejRate}%`}
            sub="Rejected / collected"
          />
          <StatBox
            label="Avg. Back-Test Deviation"
            value={`±${avgDeviation}%`}
            sub="Mean absolute deviation"
          />
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        <div className="lg:col-span-2 space-y-8">
          {/* Provenance table */}
          <section className="border border-border bg-white shadow-[0_8px_30px_rgba(32,23,63,0.055)]">

            {isLoading && (
              <div className="px-6 py-12 flex justify-center font-sans text-[14px] text-gray-400">
                Loading quality data…
              </div>
            )}

            {isError && (
              <div className="px-6 py-12 flex justify-center font-sans text-[14px] text-danger">
                Unable to load quality data.
              </div>
            )}

            {data && <ProvenancePanel stats={data} />}
          </section>
        </div>

        <div className="lg:col-span-1">
          {/* Quality framework */}
          <section className="border border-border bg-white shadow-[0_8px_30px_rgba(32,23,63,0.055)] sticky top-[88px]">
            <div className="border-b border-border px-6 py-4 bg-bg-alt">
              <h2 className="font-sans text-[16px] font-bold text-gray-900">
                Quality Assurance Framework
              </h2>
            </div>
            <div className="px-6 py-5 space-y-6">
              {[
                {
                  title: "Validity Checks",
                  items: [
                    "Fare must be positive and non-zero",
                    "Fare must fall within route-specific bounds",
                    "Itinerary must match requested route",
                    "Departure date must match AP window",
                  ],
                },
                {
                  title: "Consistency Checks",
                  items: [
                    "Same route/window observed from ≥2 sources",
                    "Day-on-day change ≤ 60% (flag for review)",
                    "Missing observations flagged, not imputed",
                    "Back-test deviation monitored monthly",
                  ],
                },
                {
                  title: "Back-Test Protocol",
                  items: [
                    "Index reconstructed on 90-day rolling window",
                    "Compared to independent reference prices",
                    "Deviation threshold: ±2% triggers review",
                    "Back-test results published quarterly",
                  ],
                },
                {
                  title: "Data Gaps",
                  items: [
                    "If ≥ 50% of basket items missing: index not published",
                    "Individual item gaps: item excluded from that day's index",
                    "Weight denominator adjusted accordingly",
                    "Gap flags retained in the data record",
                  ],
                },
              ].map(({ title, items }) => (
                <div key={title}>
                  <h3 className="font-sans text-[13px] font-bold text-gray-900 mb-2">{title}</h3>
                  <ul className="space-y-1.5 border-l-2 border-border pl-3">
                    {items.map((item, i) => (
                      <li key={i} className="font-sans text-[13px] text-text-secondary leading-snug">
                        {item}
                      </li>
                    ))}
                  </ul>
                </div>
              ))}
            </div>
          </section>
        </div>
      </div>
    </div>
  );
}

