import type { Substation } from "../lib/api";
import { StatusPill } from "./StatusPill";

type SubstationTableProps = {
  rows: Substation[];
  onSelect?: (row: Substation) => void;
  selectedId?: string;
};

function formatNumber(value: number, maximumFractionDigits = 0) {
  return new Intl.NumberFormat("pt-BR", { maximumFractionDigits }).format(value);
}

function toneFor(criticality: string): "good" | "warn" | "muted" {
  if (criticality.toUpperCase().includes("CRÍT")) return "warn";
  if (criticality.toUpperCase().includes("MÉD")) return "warn";
  return "good";
}

export function SubstationTable({ rows, onSelect, selectedId }: SubstationTableProps) {
  return (
    <div className="overflow-x-auto">
      <table className="min-w-[680px] w-full border-collapse">
        <thead>
          <tr>
            <th className="border-t-0 px-3 py-[13px] text-left text-[0.65rem] font-bold uppercase tracking-[0.1em] text-[#688287]" scope="col">Subestação</th>
            <th className="border-t-0 px-3 py-[13px] text-left text-[0.65rem] font-bold uppercase tracking-[0.1em] text-[#688287]" scope="col">Clientes</th>
            <th className="border-t-0 px-3 py-[13px] text-left text-[0.65rem] font-bold uppercase tracking-[0.1em] text-[#688287]" scope="col">Consumo anual</th>
            <th className="border-t-0 px-3 py-[13px] text-left text-[0.65rem] font-bold uppercase tracking-[0.1em] text-[#688287]" scope="col">Potência GD</th>
            <th className="border-t-0 px-3 py-[13px] text-left text-[0.65rem] font-bold uppercase tracking-[0.1em] text-[#688287]" scope="col">Situação</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr className={selectedId === row.id_tecnico ? "bg-[#6fe7d2]/[0.07]" : ""} key={row.id_tecnico}>
              <th className="border-t border-white/10 px-3 py-[13px] text-left text-xs font-semibold text-[#eef6f3]" scope="row">
                {onSelect ? (
                  <button className="rounded-sm p-0 text-left font-bold text-[#6fe7d2] underline-offset-4 hover:underline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#6fe7d2]" onClick={() => onSelect(row)} type="button">
                    {row.subestacao.split(" (ID:")[0]}
                  </button>
                ) : (
                  row.subestacao.split(" (ID:")[0]
                )}
              </th>
              <td className="border-t border-white/10 px-3 py-[13px] text-xs text-[#a8bcbd]">{formatNumber(row.metricas_rede.total_clientes)}</td>
              <td className="border-t border-white/10 px-3 py-[13px] text-xs text-[#a8bcbd]">{formatNumber(row.metricas_rede.consumo_anual_mwh, 2)} MWh</td>
              <td className="border-t border-white/10 px-3 py-[13px] text-xs text-[#a8bcbd]">{formatNumber(row.geracao_distribuida.potencia_total_kw, 2)} kW</td>
              <td className="border-t border-white/10 px-3 py-[13px] text-xs text-[#a8bcbd]">
                <StatusPill
                  label={row.metricas_rede.nivel_criticidade_gd}
                  tone={toneFor(row.metricas_rede.nivel_criticidade_gd)}
                />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
