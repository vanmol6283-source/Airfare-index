/**
 * NumberCell.jsx
 *
 * Consistent numerical formatting for tables and displays.
 * Uses font-mono and tabular-nums for column alignment.
 * Percentage/change values show + prefix and restrained color signal.
 */

/**
 * A table cell displaying a formatted fare.
 */
export function FareCell({ value }) {
  const formatted =
    value != null
      ? `₹${Math.round(value).toLocaleString("en-IN")}`
      : "—";
  return (
    <span className="font-mono tabular-nums text-gray-900">{formatted}</span>
  );
}

/**
 * A table cell displaying a formatted percentage change with color signal.
 */
export function ChangeCell({ value }) {
  if (value == null) return <span className="font-mono text-gray-400">—</span>;
  const sign = value > 0 ? "▲ +" : value < 0 ? "▼ " : "";
  const colorClass =
    value > 0 ? "text-danger" : value < 0 ? "text-success" : "text-text-secondary";
  return (
    <span className={`font-mono tabular-nums ${colorClass}`}>
      {sign}{Math.abs(value).toFixed(2)}%
    </span>
  );
}

/**
 * A table cell displaying a price relative.
 * Base = 100; above 100 → red-tinted, below → green-tinted.
 */
export function RelativeCell({ value }) {
  const colorClass =
    value > 100
      ? "text-danger"
      : value < 100
      ? "text-success"
      : "text-text-secondary";
  const icon = value > 100 ? "▲ " : value < 100 ? "▼ " : "";
  return (
    <span className={`font-mono tabular-nums ${colorClass}`}>
      {value != null ? `${icon}${value.toFixed(4)}` : "—"}
    </span>
  );
}

/**
 * Generic number cell with optional decimals.
 */
export default function NumberCell({ value, decimals = 2 }) {
  return (
    <span className="font-mono tabular-nums text-gray-900">
      {value != null ? Number(value).toFixed(decimals) : "—"}
    </span>
  );
}

