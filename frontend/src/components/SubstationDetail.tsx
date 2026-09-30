import { useEffect, useState, type ReactNode } from "react";
import { MetricCard } from "./MetricCard";
import { StatusPill } from "./StatusPill";
import { api, type SolarSimulation, type Substation } from "../lib/api";

type SubstationDetailProps = {
  row: Substation;
  onClose: () => void;
};

const eyebrow = "text-[0.66rem] font-bold uppercase tracking-[0.14em] text-[#6fe7d2]";

function formatNumber(value: number, maximumFractionDigits = 0) {
  return new Intl.NumberFormat("pt-BR", { maximumFractionDigits }).format(value);
}

function toneFor(criticality: string): "good" | "warn" | "muted" {
  return criticality === "NORMAL" ? "good" : "warn";
}

function barWidth(percentage: number) {
  if (percentage >= 90) return "w-full";
  if (percentage >= 75) return "w-3/4";
  if (percentage >= 50) return "w-1/2";
  if (percentage >= 25) return "w-1/4";
  return "w-[12%]";
}

export function SubstationDetail({ row, onClose }: SubstationDetailProps) {
  const classes = Object.entries(row.perfil_consumo);
  const generationClasses = Object.entries(row.geracao_distribuida.detalhe_por_classe);
  const [simulationDate, setSimulationDate] = useState("");
  const [simulation, setSimulation] = useState<SolarSimulation | null>(null);
  const [simulationError, setSimulationError] = useState<string | null>(null);
  const [isSimulating, setIsSimulating] = useState(false);

  useEffect(() => {
    setSimulationDate("");
    setSimulation(null);
    setSimulationError(null);
  }, [row.id_tecnico]);

  async function runSimulation() {
    setIsSimulating(true);
    setSimulationError(null);
    try {
      setSimulation(await api.getSolarSimulation(row.id_tecnico, simulationDate || undefined));
    } catch {
      setSimulationError("Não foi possível calcular a simulação para este ativo.");
      setSimulation(null);
    } finally {
      setIsSimulating(false);
    }
  }

  return (
    <section className="grid gap-6 rounded-xl border border-[#6fe7d2]/25 bg-gradient-to-br from-[#6fe7d2]/[0.07] to-[#0d202c]/70 p-3 sm:p-6" aria-labelledby="substation-detail-title">
      <div className="flex flex-col items-start justify-between gap-5 sm:flex-row">
        <div>
          <span className={eyebrow}>Ativo selecionado · ID {row.id_tecnico}</span>
          <h2 className="mt-2 text-[clamp(1.1rem,2vw,1.45rem)] font-semibold tracking-[-0.035em]" id="substation-detail-title">{row.subestacao.split(" (ID:")[0]}</h2>
        </div>
        <button className="rounded-md border border-white/10 bg-transparent px-2.5 py-2 text-xs text-[#8ea4a7] hover:border-[#6fe7d2]/40 hover:text-[#6fe7d2] focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#6fe7d2]" onClick={onClose} type="button">
          Fechar detalhe
        </button>
      </div>

      <div className="flex items-center gap-2.5 text-xs text-[#8ea4a7]">
        <StatusPill label={row.metricas_rede.nivel_criticidade_gd} tone={toneFor(row.metricas_rede.nivel_criticidade_gd)} />
        <span>Dados da carga publicada atual</span>
      </div>

      <div className="grid grid-cols-2 gap-2.5 lg:grid-cols-4">
        <MetricCard label="Clientes" value={formatNumber(row.metricas_rede.total_clientes)} />
        <MetricCard label="Consumo anual" value={`${formatNumber(row.metricas_rede.consumo_anual_mwh, 2)} MWh`} />
        <MetricCard label="Unidades GD" value={formatNumber(row.geracao_distribuida.total_unidades)} />
        <MetricCard label="Potência GD" value={`${formatNumber(row.geracao_distribuida.potencia_total_kw, 2)} kW`} />
      </div>

      <DetailSection eyebrowText="Simulação solar" title="Projeção para este ativo">
        <div className="grid gap-4 rounded-lg border border-[#ffc857]/20 bg-[#ffc857]/[0.05] p-4">
          <p className="m-0 max-w-2xl text-sm leading-relaxed text-[#a8bcbd]">Estime a geração distribuída usando o ID técnico selecionado e a condição climática da data informada. A consulta climática é feita pelo backend.</p>
          <div className="flex flex-col items-start gap-3 sm:flex-row sm:items-end">
            <label className="grid gap-1.5 text-xs font-semibold text-[#a8bcbd]" htmlFor="simulation-date">
              Data de referência
              <input className="rounded-md border border-white/10 bg-[#08141f] px-3 py-2 text-sm font-normal text-[#eef6f3] outline-none focus:border-[#6fe7d2]/60 focus:ring-2 focus:ring-[#6fe7d2]/20" id="simulation-date" onChange={(event) => setSimulationDate(event.target.value)} type="date" value={simulationDate} />
            </label>
            <button className="rounded-md border border-[#ffc857]/40 bg-[#ffc857]/10 px-3 py-2 text-xs font-bold text-[#ffc857] transition-colors hover:border-[#ffc857]/70 hover:bg-[#ffc857]/20 disabled:cursor-wait disabled:opacity-60 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#ffc857]" disabled={isSimulating} onClick={runSimulation} type="button">
              {isSimulating ? "Calculando…" : "Simular geração"}
            </button>
          </div>
          {simulationError ? <p className="m-0 text-sm text-[#ff8379]" role="alert">{simulationError}</p> : null}
          {simulation ? (
            <div className="grid gap-3 border-t border-white/10 pt-4">
              <div className="grid grid-cols-2 gap-2.5 lg:grid-cols-4">
                <MetricCard label="Geração estimada" value={`${formatNumber(simulation.geracao_estimada_mwh, 2)} MWh`} note={simulation.data_referencia} />
                <MetricCard label="Irradiação" value={`${formatNumber(simulation.irradiacao_solar_kwh_m2, 2)} kWh/m²`} note={simulation.condicao_tempo} />
                <MetricCard label="Temperatura máxima" value={`${formatNumber(simulation.temperatura_max_c, 1)} °C`} note={`Perda térmica ${formatNumber(simulation.fator_perda_termica, 2)}%`} />
                <MetricCard label="Potência instalada" value={`${formatNumber(simulation.potencia_instalada_kw, 2)} kW`} note={simulation.fonte_dados} />
              </div>
              <p className="m-0 border-l-2 border-[#ffc857] pl-3 text-sm text-[#ffc857]">{simulation.impacto_na_rede}</p>
            </div>
          ) : null}
        </div>
      </DetailSection>

      <div className="grid gap-5 lg:grid-cols-2">
        <DetailSection eyebrowText="Perfil de consumo" title="Distribuição por classe">
          {classes.length ? (
            <div className="grid gap-3">
              {classes.map(([name, values]) => (
                <div className="grid grid-cols-[minmax(110px,1fr)_minmax(80px,2fr)_auto] items-center gap-2.5" key={name}>
                  <div>
                    <strong className="block text-xs">{name}</strong>
                    <span className="mt-0.5 block text-[0.68rem] text-[#8ea4a7]">{formatNumber(values.qtd_clientes)} clientes</span>
                  </div>
                  <div className="h-1.5 overflow-hidden rounded-full bg-white/[0.08]" aria-hidden="true"><span className={`block h-full rounded-full bg-[#6fe7d2] ${barWidth(values.pct)}`} /></div>
                  <strong className="whitespace-nowrap text-xs text-[#6fe7d2]">{formatNumber(values.pct, 1)}%</strong>
                </div>
              ))}
            </div>
          ) : <p className="m-0 text-sm text-[#8ea4a7]">Perfil de consumo não informado na carga atual.</p>}
        </DetailSection>

        <DetailSection eyebrowText="Geração distribuída" title="Potência por classe">
          {generationClasses.length ? (
            <div className="grid gap-1">
              {generationClasses.map(([name, values]) => (
                <div className="grid grid-cols-[1fr_auto] gap-2 border-b border-white/10 py-2" key={name}>
                  <div><strong className="block text-xs">{name}</strong><span className="mt-0.5 block text-[0.68rem] text-[#8ea4a7]">{formatNumber(values.qtd)} unidades</span></div>
                  <strong className="whitespace-nowrap text-xs text-[#6fe7d2]">{formatNumber(values.potencia_kw, 2)} kW</strong>
                </div>
              ))}
            </div>
          ) : <p className="m-0 text-sm text-[#8ea4a7]">Nenhuma classe de GD informada na carga atual.</p>}
        </DetailSection>
      </div>

      <DetailSection eyebrowText="Série histórica disponível" title="Evolução temporal">
        {row.evolucao_temporal.length ? (
          <div className="overflow-x-auto">
            <table className="min-w-[540px] w-full border-collapse">
              <thead><tr>
                <th className="border-t-0 px-3 py-3 text-left text-[0.65rem] font-bold uppercase tracking-[0.1em] text-[#688287]" scope="col">Mês</th>
                <th className="border-t-0 px-3 py-3 text-left text-[0.65rem] font-bold uppercase tracking-[0.1em] text-[#688287]" scope="col">Clientes acumulados</th>
                <th className="border-t-0 px-3 py-3 text-left text-[0.65rem] font-bold uppercase tracking-[0.1em] text-[#688287]" scope="col">Unidades GD</th>
                <th className="border-t-0 px-3 py-3 text-left text-[0.65rem] font-bold uppercase tracking-[0.1em] text-[#688287]" scope="col">Potência GD</th>
              </tr></thead>
              <tbody>{row.evolucao_temporal.map((point) => <tr key={point.mes}>
                <th className="border-t border-white/10 px-3 py-3 text-left text-xs font-semibold text-[#eef6f3]" scope="row">{point.mes}</th>
                <td className="border-t border-white/10 px-3 py-3 text-xs text-[#a8bcbd]">{formatNumber(point.clientes)}</td>
                <td className="border-t border-white/10 px-3 py-3 text-xs text-[#a8bcbd]">{formatNumber(point.unidades_mmgd)}</td>
                <td className="border-t border-white/10 px-3 py-3 text-xs text-[#a8bcbd]">{formatNumber(point.potencia_kw, 2)} kW</td>
              </tr>)}</tbody>
            </table>
          </div>
        ) : <p className="m-0 text-sm text-[#8ea4a7]">A carga atual não possui série temporal para este ativo.</p>}
      </DetailSection>
    </section>
  );
}

function DetailSection({ eyebrowText, title, children }: { eyebrowText: string; title: string; children: ReactNode }) {
  return <div className="grid gap-3"><div><span className={eyebrow}>{eyebrowText}</span><h3 className="mt-1 text-sm font-semibold tracking-[-0.02em]">{title}</h3></div>{children}</div>;
}
