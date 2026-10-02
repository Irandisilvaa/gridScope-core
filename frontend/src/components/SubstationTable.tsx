import React, { useState, useMemo, useEffect } from "react";
import type { Substation } from "../lib/api";
import { StatusPill } from "./StatusPill";
import { Pagination } from "./Pagination";
import { ArrowUp, ArrowDown, CaretRight } from "@phosphor-icons/react";

type SubstationTableProps = {
  rows: Substation[];
  onSelect?: (row: Substation) => void;
  selectedId?: string;
  pageSize?: number;
  enablePagination?: boolean;
};

function formatNumber(value: number, maximumFractionDigits = 0) {
  return new Intl.NumberFormat("pt-BR", { maximumFractionDigits }).format(value);
}

export const SubstationTable: React.FC<SubstationTableProps> = ({
  rows,
  onSelect,
  selectedId,
  pageSize = 7,
  enablePagination = true,
}) => {
  const [sortField, setSortField] = useState<SortField>("gdPower");
  const [sortAsc, setSortAsc] = useState<boolean>(false);
  const [currentPage, setCurrentPage] = useState<number>(1);

  // Reset page when rows array changes or filters update
  useEffect(() => {
    setCurrentPage(1);
  }, [rows.length]);

  const handleSort = (field: SortField) => {
    if (sortField === field) {
      setSortAsc(!sortAsc);
    } else {
      setSortField(field);
      setSortAsc(false); // default desc for telemetry metrics
    }
    setCurrentPage(1);
  };

  type SortField = "name" | "clients" | "consumption" | "gdPower" | "criticality";

  const sortedRows = useMemo(() => {
    const copy = [...rows];
    return copy.sort((a, b) => {
      let valA: string | number = 0;
      let valB: string | number = 0;

      switch (sortField) {
        case "name":
          valA = a.subestacao.toLowerCase();
          valB = b.subestacao.toLowerCase();
          break;
        case "clients":
          valA = a.metricas_rede.total_clientes;
          valB = b.metricas_rede.total_clientes;
          break;
        case "consumption":
          valA = a.metricas_rede.consumo_anual_mwh;
          valB = b.metricas_rede.consumo_anual_mwh;
          break;
        case "gdPower":
          valA = a.geracao_distribuida.potencia_total_kw;
          valB = b.geracao_distribuida.potencia_total_kw;
          break;
        case "criticality":
          valA = a.metricas_rede.nivel_criticidade_gd;
          valB = b.metricas_rede.nivel_criticidade_gd;
          break;
      }

      if (valA < valB) return sortAsc ? -1 : 1;
      if (valA > valB) return sortAsc ? 1 : -1;
      return 0;
    });
  }, [rows, sortField, sortAsc]);

  const displayedRows = useMemo(() => {
    if (!enablePagination) return sortedRows;
    const start = (currentPage - 1) * pageSize;
    return sortedRows.slice(start, start + pageSize);
  }, [sortedRows, currentPage, pageSize, enablePagination]);

  const renderSortIcon = (field: SortField) => {
    if (sortField !== field) return null;
    return sortAsc ? (
      <ArrowUp size={12} className="inline ml-1 text-grid-yellow" />
    ) : (
      <ArrowDown size={12} className="inline ml-1 text-grid-yellow" />
    );
  };

  return (
    <div className="overflow-hidden rounded-xl border border-grid-border bg-grid-surface shadow-md">
      <div className="overflow-x-auto">
        <table className="w-full min-w-[700px] border-collapse text-left">
          <thead>
            <tr className="border-b border-grid-surface-border bg-grid-surface-raised text-[0.68rem] font-mono font-semibold uppercase tracking-[0.1em] text-grid-gray">
              <th
                className="cursor-pointer px-4 py-3.5 transition-colors hover:text-white"
                onClick={() => handleSort("name")}
                scope="col"
              >
                Subestação {renderSortIcon("name")}
              </th>
              <th
                className="cursor-pointer px-4 py-3.5 transition-colors hover:text-white"
                onClick={() => handleSort("clients")}
                scope="col"
              >
                Clientes {renderSortIcon("clients")}
              </th>
              <th
                className="cursor-pointer px-4 py-3.5 transition-colors hover:text-white"
                onClick={() => handleSort("consumption")}
                scope="col"
              >
                Consumo Anual {renderSortIcon("consumption")}
              </th>
              <th
                className="cursor-pointer px-4 py-3.5 transition-colors hover:text-white"
                onClick={() => handleSort("gdPower")}
                scope="col"
              >
                Potência GD {renderSortIcon("gdPower")}
              </th>
              <th
                className="cursor-pointer px-4 py-3.5 transition-colors hover:text-white"
                onClick={() => handleSort("criticality")}
                scope="col"
              >
                Criticidade GD {renderSortIcon("criticality")}
              </th>
              <th className="px-4 py-3.5 text-right" scope="col">
                Ação
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-grid-border-subtle">
            {displayedRows.map((row) => {
              const isSelected = selectedId === row.id_tecnico;
              const cleanName = row.subestacao.split(" (ID:")[0];

              return (
                <tr
                  key={row.id_tecnico}
                  onClick={() => onSelect && onSelect(row)}
                  className={`group cursor-pointer transition-colors ${
                    isSelected
                      ? "bg-grid-yellow/[0.08] border-l-2 border-l-grid-yellow"
                      : "hover:bg-grid-surface-elevated"
                  }`}
                >
                  <td className="px-4 py-3">
                    <div className="flex flex-col">
                      <strong className={`font-display text-xs ${isSelected ? "text-grid-yellow" : "text-white group-hover:text-grid-yellow"}`}>
                        {cleanName}
                      </strong>
                      <span className="font-mono text-[0.66rem] text-grid-gray">
                        ID: {row.id_tecnico}
                      </span>
                    </div>
                  </td>
                  <td className="px-4 py-3 font-mono text-xs text-grid-gray-subtle">
                    {formatNumber(row.metricas_rede.total_clientes)}
                  </td>
                  <td className="px-4 py-3 font-mono text-xs text-grid-gray-subtle">
                    {formatNumber(row.metricas_rede.consumo_anual_mwh, 2)}{" "}
                    <span className="text-[0.68rem] text-grid-gray">MWh</span>
                  </td>
                  <td className="px-4 py-3 font-mono text-xs font-semibold text-grid-yellow">
                    {formatNumber(row.geracao_distribuida.potencia_total_kw, 2)}{" "}
                    <span className="text-[0.68rem] text-grid-gray">kW</span>
                  </td>
                  <td className="px-4 py-3">
                    <StatusPill
                      label={row.metricas_rede.nivel_criticidade_gd}
                      size="sm"
                    />
                  </td>
                  <td className="px-4 py-3 text-right">
                    <button
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation();
                        onSelect && onSelect(row);
                      }}
                      className="inline-flex items-center gap-1 rounded-lg border border-grid-border bg-grid-surface-elevated px-2.5 py-1 text-[0.7rem] font-medium text-grid-gray transition-all hover:border-grid-yellow hover:text-grid-yellow group-hover:border-grid-yellow/50"
                    >
                      <span>Inspecionar</span>
                      <CaretRight size={12} />
                    </button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {/* Built-in Pagination Bar if > 7 items */}
      {enablePagination && (
        <Pagination
          currentPage={currentPage}
          totalItems={sortedRows.length}
          pageSize={pageSize}
          onPageChange={setCurrentPage}
        />
      )}
    </div>
  );
};
