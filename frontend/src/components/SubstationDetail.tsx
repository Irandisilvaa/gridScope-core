import { MetricCard } from "./MetricCard";
import { StatusPill } from "./StatusPill";
import type { Substation } from "../lib/api";

type SubstationDetailProps = {
  row: Substation;
  onClose: () => void;
};

function formatNumber(value: number, maximumFractionDigits = 0) {
  return new Intl.NumberFormat("pt-BR", { maximumFractionDigits }).format(value);
}

function toneFor(criticality: string): "good" | "warn" | "muted" {
  return criticality === "NORMAL" ? "good" : "warn";
}

export function SubstationDetail({ row, onClose }: SubstationDetailProps) {
  const classes = Object.entries(row.perfil_consumo);
  const generationClasses = Object.entries(row.geracao_distribuida.detalhe_por_classe);

  return (
    <section className="detail-panel rounded-xl" aria-labelledby="substation-detail-title">
      <div className="detail-heading">
        <div>
          <span className="eyebrow">Ativo selecionado · ID {row.id_tecnico}</span>
          <h2 id="substation-detail-title">{row.subestacao.split(" (ID:")[0]}</h2>
        </div>
        <button className="detail-close rounded-md focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#6fe7d2]" onClick={onClose} type="button">
          Fechar detalhe
        </button>
      </div>

      <div className="detail-status">
        <StatusPill
          label={row.metricas_rede.nivel_criticidade_gd}
          tone={toneFor(row.metricas_rede.nivel_criticidade_gd)}
        />
        <span>Dados da carga publicada atual</span>
      </div>

      <div className="detail-metrics">
        <MetricCard label="Clientes" value={formatNumber(row.metricas_rede.total_clientes)} />
        <MetricCard label="Consumo anual" value={`${formatNumber(row.metricas_rede.consumo_anual_mwh, 2)} MWh`} />
        <MetricCard label="Unidades GD" value={formatNumber(row.geracao_distribuida.total_unidades)} />
        <MetricCard label="Potência GD" value={`${formatNumber(row.geracao_distribuida.potencia_total_kw, 2)} kW`} />
      </div>

      <div className="detail-columns">
        <div className="detail-section">
          <span className="eyebrow">Perfil de consumo</span>
          <h3>Distribuição por classe</h3>
          {classes.length ? (
            <div className="class-list">
              {classes.map(([name, values]) => (
                <div className="class-row" key={name}>
                  <div className="class-row__label">
                    <strong>{name}</strong>
                    <span>{formatNumber(values.qtd_clientes)} clientes</span>
                  </div>
                  <div className="class-row__bar" aria-hidden="true">
                    <span style={{ width: `${Math.min(Math.max(values.pct, 0), 100)}%` }} />
                  </div>
                  <strong className="class-row__value">{formatNumber(values.pct, 1)}%</strong>
                </div>
              ))}
            </div>
          ) : (
            <p className="empty-copy">Perfil de consumo não informado na carga atual.</p>
          )}
        </div>

        <div className="detail-section">
          <span className="eyebrow">Geração distribuída</span>
          <h3>Potência por classe</h3>
          {generationClasses.length ? (
            <div className="class-list">
              {generationClasses.map(([name, values]) => (
                <div className="class-row class-row--compact" key={name}>
                  <div className="class-row__label">
                    <strong>{name}</strong>
                    <span>{formatNumber(values.qtd)} unidades</span>
                  </div>
                  <strong className="class-row__value">{formatNumber(values.potencia_kw, 2)} kW</strong>
                </div>
              ))}
            </div>
          ) : (
            <p className="empty-copy">Nenhuma classe de GD informada na carga atual.</p>
          )}
        </div>
      </div>

      <div className="detail-section">
        <span className="eyebrow">Série histórica disponível</span>
        <h3>Evolução temporal</h3>
        {row.evolucao_temporal.length ? (
          <div className="table-wrap">
            <table className="detail-history">
              <thead>
                <tr>
                  <th scope="col">Mês</th>
                  <th scope="col">Clientes acumulados</th>
                  <th scope="col">Unidades GD</th>
                  <th scope="col">Potência GD</th>
                </tr>
              </thead>
              <tbody>
                {row.evolucao_temporal.map((point) => (
                  <tr key={point.mes}>
                    <th scope="row">{point.mes}</th>
                    <td>{formatNumber(point.clientes)}</td>
                    <td>{formatNumber(point.unidades_mmgd)}</td>
                    <td>{formatNumber(point.potencia_kw, 2)} kW</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="empty-copy">A carga atual não possui série temporal para este ativo.</p>
        )}
      </div>
    </section>
  );
}
