import React, { useEffect, useState, useMemo } from "react";
import { MetricCard } from "./MetricCard";
import { StatusPill } from "./StatusPill";
import { TemporalChart, DailyDispatchChart, ClassBarChart } from "./EnergyCharts";
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
  CloudSun,
  ArrowClockwise,
} from "@phosphor-icons/react";

type SubstationDetailProps = {
  row: Substation;
  onClose: () => void;
};

function formatNumber(value: number, maximumFractionDigits = 0) {
  return new Intl.NumberFormat("pt-BR", { maximumFractionDigits }).format(value);
}

export const SubstationDetail: React.FC<SubstationDetailProps> = ({ row, onClose }) => {
  const [simulationDate, setSimulationDate] = useState("");
  const [simulation, setSimulation] = useState<SolarSimulation | null>(null);
  const [simulationError, setSimulationError] = useState<string | null>(null);
  const [isSimulating, setIsSimulating] = useState(false);
  const [showJsonRaw, setShowJsonRaw] = useState(false);
  const [historyPage, setHistoryPage] = useState(1);
  const historyPageSize = 7;

  // Simulator Sliders & Parameters
  const [customIrradiation, setCustomIrradiation] = useState(5.4);
  const [customTemp, setCustomTemp] = useState(31.5);
  const [consumptionMetric, setConsumptionMetric] = useState<"consumo" | "clientes">("consumo");

  useEffect(() => {
    const today = new Date().toISOString().split("T")[0];
    setSimulationDate(today);
    setSimulation(null);
    setSimulationError(null);
    setShowJsonRaw(false);
    setHistoryPage(1);
    // Trigger simulation fetch
    executeSimulation(today);
  }, [row.id_tecnico]);

  async function executeSimulation(dateStr?: string) {
    setIsSimulating(true);
    setSimulationError(null);
    try {
      const res = await api.getSolarSimulation(row.id_tecnico, dateStr || simulationDate || undefined);
      setSimulation(res);
      setCustomIrradiation(res.irradiacao_solar_kwh_m2);
      setCustomTemp(res.temperatura_max_c);
    } catch {
      setSimulationError("Não foi possível carregar a simulação climática da API.");
      setSimulation(null);
    } finally {
      setIsSimulating(false);
    }
  }

  // Calculate dynamic generation using adjusted slider values
  const dynamicThermalLoss = 5.0 + Math.max(0, (customTemp - 25) * 0.42);
  const dynamicGenerationMwh =
    (row.geracao_distribuida.potencia_total_kw *
      customIrradiation *
      (1 - dynamicThermalLoss / 100) *
      30) /
    1000;

  const cleanName = row.subestacao.split(" (ID:")[0];

  // Prepare Class Breakdown Data for Charts
  const consumptionChartItems = useMemo(() => {
    const entries = Object.entries(row.perfil_consumo);
    return entries.map(([className, values]) => {
      const val = consumptionMetric === "consumo" ? (values.consumo_anual_mwh ?? 0) : values.qtd_clientes;
      return {
        name: className,
        value: val,
        percentage: values.pct,
        secondaryText: consumptionMetric === "consumo" ? `${formatNumber(values.qtd_clientes)} UCs` : undefined,
      };
    }).sort((a, b) => b.value - a.value);
  }, [row.perfil_consumo, consumptionMetric]);

  const gdClassChartItems = useMemo(() => {
    const entries = Object.entries(row.geracao_distribuida.detalhe_por_classe);
    const totalPower = row.geracao_distribuida.potencia_total_kw || 1;
    return entries.map(([segName, values]) => ({
      name: segName,
      value: values.potencia_kw,
      secondaryText: `${formatNumber(values.qtd)} unid.`,
      percentage: (values.potencia_kw / totalPower) * 100,
    })).sort((a, b) => b.value - a.value);
  }, [row.geracao_distribuida]);

  // Order historical evolution DESCENDING so page 1 shows most recent months
  const sortedEvolution = useMemo(() => {
    return [...row.evolucao_temporal].reverse();
  }, [row.evolucao_temporal]);

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
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between border-b border-[#222222] pb-4">
          <div className="flex items-center gap-2.5">
            <SunHorizon size={24} className="text-[#FFD400] shrink-0" />
            <div>
              <h3 className="font-display text-base font-semibold text-white">
                Simulação Fotovoltaica & Despacho de Alimentador
              </h3>
              <p className="text-xs text-[#8A8A8A]">
                Projeção integrada com modelo solar horário e consulta meteorológica por API.
              </p>
            </div>
          </div>

          {/* Date Picker & Simulation Trigger */}
          <div className="flex items-center gap-2">
            <div className="flex items-center gap-1.5 rounded-xl border border-[#2A2A2A] bg-[#141414] px-2.5 py-1.5 font-mono text-xs text-[#A0A0A0]">
              <Calendar size={14} className="text-[#FFD400]" />
              <input
                type="date"
                value={simulationDate}
                onChange={(e) => setSimulationDate(e.target.value)}
                className="bg-transparent text-white outline-none cursor-pointer"
              />
            </div>

            <button
              type="button"
              onClick={() => executeSimulation()}
              disabled={isSimulating}
              className="flex items-center gap-1.5 rounded-xl border border-[#FFD400]/50 bg-[#FFD400]/15 px-3 py-2 font-mono text-xs font-bold text-[#FFD400] transition-colors hover:bg-[#FFD400]/25 disabled:opacity-50"
            >
              <ArrowClockwise size={13} className={isSimulating ? "animate-spin" : ""} />
              <span>{isSimulating ? "Calculando…" : "Simular"}</span>
            </button>
          </div>
        </div>

        {/* Real Simulation API Result Highlights */}
        {simulation && (
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4 rounded-xl border border-[#262626] bg-[#0A0A0A] p-3.5 font-mono text-xs">
            <div>
              <span className="text-[0.66rem] text-[#8A8A8A] uppercase block">Fonte Meteorológica</span>
              <strong className="text-white text-[0.75rem] truncate block mt-0.5">{simulation.fonte_dados}</strong>
              <span className="text-[0.65rem] text-[#FFD400]">{simulation.condicao_tempo}</span>
            </div>
            <div>
              <span className="text-[0.66rem] text-[#8A8A8A] uppercase block">Irradiação Solar</span>
              <strong className="text-[#FFD400] text-sm block mt-0.5">
                {customIrradiation.toFixed(2)} kWh/m²
              </strong>
              <span className="text-[0.65rem] text-[#8A8A8A]">Base diária horizontal</span>
            </div>
            <div>
              <span className="text-[0.66rem] text-[#8A8A8A] uppercase block">Temperatura Máxima</span>
              <strong className="text-white text-sm block mt-0.5">
                {customTemp.toFixed(1)} °C
              </strong>
              <span className="text-[0.65rem] text-[#8A8A8A]">Perda térmica {dynamicThermalLoss.toFixed(1)}%</span>
            </div>
            <div>
              <span className="text-[0.66rem] text-[#8A8A8A] uppercase block">Geração Estimada (30d)</span>
              <strong className="text-[#FFD400] text-sm block mt-0.5">
                {formatNumber(dynamicGenerationMwh, 2)} MWh
              </strong>
              <span className="text-[0.65rem] text-[#22C55E]">Rendimento calculado</span>
            </div>
          </div>
        )}

        {simulationError && (
          <div className="rounded-xl border border-[#EF4444]/30 bg-[#EF4444]/10 p-3 text-xs text-[#EF4444] font-mono">
            {simulationError}
          </div>
        )}

        {/* 24h Solar Dispatch Duck Curve Chart connected dynamically */}
        <DailyDispatchChart
          gdPowerKw={row.geracao_distribuida.potencia_total_kw}
          annualConsumptionMwh={row.metricas_rede.consumo_anual_mwh}
          substationName={cleanName}
          irradianceKwhM2={customIrradiation}
          tempMaxC={customTemp}
          thermalLossPct={dynamicThermalLoss}
          calculatedGenerationMwh={dynamicGenerationMwh}
        />

        {/* Fine Tuning Sliders */}
        <div className="rounded-xl border border-[#242424] bg-[#0A0A0A] p-4 space-y-3">
          <div className="flex items-center gap-2 border-b border-[#1A1A1A] pb-2">
            <SlidersHorizontal size={15} className="text-[#FFD400]" />
            <span className="font-mono text-xs font-semibold text-white">
              Ajuste Sensível de Variáveis Ambientais
            </span>
          </div>

          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-1.5">
              <div className="flex justify-between font-mono text-xs">
                <span className="text-[#8A8A8A]">Irradiação Solar Diária:</span>
                <strong className="text-[#FFD400]">{customIrradiation.toFixed(2)} kWh/m²</strong>
              </div>
              <input
                type="range"
                min="2.0"
                max="8.0"
                step="0.1"
                value={customIrradiation}
                onChange={(e) => setCustomIrradiation(parseFloat(e.target.value))}
                className="w-full accent-[#FFD400] cursor-pointer"
              />
              <span className="text-[0.65rem] text-[#666666] block">
                Média do Nordeste Brasileiro: 5.4 kWh/m²
              </span>
            </div>

            <div className="space-y-1.5">
              <div className="flex justify-between font-mono text-xs">
                <span className="text-[#8A8A8A]">Temperatura Máxima do Módulo:</span>
                <strong className="text-[#FFD400]">{customTemp.toFixed(1)} °C</strong>
              </div>
              <input
                type="range"
                min="18"
                max="48"
                step="0.5"
                value={customTemp}
                onChange={(e) => setCustomTemp(parseFloat(e.target.value))}
                className="w-full accent-[#FFD400] cursor-pointer"
              />
              <span className="text-[0.65rem] text-[#666666] block">
                Perda térmica calculada no silício: {dynamicThermalLoss.toFixed(2)}%
              </span>
            </div>
          </div>
        </div>

        {/* Impact Analysis Callout */}
        <div className="rounded-xl border border-[#FFD400]/30 bg-[#FFD400]/[0.06] p-3.5 text-xs text-[#FFD400]">
          <strong className="block font-mono uppercase tracking-wider text-[0.7rem] text-white">
            Diagnóstico de Despacho & Estabilidade:
          </strong>
          <p className="mt-1 leading-relaxed">
            {simulation?.impacto_na_rede ??
              (row.geracao_distribuida.potencia_total_kw > 7000
                ? "Atenção: Alta concentração de GD. Risco de sobretensão no pico das 12h às 13h. Recomenda-se controle de tensão por tap automático de subestação."
                : "Operação estável. A curva de geração fotovoltaica é absorvida pela demanda local sem excedentes significativos na barra de alta tensão.")}
          </p>
        </div>
      </div>

      {/* Grid: Consumption Profiles & GD Breakdown (Using ClassBarChart) */}
      <div className="my-6 grid gap-6 lg:grid-cols-2">
        {/* Perfil de Consumo */}
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <span className="font-mono text-xs text-[#8A8A8A]">Métrica de Distribuição:</span>
            <div className="flex items-center gap-1 rounded-lg border border-[#222222] bg-[#141414] p-1 font-mono text-[0.65rem]">
              <button
                type="button"
                onClick={() => setConsumptionMetric("consumo")}
                className={`rounded px-2 py-0.5 transition-colors ${
                  consumptionMetric === "consumo"
                    ? "bg-[#FFD400] font-bold text-black"
                    : "text-[#8A8A8A] hover:text-white"
                }`}
              >
                Consumo MWh
              </button>
              <button
                type="button"
                onClick={() => setConsumptionMetric("clientes")}
                className={`rounded px-2 py-0.5 transition-colors ${
                  consumptionMetric === "clientes"
                    ? "bg-[#FFD400] font-bold text-black"
                    : "text-[#8A8A8A] hover:text-white"
                }`}
              >
                Clientes (UCs)
              </button>
            </div>
          </div>

          <ClassBarChart
            title="DEMANDA POR CLASSE"
            subtitle={consumptionMetric === "consumo" ? "Consumo Anual Consolidado (MWh)" : "Número de Unidades Consumidoras"}
            items={consumptionChartItems}
            unit={consumptionMetric === "consumo" ? "MWh" : "UCs"}
            accentColor="#FFD400"
          />
        </div>

        {/* Detalhe GD por Segmento */}
        <div className="space-y-3">
          <div className="h-[26px]" /> {/* Spacer to align with metric switcher */}
          <ClassBarChart
            title="GERAÇÃO DISTRIBUÍDA"
            subtitle="Capacidade Instalada por Segmento (kW)"
            items={gdClassChartItems}
            unit="kW"
            accentColor="#FFD400"
          />
        </div>
      </div>

      {/* Historical Evolution Section with Multi-Metric Temporal Chart */}
      {row.evolucao_temporal.length > 0 ? (
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
              {row.evolucao_temporal.length} amostras mensais
            </span>
          </div>

          {/* Interactive Multi-Metric SVG Chart */}
          <TemporalChart data={row.evolucao_temporal} />

          {/* Table of samples with Most Recent First & Strict Pagination */}
          <div className="space-y-2 pt-2">
            <div className="flex items-center justify-between text-xs text-[#8A8A8A] font-mono">
              <span>Registros Mensais (Ordem Decrescente — Mais Recentes Primeiro)</span>
              <span>7 itens por página</span>
            </div>

            <div className="overflow-x-auto rounded-xl border border-[#222222] bg-[#0C0C0C]">
              <table className="w-full min-w-[500px] border-collapse text-left font-mono text-xs">
                <thead>
                  <tr className="border-b border-[#222222] bg-[#141414] text-[0.68rem] uppercase tracking-wider text-[#8A8A8A]">
                    <th className="py-2.5 px-3">Mês de Referência</th>
                    <th className="py-2.5 px-3">Clientes Acumulados</th>
                    <th className="py-2.5 px-3">Unidades MMGD</th>
                    <th className="py-2.5 px-3 text-right">Potência GD (kW)</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[#1C1C1C]">
                  {sortedEvolution
                    .slice((historyPage - 1) * historyPageSize, historyPage * historyPageSize)
                    .map((p) => (
                      <tr key={p.mes} className="hover:bg-[#161616] transition-colors">
                        <td className="py-2.5 px-3 font-bold text-white">{p.mes}</td>
                        <td className="py-2.5 px-3 text-[#CCCCCC]">{formatNumber(p.clientes)}</td>
                        <td className="py-2.5 px-3 text-[#CCCCCC]">{formatNumber(p.unidades_mmgd)}</td>
                        <td className="py-2.5 px-3 text-right font-bold text-[#FFD400]">
                          {formatNumber(p.potencia_kw, 2)} kW
                        </td>
                      </tr>
                    ))}
                </tbody>
              </table>
            </div>

            {/* Pagination for historical series (7 items per page) */}
            <Pagination
              currentPage={historyPage}
              totalItems={sortedEvolution.length}
              pageSize={historyPageSize}
              onPageChange={setHistoryPage}
            />
          </div>
        </div>
      ) : (
        <div className="rounded-2xl border border-[#222222] bg-[#101010] p-6 text-center text-xs text-[#8A8A8A]">
          A carga atual não possui série temporal histórica registrada para este ativo.
        </div>
      )}
    </section>
  );
};
