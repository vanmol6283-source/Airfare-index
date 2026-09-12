/**
 * GovUtilityBar.jsx
 *
 * Top utility strip styled after India.gov.in & UDISE+ portals:
 *   — Skip to main content (accessibility)
 *   — Screen reader / High contrast toggle
 *   — Text size controls
 *   — India flag + NIC / GOI branding
 */

import { useState, useEffect } from "react";

export default function GovUtilityBar() {
  const [textSize, setTextSize] = useState(0); // -1, 0, +1
  const [highContrast, setHighContrast] = useState(false);

  // Apply text-size and high-contrast to <html>
  useEffect(() => {
    const root = document.documentElement;
    const sizes = [14, 16, 18];
    root.style.fontSize = sizes[textSize + 1] + "px";
  }, [textSize]);

  useEffect(() => {
    document.documentElement.classList.toggle("high-contrast", highContrast);
  }, [highContrast]);

  return (
    <div
      role="navigation"
      aria-label="Utility navigation"
      className="hidden sm:flex items-center justify-between bg-[#f1f1f1] border-b border-[#d5d5d5] px-4 py-0.5 text-[10px] text-[#333] select-none"
    >
      {/* Left: Skip + Screen Reader */}
      <div className="flex items-center gap-3">
        <a
          href="#main-content"
          className="sr-only focus:not-sr-only focus:absolute focus:top-1 focus:left-1 focus:z-[9999] focus:bg-primary focus:text-white focus:px-3 focus:py-1 focus:rounded focus:text-[10px] focus:font-bold"
        >
          Skip to main content
        </a>
        <span className="text-text-secondary border-r border-[#ccc] pr-3">
          Screen Reader Access
        </span>

        {/* Contrast */}
        <div className="flex items-center gap-1.5 border-r border-[#ccc] pr-3">
          <span className="text-text-secondary">A+</span>
          <button
            aria-label="Increase text size"
            onClick={() => setTextSize((s) => Math.min(1, s + 1))}
            className="w-5 h-5 flex items-center justify-center rounded border border-[#ccc] bg-white hover:bg-[#e0e0e0] font-bold text-[11px]"
          >
            +
          </button>
          <button
            aria-label="Reset text size"
            onClick={() => setTextSize(0)}
            className="w-5 h-5 flex items-center justify-center rounded border border-[#ccc] bg-white hover:bg-[#e0e0e0] font-bold text-[10px]"
          >
            A
          </button>
          <button
            aria-label="Decrease text size"
            onClick={() => setTextSize((s) => Math.max(-1, s - 1))}
            className="w-5 h-5 flex items-center justify-center rounded border border-[#ccc] bg-white hover:bg-[#e0e0e0] font-bold text-[9px]"
          >
            −
          </button>
        </div>

        {/* High contrast */}
        <button
          onClick={() => setHighContrast((c) => !c)}
          aria-pressed={highContrast}
          className={`flex items-center gap-1 border px-2 py-0.5 rounded text-[9px] font-semibold transition ${
            highContrast
              ? "bg-primary text-white border-primary"
              : "bg-white text-[#333] border-[#ccc] hover:bg-[#e0e0e0]"
          }`}
        >
          <span aria-hidden="true">◑</span>
          {highContrast ? "Normal" : "High Contrast"}
        </button>
      </div>

      {/* Right: GOI branding */}
      <div className="flex items-center gap-3 font-sans">
        <div className="flex items-center gap-2 border-l border-[#ccc] pl-3">
          <span className="font-bold text-[10px] text-[#333]">IN</span>
          <div className="text-right leading-tight border-l border-[#ccc] pl-2 ml-1">
            <div className="text-[9px] font-bold text-[#333] uppercase tracking-wide">
              GOI — NIC
            </div>
            <div className="text-[8px] text-text-secondary">
              Ministry of Civil Aviation
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
