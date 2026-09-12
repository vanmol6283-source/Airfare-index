import {
  useReactTable,
  getCoreRowModel,
  getSortedRowModel,
  getFilteredRowModel,
  flexRender,
} from "@tanstack/react-table";
import { useState } from "react";

const densityPadding = {
  compact: "px-4 py-1.5",
  comfortable: "px-4 py-3",
};

export default function DataTable({
  data,
  columns,
  density = "comfortable",
  globalFilter,
  onGlobalFilterChange,
  showFilter = false,
}) {
  const [sorting, setSorting] = useState([]);
  const [internalFilter, setInternalFilter] = useState("");

  const filterValue =
    globalFilter !== undefined ? globalFilter : internalFilter;
  const setFilterValue =
    onGlobalFilterChange !== undefined
      ? onGlobalFilterChange
      : setInternalFilter;

  const table = useReactTable({
    data: data ?? [],
    columns,
    state: {
      sorting,
      globalFilter: filterValue,
    },
    onSortingChange: setSorting,
    onGlobalFilterChange: setFilterValue,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    getFilteredRowModel: getFilteredRowModel(),
  });

  const cellPad = densityPadding[density] || densityPadding.comfortable;

  return (
    <div>
      {showFilter && (
        <div className="border-b border-border px-4 py-2">
          <input
            type="text"
            value={filterValue}
            onChange={(e) => setFilterValue(e.target.value)}
            placeholder="Filter…"
            className="w-full max-w-xs border border-border bg-white px-3 py-1.5 font-sans text-[12px] text-gray-800 placeholder-gray-400 focus:outline-none focus:border-primary"
          />
        </div>
      )}

      <div className="overflow-x-auto">
        <table className="w-full border-collapse">
          <thead className="sticky top-0 z-10">
            {table.getHeaderGroups().map((headerGroup) => (
              <tr
                key={headerGroup.id}
                className="border-b border-border bg-gray-50"
              >
                {headerGroup.headers.map((header) => (
                  <th
                    key={header.id}
                    onClick={
                      header.column.getCanSort()
                        ? header.column.getToggleSortingHandler()
                        : undefined
                    }
                    className={`px-4 py-2 select-none whitespace-nowrap text-left font-sans text-[10px] font-semibold uppercase tracking-wide text-text-secondary ${
                      header.column.getCanSort()
                        ? "cursor-pointer hover:bg-gray-100"
                        : ""
                    }`}
                  >
                    <span className="inline-flex items-center gap-1">
                      {flexRender(
                        header.column.columnDef.header,
                        header.getContext()
                      )}
                      <span className="text-[8px]">
                        {header.column.getIsSorted() === "asc" && " ▲"}
                        {header.column.getIsSorted() === "desc" && " ▼"}
                      </span>
                    </span>
                  </th>
                ))}
              </tr>
            ))}
          </thead>

          <tbody className="bg-white">
            {table.getRowModel().rows.length === 0 ? (
              <tr>
                <td
                  colSpan={columns.length}
                  className="px-4 py-8 text-center text-gray-400 font-sans text-[12px]"
                >
                  No data available.
                </td>
              </tr>
            ) : (
              table.getRowModel().rows.map((row, i) => (
                <tr
                  key={row.id}
                  className={`border-b border-border hover:bg-blue-50/30 ${
                    i % 2 === 1 ? "bg-gray-50/40" : "bg-white"
                  }`}
                >
                  {row.getVisibleCells().map((cell) => (
                    <td key={cell.id} className={`${cellPad} text-gray-800 font-sans text-[12px]`}>
                      {flexRender(
                        cell.column.columnDef.cell,
                        cell.getContext()
                      )}
                    </td>
                  ))}
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

