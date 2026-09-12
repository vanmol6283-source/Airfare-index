/**
 * ExportButton.jsx
 *
 * Generates a CSV download from the provided table data.
 * Runs entirely in the browser — no backend required.
 */

function toCSV(rows, headers) {
  if (!rows || rows.length === 0) return "";
  const keys = headers || Object.keys(rows[0]);

  const escape = (val) => {
    if (val == null) return "";
    const str = String(val);
    if (str.includes(",") || str.includes('"') || str.includes("\n")) {
      return `"${str.replace(/"/g, '""')}"`;
    }
    return str;
  };

  const headerRow = keys.map(escape).join(",");
  const dataRows = rows.map((row) =>
    keys.map((k) => escape(row[k])).join(",")
  );
  return [headerRow, ...dataRows].join("\r\n");
}

/**
 * ExportButton component.
 *
 * @param {object} props
 * @param {object[]} props.data      - array of row objects to export
 * @param {string}  props.filename   - download filename (without .csv)
 * @param {string[]} [props.headers] - optional column order
 */
export default function ExportButton({ data, filename, headers }) {
  const handleExport = () => {
    if (!data || data.length === 0) return;
    const csv = toCSV(data, headers);
    const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    const ts = new Date().toISOString().slice(0, 10);
    link.href = url;
    link.download = `${filename}_${ts}.csv`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  };

  return (
    <button
      onClick={handleExport}
      disabled={!data || data.length === 0}
      className="border border-gray-400 bg-white px-3 py-1.5 font-mono text-xs text-text-secondary hover:bg-gray-50 disabled:cursor-not-allowed disabled:opacity-50"
    >
      Export CSV
    </button>
  );
}

