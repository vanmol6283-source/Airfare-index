import 'katex/dist/katex.min.css';
import { BlockMath, InlineMath } from 'react-katex';

function Section({ id, title, children }) {
  return (
    <section id={id} className="mb-12 scroll-mt-24">
      <h2 className="font-sans text-[20px] font-bold text-gray-900 mb-4 pb-2 border-b border-border">
        {title}
      </h2>
      <div className="space-y-4 font-sans text-[15px] text-gray-800 leading-[1.7]">
        {children}
      </div>
    </section>
  );
}

function FormulaBox({ math, descriptionLines }) {
  return (
    <div className="my-6 border border-border bg-bg-alt px-6 py-5">
      <div className="text-gray-900 overflow-x-auto pb-4">
        <BlockMath math={math} />
      </div>
      {descriptionLines && descriptionLines.length > 0 && (
        <div className="mt-4 font-mono text-[13px] text-text-secondary leading-relaxed border-t border-border pt-4">
          {descriptionLines.map((line, i) => (
            <div key={i}>{line}</div>
          ))}
        </div>
      )}
    </div>
  );
}

function Note({ children }) {
  return (
    <div className="mb-8 border-l-4 border-accent bg-amber-50 px-5 py-4 font-sans text-[14px] text-amber-900">
      {children}
    </div>
  );
}

const TOC_ITEMS = [
  { id: "overview", label: "1. Overview" },
  { id: "formula", label: "2. Index Formula" },
  { id: "weighting", label: "3. Traffic-Based Weighting" },
  { id: "windows", label: "4. Advance Purchase Windows" },
  { id: "change-measures", label: "5. Change Measures" },
  { id: "data-collection", label: "6. Data Collection" },
  { id: "base-period", label: "7. Base Period" },
  { id: "publication", label: "8. Frequency & Publication" },
];

export default function Methodology() {
  return (
    <div data-page="methodology" className="flex flex-col lg:flex-row gap-6 lg:gap-12 w-full max-w-[1200px] mx-auto">
      {/* Sidebar TOC */}
      <aside className="w-full lg:w-64 flex-shrink-0">
        <div className="sticky top-[88px] space-y-1">
          <h3 className="font-sans text-[11px] font-bold uppercase tracking-wider text-text-secondary mb-4 px-2">
            Contents
          </h3>
          <nav className="flex flex-col">
            {TOC_ITEMS.map((item) => (
              <a
                key={item.id}
                href={`#${item.id}`}
                className="px-2 py-1.5 font-sans text-[13px] text-text-secondary hover:text-accent hover:bg-[#fff0f2] rounded transition-colors"
              >
                {item.label}
              </a>
            ))}
          </nav>
        </div>
      </aside>

      {/* Main Content */}
      <div className="flex-1 min-w-0 max-w-3xl">
        <header className="mb-10 rounded-2xl border border-border bg-gradient-to-br from-white to-[#f4eefb] px-6 py-6 shadow-[0_12px_35px_rgba(32,23,63,0.07)]">
          <div className="mb-2 text-[10px] font-bold uppercase tracking-[0.2em] text-accent">INDEX METHODOLOGY</div>
          <h1 className="font-sans text-[30px] sm:text-[36px] font-bold text-gray-900 tracking-tight">
            Methodology
          </h1>
          <p className="mt-2 font-sans text-[16px] text-text-secondary">
            Technical specification of the Airfare Price Index (APIx)
          </p>
        </header>

        <Note>
          <strong>Notice:</strong> The APIx is an experimental price index developed for domestic aviation monitoring.
          It does not represent an official DGCA or government statistical publication.
          Methodology decisions are those of the project team.
        </Note>

        <Section id="overview" title="1. Overview">
          <p>
            The Airfare Price Index (APIx) measures the aggregate movement of domestic
            airfares across a representative basket of Indian routes and advance-purchase
            windows. It is designed to serve as a leading indicator of airfare inflation
            and to support policy analysis, economic monitoring, and academic research.
          </p>
          <p>
            The index follows the weighted-average price-relative approach, analogous
            in structure to CPI-based price indices, adapted for the specific
            characteristics of aviation pricing.
          </p>
        </Section>

        <Section id="formula" title="2. Index Formula">
          <p>
            At each time point <InlineMath math="t" />, the index value is computed as:
          </p>

          <FormulaBox
            math="APIx(t) = \frac{\sum_i \left[ W(i) \times PR(i, t) \right]}{\sum_i W(i)}"
            descriptionLines={[
              "where:",
              "  i       = basket item (route × AP window pair)",
              "  W(i)    = traffic weight for basket item i",
              "  PR(i,t) = price relative for basket item i at time t",
            ]}
          />

          <p>
            The price relative compares the current observed fare to the base period fare:
          </p>

          <FormulaBox
            math="PR(i, t) = \frac{P(i, t)}{P(i, 0)} \times 100"
            descriptionLines={[
              "where:",
              "  P(i, t) = observed fare for item i at time t",
              "  P(i, 0) = base period fare for item i",
            ]}
          />

          <p>
            A price relative of 100 indicates fares are at their base-period level.
            Values above 100 indicate fares have risen; values below 100 indicate fares
            have fallen.
          </p>
        </Section>

        <Section id="weighting" title="3. Traffic-Based Weighting">
          <p>
            Each basket item receives a weight proportional to observed passenger volumes
            on that route, reflecting economic significance:
          </p>

          <FormulaBox
            math="W(i) = \frac{\text{Passengers}(i)}{\sum \text{Passengers}}"
            descriptionLines={[
              "Weights are normalised so that:",
              "  Σ W(i) = 100",
            ]}
          />

          <p>
            Traffic data is sourced from DGCA scheduled domestic airline statistics.
            Weights are reviewed periodically (typically annually) to reflect current
            traffic patterns.
          </p>
          <p>
            This approach ensures that high-volume routes (such as Delhi–Mumbai) receive
            greater representation in the index, consistent with their economic significance
            to the domestic aviation market.
          </p>
        </Section>

        <Section id="windows" title="4. Advance Purchase Windows">
          <p>
            Aviation fares vary substantially depending on how far in advance a ticket
            is purchased. To account for this, each route is tracked across five
            standardised advance-purchase (AP) windows:
          </p>

          <div className="overflow-x-auto my-6 border border-border">
            <table className="w-full border-collapse text-[14px]">
              <thead>
                <tr className="border-b border-border bg-bg-alt text-[11px] uppercase tracking-wider text-text-secondary">
                  <th className="px-4 py-3 text-left font-semibold">Window</th>
                  <th className="px-4 py-3 text-left font-semibold">Days Before Departure</th>
                  <th className="px-4 py-3 text-left font-semibold">Fare Characteristic</th>
                </tr>
              </thead>
              <tbody>
                {[
                  ["T+1",  "1 day",  "Last-minute / walk-up fare (highest typically)"],
                  ["T+7",  "7 days", "Short-notice fare"],
                  ["T+15", "15 days","Standard leisure/advance fare"],
                  ["T+30", "30 days","Early advance purchase"],
                  ["T+45", "45 days","Deep advance / lowest typical fare"],
                ].map(([win, days, note], idx) => (
                  <tr key={win} className={idx !== 4 ? "border-b border-gray-100" : ""}>
                    <td className="px-4 py-3 font-semibold text-gray-900 bg-bg-alt">{win}</td>
                    <td className="px-4 py-3 text-text-secondary">{days}</td>
                    <td className="px-4 py-3 text-text-secondary">{note}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <p>
            Each route × AP window combination constitutes a distinct basket item.
            This ensures the index captures price movements across the full advance-purchase
            spectrum, not only a single booking horizon.
          </p>
        </Section>

        <Section id="change-measures" title="5. Period-on-Period Change Measures">
          <p>
            Two standard change measures are computed from the index:
          </p>

          <div className="mt-6 mb-8">
            <h4 className="font-semibold text-gray-900 mb-2">Month-on-Month (MoM) Change:</h4>
            <FormulaBox
              math="\text{MoM}\% = \frac{APIx_{\text{month}_2} - APIx_{\text{month}_1}}{APIx_{\text{month}_1}} \times 100"
              descriptionLines={[
                "where month₂ is the current month average and month₁ is the prior month average.",
              ]}
            />
          </div>

          <div className="mb-6">
            <h4 className="font-semibold text-gray-900 mb-2">Year-on-Year (YoY) Change:</h4>
            <FormulaBox
              math="\text{YoY}\% = \frac{APIx_t - APIx_{t-12\text{mo}}}{APIx_{t-12\text{mo}}} \times 100"
              descriptionLines={[
                "where t is the current observation date and t−12mo is the same date 12 months prior.",
              ]}
            />
          </div>

          <p>
            Both measures are reported as percentage changes. Positive values indicate
            fares have increased relative to the comparison period; negative values
            indicate fares have fallen.
          </p>
        </Section>

        <Section id="data-collection" title="6. Data Collection">
          <p>
            Fare observations are collected by automated scraping of publicly available
            airline booking portals and, where available, Global Distribution System
            (GDS) feeds. Quotes are recorded at standardised times to ensure
            comparability.
          </p>

          <p>
            Each daily observation represents the lowest available published fare
            for the specified route and advance-purchase window, consistent with
            standard practice in airfare index construction.
          </p>

          <p>
            Quotes that fail basic validity checks (e.g., implausibly low or high values,
            unavailable itineraries, mismatched routes) are rejected prior to aggregation.
            Rejection rates are monitored as a data quality indicator.
          </p>
        </Section>

        <Section id="base-period" title="7. Base Period">
          <p>
            The index base period is set such that <InlineMath math="APIx = 100" /> at the reference date.
            All price relatives and the index itself are expressed relative to this baseline.
          </p>
          <p>
            The base period fare for each basket item (<InlineMath math="P(i,0)" />) is the average observed
            fare during the base reference month. Base fares are fixed until a methodological
            review or rebase is performed.
          </p>
        </Section>

        <Section id="publication" title="8. Frequency and Publication">
          <p>
            The APIx is updated daily. Weekly and monthly aggregates are derived
            by arithmetic averaging of daily index values within the respective period.
            No separate weekly or monthly data collection is performed.
          </p>
          <p>
            Observations are typically collected during standard business hours (IST).
            The index reflects fare levels at the time of collection.
          </p>
        </Section>
      </div>
    </div>
  );
}
