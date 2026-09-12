/**
 * Routes.jsx — Full basket table
 *
 * Shows all basket items with TanStack Table v8:
 * sorting, filtering, density toggle, CSV export.
 */

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { getBasketItems } from "../api";
import DataTable from "../components/table/DataTable";
import { routeTableColumns } from "../components/table/RouteTableColumns";
import DensityToggle from "../components/table/DensityToggle";
import ExportButton from "../components/shared/ExportButton";
import IndexLineChart from "../components/charts/IndexLineChart";

export default function Routes() {
  const [density, setDensity] = useState("comfortable");
  const [globalFilter, setGlobalFilter] = useState("");

  const { data, isLoading, isError } = useQuery({
    queryKey: ["basket"],
    queryFn: getBasketItems,
  });

  // Flatten for CSV export (no nested history)
  // Strip nested history array from CSV export (not useful in tabular form)
  const exportData = data?.map((item) => {
    const copy = { ...item };
    delete copy.history;
    return copy;
  }) ?? [];

  return (
    <div data-page="routes" className="w-full max-w-[1200px] mx-auto px-1 sm:px-2 space-y-4">
      {/* Page header */}
      <div className="relative overflow-hidden rounded-xl border border-primary/20 bg-gradient-to-br from-white via-white to-bg-alt px-6 py-6 shadow-[0_6px_20px_rgba(0,102,102,0.06)]">
        <div>
          <div className="mb-2 text-[10px] font-bold uppercase tracking-[0.2em] text-primary">ROUTE INTELLIGENCE</div>
          <h1 className="font-sans text-[28px] sm:text-[34px] font-black text-primary-dark tracking-tight">
            Monitored Basket
          </h1>
          <p className="mt-2 font-sans text-[14px] text-text-secondary">
            All route × advance-purchase window observations
          </p>
        </div>
      </div>

      {/* APIx Trend Chart */}
      <div className="h-[340px] rounded-xl overflow-hidden shadow-[0_6px_20px_rgba(0,102,102,0.06)] border border-primary/20 bg-white">
        <IndexLineChart />
      </div>

      {/* Controls bar */}
      <section className="overflow-hidden rounded-xl border border-primary/20 bg-white shadow-[0_6px_20px_rgba(0,102,102,0.06)]">
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-primary/10 px-6 py-4 bg-bg-alt">
          <div className="flex items-center gap-4">
            <DensityToggle density={density} onChange={setDensity} />
            <input
              type="text"
              value={globalFilter}
              onChange={(e) => setGlobalFilter(e.target.value)}
              placeholder="Filter routes…"
              className="border border-primary/30 bg-white px-3 py-1.5 font-sans text-[12px] text-primary-dark placeholder-[var(--color-primary)]/50 focus:outline-none focus:border-primary focus:ring-1 focus:ring-primary rounded-lg w-full sm:w-[220px]"
            />
          </div>
          <ExportButton
            data={exportData}
            filename="airfare_basket"
          />
        </div>

        {isLoading && (
          <div className="px-6 py-12 flex justify-center font-sans text-[13px] text-[#9a97aa]">
            Loading basket data…
          </div>
        )}

        {isError && (
          <div className="px-6 py-12 flex justify-center font-sans text-[13px] text-accent">
            Unable to load basket data.
          </div>
        )}

        {data && (
          <DataTable
            data={data}
            columns={routeTableColumns}
            density={density}
            globalFilter={globalFilter}
            onGlobalFilterChange={setGlobalFilter}
          />
        )}

        {data && (
          <div className="border-t border-primary/10 px-6 py-3 bg-bg-alt">
            <p className="font-sans text-[10px] text-primary/70">
              Showing {data.length} basket items. Click column headers to sort. Click route code to view detail.
            </p>
          </div>
        )}
      </section>
    </div>
  );
}
