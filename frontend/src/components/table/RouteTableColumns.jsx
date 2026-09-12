import { createColumnHelper } from "@tanstack/react-table";
import { Link } from "react-router-dom";
import {
  FareCell,
  ChangeCell,
  RelativeCell,
} from "../shared/NumberCell";
import Sparkline from "../charts/Sparkline";

const helper = createColumnHelper();

export const routeTableColumns = [
  helper.accessor("route", {
    header: "Route",
    cell: (info) => (
      <Link
        to={`/route/${info.getValue()}`}
        className="font-sans font-semibold text-gray-900 hover:underline"
      >
        {info.getValue()}
      </Link>
    ),
    enableSorting: true,
  }),

  helper.accessor("origin", {
    header: "Origin",
    cell: (info) => (
      <span className="font-sans text-text-secondary">{info.getValue()}</span>
    ),
    enableSorting: true,
  }),

  helper.accessor("destination", {
    header: "Dest.",
    cell: (info) => (
      <span className="font-sans text-text-secondary">{info.getValue()}</span>
    ),
    enableSorting: true,
  }),

  helper.accessor("apWindow", {
    header: "AP Window",
    cell: (info) => (
      <span className="font-sans text-text-secondary">{info.getValue()}</span>
    ),
    enableSorting: true,
  }),

  helper.accessor("baseFare", {
    header: () => <span className="block text-right">Base Fare</span>,
    cell: (info) => (
      <div className="text-right">
        <FareCell value={info.getValue()} />
      </div>
    ),
    enableSorting: true,
  }),

  helper.accessor("currentFare", {
    header: () => <span className="block text-right">Current Fare</span>,
    cell: (info) => (
      <div className="text-right">
        <FareCell value={info.getValue()} />
      </div>
    ),
    enableSorting: true,
  }),

  helper.accessor("priceRelative", {
    header: () => <span className="block text-right">Pr. Relative</span>,
    cell: (info) => (
      <div className="text-right">
        <RelativeCell value={info.getValue() * 100} />
      </div>
    ),
    enableSorting: true,
  }),

  helper.accessor("weight", {
    header: () => <span className="block text-right">Weight</span>,
    cell: (info) => (
      <div className="text-right font-mono tabular-nums text-text-secondary">
        {info.getValue()?.toFixed(4)}
      </div>
    ),
    enableSorting: true,
  }),

  helper.accessor("change7d", {
    header: () => <span className="block text-right">7D Chg.</span>,
    cell: (info) => (
      <div className="text-right">
        <ChangeCell value={info.getValue()} />
      </div>
    ),
    enableSorting: true,
  }),

  helper.accessor("change30d", {
    header: () => <span className="block text-right">30D Chg.</span>,
    cell: (info) => (
      <div className="text-right">
        <ChangeCell value={info.getValue()} />
      </div>
    ),
    enableSorting: true,
  }),

  helper.accessor("history", {
    id: "trend",
    header: "30D Trend",
    cell: (info) => (
      <Sparkline data={info.getValue()} width={60} height={20} />
    ),
    enableSorting: false,
  }),
];

