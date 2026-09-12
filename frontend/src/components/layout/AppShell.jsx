import { useState, useEffect } from "react";
import { Outlet, NavLink, Link, useLocation } from "react-router-dom";
import { Search, Plane, Menu, X } from "lucide-react";
import SearchOverlay from "./SearchOverlay";
import GovUtilityBar from "./GovUtilityBar";

const navigation = [
  { label: "Home", path: "/", icon: "⌂" },
  { label: "Index Monitor", path: "/routes", icon: "✈" },
  { label: "Route Explorer", path: "/explorer", icon: "▥" },
  { label: "Technical Notes", path: "/methodology", icon: "▤" },
  { label: "Data Quality", path: "/data-quality", icon: "⬡" },
  { label: "Developers", path: "/api-docs", icon: "</>" },
];

function Breadcrumbs() {
  const location = useLocation();
  if (location.pathname === "/") return null;

  const paths = location.pathname.split("/").filter(Boolean);
  let currentPath = "";
  const labels = {
    explorer: "Route Explorer",
    routes: "Index Monitor",
    methodology: "Technical Notes",
    "data-quality": "Data Quality",
    "api-docs": "Developers",
    route: "Route Details",
  };

  return (
    <div className="mx-auto w-full max-w-[1600px] px-3 sm:px-4 lg:px-6 pt-4">
      <nav className="flex items-center text-[10px] font-semibold uppercase tracking-[0.1em] text-text-secondary">
        <Link to="/" className="transition hover:text-accent">Home</Link>
        {paths.map((path, index) => {
          currentPath += `/${path}`;
          const isLast = index === paths.length - 1;
          const label = labels[path] || path.charAt(0).toUpperCase() + path.slice(1);
          return (
            <span key={currentPath} className="flex items-center">
              <span className="mx-2 text-text-secondary">/</span>
              {isLast ? (
                <span className="text-text-primary">{label}</span>
              ) : (
                <Link to={currentPath} className="hover:text-accent">{label}</Link>
              )}
            </span>
          );
        })}
      </nav>
    </div>
  );
}

export default function AppShell() {
  const [isSearchOpen, setIsSearchOpen] = useState(false);
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);

  return (
    <div className="min-h-screen bg-bg-alt text-text-primary font-sans flex flex-col">
      {isSearchOpen && <SearchOverlay onClose={() => setIsSearchOpen(false)} />}

      <header className="sticky top-0 z-50 flex flex-col w-full shadow-[0_10px_30px_rgba(25,22,73,0.24)]">
        {/* BAND 1: Utility Bar */}
        <GovUtilityBar />

        {/* BAND 2: Logo + Search */}
        <div className="w-full bg-bg px-6 py-3 flex justify-between items-center border-b border-border">
          {/* Left side — Logo */}
          <Link to="/" className="flex items-center gap-4 py-3" aria-label="Airfare Price Index Home">
            <Plane className="h-8 w-8 text-text-primary" strokeWidth={2.5} />
            <div>
              <div className="font-sans text-[22px] font-bold text-text-primary tracking-tight leading-none">
                AIRFARE PRICE <span className="text-accent">INDEX</span>
              </div>
              <div className="font-sans text-[11px] text-text-secondary mt-0.5 tracking-wide">
                DOMESTIC AVIATION PRICE MONITOR · INDIA
              </div>
            </div>
          </Link>

          {/* Right side — Search bar and Mobile Hamburger */}
          <div className="flex items-center gap-4">
            <button
              onClick={() => setIsSearchOpen(true)}
              className="hidden lg:flex items-center justify-between gap-2 border border-border rounded shadow-sm px-3 py-1.5 bg-white text-text-secondary text-[13px] font-sans hover:border-primary hover:shadow focus:outline-none focus:ring-2 focus:ring-primary focus:border-transparent transition w-[240px]"
              aria-label="Search routes and airports"
            >
              <div className="flex items-center gap-2">
                <Search className="h-4 w-4 text-text-secondary" />
                <span className="text-text-secondary truncate">Search routes...</span>
              </div>
              <kbd className="hidden sm:inline-block rounded border border-border bg-gray-50 px-1.5 py-0.5 text-[10px] font-mono font-medium text-text-secondary">⌘K</kbd>
            </button>
            <button
              type="button"
              onClick={() => setIsMobileMenuOpen(true)}
              className="flex h-9 w-9 items-center justify-center rounded-lg border border-border bg-gray-50 text-text-secondary md:hidden focus:ring-2 focus:ring-primary"
              aria-label="Open navigation menu"
              aria-expanded={isMobileMenuOpen}
            >
              <Menu className="h-5 w-5" />
            </button>
          </div>
        </div>

        {/* BAND 3: Navigation */}
        <nav style={{ background: 'var(--color-primary)' }} className="hidden md:flex w-full h-[56px]" aria-label="Main navigation">
          <div className="flex items-center justify-center w-full px-6 h-full">
            {navigation.map((link, i) => (
              <div key={link.path} className="flex items-center h-full">
                <NavLink
                  to={link.path}
                  end={link.path === '/'}
                  className={({ isActive }) =>
                    isActive
                      ? 'px-6 py-2.5 mx-2 font-sans text-[13px] font-bold uppercase tracking-wide bg-white text-primary rounded-md shadow-[0_2px_8px_rgba(0,0,0,0.15)] ring-2 ring-white/50'
                      : 'px-6 py-2.5 mx-2 font-sans text-[13px] font-bold uppercase tracking-wide text-white/90 hover:text-white hover:bg-white/10 rounded-md transition focus:outline-none focus:ring-2 focus:ring-white'
                  }
                >
                  {link.label}
                </NavLink>
                {i < navigation.length - 1 && (
                  <div className="h-[22px] w-[1px] bg-primary-dark" aria-hidden="true" />
                )}
              </div>
            ))}
          </div>
        </nav>
      </header>

      {/* Mobile Menu Drawer */}
      {isMobileMenuOpen && (
        <div className="fixed inset-0 z-[60] md:hidden" aria-label="Mobile navigation">
          <button
            type="button"
            aria-label="Close menu"
            className="absolute inset-0 bg-[var(--color-text-primary)]/55 backdrop-blur-[2px]"
            onClick={() => setIsMobileMenuOpen(false)}
          />
          <aside className="absolute right-0 top-0 h-full w-[min(88vw,360px)] overflow-y-auto bg-white shadow-[-18px_0_45px_rgba(17,22,70,0.28)]">
            <div className="flex h-[60px] items-center justify-between bg-primary px-5 text-white">
              <div className="text-[11px] font-black uppercase tracking-[0.12em]">Navigation</div>
              <button
                type="button"
                onClick={() => setIsMobileMenuOpen(false)}
                className="flex h-8 w-8 items-center justify-center rounded-full bg-white/10 text-white transition hover:bg-white/20 focus:ring-2 focus:ring-white"
                aria-label="Close menu"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
            <div className="p-3">
              {navigation.map((item) => (
                <NavLink
                  key={item.path}
                  to={item.path}
                  end={item.path === "/"}
                  onClick={() => setIsMobileMenuOpen(false)}
                  className={({ isActive }) =>
                    `flex items-center gap-3 rounded-xl px-4 py-3.5 text-[12px] font-bold transition ${
                      isActive
                        ? "bg-bg-alt text-[#24205e]"
                        : "text-[#4f4a68] hover:bg-bg-alt"
                    }`
                  }
                >
                  <span className="flex w-6 justify-center text-[16px]">{item.icon}</span>
                  <span>{item.label}</span>
                </NavLink>
              ))}

              <div className="my-3 border-t border-border" />

              <button
                type="button"
                onClick={() => {
                  setIsMobileMenuOpen(false);
                  setIsSearchOpen(true);
                }}
                className="flex w-full items-center gap-3 rounded-xl px-4 py-3.5 text-left text-[12px] font-bold text-[#4f4a68] hover:bg-bg-alt"
              >
                <span className="flex w-6 justify-center text-[18px]">⌕</span>
                <span>Search routes &amp; airports</span>
              </button>
            </div>
          </aside>
        </div>
      )}

      {/* Mobile Search Bar Trigger below header */}
      <div className="border-b border-[#e7e3ef] bg-white px-3 py-2.5 md:hidden">
        <button
          type="button"
          onClick={() => setIsSearchOpen(true)}
          className="flex h-10 w-full items-center gap-2 rounded-lg border border-border bg-bg-alt px-3 text-left text-[11px] text-text-secondary"
        >
          <span className="text-[17px] text-text-secondary">⌕</span>
          <span>Search routes, airports...</span>
        </button>
      </div>

      <Breadcrumbs />

      <main id="main-content" className="mx-auto w-full max-w-[1600px] flex-1 px-3 sm:px-4 lg:px-6 pb-10 pt-1">
        <Outlet />
      </main>

      <footer className="mt-auto overflow-hidden bg-primary text-white">
        <div className="mx-auto max-w-[1600px] px-6 py-7">
          <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-[1.25fr_1.3fr_1fr_1.25fr] gap-6 xl:gap-8">
            <div>
              <div className="flex items-center gap-3">
                <span className="text-[28px]">✈</span>
                <div>
                  <div className="text-[15px] font-black">AIRFARE <span className="text-accent">INDEX</span></div>
                  <div className="text-[9px] text-white/80">India's domestic aviation price intelligence platform</div>
                </div>
              </div>
            </div>
            <div>
              <h3 className="mb-3 text-[10px] font-black uppercase tracking-[0.1em] text-white">Quick Links</h3>
              <div className="grid grid-cols-2 gap-x-5 gap-y-2 text-[10px] text-white/65">
                <Link to="/" className="hover:text-white">Home</Link><Link to="/explorer" className="hover:text-white">Route Explorer</Link>
                <Link to="/routes" className="hover:text-white">Index Monitor</Link><Link to="/methodology" className="hover:text-white">Technical Notes</Link>
                <Link to="/data-quality" className="hover:text-white">Data Quality</Link><Link to="/api-docs" className="hover:text-white">Developers</Link>
              </div>
            </div>
            <div>
              <h3 className="mb-3 text-[10px] font-black uppercase tracking-[0.1em] text-white">Data Source</h3>
              <div className="space-y-2 text-[10px] text-white/65">
                <div>DGCA Fare Observation Data</div><div>Base period: January 2025</div>
              </div>
            </div>
            <div className="relative">
              <h3 className="mb-3 text-[10px] font-black uppercase tracking-[0.1em] text-white">Built for a Connected India</h3>
              <p className="text-[10px] leading-5 text-white/65">Smarter data. Stronger skies.</p>
              <div className="absolute right-0 top-0 text-[55px] opacity-10">✈︎</div>
            </div>
          </div>
          <div className="mt-6 flex flex-col gap-3 border-t border-white/10 pt-4 text-[9px] text-white/45">
            <span>© 2026 Airfare Index. All rights reserved.</span>
            <div className="flex gap-5"><span>Privacy</span><span>Terms</span><span>Contact</span></div>
          </div>
        </div>
      </footer>
    </div>
  );
}
