/**
 * DensityToggle.jsx
 *
 * Compact / Comfortable toggle for table row height.
 */

export default function DensityToggle({ density, onChange }) {
  return (
    <div className="flex border border-border font-mono text-xs">
      {["compact", "comfortable"].map((d) => (
        <button
          key={d}
          onClick={() => onChange(d)}
          className={`px-3 py-1.5 capitalize ${
            density === d
              ? "bg-gray-900 text-white"
              : "bg-white text-text-secondary hover:bg-gray-50"
          }`}
        >
          {d}
        </button>
      ))}
    </div>
  );
}

