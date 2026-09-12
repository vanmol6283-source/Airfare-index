import { useState } from "react";

function CheckboxList({ filterType, options, activeFilters, handleCheckboxChange }) {
  const [search, setSearch] = useState("");
  const filteredOptions = options.filter(opt => opt.toLowerCase().includes(search.toLowerCase()));
  
  return (
    <div className="flex flex-col gap-2">
      <input 
        type="text" 
        placeholder="Search..." 
        value={search}
        onChange={e => setSearch(e.target.value)}
        className="w-full border border-border rounded-sm px-2 py-1 font-sans text-[12px] focus:outline-none focus:border-primary"
      />
      <div className="max-h-[200px] overflow-y-auto flex flex-col gap-1 mt-1">
        {filteredOptions.map(opt => {
          const isChecked = activeFilters[filterType].includes(opt);
          return (
            <label key={opt} className="flex items-center gap-2 cursor-pointer hover:bg-gray-50 py-1 px-1">
              <input 
                type="checkbox" 
                checked={isChecked}
                onChange={(e) => handleCheckboxChange(filterType, opt, e.target.checked)}
                className="rounded-sm border-border text-primary focus:ring-primary"
              />
              <span className={`font-sans text-[12px] ${isChecked ? 'font-medium text-gray-900' : 'text-text-secondary'}`}>
                {opt}
              </span>
            </label>
          );
        })}
        {filteredOptions.length === 0 && (
          <div className="text-[11px] text-gray-400 font-sans italic py-1">No matches found.</div>
        )}
      </div>
    </div>
  );
}

function FilterSection({ title, count, total, isOpen, onToggle, children }) {
  return (
    <div className="border-b border-border">
      <button 
        onClick={onToggle}
        className="w-full flex items-center justify-between py-3 px-4 hover:bg-gray-50 focus:outline-none"
      >
        <div className="flex items-center gap-2">
          <span className="font-sans text-[13px] font-semibold text-text-secondary">{title}</span>
          <span className="font-sans text-[10px] text-gray-400">({count}/{total} selected)</span>
        </div>
        <span className="text-gray-400 text-xs">{isOpen ? "▼" : "▶"}</span>
      </button>
      {isOpen && (
        <div className="px-4 pb-4">
          {children}
        </div>
      )}
    </div>
  );
}

export default function FilterPanel({ 
  basket, 
  activeFilters, 
  setActiveFilters, 
  hideEmpty, 
  setHideEmpty,
  clearAllFilters 
}) {
  const [openSections, setOpenSections] = useState({
    routes: true,
    origins: false,
    destinations: false,
    airlines: false,
    fareTypes: false,
    apWindows: true,
  });

  const toggleSection = (section) => {
    setOpenSections(prev => ({ ...prev, [section]: !prev[section] }));
  };

  // Extract unique values
  const uniqueRoutes = Array.from(new Set(basket.map(i => i.route))).sort();
  const uniqueOrigins = Array.from(new Set(basket.map(i => i.origin))).sort();
  const uniqueDestinations = Array.from(new Set(basket.map(i => i.destination))).sort();
  const uniqueApWindows = Array.from(new Set(basket.map(i => i.apWindow))).sort();

  const handleCheckboxChange = (filterType, value, checked) => {
    setActiveFilters(prev => {
      const current = prev[filterType];
      if (checked) {
        return { ...prev, [filterType]: [...current, value] };
      } else {
        return { ...prev, [filterType]: current.filter(v => v !== value) };
      }
    });
  };


  const activeCount = Object.values(activeFilters).reduce((acc, curr) => acc + curr.length, 0);

  return (
    <div className="flex flex-col h-full">
      <div className="p-4 border-b border-border sticky top-0 bg-white z-10 flex flex-col gap-1">
        <div className="flex items-center justify-between">
          <h2 className="font-sans text-[12px] font-semibold uppercase tracking-wider text-text-secondary">FILTERS</h2>
          <button 
            onClick={clearAllFilters}
            className="font-sans text-[11px] font-medium text-primary hover:underline focus:outline-none"
          >
            Clear All
          </button>
        </div>
        <div className="font-sans text-[11px] text-gray-400">
          {activeCount} filter{activeCount !== 1 ? 's' : ''} active
        </div>
      </div>

      <div className="flex-1 overflow-y-auto">
        <FilterSection 
          title="Route" 
          count={activeFilters.routes.length} 
          total={uniqueRoutes.length}
          isOpen={openSections.routes}
          onToggle={() => toggleSection('routes')}
        >
          <CheckboxList filterType="routes" options={uniqueRoutes} activeFilters={activeFilters} handleCheckboxChange={handleCheckboxChange} />
        </FilterSection>

        <FilterSection 
          title="Origin" 
          count={activeFilters.origins.length} 
          total={uniqueOrigins.length}
          isOpen={openSections.origins}
          onToggle={() => toggleSection('origins')}
        >
          <CheckboxList filterType="origins" options={uniqueOrigins} activeFilters={activeFilters} handleCheckboxChange={handleCheckboxChange} />
        </FilterSection>

        <FilterSection 
          title="Destination" 
          count={activeFilters.destinations.length} 
          total={uniqueDestinations.length}
          isOpen={openSections.destinations}
          onToggle={() => toggleSection('destinations')}
        >
          <CheckboxList filterType="destinations" options={uniqueDestinations} activeFilters={activeFilters} handleCheckboxChange={handleCheckboxChange} />
        </FilterSection>

        <FilterSection 
          title="Airline" 
          count={0} 
          total={0}
          isOpen={openSections.airlines}
          onToggle={() => toggleSection('airlines')}
        >
          <div className="text-[11px] text-gray-400 font-sans italic">All Airlines (coming soon)</div>
        </FilterSection>
        
        <FilterSection 
          title="Fare Type" 
          count={0} 
          total={0}
          isOpen={openSections.fareTypes}
          onToggle={() => toggleSection('fareTypes')}
        >
          <div className="text-[11px] text-gray-400 font-sans italic">Economy only currently</div>
        </FilterSection>

        <FilterSection 
          title="AP Window" 
          count={activeFilters.apWindows.length} 
          total={uniqueApWindows.length}
          isOpen={openSections.apWindows}
          onToggle={() => toggleSection('apWindows')}
        >
          <CheckboxList filterType="apWindows" options={uniqueApWindows} activeFilters={activeFilters} handleCheckboxChange={handleCheckboxChange} />
        </FilterSection>
      </div>

      <div className="p-4 border-t border-border bg-gray-50 sticky bottom-0 z-10 flex flex-col gap-3">
        <button 
          className="w-full bg-primary text-white font-sans text-[12px] font-medium py-2 rounded-sm hover:bg-blue-800 transition-colors"
        >
          Apply Filters
        </button>
        <label className="flex items-center gap-2 cursor-pointer">
          <input 
            type="checkbox" 
            checked={hideEmpty}
            onChange={(e) => setHideEmpty(e.target.checked)}
            className="rounded-sm border-border text-primary focus:ring-primary"
          />
          <span className="font-sans text-[11px] text-text-secondary">
            Hide items without data
          </span>
        </label>
      </div>
    </div>
  );
}
