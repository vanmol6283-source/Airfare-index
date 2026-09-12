export default function InfoTooltip({ text, label = "More information", position = "top" }) {
  const isTop = position === "top";

  return (
    <span className="group relative z-0 inline-flex align-middle group-hover:z-[100] group-focus-within:z-[100]">
      <button
        type="button"
        aria-label={label}
        className="flex h-3.5 w-3.5 items-center justify-center rounded-full border border-current/45 text-[8px] font-bold leading-none text-[#8b879c] transition hover:border-[#5f5a78] hover:text-[#5f5a78] focus:outline-none focus:ring-2 focus:ring-[#7c52e8]/25"
      >
        i
      </button>
      <span
        role="tooltip"
        className={`pointer-events-none invisible absolute left-1/2 z-50 w-[220px] -translate-x-1/2 rounded-lg border border-[#dcd7e8] bg-[#24203f] px-3 py-2.5 text-left text-[9px] font-medium leading-4 text-white opacity-0 shadow-[0_12px_28px_rgba(24,20,55,0.22)] transition-all duration-150 group-hover:visible group-hover:opacity-100 group-focus-within:visible group-focus-within:opacity-100 sm:w-[240px] ${isTop ? "bottom-[calc(100%+8px)]" : "top-[calc(100%+8px)]"}`}
      >
        <span className={`absolute left-1/2 h-2 w-2 -translate-x-1/2 rotate-45 border-[#dcd7e8] bg-[#24203f] ${isTop ? "-bottom-1 border-r border-b" : "-top-1 border-l border-t"}`} />
        {text}
      </span>
    </span>
  );
}
