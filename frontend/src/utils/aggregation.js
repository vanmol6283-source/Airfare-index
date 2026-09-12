/**
 * aggregation.js
 *
 * Client-side aggregation utilities for airfare index data.
 * The stored index history is daily only. Weekly and monthly
 * values are derived here by grouping daily points and averaging.
 */

/**
 * Groups daily index history into weekly or monthly buckets.
 * Each bucket's apix value is the arithmetic mean of the daily values within it.
 *
 * @param {Array<{date: string, apix: number, frequency: string}>} dailyData
 * @param {"daily"|"weekly"|"monthly"} frequency
 * @returns {Array<{date: string, apix: number, frequency: string}>}
 */
export function aggregateByFrequency(dailyData, frequency) {
  if (frequency === "daily") {
    return dailyData;
  }

  // Map from period key → array of daily points in that period
  const groups = new Map();

  dailyData.forEach((point) => {
    const date = new Date(point.date);
    let key;

    if (frequency === "weekly") {
      // Align to the Monday of the ISO week
      const day = date.getUTCDay(); // 0=Sun, 1=Mon, …, 6=Sat
      const diff = day === 0 ? -6 : 1 - day;
      const weekStart = new Date(date);
      weekStart.setUTCDate(date.getUTCDate() + diff);
      key = weekStart.toISOString().split("T")[0];
    }

    if (frequency === "monthly") {
      // Key is "YYYY-MM"
      key = `${date.getUTCFullYear()}-${String(
        date.getUTCMonth() + 1
      ).padStart(2, "0")}`;
    }

    if (!groups.has(key)) {
      groups.set(key, []);
    }
    groups.get(key).push(point);
  });

  // Build result sorted chronologically
  return Array.from(groups.entries())
    .sort(([a], [b]) => (a < b ? -1 : 1))
    .map(([key, points]) => ({
      date: key,
      apix:
        points.reduce((sum, p) => sum + p.apix, 0) / points.length,
      frequency,
    }));
}

