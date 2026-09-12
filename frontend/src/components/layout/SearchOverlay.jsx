import { useState, useEffect, useRef } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { getBasketItems } from "../../api";

const PAGES = [
  { title: "Overview", path: "/" },
  { title: "Data Explorer", path: "/explorer" },
  { title: "Routes", path: "/routes" },
  { title: "Methodology", path: "/methodology" },
  { title: "Data Quality", path: "/data-quality" },
  { title: "API Docs", path: "/api-docs" },
];

export default function SearchOverlay({ onClose }) {
  const [query, setQuery] = useState("");
  const inputRef = useRef(null);
  const navigate = useNavigate();

  const { data: basket } = useQuery({
    queryKey: ["basket"],
    queryFn: getBasketItems,
  });

  useEffect(() => {
    if (inputRef.current) {
      inputRef.current.focus();
    }
    
    const handleKeyDown = (e) => {
      if (e.key === "Escape") {
        onClose();
      }
    };
    
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [onClose]);

  const q = query.toLowerCase().trim();
  
  // Extract unique route IDs from basket
  const uniqueRoutes = basket 
    ? Array.from(new Set(basket.map(item => item.route)))
    : [];

  const matchedRoutes = q ? uniqueRoutes.filter(route => route.toLowerCase().includes(q)) : [];
  const matchedPages = q ? PAGES.filter(page => page.title.toLowerCase().includes(q)) : [];

  const handleNavigate = (path) => {
    navigate(path);
    onClose();
  };

  return (
    <div className="fixed inset-0 z-[100] bg-white/95 backdrop-blur flex flex-col items-center pt-24 px-6 overflow-y-auto">
      <div className="w-full max-w-3xl relative">
        <input
          ref={inputRef}
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search routes, indicators, airlines..."
          className="w-full font-sans text-[24px] text-gray-900 border-b-2 border-border pb-4 bg-transparent focus:outline-none focus:border-primary placeholder-gray-400"
        />
        <button 
          onClick={onClose}
          className="absolute right-0 top-1 text-gray-400 hover:text-gray-900 text-[24px] leading-none"
        >
          &times;
        </button>

        {query && (
          <div className="mt-8 space-y-8 pb-12 w-full text-left">
            {matchedRoutes.length > 0 && (
              <div>
                <h3 className="font-sans text-[11px] font-semibold uppercase tracking-wider text-text-secondary mb-3">
                  Routes
                </h3>
                <div className="flex flex-col gap-1">
                  {matchedRoutes.map(route => (
                    <button
                      key={route}
                      onClick={() => handleNavigate(`/route/${route}`)}
                      className="text-left font-mono text-[16px] text-gray-800 hover:text-primary hover:bg-blue-50/50 py-2 px-3 rounded transition-colors"
                    >
                      {route}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {matchedPages.length > 0 && (
              <div>
                <h3 className="font-sans text-[11px] font-semibold uppercase tracking-wider text-text-secondary mb-3">
                  Pages
                </h3>
                <div className="flex flex-col gap-1">
                  {matchedPages.map(page => (
                    <button
                      key={page.path}
                      onClick={() => handleNavigate(page.path)}
                      className="text-left font-sans text-[16px] text-gray-800 hover:text-primary hover:bg-blue-50/50 py-2 px-3 rounded transition-colors"
                    >
                      {page.title}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {matchedRoutes.length === 0 && matchedPages.length === 0 && (
              <div className="font-sans text-[14px] text-text-secondary py-4">
                No results found for "{query}".
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
