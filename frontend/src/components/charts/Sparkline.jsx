/**
 * Sparkline.jsx
 *
 * Small inline Recharts line chart for use in route displays.
 * No axes, no labels — pure visual signal.
 */

import {
  ResponsiveContainer,
  LineChart,
  Line,
  Tooltip,
} from "recharts";

export default function Sparkline({ data, dataKey = "fare", width = 80, height = 32 }) {
  if (!data || data.length === 0) {
    return (
      <div
        style={{ width, height }}
        className="flex items-center justify-center font-mono text-[10px] text-gray-300"
      >
        —
      </div>
    );
  }

  // Determine color from trend (first to last)
  const first = data[0]?.[dataKey];
  const last = data[data.length - 1]?.[dataKey];
  const strokeColor =
    last > first ? "var(--color-danger)" : last < first ? "var(--color-success)" : "var(--color-text-secondary)";

  return (
    <ResponsiveContainer width={width} height={height}>
      <LineChart data={data} margin={{ top: 2, right: 2, bottom: 2, left: 2 }}>
        <Line
          type="monotone"
          dataKey={dataKey}
          stroke={strokeColor}
          strokeWidth={1.5}
          dot={false}
          isAnimationActive={false}
        />
        <Tooltip
          content={({ active, payload }) => {
            if (!active || !payload?.length) return null;
            return (
              <div className="border border-border bg-white px-2 py-1 font-mono text-[10px]">
                ₹{Math.round(payload[0].value).toLocaleString("en-IN")}
              </div>
            );
          }}
        />
      </LineChart>
    </ResponsiveContainer>
  );
}

