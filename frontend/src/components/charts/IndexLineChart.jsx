import { useState, useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { ResponsiveContainer, LineChart as RechartsLineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ReferenceLine } from "recharts";
import { getIndexHistory } from "../../api";
import InfoTooltip from "../shared/InfoTooltip";
import Card from "../shared/Card";
import Skeleton from "../shared/Skeleton";
import { LineChart, BarChart2, Table as TableIcon } from "lucide-react";
import { Link } from "react-router-dom";

const FREQUENCIES = [{ id: "daily", label: "D" }, { id: "weekly", label: "W" }, { id: "monthly", label: "M" }];
const RANGES = ["1M", "3M", "6M", "1Y", "MAX"];

function formatDateLabel(dateStr, frequency) {
  if (!dateStr) return "";
  const d = new Date(dateStr + "T00:00:00Z");
  const month = d.toLocaleString("en-US", { month: "short", timeZone: "UTC" });
  if (frequency === "monthly") return `${month} '${d.getUTCFullYear().toString().slice(2)}`;
  return `${d.getUTCDate()} ${month}`;
}

function CustomTooltip({ active, payload, label, frequency }) {
  if (!active || !payload?.length) return null;
  const val = payload[0]?.value;
  return <div className="rounded-lg border border-[#ddd8eb] bg-white px-3 py-2 shadow-[0_10px_24px_rgba(31,26,73,0.16)]"><div className="font-mono text-[9px] uppercase tracking-wide text-black/70">{formatDateLabel(label, frequency)}</div><div className="mt-1 font-mono text-[14px] font-bold text-black">{val != null ? val.toFixed(2) : "—"}</div></div>;
}

export default function IndexLineChart() {
  const [frequency, setFrequency] = useState("daily");
  const [range, setRange] = useState("6M");
  const [viewMode, setViewMode] = useState("chart");

  const { data: rawData = [], isLoading, isError } = useQuery({ queryKey: ["indexHistory", frequency], queryFn: () => getIndexHistory(frequency) });

  const filteredData = useMemo(() => {
    let data = [...rawData];
    data.sort((a, b) => new Date(a.date) - new Date(b.date));
    
    if (range === "MAX") return data;
    const today = new Date();
    const cutoff = new Date();
    if (range === "1M") cutoff.setMonth(today.getMonth() - 1);
    if (range === "3M") cutoff.setMonth(today.getMonth() - 3);
    if (range === "6M") cutoff.setMonth(today.getMonth() - 6);
    if (range === "1Y") cutoff.setFullYear(today.getFullYear() - 1);
    return data.filter(d => new Date(d.date + "T00:00:00Z") >= cutoff);
  }, [rawData, range]);

  return (
    <Card noPadding className="h-full flex flex-col overflow-visible">
      <div className="flex flex-col gap-2 border-b border-primary/10 px-4 py-3 shrink-0">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h2 className="flex items-center gap-1.5 text-[15px] font-black text-primary">
            <LineChart className="h-4 w-4 text-primary" />
            <Link to="/explorer" className="hover:underline">APIx Trend</Link>
            <InfoTooltip position="bottom" text="Daily movement of the domestic airfare price index" />
          </h2>
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-1.5">
              <span className="text-[9px] font-bold uppercase tracking-wide text-primary/80">Granularity:</span>
              <div className="flex overflow-hidden rounded-md border border-primary/20 shadow-sm">{FREQUENCIES.map((f, i) => <button key={f.id} aria-pressed={frequency === f.id} onClick={() => setFrequency(f.id)} className={`px-2.5 py-1 text-[9px] font-bold ${frequency === f.id ? "bg-primary text-white" : "bg-white text-primary/80 hover:bg-bg-alt focus:ring-1 focus:ring-primary"} ${i < FREQUENCIES.length - 1 ? "border-r border-primary/20" : ""}`}>{f.label}</button>)}</div>
            </div>
            <div className="flex items-center gap-1.5">
              <span className="text-[9px] font-bold uppercase tracking-wide text-primary/80">Range:</span>
              <div className="flex overflow-hidden rounded-md border border-primary/20 shadow-sm">{RANGES.map((r, i) => <button key={r} aria-pressed={range === r} onClick={() => setRange(r)} className={`px-2.5 py-1 text-[9px] font-bold ${range === r ? "bg-primary text-white" : "bg-white text-primary/80 hover:bg-bg-alt focus:ring-1 focus:ring-primary"} ${i < RANGES.length - 1 ? "border-r border-primary/20" : ""}`}>{r}</button>)}</div>
            </div>
          </div>
        </div>
        <div className="flex items-center justify-end gap-2 mt-1">
          <div className="hidden items-center gap-1.5 text-[9px] xl:flex">
            <label htmlFor="date-from" className="font-bold text-primary/80">From</label>
            <input id="date-from" type="date" aria-label="Start date filter" className="h-6 w-[86px] rounded border border-primary/30 px-1.5 text-[9px] font-mono text-primary-dark focus:border-primary focus:ring-1 focus:ring-primary shadow-sm" />
            <label htmlFor="date-to" className="font-bold text-primary/80 ml-1">To</label>
            <input id="date-to" type="date" aria-label="End date filter" className="h-6 w-[86px] rounded border border-primary/30 px-1.5 text-[9px] font-mono text-primary-dark focus:border-primary focus:ring-1 focus:ring-primary shadow-sm" />
          </div>
          <div className="flex overflow-hidden rounded-md border border-primary/20 shadow-sm">
            <button aria-label="Show chart view" aria-pressed={viewMode === "chart"} onClick={() => setViewMode("chart")} className={`px-2.5 py-1 ${viewMode === "chart" ? "bg-primary text-white" : "bg-white text-primary/80 hover:bg-bg-alt focus:ring-1 focus:ring-primary"}`}><BarChart2 className="h-3.5 w-3.5" /></button>
            <button aria-label="Show table view" aria-pressed={viewMode === "table"} onClick={() => setViewMode("table")} className={`px-2.5 py-1 border-l border-primary/20 ${viewMode === "table" ? "bg-primary text-white" : "bg-white text-primary/80 hover:bg-bg-alt focus:ring-1 focus:ring-primary"}`}><TableIcon className="h-3.5 w-3.5" /></button>
          </div>
        </div>
      </div>
      <div className="flex-1 bg-white px-3 py-2 flex flex-col justify-center">
        {isLoading && <div className="p-4 space-y-4"><Skeleton height="20px" width="40px" /><Skeleton height="140px" /><Skeleton height="20px" width="100%" /></div>}
        {isError && <div className="relative flex h-[200px] items-center justify-center overflow-hidden"><div className="absolute inset-x-8 top-[32%] h-px bg-primary/10" /><div className="absolute inset-x-14 top-1/2 h-px bg-primary/10" /><div className="absolute inset-x-20 top-[68%] h-px bg-primary/10" /><div className="relative text-center"><div className="mx-auto mb-3 flex h-11 w-11 items-center justify-center rounded-full bg-bg-alt text-[20px] font-black text-primary">!</div><p className="text-[12px] font-bold text-primary">Index data unavailable</p><p className="mt-1 max-w-[330px] text-[10px] leading-4 text-primary/60">The latest index observations could not be loaded. Please try again shortly.</p></div></div>}
        {!isLoading && !isError && filteredData.length > 0 && viewMode === "chart" && <ResponsiveContainer width="100%" height="100%"><RechartsLineChart data={filteredData} margin={{ top: 10, right: 18, bottom: 4, left: 2 }}><CartesianGrid stroke="rgba(15, 92, 92, 0.15)" strokeDasharray="3 5" vertical={false} /><XAxis dataKey="date" tickFormatter={v => formatDateLabel(v, frequency)} tick={{ fontFamily: "IBM Plex Mono", fontSize: 9, fill: "var(--color-text-primary)" }} tickLine={false} axisLine={{ stroke: "rgba(15, 92, 92, 0.20)" }} minTickGap={35} /><YAxis domain={["auto", "auto"]} tickFormatter={v => v.toFixed(1)} tick={{ fontFamily: "IBM Plex Mono", fontSize: 9, fill: "var(--color-text-primary)" }} tickLine={false} axisLine={false} width={46} /><ReferenceLine y={100} stroke="rgba(15, 92, 92, 0.40)" strokeDasharray="5 5" /><Tooltip content={<CustomTooltip frequency={frequency} />} /><Line type="monotone" dataKey="apix" stroke="var(--color-primary)" strokeWidth={2.6} dot={false} activeDot={{ r: 5, fill: "var(--color-primary)", stroke: "#ffffff", strokeWidth: 2 }} isAnimationActive={false} /></RechartsLineChart></ResponsiveContainer>}
        {!isLoading && !isError && viewMode === "table" && <div className="h-full overflow-auto border border-primary/10"><table className="w-full text-left text-[10px]"><thead className="sticky top-0 bg-bg-alt"><tr><th className="px-3 py-2 font-bold uppercase tracking-wide text-primary/80">Date</th><th className="px-3 py-2 text-right font-bold uppercase tracking-wide text-primary/80">Value</th></tr></thead><tbody className="divide-y divide-[var(--color-primary)]/5">{filteredData.map((d) => <tr key={d.date} className="bg-white hover:bg-[var(--color-bg-alt)]"><td className="px-3 py-1.5 font-mono text-primary/80">{d.date}</td><td className="px-3 py-1.5 text-right font-mono font-semibold text-primary">{d.apix.toFixed(2)}</td></tr>)}</tbody></table></div>}
      </div>
    </Card>
  );
}
