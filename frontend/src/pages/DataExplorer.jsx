import { useState, useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { 
  useReactTable, 
  getCoreRowModel, 
  getSortedRowModel, 
  flexRender,
  getPaginationRowModel
} from "@tanstack/react-table";
import {
  ResponsiveContainer,
  LineChart,
  Line,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend
} from "recharts";
import { getBasketItems } from "../api";
import FilterPanel from "../components/explorer/FilterPanel";
import ExportButton from "../components/shared/ExportButton";

const CHART_PALETTE = [
  "var(--color-chart-1)",
  "var(--color-chart-2)",
  "var(--color-chart-3)",
  "var(--color-chart-4)",
  "var(--color-chart-5)",
  "var(--color-chart-6)",
  "var(--color-chart-7)",
  "var(--color-chart-8)",
];

export default function DataExplorer() {
  const [activeFilters, setActiveFilters] = useState({
    routes: [],
    origins: [],
    destinations: [],
    apWindows: []
  });
  const [hideEmpty, setHideEmpty] = useState(false);
  const [viewMode, setViewMode] = useState("chart"); // "chart", "bar", "table", "heatmap"

  const { data: basket, isLoading } = useQuery({
    queryKey: ["basket"],
    queryFn: getBasketItems,
  });

  // Filter data based on active filters
  const filteredData = useMemo(() => {
    if (!basket) return [];
    return basket.filter(item => {
      const matchRoute = activeFilters.routes.length === 0 || activeFilters.routes.includes(item.route);
      const matchOrigin = activeFilters.origins.length === 0 || activeFilters.origins.includes(item.origin);
      const matchDest = activeFilters.destinations.length === 0 || activeFilters.destinations.includes(item.destination);
      const matchAp = activeFilters.apWindows.length === 0 || activeFilters.apWindows.includes(item.apWindow);
      return matchRoute && matchOrigin && matchDest && matchAp;
    });
  }, [basket, activeFilters]);

  const removeFilter = (type, value) => {
    setActiveFilters(prev => ({
      ...prev,
      [type]: prev[type].filter(v => v !== value)
    }));
  };

  const clearAllFilters = () => {
    setActiveFilters({
      routes: [],
      origins: [],
      destinations: [],
      apWindows: []
    });
  };

  // Transform data for multi-series chart
  // Group by date, then add each route's apix value
  const chartData = useMemo(() => {
    if (!filteredData.length) return [];
    const dateMap = {};
    
    // Using history from items
    filteredData.forEach(item => {
      if (item.history) {
        item.history.forEach(h => {
          if (!dateMap[h.date]) {
            dateMap[h.date] = { date: h.date };
          }
          dateMap[h.date][item.route] = h.fare;
        });
      }
    });

    return Object.values(dateMap).sort((a, b) => a.date.localeCompare(b.date));
  }, [filteredData]);

  const chartKeys = useMemo(() => {
    const keys = new Set();
    filteredData.forEach(item => keys.add(item.route));
    return Array.from(keys);
  }, [filteredData]);

  // Table setup
  const [sorting, setSorting] = useState([]);
  const columns = [
    { accessorKey: "route", header: "ROUTE" },
    { accessorKey: "origin", header: "ORIGIN" },
    { accessorKey: "destination", header: "DESTINATION" },
    { accessorKey: "apWindow", header: "AP WINDOW" },
    { accessorKey: "baseFare", header: () => <div className="text-right">BASE FARE</div>, cell: info => <div className="text-right font-mono">₹{info.getValue().toLocaleString()}</div> },
    { accessorKey: "currentFare", header: () => <div className="text-right">CURRENT FARE</div>, cell: info => <div className="text-right font-mono">₹{info.getValue().toLocaleString()}</div> },
    { accessorKey: "change30d", header: () => <div className="text-right">30D CHG</div>, cell: info => <div className="text-right font-mono">{info.getValue()}%</div> }
  ];

  const table = useReactTable({
    data: filteredData,
    columns,
    state: { sorting },
    onSortingChange: setSorting,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    getPaginationRowModel: getPaginationRowModel(),
  });

  return (
    <div
      data-page="explorer"
      className="flex min-h-[calc(100vh-130px)] flex-col md:flex-row mt-[-24px] mx-[-12px] md:mx-[-24px] border-t border-primary/20"
    >
      {/* Sidebar Filter Panel */}
      <div className="w-full md:w-[300px] flex-shrink-0 bg-white border-b md:border-b-0 md:border-r border-primary/20 md:h-full overflow-y-auto">
        <FilterPanel
          basket={basket || []}
          activeFilters={activeFilters}
          setActiveFilters={setActiveFilters}
          hideEmpty={hideEmpty}
          setHideEmpty={setHideEmpty}
          clearAllFilters={clearAllFilters}
        />
      </div>

      {/* Main Data View */}
      <div className="flex-1 min-w-0 p-3 sm:p-4 md:p-6 overflow-y-auto bg-white flex flex-col gap-4">

        {/* Explorer Header */}
        <div className="relative overflow-hidden rounded-xl border border-primary/20 bg-gradient-to-br from-white to-bg-alt px-5 py-4 shadow-[0_6px_20px_rgba(0,102,102,0.06)]">
          <div className="text-[10px] font-bold uppercase tracking-[0.2em] text-primary">DATA INTELLIGENCE</div>
          <div className="mt-1 flex flex-col gap-1 sm:flex-row sm:items-end sm:justify-between">
            <div>
              <h1 className="font-sans text-[24px] font-black tracking-tight text-primary-dark">Data Explorer</h1>
              <p className="mt-1 font-sans text-[12px] text-text-secondary">Filter, compare and visualise monitored airfare observations.</p>
            </div>
            <div className="font-mono text-[10px] font-semibold text-primary">EXPLORE → COMPARE → INSPECT</div>
          </div>
        </div>

        {/* Active Filter Pill Bar */}
        <div className="bg-white border border-primary/20 rounded-lg p-3 flex flex-wrap gap-2 items-center min-h-[46px]">
          {Object.entries(activeFilters).every(([, vals]) => vals.length === 0) ? (
            <span className="font-sans text-[11px] text-primary/60">All data — no filters applied</span>
          ) : (
            <>
              {Object.entries(activeFilters).map(([type, values]) =>
                values.map((val) => (
                  <div
                    key={`${type}-${val}`}
                    className="flex items-center gap-1 bg-bg-alt text-primary border border-primary/30 rounded-full px-2.5 py-0.5 font-sans text-[11px]"
                  >
                    <span>
                      {type === "apWindows" ? "AP" : type.charAt(0).toUpperCase() + type.slice(1).replace(/s$/, "")}: {val}
                    </span>
                    <button
                      onClick={() => removeFilter(type, val)}
                      className="hover:text-primary-dark ml-0.5 font-bold"
                      aria-label={`Remove filter ${val}`}
                    >
                      ×
                    </button>
                  </div>
                ))
              )}
              <button
                onClick={clearAllFilters}
                className="ml-auto text-[10px] font-semibold text-primary hover:text-primary-dark hover:underline"
              >
                Clear all
              </button>
            </>
          )}
        </div>

        {/* View Toggle Toolbar + Download */}
        <div className="flex items-center justify-between gap-3">
          <div className="flex items-center border border-primary/20 bg-white w-fit rounded-lg overflow-hidden shadow-sm">
            {[
              { id: "chart",   label: "Line Chart",  icon: "▱" },
              { id: "bar",     label: "Bar Chart",   icon: "▥" },
              { id: "table",   label: "Data Table",  icon: "▤" },
              { id: "heatmap", label: "Heatmap",     icon: "▣" },
            ].map((m, i, arr) => (
              <button
                key={m.id}
                onClick={() => setViewMode(m.id)}
                className={`px-4 py-2 text-[11px] font-bold flex items-center gap-1.5 transition-colors ${
                  viewMode === m.id
                    ? "bg-primary hover:bg-primary-dark text-white"
                    : "bg-white text-primary hover:bg-bg-alt"
                } ${i < arr.length - 1 ? "border-r border-primary/20" : ""}`}
              >
                <span className="text-[13px]">{m.icon}</span>
                <span className="hidden sm:inline">{m.label}</span>
              </button>
            ))}
          </div>
          <ExportButton
            data={filteredData.map(({ history, ...rest }) => rest)}
            filename="airfare_data"
            headers={["route", "origin", "destination", "apWindow", "baseFare", "currentFare", "priceRelative", "weight", "change7d", "change30d", "dataPoints"]}
          />
        </div>

        {/* Content Area */}
        <div className="bg-white border border-primary/20 rounded-xl flex-1 min-h-[400px] flex flex-col overflow-hidden shadow-[0_6px_20px_rgba(0,102,102,0.06)]">
          {isLoading ? (
            <div className="flex-1 flex items-center justify-center font-sans text-[12px] text-primary/60">Loading data…</div>
          ) : filteredData.length === 0 ? (
            <div className="flex-1 flex items-center justify-center font-sans text-[12px] text-primary/60">No data matches the selected filters.</div>
          ) : (
            <>
              {viewMode === "chart" && (
                <div className="p-4 flex-1" style={{ minHeight: 420 }}>
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={chartData} margin={{ top: 20, right: 30, left: 20, bottom: 5 }}>
                      <CartesianGrid strokeDasharray="3 5" vertical={false} stroke="rgba(15, 92, 92, 0.15)" />
                      <XAxis dataKey="date" tick={{ fontFamily: "IBM Plex Mono", fontSize: 9, fill: "var(--color-primary)" }} tickLine={false} axisLine={{ stroke: "rgba(15, 92, 92, 0.20)" }} />
                      <YAxis tick={{ fontFamily: "IBM Plex Mono", fontSize: 9, fill: "var(--color-primary)" }} tickLine={false} axisLine={false} />
                      <Tooltip contentStyle={{ fontFamily: "IBM Plex Mono", fontSize: "11px", border: "1px solid rgba(15, 92, 92, 0.20)", borderRadius: "8px" }} />
                      <Legend wrapperStyle={{ fontFamily: "Public Sans", fontSize: "11px" }} />
                      {chartKeys.map((key, i) => (
                        <Line key={key} type="monotone" dataKey={key} stroke={CHART_PALETTE[i % CHART_PALETTE.length]} dot={false} activeDot={{ r: 4 }} strokeWidth={2} />
                      ))}
                    </LineChart>
                  </ResponsiveContainer>
                </div>
              )}

              {viewMode === "bar" && (
                <div className="p-4 flex-1" style={{ minHeight: 420 }}>
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={filteredData} margin={{ top: 20, right: 30, left: 20, bottom: 5 }}>
                      <CartesianGrid strokeDasharray="3 5" vertical={false} stroke="rgba(15, 92, 92, 0.15)" />
                      <XAxis dataKey="route" tick={{ fontFamily: "IBM Plex Mono", fontSize: 9, fill: "var(--color-primary)" }} tickLine={false} axisLine={{ stroke: "rgba(15, 92, 92, 0.20)" }} />
                      <YAxis tick={{ fontFamily: "IBM Plex Mono", fontSize: 9, fill: "var(--color-primary)" }} tickLine={false} axisLine={false} tickFormatter={v => `₹${v.toLocaleString("en-IN")}`} />
                      <Tooltip contentStyle={{ fontFamily: "IBM Plex Mono", fontSize: "11px", border: "1px solid rgba(15, 92, 92, 0.20)", borderRadius: "8px" }} formatter={v => [`₹${v.toLocaleString("en-IN")}`, "Current Fare"]} />
                      <Bar dataKey="currentFare" fill="var(--color-accent)" radius={[4, 4, 0, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              )}

              {viewMode === "table" && (
                <div className="flex-1 flex flex-col">
                  <div className="flex-1 overflow-auto">
                    <table className="w-full border-collapse">
                      <thead className="bg-bg-alt border-b border-primary/10 sticky top-0">
                        {table.getHeaderGroups().map((hg) => (
                          <tr key={hg.id}>
                            {hg.headers.map((h) => (
                              <th
                                key={h.id}
                                onClick={h.column.getToggleSortingHandler()}
                                className="px-4 py-2.5 text-left text-[9px] font-black uppercase tracking-[0.08em] text-primary-dark cursor-pointer hover:bg-primary/10"
                              >
                                <div className="flex items-center gap-1">
                                  {flexRender(h.column.columnDef.header, h.getContext())}
                                  <span className="text-[8px]">
                                    {h.column.getIsSorted() === "asc" ? " ▲" : h.column.getIsSorted() === "desc" ? " ▼" : ""}
                                  </span>
                                </div>
                              </th>
                            ))}
                          </tr>
                        ))}
                      </thead>
                      <tbody>
                        {table.getRowModel().rows.map((row, i) => (
                          <tr key={row.id} className={`border-b border-primary/10 ${i % 2 === 0 ? "bg-white" : "bg-bg-alt/30"} hover:bg-bg-alt`}>
                            {row.getVisibleCells().map((cell) => (
                              <td key={cell.id} className="px-4 py-2 font-sans text-[11px] text-primary-dark">
                                {flexRender(cell.column.columnDef.cell, cell.getContext())}
                              </td>
                            ))}
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                  <div className="p-3 border-t border-primary/10 flex justify-between items-center bg-bg-alt text-[11px] font-sans">
                    <div className="text-primary/60">
                      Showing {table.getRowModel().rows.length} of {filteredData.length} entries
                    </div>
                    <div className="flex gap-2">
                      <button
                        onClick={() => table.previousPage()}
                        disabled={!table.getCanPreviousPage()}
                        className="px-3 py-1 border border-primary/20 rounded bg-white text-primary-dark disabled:opacity-40 hover:bg-primary/10"
                      >
                        Prev
                      </button>
                      <button
                        onClick={() => table.nextPage()}
                        disabled={!table.getCanNextPage()}
                        className="px-3 py-1 border border-primary/20 rounded bg-white text-primary-dark disabled:opacity-40 hover:bg-primary/10"
                      >
                        Next
                      </button>
                    </div>
                  </div>
                </div>
              )}

              {viewMode === "heatmap" && (
                <div className="p-6 flex-1 overflow-auto">
                  <div className="grid gap-1" style={{gridTemplateColumns: `auto repeat(${chartData.length}, minmax(40px, 1fr))`}}>
                    <div className="sticky left-0 bg-white z-10"></div>
                    {chartData.map(d => (
                      <div key={d.date} className="text-center font-mono text-[9px] text-text-secondary transform -rotate-45 origin-bottom-left mb-2">{d.date.slice(5)}</div>
                    ))}
                    
                    {chartKeys.map(route => {
                      const maxFare = Math.max(...chartData.map(d => d[route] || 0));
                      const minFare = Math.min(...chartData.map(d => d[route] || Infinity).filter(v => v > 0));
                      
                      return (
                        <div key={route} className="contents">
                          <div className="sticky left-0 bg-white z-10 font-mono text-[11px] font-semibold flex items-center pr-2">{route}</div>
                          {chartData.map(d => {
                            const val = d[route];
                            let bg = "bg-gray-100";
                            if (val) {
                              // Simple diverging color logic for demo
                              const rel = (val - minFare) / (maxFare - minFare || 1);
                              if (rel > 0.8) bg = "bg-red-700";
                              else if (rel > 0.6) bg = "bg-red-400";
                              else if (rel > 0.4) bg = "bg-yellow-200";
                              else if (rel > 0.2) bg = "bg-green-400";
                              else bg = "bg-green-700";
                            }
                            return <div key={`${route}-${d.date}`} className={`h-8 ${bg} rounded-sm group relative`}>
                              {val && (
                                <div className="absolute hidden group-hover:block bottom-full mb-1 left-1/2 transform -translate-x-1/2 bg-primary-dark text-white text-[10px] py-1 px-2 rounded whitespace-nowrap z-20 font-mono">
                                  ₹{val.toLocaleString()}
                                </div>
                              )}
                            </div>
                          })}
                        </div>
                      )
                    })}
                  </div>
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}
