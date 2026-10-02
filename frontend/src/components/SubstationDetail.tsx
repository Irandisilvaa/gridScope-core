import React, { useEffect, useState, useMemo } from "react";
import { MetricCard } from "./MetricCard";
import { StatusPill } from "./StatusPill";
import { TemporalChart, DailyDispatchChart, ClassBarChart } from "./EnergyCharts";
import { Pagination } from "./Pagination";
import { api, type SolarSimulation, type Substation } from "../lib/api";
import { THEME_COLORS } from "../lib/theme";
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
import { DatePicker } from "./DatePicker";

type SubstationDetailProps = {
  row: Substation;
  onClose: () => void;
  municipalityCode?: string;
};

function formatNumber(value: number, maximumFractionDigits = 0) {
  return new Intl.NumberFormat("pt-BR", { maximumFractionDigits }).format(value);
}

export const SubstationDetail: React.FC<SubstationDetailProps> = ({ row, onClose, municipalityCode = "all" }) => {
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
      const res = await api.getSolarSimulation(
        row.id_tecnico,
        dateStr || simulationDate || undefined,
        municipalityCode,
      );
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
      className="relative overflow-hidden rounded-3xl border border-grid-border-card bg-grid-surface p-4 md:p-6 shadow-2xl double-bezel"
    >
      {/* Top Ambient Glow Line */}
      <div className="absolute inset-x-0 top-0 h-[2px] bg-gradient-to-r from-transparent via-grid-yellow to-transparent opacity-80" />

      {/* Header & Controls */}
      <div className="flex flex-col gap-4 border-b border-grid-border-subtle pb-5 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <div className="flex items-center gap-2">
            <span className="font-mono text-[0.68rem] font-bold uppercase tracking-[0.14em] text-grid-yellow">
              TELEMETRIA DO ATIVO OPERACIONAL
            </span>
            <span className="text-grid-gray">/</span>
            <span className="font-mono text-xs text-grid-gray">ID {row.id_tecnico}</span>
          </div>
          <h2
            id="substation-detail-title"
            className="mt-1 font-display text-2xl font-bold tracking-tight text-white md:text-3xl"
          >
            {cleanName}
          </h2>
          <div className="mt-2.5 flex flex-wrap items-center gap-3">
            <StatusPill label={row.metricas_rede.nivel_criticidade_gd} size="md" />
            <span className="font-mono text-xs text-grid-gray">
              Topologia de Barramento · Carga Publicada Vigente
            </span>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => setShowJsonRaw(!showJsonRaw)}
            className="flex items-center gap-1.5 rounded-lg border border-grid-border bg-grid-surface-elevated px-3 py-2 text-xs font-mono text-grid-gray transition-colors hover:border-grid-yellow hover:text-grid-yellow"
          >
            <Code size={14} />
            <span>{showJsonRaw ? "Ocultar JSON" : "Dados JSON"}</span>
          </button>
          <button
            type="button"
            onClick={onClose}
            className="flex h-9 w-9 items-center justify-center rounded-lg border border-grid-border bg-grid-surface-elevated text-grid-gray transition-colors hover:border-status-danger hover:text-status-danger"
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
        <div className="my-5 overflow-hidden rounded-xl border border-grid-border bg-grid-black p-4">
          <div className="flex items-center justify-between pb-2 mb-2 border-b border-grid-border-subtle">
            <span className="font-mono text-xs text-grid-yellow">Payload Técnico Bruto: {cleanName}</span>
          </div>
          <pre className="max-h-72 overflow-auto font-mono text-[0.72rem] text-grid-gray leading-relaxed select-all">
            {JSON.stringify(row, null, 2)}
          </pre>
        </div>
      )}

      {/* Solar Generation Simulation Module with Duck Curve Dispatch Chart */}
      <div className="my-6 rounded-2xl border border-grid-border-card bg-grid-surface p-4 md:p-6 double-bezel space-y-6">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between border-b border-grid-border-subtle pb-4">
          <div className="flex items-center gap-2.5">
            <SunHorizon size={24} className="text-grid-yellow shrink-0" />
            <div>
              <h3 className="font-display text-base font-semibold text-white">
                Simulação Fotovoltaica & Despacho de Alimentador
              </h3>
              <p className="text-xs text-grid-gray">
                Projeção integrada com modelo solar horário e consulta meteorológica por API.
              </p>
            </div>
          </div>

          {/* Date Picker & Simulation Trigger */}
          <div className="flex items-center gap-2">
            <DatePicker
              value={simulationDate}
              onChange={(date) => {
                setSimulationDate(date);
                executeSimulation(date);
              }}
              size="sm"
              align="right"
              placeholder="Selecionar data..."
            />

            <button
              type="button"
              onClick={() => executeSimulation()}
              disabled={isSimulating}
              className="flex items-center gap-1.5 rounded-xl border border-grid-yellow/50 bg-grid-yellow/15 px-3 py-2 font-mono text-xs font-bold text-grid-yellow transition-colors hover:bg-grid-yellow/25 disabled:opacity-50"
            >
              <ArrowClockwise size={13} className={isSimulating ? "animate-spin" : ""} />
              <span>{isSimulating ? "Calculando…" : "Simular"}</span>
            </button>
          </div>
        </div>

        {/* Real Simulation API Result Highlights */}
        {simulation && (
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4 rounded-xl border border-grid-border bg-grid-surface p-3.5 font-mono text-xs">
            <div>
              <span className="text-[0.66rem] text-grid-gray uppercase block">Fonte Meteorológica</span>
              <strong className="text-white text-[0.75rem] truncate block mt-0.5">{simulation.fonte_dados}</strong>
              <span className="text-[0.65rem] text-grid-yellow">{simulation.condicao_tempo}</span>
            </div>
            <div>
              <span className="text-[0.66rem] text-grid-gray uppercase block">Irradiação Solar</span>
              <strong className="text-grid-yellow text-sm block mt-0.5">
                {customIrradiation.toFixed(2)} kWh/m²
              </strong>
              <span className="text-[0.65rem] text-grid-gray">Base diária horizontal</span>
            </div>
            <div>
              <span className="text-[0.66rem] text-grid-gray uppercase block">Temperatura Máxima</span>
              <strong className="text-white text-sm block mt-0.5">
                {customTemp.toFixed(1)} °C
              </strong>
              <span className="text-[0.65rem] text-grid-gray">Perda térmica {dynamicThermalLoss.toFixed(1)}%</span>
            </div>
            <div>
              <span className="text-[0.66rem] text-grid-gray uppercase block">Geração Estimada (30d)</span>
              <strong className="text-grid-yellow text-sm block mt-0.5">
                {formatNumber(dynamicGenerationMwh, 2)} MWh
              </strong>
              <span className="text-[0.65rem] text-status-success">Rendimento calculado</span>
            </div>
          </div>
        )}

        {simulationError && (
          <div className="rounded-xl border border-status-danger/30 bg-status-danger/10 p-3 text-xs text-status-danger font-mono">
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
        <div className="rounded-xl border border-grid-surface-border bg-grid-surface p-4 space-y-3">
          <div className="flex items-center gap-2 border-b border-grid-border-subtle pb-2">
            <SlidersHorizontal size={15} className="text-grid-yellow" />
            <span className="font-mono text-xs font-semibold text-white">
              Ajuste Sensível de Variáveis Ambientais
            </span>
          </div>

          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-1.5">
              <div className="flex justify-between font-mono text-xs">
                <span className="text-grid-gray">Irradiação Solar Diária:</span>
                <strong className="text-grid-yellow">{customIrradiation.toFixed(2)} kWh/m²</strong>
              </div>
              <input
                type="range"
                min="2.0"
                max="8.0"
                step="0.1"
                value={customIrradiation}
                onChange={(e) => setCustomIrradiation(parseFloat(e.target.value))}
                className="w-full accent-grid-yellow cursor-pointer"
              />
              <span className="text-[0.65rem] text-grid-gray-dim block">
                Média do Nordeste Brasileiro: 5.4 kWh/m²
              </span>
            </div>

            <div className="space-y-1.5">
              <div className="flex justify-between font-mono text-xs">
                <span className="text-grid-gray">Temperatura Máxima do Módulo:</span>
                <strong className="text-grid-yellow">{customTemp.toFixed(1)} °C</strong>
              </div>
              <input
                type="range"
                min="18"
                max="48"
                step="0.5"
                value={customTemp}
                onChange={(e) => setCustomTemp(parseFloat(e.target.value))}
                className="w-full accent-grid-yellow cursor-pointer"
              />
              <span className="text-[0.65rem] text-grid-gray-dim block">
                Perda térmica calculada no silício: {dynamicThermalLoss.toFixed(2)}%
              </span>
            </div>
          </div>
        </div>

        {/* Impact Analysis Callout */}
        <div className="rounded-xl border border-grid-yellow/30 bg-grid-yellow/[0.06] p-3.5 text-xs text-grid-yellow">
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
            <span className="font-mono text-xs text-grid-gray">Métrica de Distribuição:</span>
            <div className="flex items-center gap-1 rounded-lg border border-grid-border bg-grid-surface-elevated p-1 font-mono text-[0.65rem]">
              <button
                type="button"
                onClick={() => setConsumptionMetric("consumo")}
                className={`rounded px-2 py-0.5 transition-colors ${
                  consumptionMetric === "consumo"
                    ? "bg-grid-yellow font-bold text-black"
                    : "text-grid-gray hover:text-white"
                }`}
              >
                Consumo MWh
              </button>
              <button
                type="button"
                onClick={() => setConsumptionMetric("clientes")}
                className={`rounded px-2 py-0.5 transition-colors ${
                  consumptionMetric === "clientes"
                    ? "bg-grid-yellow font-bold text-black"
                    : "text-grid-gray hover:text-white"
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
            accentColor={THEME_COLORS.brand.yellow}
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
            accentColor={THEME_COLORS.brand.yellow}
          />
        </div>
      </div>

      {/* Historical Evolution Section with Multi-Metric Temporal Chart */}
      {row.evolucao_temporal.length > 0 ? (
        <div className="rounded-2xl border border-grid-surface-border bg-grid-surface p-4 md:p-5 space-y-4">
          <div className="flex items-center justify-between border-b border-grid-border-subtle pb-3">
            <div>
              <span className="font-mono text-[0.66rem] font-bold uppercase tracking-[0.14em] text-grid-yellow">
                SÉRIE HISTÓRICA & TRAJETÓRIA GD
              </span>
              <h3 className="font-display text-sm font-semibold text-white">
                Evolução Temporal da Subestação
              </h3>
            </div>
            <span className="font-mono text-xs text-grid-gray">
              {row.evolucao_temporal.length} amostras mensais
            </span>
          </div>

          {/* Interactive Multi-Metric SVG Chart */}
          <TemporalChart data={row.evolucao_temporal} />

          {/* Table of samples with Most Recent First & Strict Pagination */}
          <div className="space-y-2 pt-2">
            <div className="flex items-center justify-between text-xs text-grid-gray font-mono">
              <span>Registros Mensais (Ordem Decrescente — Mais Recentes Primeiro)</span>
              <span>7 itens por página</span>
            </div>

            <div className="overflow-x-auto rounded-xl border border-grid-border bg-grid-surface">
              <table className="w-full min-w-[500px] border-collapse text-left font-mono text-xs">
                <thead>
                  <tr className="border-b border-grid-border bg-grid-surface-elevated text-[0.68rem] uppercase tracking-wider text-grid-gray">
                    <th className="py-2.5 px-3">Mês de Referência</th>
                    <th className="py-2.5 px-3">Clientes Acumulados</th>
                    <th className="py-2.5 px-3">Unidades MMGD</th>
                    <th className="py-2.5 px-3 text-right">Potência GD (kW)</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-grid-border-subtle">
                  {sortedEvolution
                    .slice((historyPage - 1) * historyPageSize, historyPage * historyPageSize)
                    .map((p) => (
                      <tr key={p.mes} className="hover:bg-grid-surface-elevated transition-colors">
                        <td className="py-2.5 px-3 font-bold text-white">{p.mes}</td>
                        <td className="py-2.5 px-3 text-grid-gray-subtle">{formatNumber(p.clientes)}</td>
                        <td className="py-2.5 px-3 text-grid-gray-subtle">{formatNumber(p.unidades_mmgd)}</td>
                        <td className="py-2.5 px-3 text-right font-bold text-grid-yellow">
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
        <div className="rounded-2xl border border-grid-border bg-grid-surface p-6 text-center text-xs text-grid-gray">
          A carga atual não possui série temporal histórica registrada para este ativo.
        </div>
      )}
    </section>
  );
};
