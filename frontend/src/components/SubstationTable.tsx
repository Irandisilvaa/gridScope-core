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
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th scope="col">Subestação</th>
            <th scope="col">Clientes</th>
            <th scope="col">Consumo anual</th>
            <th scope="col">Potência GD</th>
            <th scope="col">Situação</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr className={selectedId === row.id_tecnico ? "table-row--selected" : ""} key={row.id_tecnico}>
              <th scope="row">
                {onSelect ? (
                  <button className="table-link rounded-sm focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#6fe7d2]" onClick={() => onSelect(row)} type="button">
                    {row.subestacao.split(" (ID:")[0]}
                  </button>
                ) : (
                  row.subestacao.split(" (ID:")[0]
                )}
              </th>
              <td>{formatNumber(row.metricas_rede.total_clientes)}</td>
              <td>{formatNumber(row.metricas_rede.consumo_anual_mwh, 2)} MWh</td>
              <td>{formatNumber(row.geracao_distribuida.potencia_total_kw, 2)} kW</td>
              <td>
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
