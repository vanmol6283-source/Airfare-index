import { useQuery } from "@tanstack/react-query";
import { Link, useNavigate } from "react-router-dom";
import { useState, useMemo, useRef, useCallback } from "react";
import { useReactTable, getCoreRowModel, getSortedRowModel, flexRender } from "@tanstack/react-table";
import { getSummary, getBasketItems } from "../api";
import { TrendingUp } from "lucide-react";
import SummaryStrip from "../components/layout/SummaryStrip";
import IndexLineChart from "../components/charts/IndexLineChart";
import Sparkline from "../components/charts/Sparkline";
import india from "@svg-maps/india";

const AIRPORTS = {
  "DEL": { lat: 28.5562, lng: 77.1000 },
  "BOM": { lat: 19.0896, lng: 72.8656 },
  "BLR": { lat: 13.1986, lng: 77.7066 },
  "HYD": { lat: 17.2403, lng: 78.4294 },
  "MAA": { lat: 12.9941, lng: 80.1709 },
  "CCU": { lat: 22.6520, lng: 88.4467 },
  "AMD": { lat: 23.0734, lng: 72.6346 },
  "PNQ": { lat: 18.5793, lng: 73.9089 },
  "GOX": { lat: 15.7320, lng: 73.8711 },
  "GOI": { lat: 15.3803, lng: 73.8313 },
  "COK": { lat: 10.1518, lng: 76.3930 },
  "LKO": { lat: 26.7606, lng: 80.8893 },
  "ATQ": { lat: 31.7096, lng: 74.7973 },
  "PAT": { lat: 25.5913, lng: 85.0881 },
  "IXC": { lat: 30.6735, lng: 76.7885 },
  "TRV": { lat: 8.4821, lng: 76.9200 },
  "SXR": { lat: 33.9980, lng: 74.7745 },
  "JAI": { lat: 26.8242, lng: 75.8122 }
};

export default function Overview() {
  const [sorting, setSorting] = useState([]);
  const [density, setDensity] = useState("sm");
  const navigate = useNavigate();

  const summaryQ = useQuery({ queryKey: ["summary"], queryFn: getSummary });
  const basketQ = useQuery({ queryKey: ["basket"], queryFn: getBasketItems });

  const columns = [
    { accessorKey: "route", header: "ROUTE", cell: info => <Link to={`/route/${info.getValue()}`} className="font-sans font-bold text-primary hover:text-primary-dark hover:underline">{info.getValue()}</Link> },
    { accessorKey: "apWindow", header: "AP WINDOW", cell: info => <span className="font-sans text-text-secondary">{info.getValue()}</span> },
    { accessorKey: "baseFare", header: () => <div className="text-right">BASE FARE</div>, cell: info => <div className="text-right font-mono tabular-nums text-text-primary">₹{info.getValue().toLocaleString("en-IN")}</div> },
    { accessorKey: "currentFare", header: () => <div className="text-right">CURRENT FARE</div>, cell: info => <div className="text-right font-mono font-semibold tabular-nums text-text-primary">₹{info.getValue().toLocaleString("en-IN")}</div> },
    { accessorKey: "change7d", header: () => <div className="text-right">7D CHG.</div>, cell: info => { const val = info.getValue(); if (val == null) return <div className="text-right text-text-secondary">—</div>; const color = val > 0 ? "text-danger" : val < 0 ? "text-success" : "text-text-primary"; return <div className={`text-right font-mono font-semibold tabular-nums ${color}`}>{val > 0 ? "▲ +" : val < 0 ? "▼ " : ""}{Math.abs(val).toFixed(2)}%</div>; } },
    { id: "trend30d", header: "30D TREND", cell: info => <Sparkline data={info.row.original.history} width={70} height={24} /> },
    { id: "detail", header: "", cell: info => <Link to={`/route/${info.row.original.route}`} className="font-mono text-primary hover:underline">→</Link> },
  ];

  // Filter out 0% change and nulls, group by route to prevent repeats, and get top 4
  const topMovers = useMemo(() => {
    if (!basketQ.data) return [];
    
    // Sort all by absolute change
    const valid = basketQ.data
      .filter(item => item.change7d != null && item.change7d !== 0)
      .sort((a, b) => Math.abs(b.change7d) - Math.abs(a.change7d));
      
    // Deduplicate so a route only appears once
    const seenRoutes = new Set();
    const uniqueMovers = [];
    for (const item of valid) {
      if (!seenRoutes.has(item.route)) {
        seenRoutes.add(item.route);
        uniqueMovers.push(item);
      }
    }
    
    return uniqueMovers.slice(0, 4);
  }, [basketQ.data]);
  const table = useReactTable({ data: basketQ.data ?? [], columns, state: { sorting }, onSortingChange: setSorting, getCoreRowModel: getCoreRowModel(), getSortedRowModel: getSortedRowModel() });

  // Generate polylines for map
  const routeLines = useMemo(() => {
    if (!basketQ.data) return [];
    
    // Get unique routes
    const uniqueRoutes = new Set(basketQ.data.map(d => d.route));
    const lines = [];
    
    uniqueRoutes.forEach(r => {
      const [origin, dest] = r.split('-');
      if (AIRPORTS[origin] && AIRPORTS[dest]) {
        lines.push({
          id: r,
          path: [AIRPORTS[origin], AIRPORTS[dest]]
        });
      }
    });
    
    return lines;
  }, [basketQ.data]);

  const uniqueAirports = useMemo(() => {
    const airports = new Set();
    routeLines.forEach(line => {
      const [origin, dest] = line.id.split('-');
      airports.add(origin);
      airports.add(dest);
    });
    return Array.from(airports).filter(code => AIRPORTS[code]).map(code => ({ code, ...AIRPORTS[code] }));
  }, [routeLines]);

  // Resizable split: mapRatio is % width for the map panel (30-70)
  const [mapRatio, setMapRatio] = useState(50);
  const containerRef = useRef(null);
  const isDragging = useRef(false);

  const onMouseDown = useCallback((e) => {
    e.preventDefault();
    isDragging.current = true;
    const onMouseMove = (ev) => {
      if (!isDragging.current || !containerRef.current) return;
      const rect = containerRef.current.getBoundingClientRect();
      const pct = ((ev.clientX - rect.left) / rect.width) * 100;
      setMapRatio(Math.min(70, Math.max(30, pct)));
    };
    const onMouseUp = () => {
      isDragging.current = false;
      document.removeEventListener("mousemove", onMouseMove);
      document.removeEventListener("mouseup", onMouseUp);
    };
    document.addEventListener("mousemove", onMouseMove);
    document.addEventListener("mouseup", onMouseUp);
  }, []);

  return (
    <div className="space-y-6 mt-4 pb-12">

      {/* TOP SECTION: Map on Left, Index + Summary on Right — resizable */}
      <div ref={containerRef} className="flex h-[580px] gap-0"  style={{ userSelect: isDragging.current ? "none" : "auto" }}>
        {/* Left: Map */}
        <div className="bg-[#B8C2C9] rounded-2xl shadow-[0_4px_20px_rgba(0,102,102,0.08)] overflow-hidden relative flex flex-col shrink-0" style={{ width: `${mapRatio}%` }}>
          <div className="p-6 shrink-0 relative z-10">
            <h2 className="text-[#0D1B2A] font-bold text-[20px] tracking-tight">Geography Map</h2>
            <p className="text-[13px] text-text-secondary mt-1">Official boundaries (offline SVG) · { 'All' /* TODO: hook to filter */ } fare levels · 7-day price direction</p>
          </div>
          <div className="flex-1 w-full relative -mt-4 pb-4 px-4 flex items-center justify-center min-h-0">
            <div className="relative w-full h-full flex items-center justify-center">
              <svg
                xmlns="http://www.w3.org/2000/svg"
                viewBox={india.viewBox}
                className="w-full h-full max-h-full"
                preserveAspectRatio="xMidYMid meet"
                aria-label={india.label}
              >
                {/* State/UT boundaries */}
                {india.locations.map((location) => (
                  <path
                    key={location.id}
                    d={location.path}
                    fill="#0D1B2A"
                    stroke="#1B3A4B"
                    strokeWidth="0.5"
                    style={{ outline: "none" }}
                  />
                ))}

                {/* Route lines */}
                {routeLines.map((line) => {
                  const origin = AIRPORTS[line.id.split('-')[0]];
                  const dest = AIRPORTS[line.id.split('-')[1]];
                  const fromX = ((origin.lng - 68.1) / (97.4 - 68.1)) * 612;
                  const fromY = (1 - (origin.lat - 6.5) / (37.6 - 6.5)) * 696;
                  const toX = ((dest.lng - 68.1) / (97.4 - 68.1)) * 612;
                  const toY = (1 - (dest.lat - 6.5) / (37.6 - 6.5)) * 696;
                  
                  return (
                    <line
                      key={line.id}
                      x1={fromX}
                      y1={fromY}
                      x2={toX}
                      y2={toY}
                      stroke="var(--color-success)"
                      strokeWidth="1.5"
                      strokeOpacity="0.85"
                    />
                  );
                })}

                {/* Airport markers and labels */}
                {uniqueAirports.map((airport) => {
                  const x = ((airport.lng - 68.1) / (97.4 - 68.1)) * 612;
                  const y = (1 - (airport.lat - 6.5) / (37.6 - 6.5)) * 696;
                  
                  return (
                    <g key={airport.code}>
                      <circle cx={x} cy={y} r={6} fill="var(--color-success)" stroke="#FFFFFF" strokeWidth="1.5" />
                      <text
                        x={x + 10}
                        y={y + 4}
                        fill="#FFFFFF"
                        fontSize="10px"
                        fontFamily="sans-serif"
                        fontWeight="bold"
                      >
                        {airport.code}
                      </text>
                    </g>
                  );
                })}
              </svg>
            </div>
          </div>
        </div>

        {/* Invisible drag divider */}
        <div
          onMouseDown={onMouseDown}
          className="w-3 shrink-0 cursor-col-resize flex items-center justify-center"
          title="Drag to resize"
        >
          <div className="w-[3px] h-12 rounded-full bg-transparent transition-colors" />
        </div>

        {/* Right: Graph + Tiles */}
        <div className="flex flex-col gap-6 flex-1 min-w-0">
          <div 
            onClick={(e) => {
              // Only navigate if the click wasn't on the title Link itself
              if (e.target.closest('a')) return;
              navigate('/routes');
            }}
            className="block bg-white rounded-xl shadow-[0_4px_20px_rgba(0,102,102,0.08)] border border-primary/20 overflow-hidden h-[300px] transition-transform hover:scale-[1.01] hover:shadow-[0_8px_30px_rgba(0,102,102,0.12)] cursor-pointer"
          >
            <IndexLineChart />
          </div>
          
          <div className="flex-1">
            {summaryQ.data && <SummaryStrip summary={summaryQ.data} />}
          </div>
        </div>
      </div>

      {/* BOTTOM SECTION: Data Table */}
      <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_350px]">
        {/* Table */}
        <section className="app-card overflow-hidden">
          <div className="border-b border-primary/10 px-5 py-4 flex items-center justify-between">
            <div>
              <h2 className="text-[15px] font-black text-primary">Active Index Components</h2>
              <p className="mt-0.5 text-[11px] text-primary/80">Current fare quotes tracking across AP (Advance Purchase) windows.</p>
            </div>
            <Link to="/explorer" className="rounded-lg bg-bg-alt px-4 py-2 text-[11px] font-bold text-primary transition hover:bg-bg-alt">Data Explorer →</Link>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-left text-[11px] whitespace-nowrap">
              <thead className="bg-[var(--color-bg-alt)]">
                {table.getHeaderGroups().map(hg => (
                  <tr key={hg.id} className="border-b border-primary/10">
                    {hg.headers.map(h => <th key={h.id} className="px-5 py-3 font-bold uppercase tracking-wider text-primary/60 cursor-pointer hover:text-primary" onClick={h.column.getToggleSortingHandler()}>{flexRender(h.column.columnDef.header, h.getContext())} {h.column.getIsSorted() === 'asc' ? ' ↑' : h.column.getIsSorted() === 'desc' ? ' ↓' : ''}</th>)}
                  </tr>
                ))}
              </thead>
              <tbody className="divide-y divide-[var(--color-primary)]/5">
                {table.getRowModel().rows.slice(0, 10).map(row => (
                  <tr key={row.id} className="transition-colors hover:bg-[var(--color-bg-alt)]">
                    {row.getVisibleCells().map(cell => <td key={cell.id} className="px-5 py-2.5">{flexRender(cell.column.columnDef.cell, cell.getContext())}</td>)}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>

        <section className="app-card self-start">
          <div className="flex items-start justify-between p-4 pb-3">
            <div><h2 className="flex items-center gap-2 text-[15px] font-black text-primary"><TrendingUp className="h-4 w-4 text-primary" /> Top Route Movers</h2><p className="mt-0.5 text-[10px] text-primary/80">Largest 7-day fare movements.</p></div>
          </div>
          <div className="px-4 pb-4 mt-2">
            <div className="space-y-2">
              {topMovers.length ? topMovers.map(item => (
                <Link key={`${item.route}-${item.apWindow}`} to={`/route/${item.route}`} className="block rounded-lg border border-primary/10 px-3 py-2.5 transition hover:border-primary/30 hover:bg-[var(--color-bg-alt)]">
                  <div className="flex items-center justify-between"><span className="font-mono text-[11px] font-bold text-primary">{item.route} · {item.apWindow}</span><span className={`font-mono text-[11px] font-bold ${item.change7d > 0 ? "text-danger" : "text-success"}`}>{item.change7d > 0 ? "▲ +" : "▼ "}{Math.abs(item.change7d).toFixed(2)}%</span></div>
                  <div className="mt-1.5 h-1 overflow-hidden rounded-full bg-bg-alt"><div className={`h-full rounded-full ${item.change7d > 0 ? "bg-[var(--color-danger)]" : "bg-success"}`} style={{ width: `${Math.min(100, Math.max(12, Math.abs(item.change7d) * 7))}%` }} /></div>
                </Link>
              )) : (
                <div className="py-8 text-center text-[11px] text-primary/50">No movement data available</div>
              )}
            </div>
            <div className="mt-3 text-center">
              <Link to="/routes" className="text-[10px] font-bold text-primary hover:underline">View all routes →</Link>
            </div>
          </div>
        </section>
      </div>
    </div>
  );
}
