import InfoTooltip from "../shared/InfoTooltip";
import { BarChart3, Plane, TrendingUp, CalendarClock } from "lucide-react";

export default function SummaryStrip({ summary }) {
  // YOY logic fallback
  let yoyDisplay = "—";
  let yoyHint = "Insufficient historical data";
  if (summary?.yoyChange != null && summary.yoyChange !== 0) {
    yoyDisplay = `${summary.yoyChange > 0 ? "▲ +" : summary.yoyChange < 0 ? "▼ " : ""}${summary.yoyChange.toFixed(2)}%`;
    yoyHint = "Change vs. previous year";
  }

  const metrics = [
    {
      label: "APIx TODAY",
      value: summary?.apixToday?.toFixed(2) ?? "—",
      icon: <BarChart3 className="h-3.5 w-3.5" />,
      hint: summary?.apixToday != null ? "Current index level" : "No data available",
      info: "APIx is the project's headline airfare price index. It measures the weighted movement of domestic airfares relative to the January 2025 base period.",
    },
    {
      label: "ROUTES MONITORED",
      value: summary?.routesTracked ?? "—",
      icon: <Plane className="h-3.5 w-3.5" />,
      hint: summary?.routesTracked != null ? "Active domestic routes" : "No data available",
      info: "The number of domestic routes currently represented in the monitored airfare basket.",
    },
    {
      label: "MONTH OVER MONTH",
      value: summary?.momChange != null ? `${summary.momChange > 0 ? "▲ +" : summary.momChange < 0 ? "▼ " : ""}${summary.momChange.toFixed(2)}%` : "—",
      icon: <TrendingUp className="h-3.5 w-3.5" />,
      hint: summary?.momChange != null ? "Change vs. previous month" : "No data available",
      info: "Month-on-month change compares the current month's average APIx with the previous month's average APIx.",
    },
    {
      label: "YEAR OVER YEAR",
      value: yoyDisplay,
      icon: <CalendarClock className="h-3.5 w-3.5" />,
      hint: yoyHint,
      info: "Year-on-year change compares the current period with the corresponding period one year earlier.",
    },
  ];

  return (
    <section className="grid grid-cols-2 gap-5">
      {metrics.map((metric) => (
        <div key={metric.label} className="app-card relative z-10 hover:z-50 overflow-visible p-4">
          <div className="absolute inset-x-0 top-0 h-[3px] bg-primary rounded-t-2xl" />
          <div className="flex flex-col gap-2 mt-1">
            <div className="flex items-center gap-2">
              <div className="flex h-7 w-7 items-center justify-center rounded-full bg-bg-alt text-primary">{metric.icon}</div>
              <div className="flex items-center gap-1.5 text-[9px] font-black uppercase tracking-[0.09em] text-primary">{metric.label}<InfoTooltip text={metric.info} label={`More information about ${metric.label}`} /></div>
            </div>
            <div>
              <div className="font-mono text-[24px] font-bold leading-none tracking-[-0.04em] text-primary-dark tabular-nums">{metric.value}</div>
              <span className="mt-2 inline-flex rounded-md bg-bg-alt px-2 py-1 text-[8px] font-bold text-primary">{metric.hint}</span>
            </div>
          </div>
        </div>
      ))}
    </section>
  );
}
