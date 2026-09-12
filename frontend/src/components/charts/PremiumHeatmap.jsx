/**
 * PremiumHeatmap.jsx
 *
 * Route × AP-Window heatmap showing price relatives.
 * Uses a simple grid with color intensity encoding.
 */

const routes = [
  "DEL-BOM",
  "DEL-BLR",
  "BOM-BLR",
  "DEL-CCU",
  "BLR-HYD",
  "MAA-DEL",
  "DEL-HYD",
  "BOM-CCU",
];

const apWindows = ["T+1", "T+7", "T+15", "T+30", "T+45"];

/**
 * Maps a price relative (0–200) to a background color.
 * Neutral around 100; above = red-tinted, below = green-tinted.
 */
function prCell(value) {
  if (value == null) return { bg: "bg-gray-100", text: "text-gray-400" };
  const delta = value - 100;
  if (delta > 20) return { bg: "bg-red-200", text: "text-danger" };
  if (delta > 10) return { bg: "bg-red-100", text: "text-danger" };
  if (delta > 3)  return { bg: "bg-red-50", text: "text-danger" };
  if (delta < -20) return { bg: "bg-green-200", text: "text-success" };
  if (delta < -10) return { bg: "bg-green-100", text: "text-success" };
  if (delta < -3)  return { bg: "bg-green-50", text: "text-success" };
  return { bg: "bg-gray-50", text: "text-text-secondary" };
}

export default function PremiumHeatmap({ basketItems }) {
  if (!basketItems || basketItems.length === 0) {
    return (
      <div className="px-4 py-8 text-center font-mono text-xs text-gray-400">
        No basket data available.
      </div>
    );
  }

  // Build lookup: route → apWindow → priceRelative×100
  const lookup = {};
  basketItems.forEach((item) => {
    if (!lookup[item.route]) lookup[item.route] = {};
    lookup[item.route][item.apWindow] = item.priceRelative * 100;
  });

  return (
    <div className="overflow-x-auto">
      <table className="w-full border-collapse font-mono text-xs">
        <thead>
          <tr className="border-b border-border bg-gray-50">
            <th className="px-3 py-2 text-left text-[10px] font-semibold uppercase tracking-wide text-text-secondary">
              Route
            </th>
            {apWindows.map((ap) => (
              <th
                key={ap}
                className="px-3 py-2 text-center text-[10px] font-semibold uppercase tracking-wide text-text-secondary"
              >
                {ap}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {routes.map((route) => (
            <tr key={route} className="border-b border-border">
              <td className="px-3 py-2 font-semibold text-gray-800">
                {route}
              </td>
              {apWindows.map((ap) => {
                const val = lookup[route]?.[ap];
                const { bg, text } = prCell(val);
                return (
                  <td
                    key={ap}
                    className={`${bg} px-3 py-2 text-center tabular-nums ${text}`}
                  >
                    {val != null ? `${val > 100 ? '▲ ' : val < 100 ? '▼ ' : ''}${val.toFixed(1)}` : "—"}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
      <div className="border-t border-border px-4 py-2">
        <p className="font-mono text-[10px] text-gray-400">
          Values are price relatives (base period = 100). Green = below base; Red = above base.
        </p>
      </div>
    </div>
  );
}

