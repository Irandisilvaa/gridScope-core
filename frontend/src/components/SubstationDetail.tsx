import React, { useEffect, useState } from "react";
import { MetricCard } from "./MetricCard";
import { StatusPill } from "./StatusPill";
import { TemporalChart, DailyDispatchChart } from "./EnergyCharts";
import { Pagination } from "./Pagination";
import { api, type SolarSimulation, type Substation } from "../lib/api";
import {
  Lightning,
  SunHorizon,
  Calendar,
  X,
  TrendUp,
  Buildings,
  Code,
  ShieldCheck,
  SlidersHorizontal,
} from "@phosphor-icons/react";

type SubstationDetailProps = {
  row: Substation;
  onClose: () => void;
};

function formatNumber(value: number, maximumFractionDigits = 0) {
  return new Intl.NumberFormat("pt-BR", { maximumFractionDigits }).format(value);
}

export const SubstationDetail: React.FC<SubstationDetailProps> = ({ row, onClose }) => {
  const classes = Object.entries(row.perfil_consumo);
  const generationClasses = Object.entries(row.geracao_distribuida.detalhe_por_classe);
  const [simulationDate, setSimulationDate] = useState("");
  const [simulation, setSimulation] = useState<SolarSimulation | null>(null);
  const [simulationError, setSimulationError] = useState<string | null>(null);
  const [isSimulating, setIsSimulating] = useState(false);
  const [showJsonRaw, setShowJsonRaw] = useState(false);
  const [historyPage, setHistoryPage] = useState(1);
  const historyPageSize = 7;

  // Dynamic Simulator Adjustment Sliders
  const [customIrradiation, setCustomIrradiation] = useState(5.4);
  const [customTemp, setCustomTemp] = useState(31.5);

  useEffect(() => {
    setSimulationDate(new Date().toISOString().split("T")[0]);
    setSimulation(null);
    setSimulationError(null);
    setShowJsonRaw(false);
    setHistoryPage(1);
    // Auto-run simulation on asset open
    runSimulation();
  }, [row.id_tecnico]);

  async function runSimulation() {
    setIsSimulating(true);
    setSimulationError(null);
    try {
      const res = await api.getSolarSimulation(row.id_tecnico, simulationDate || undefined);
      setSimulation(res);
      setCustomIrradiation(res.irradiacao_solar_kwh_m2);
      setCustomTemp(res.temperatura_max_c);
    } catch {
      setSimulationError("Não foi possível calcular a simulação para este ativo.");
      setSimulation(null);
    } finally {
      setIsSimulating(false);
    }
  }

  // Recalculate dynamic generation with adjusted sliders
  const dynamicThermalLoss = 5.0 + Math.max(0, (customTemp - 25) * 0.42);
  const dynamicGenerationMwh =
    (row.geracao_distribuida.potencia_total_kw *
      customIrradiation *
      (1 - dynamicThermalLoss / 100) *
      30) /
    1000;

  const cleanName = row.subestacao.split(" (ID:")[0];

  return (
    <section
      aria-labelledby="substation-detail-title"
      className="relative overflow-hidden rounded-3xl border border-[#2E2E2E] bg-[#0A0A0A] p-4 md:p-6 shadow-2xl double-bezel"
    >
      {/* Top Ambient Glow Line */}
      <div className="absolute inset-x-0 top-0 h-[2px] bg-gradient-to-r from-transparent via-[#FFD400] to-transparent opacity-80" />

      {/* Header & Controls */}
      <div className="flex flex-col gap-4 border-b border-[#222222] pb-5 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <div className="flex items-center gap-2">
            <span className="font-mono text-[0.68rem] font-bold uppercase tracking-[0.14em] text-[#FFD400]">
              TELEMETRIA DO ATIVO OPERACIONAL
            </span>
            <span className="text-[#8A8A8A]">/</span>
            <span className="font-mono text-xs text-[#8A8A8A]">ID {row.id_tecnico}</span>
          </div>
          <h2
            id="substation-detail-title"
            className="mt-1 font-display text-2xl font-bold tracking-tight text-white md:text-3xl"
          >
            {cleanName}
          </h2>
          <div className="mt-2.5 flex flex-wrap items-center gap-3">
            <StatusPill label={row.metricas_rede.nivel_criticidade_gd} size="md" />
            <span className="font-mono text-xs text-[#8A8A8A]">
              Topologia de Barramento · Carga Publicada Vigente
            </span>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => setShowJsonRaw(!showJsonRaw)}
            className="flex items-center gap-1.5 rounded-lg border border-[#262626] bg-[#141414] px-3 py-2 text-xs font-mono text-[#8A8A8A] transition-colors hover:border-[#FFD400] hover:text-[#FFD400]"
          >
            <Code size={14} />
            <span>{showJsonRaw ? "Ocultar JSON" : "Dados JSON"}</span>
          </button>
          <button
            type="button"
            onClick={onClose}
            className="flex h-9 w-9 items-center justify-center rounded-lg border border-[#262626] bg-[#141414] text-[#8A8A8A] transition-colors hover:border-[#EF4444] hover:text-[#EF4444]"
            title="Fechar Detalhe"
          >
            <X size={18} />
          </button>
        </div>
      </div>

      {/* Primary Telemetry Metrics */}
      <div className="my-6 grid grid-cols-2 gap-3 lg:grid-cols-4">
        <MetricCard
          label="Unidades Consumidoras"
          value={formatNumber(row.metricas_rede.total_clientes)}
          note="Consumidores cadastrados"
          icon={<Buildings size={16} />}
        />
        <MetricCard
          label="Consumo Anual Total"
          value={formatNumber(row.metricas_rede.consumo_anual_mwh, 2)}
          unit="MWh"
          note="Período da carga oficial"
          icon={<TrendUp size={16} />}
        />
        <MetricCard
          label="Unidades GD Instaladas"
          value={formatNumber(row.geracao_distribuida.total_unidades)}
          note="Sistemas conectados"
          icon={<ShieldCheck size={16} />}
        />
        <MetricCard
          label="Potência GD Total"
          value={formatNumber(row.geracao_distribuida.potencia_total_kw, 2)}
          unit="kW"
          note="Capacidade instalada"
          accent
          icon={<Lightning size={16} />}
        />
      </div>

      {/* Raw JSON Inspection Drawer */}
      {showJsonRaw && (
        <div className="my-5 overflow-hidden rounded-xl border border-[#2A2A2A] bg-[#050505] p-4">
          <div className="flex items-center justify-between pb-2 mb-2 border-b border-[#1F1F1F]">
            <span className="font-mono text-xs text-[#FFD400]">Payload Técnico Bruto: {cleanName}</span>
            <span className="font-mono text-[0.65rem] text-[#8A8A8A]">Schema v1.0</span>
          </div>
          <pre className="max-h-72 overflow-auto font-mono text-[0.72rem] text-[#8A8A8A] leading-relaxed select-all">
            {JSON.stringify(row, null, 2)}
          </pre>
        </div>
      )}

      {/* Solar Generation Simulation Module with Duck Curve Dispatch Chart */}
      <div className="my-6 rounded-2xl border border-[#2B2B2B] bg-[#0F0F0F] p-4 md:p-6 double-bezel space-y-6">
        <div className="flex items-center justify-between border-b border-[#222222] pb-3">
          <div className="flex items-center gap-2">
            <SunHorizon size={22} className="text-[#FFD400]" />
            <div>
              <h3 className="font-display text-base font-semibold text-white">
                Simulação Fotovoltaica & Despacho de Alimentador
              </h3>
              <p className="text-xs text-[#8A8A8A]">
                Modelagem estocástica do fluxo reverso de potência ativa ao longo de 24 horas.
              </p>
            </div>
          </div>
          <span className="font-mono text-xs text-[#FFD400]">
            Capacidade GD: {formatNumber(row.geracao_distribuida.potencia_total_kw, 1)} kW
          </span>
        </div>

        {/* 24h Solar Dispatch Duck Curve Chart */}
        <DailyDispatchChart gdPowerKw={row.geracao_distribuida.potencia_total_kw} />

        {/* Interactive Sliders: Solar Radiation & Temperature */}
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 rounded-xl border border-[#242424] bg-[#0A0A0A] p-4">
          <div className="space-y-1.5">
            <div className="flex justify-between font-mono text-xs">
              <span className="text-[#8A8A8A]">Irradiação Solar Diária:</span>
              <strong className="text-[#FFD400]">{customIrradiation.toFixed(2)} kWh/m²</strong>
            </div>
            <input
              type="range"
              min="2.5"
              max="7.5"
              step="0.1"
              value={customIrradiation}
              onChange={(e) => setCustomIrradiation(parseFloat(e.target.value))}
              className="w-full accent-[#FFD400] cursor-pointer"
            />
            <span className="text-[0.65rem] text-[#666666] block">
              Média regional NE: 5.4 kWh/m²
            </span>
          </div>

          <div className="space-y-1.5">
            <div className="flex justify-between font-mono text-xs">
              <span className="text-[#8A8A8A]">Temperatura Máxima Ambiente:</span>
              <strong className="text-[#FFD400]">{customTemp.toFixed(1)} °C</strong>
            </div>
            <input
              type="range"
              min="18"
              max="45"
              step="0.5"
              value={customTemp}
              onChange={(e) => setCustomTemp(parseFloat(e.target.value))}
              className="w-full accent-[#FFD400] cursor-pointer"
            />
            <span className="text-[0.65rem] text-[#666666] block">
              Perda térmica estimada: {dynamicThermalLoss.toFixed(2)}%
            </span>
          </div>

          <div className="flex flex-col justify-center rounded-lg border border-[#282828] bg-[#121212] p-3 text-center sm:col-span-2 lg:col-span-1">
            <span className="font-mono text-[0.68rem] text-[#8A8A8A]">GERAÇÃO CALCULADA (30 DIAS)</span>
            <strong className="font-mono text-xl text-[#FFD400] font-bold mt-0.5">
              {formatNumber(dynamicGenerationMwh, 2)} MWh
            </strong>
          </div>
        </div>

        {/* Impact Message */}
        <div className="rounded-xl border border-[#FFD400]/30 bg-[#FFD400]/[0.06] p-3.5 text-xs text-[#FFD400]">
          <strong className="block font-mono uppercase tracking-wider text-[0.7rem] text-white">
            Diagnóstico de Despacho & Estabilidade:
          </strong>
          <p className="mt-1 leading-relaxed">
            {row.geracao_distribuida.potencia_total_kw > 7000
              ? "Atenção: Alta concentração de GD. Risco de sobretensão no pico das 12h às 13h. Recomenda-se controle de tensão por tap automático de subestação."
              : "Operação estável. A curva de geração fotovoltaica é absorvida pela demanda local sem excedentes significativos na barra de alta tensão."}
          </p>
        </div>
      </div>

      {/* Grid: Consumption Profiles & GD Breakdown */}
      <div className="my-6 grid gap-6 lg:grid-cols-2">
        {/* Perfil de Consumo */}
        <div className="rounded-2xl border border-[#242424] bg-[#101010] p-4 md:p-5">
          <div className="flex items-center justify-between border-b border-[#202020] pb-3 mb-4">
            <div>
              <span className="font-mono text-[0.66rem] font-bold uppercase tracking-[0.14em] text-[#FFD400]">
                DEMANDA POR CLASSE
              </span>
              <h3 className="font-display text-sm font-semibold text-white">
                Distribuição de Consumo
              </h3>
            </div>
            <span className="font-mono text-xs text-[#8A8A8A]">{classes.length} classes</span>
          </div>

          <div className="space-y-3.5">
            {classes.map(([className, values]) => (
              <div key={className} className="space-y-1">
                <div className="flex items-center justify-between text-xs">
                  <span className="font-medium text-white">{className}</span>
                  <div className="flex items-center gap-3 font-mono">
                    <span className="text-[#8A8A8A]">
                      {formatNumber(values.qtd_clientes)} UC
                    </span>
                    <span className="font-bold text-[#FFD400]">
                      {formatNumber(values.pct, 1)}%
                    </span>
                  </div>
                </div>
                <div className="h-1.5 w-full overflow-hidden rounded-full bg-[#1C1C1C]">
                  <div
                    className="h-full rounded-full bg-[#FFD400] transition-all duration-500"
                    style={{ width: `${Math.min(values.pct, 100)}%` }}
                  />
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Detalhe GD por Classe */}
        <div className="rounded-2xl border border-[#242424] bg-[#101010] p-4 md:p-5">
          <div className="flex items-center justify-between border-b border-[#202020] pb-3 mb-4">
            <div>
              <span className="font-mono text-[0.66rem] font-bold uppercase tracking-[0.14em] text-[#FFD400]">
                GERAÇÃO DISTRIBUÍDA
              </span>
              <h3 className="font-display text-sm font-semibold text-white">
                Capacidade por Segmento
              </h3>
            </div>
            <span className="font-mono text-xs text-[#8A8A8A]">
              {generationClasses.length} segmentos
            </span>
          </div>

          <div className="space-y-3">
            {generationClasses.map(([segName, values]) => (
              <div
                key={segName}
                className="flex items-center justify-between border-b border-[#1C1C1C] pb-2 text-xs"
              >
                <div>
                  <strong className="block text-white">{segName}</strong>
                  <span className="font-mono text-[0.68rem] text-[#8A8A8A]">
                    {formatNumber(values.qtd)} unidades conectadas
                  </span>
                </div>
                <div className="text-right font-mono">
                  <strong className="block text-sm font-bold text-[#FFD400]">
                    {formatNumber(values.potencia_kw, 2)}{" "}
                    <span className="text-[0.7rem] text-[#8A8A8A]">kW</span>
                  </strong>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Historical Evolution Section with Temporal Growth Chart */}
      {row.evolucao_temporal.length > 0 && (
        <div className="rounded-2xl border border-[#242424] bg-[#101010] p-4 md:p-5 space-y-4">
          <div className="flex items-center justify-between border-b border-[#202020] pb-3">
            <div>
              <span className="font-mono text-[0.66rem] font-bold uppercase tracking-[0.14em] text-[#FFD400]">
                SÉRIE HISTÓRICA & TRAJETÓRIA GD
              </span>
              <h3 className="font-display text-sm font-semibold text-white">
                Evolução Temporal da Subestação
              </h3>
            </div>
            <span className="font-mono text-xs text-[#8A8A8A]">
              {row.evolucao_temporal.length} amostras
            </span>
          </div>

          {/* Interactive SVG Area Chart */}
          <TemporalChart data={row.evolucao_temporal} />

          {/* Table of samples */}
          <div className="overflow-x-auto pt-2">
            <table className="w-full min-w-[500px] border-collapse text-left font-mono text-xs">
              <thead>
                <tr className="border-b border-[#222222] text-[0.68rem] uppercase tracking-wider text-[#8A8A8A]">
                  <th className="py-2 px-3">Mês</th>
                  <th className="py-2 px-3">Clientes Acumulados</th>
                  <th className="py-2 px-3">Unidades GD</th>
                  <th className="py-2 px-3 text-right">Potência GD (kW)</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#1C1C1C]">
                {row.evolucao_temporal
                  .slice((historyPage - 1) * historyPageSize, historyPage * historyPageSize)
                  .map((p) => (
                    <tr key={p.mes} className="hover:bg-[#161616]">
                      <td className="py-2.5 px-3 font-semibold text-white">{p.mes}</td>
                      <td className="py-2.5 px-3 text-[#A0A0A0]">{formatNumber(p.clientes)}</td>
                      <td className="py-2.5 px-3 text-[#A0A0A0]">{formatNumber(p.unidades_mmgd)}</td>
                      <td className="py-2.5 px-3 text-right font-bold text-[#FFD400]">
                        {formatNumber(p.potencia_kw, 2)}
                      </td>
                    </tr>
                  ))}
              </tbody>
            </table>
          </div>

          {/* Pagination for historical series (7 items per page) */}
          <Pagination
            currentPage={historyPage}
            totalItems={row.evolucao_temporal.length}
            pageSize={historyPageSize}
            onPageChange={setHistoryPage}
          />
        </div>
      )}
    </section>
  );
};
