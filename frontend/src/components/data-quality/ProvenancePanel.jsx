/**
 * ProvenancePanel.jsx
 *
 * Displays data quality and provenance statistics with CSV export.
 */

function formatDate(isoStr) {
  if (!isoStr) return "—";
  const d = new Date(isoStr);
  // If the time component is exactly midnight UTC, this is a date-only value
  // from the backend — show only the date, not a misleading '5:30 am'
  const isDateOnly = d.getUTCHours() === 0 && d.getUTCMinutes() === 0 && d.getUTCSeconds() === 0;
  if (isDateOnly) {
    return d.toLocaleDateString("en-IN", {
      year: "numeric",
      month: "short",
      day: "numeric",
      timeZone: "Asia/Kolkata",
    });
  }
  return d.toLocaleDateString("en-IN", {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    timeZone: "Asia/Kolkata",
  }) + " IST";
}

export default function ProvenancePanel({ stats }) {
  const handleExportCSV = () => {
    if (!stats || stats.length === 0) return;

    const headers = [
      'Source',
      'Last Scraped (IST)',
      'Quotes Collected',
      'Quotes Rejected',
      'Rejection Rate (%)',
      'Back-Test Deviation (%)',
    ];

    const rows = stats.map(row => {
      const rejRate = row.quotesCollected > 0
        ? ((row.quotesRejected / row.quotesCollected) * 100).toFixed(2)
        : '0.00';
      return [
        `"${row.source}"`,
        `"${formatDate(row.lastScraped)}"`,
        row.quotesCollected ?? 0,
        row.quotesRejected ?? 0,
        rejRate,
        row.backTestDeviationPct != null ? row.backTestDeviationPct.toFixed(2) : '0.00',
      ].join(',');
    });

    const csvContent = [headers.join(','), ...rows].join('\n');
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    const today = new Date().toISOString().split('T')[0];
    link.setAttribute('href', url);
    link.setAttribute('download', `data_quality_provenance_${today}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  };

  if (!stats || stats.length === 0) {
    return (
      <div className="px-6 py-12 text-center font-sans text-[13px] text-gray-400">
        No provenance data available.
      </div>
    );
  }

  return (
    <div>
      {/* Section Header with Export CSV */}
      <div className="border-b border-border px-6 py-4 bg-bg-alt flex justify-between items-start">
        <div>
          <h2 className="font-sans text-[16px] font-bold text-gray-900">
            Data Source Provenance
          </h2>
          <p className="mt-1 font-sans text-[13px] text-text-secondary">
            Per-source collection and quality statistics
          </p>
        </div>
        <button
          onClick={handleExportCSV}
          className="flex items-center gap-1.5 px-3 py-1.5 border border-primary text-primary hover:bg-primary hover:text-white font-sans text-[11px] font-semibold rounded transition mt-0.5"
        >
          ↓ Export CSV
        </button>
      </div>

      {/* Provenance Table */}
      <div className="overflow-x-auto">
        <table className="w-full border-collapse font-sans text-[12px]">
          <thead>
            <tr className="border-b border-border bg-gray-50">
              {[
                "Source",
                "Last Scraped",
                "Quotes Collected",
                "Quotes Rejected",
                "Rejection Rate",
                "Back-Test Deviation",
              ].map((h) => (
                <th
                  key={h}
                  className="px-6 py-3 text-left text-[11px] font-bold uppercase tracking-wider text-text-secondary"
                >
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="bg-white">
            {stats.map((row, i) => {
              const rejRate =
                row.quotesCollected > 0
                  ? ((row.quotesRejected / row.quotesCollected) * 100).toFixed(2)
                  : "0.00";
              return (
                <tr key={i} className="border-b border-border hover:bg-gray-50/50 transition-colors">
                  <td className="px-6 py-4 font-semibold text-gray-900">{row.source}</td>
                  <td className="px-6 py-4 font-mono tabular-nums text-text-secondary">
                    {formatDate(row.lastScraped)}
                  </td>
                  <td className="px-6 py-4 font-mono tabular-nums text-gray-800">
                    {row.quotesCollected?.toLocaleString("en-IN") ?? "—"}
                  </td>
                  <td className="px-6 py-4 font-mono tabular-nums text-gray-800">
                    {row.quotesRejected?.toLocaleString("en-IN") ?? "—"}
                  </td>
                  <td className="px-6 py-4 font-mono tabular-nums text-text-secondary">
                    {rejRate}%
                  </td>
                  <td
                    className={`px-6 py-4 font-mono tabular-nums ${
                      row.backTestDeviationPct > 2
                        ? "text-danger font-medium"
                        : "text-text-secondary"
                    }`}
                  >
                    {row.backTestDeviationPct != null
                      ? `±${row.backTestDeviationPct.toFixed(2)}%`
                      : "—"}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
