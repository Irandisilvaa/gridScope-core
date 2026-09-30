import React from "react";
import type { Substation, DataStatus } from "../lib/api";
import { BrandLogo } from "./BrandLogo";
import { Printer, X, ShieldCheck, DownloadSimple } from "@phosphor-icons/react";

interface ReportDossierModalProps {
  isOpen: boolean;
  onClose: () => void;
  rows: Substation[];
  dataStatus: DataStatus | null;
}

function formatNumber(value: number, maximumFractionDigits = 0) {
  return new Intl.NumberFormat("pt-BR", { maximumFractionDigits }).format(value);
}

export const ReportDossierModal: React.FC<ReportDossierModalProps> = ({
  isOpen,
  onClose,
  rows,
  dataStatus,
}) => {
  if (!isOpen) return null;

  const totalClients = rows.reduce((acc, r) => acc + r.metricas_rede.total_clientes, 0);
  const totalMwh = rows.reduce((acc, r) => acc + r.metricas_rede.consumo_anual_mwh, 0);
  const totalGdKw = rows.reduce((acc, r) => acc + r.geracao_distribuida.potencia_total_kw, 0);
  const totalGdUnits = rows.reduce((acc, r) => acc + r.geracao_distribuida.total_unidades, 0);

  const criticalRows = rows.filter(
    (r) => r.metricas_rede.nivel_criticidade_gd.toUpperCase() !== "NORMAL"
  );

  const handlePrint = () => {
    window.print();
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-3 sm:p-6 overflow-y-auto bg-black/85 backdrop-blur-md">
      <div className="relative w-full max-w-4xl max-h-[92vh] overflow-y-auto rounded-3xl border border-[#2B2B2B] bg-[#0A0A0A] p-6 sm:p-8 shadow-2xl text-white double-bezel print:border-none print:bg-white print:text-black print:p-0 print:max-h-none print:shadow-none">
        {/* Modal Controls (Hidden in Print) */}
        <div className="flex items-center justify-between border-b border-[#202020] pb-4 mb-6 print:hidden">
          <div className="flex items-center gap-2">
            <span className="font-mono text-xs text-[#FFD400]">VISUALIZAÇÃO DE DOCUMENTO OFICIAL</span>
            <span className="text-[#555555]">·</span>
            <span className="font-mono text-xs text-[#8A8A8A]">A4 / Impressão Técnica</span>
          </div>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={handlePrint}
              className="flex items-center gap-1.5 rounded-xl border border-[#FFD400] bg-[#FFD400] px-4 py-2 font-display text-xs font-bold text-black transition-colors hover:bg-[#FFE033]"
            >
              <Printer size={16} weight="bold" />
              <span>Imprimir / Salvar PDF</span>
            </button>
            <button
              type="button"
              onClick={onClose}
              className="flex h-9 w-9 items-center justify-center rounded-xl border border-[#2A2A2A] bg-[#141414] text-[#8A8A8A] hover:text-white"
            >
              <X size={18} />
            </button>
          </div>
        </div>

        {/* Printable Document Body */}
        <div className="space-y-6 print:text-black print:space-y-4">
          {/* Institutional Header */}
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between border-b border-[#2B2B2B] print:border-black pb-5 gap-4">
            <div>
              <BrandLogo variant="full" size="md" />
            </div>
            <div className="text-right font-mono text-xs text-[#8A8A8A] print:text-black">
              <strong className="block text-sm text-white print:text-black font-display">
                DOSSIÊ TÉCNICO DE TELEMETRIA
              </strong>
              <span>Doc. Ref: GS-REL-{new Date().getFullYear()}-001</span>
              <span className="block mt-0.5">
                Emissão: {new Date().toLocaleDateString("pt-BR")} às{" "}
                {new Date().toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" })}
              </span>
            </div>
          </div>

          {/* Document Metadata Bar */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 rounded-xl border border-[#222222] bg-[#121212] p-3.5 font-mono text-xs print:border-gray-300 print:bg-gray-100">
            <div>
              <span className="text-[0.66rem] text-[#8A8A8A] print:text-gray-600 block uppercase">
                Carga / Entrega
              </span>
              <strong className="text-white print:text-black font-bold">
                {dataStatus?.delivery_id ?? "GS-PROD-2026"}
              </strong>
            </div>
            <div>
              <span className="text-[0.66rem] text-[#8A8A8A] print:text-gray-600 block uppercase">
                Período Vigente
              </span>
              <strong className="text-white print:text-black font-bold">
                {dataStatus?.reference_period ?? "2025/2026"}
              </strong>
            </div>
            <div>
              <span className="text-[0.66rem] text-[#8A8A8A] print:text-gray-600 block uppercase">
                Status dos Dados
              </span>
              <strong className="text-[#22C55E] print:text-green-700 font-bold">
                Carga Homologada
              </strong>
            </div>
            <div>
              <span className="text-[0.66rem] text-[#8A8A8A] print:text-gray-600 block uppercase">
                Total de Ativos
              </span>
              <strong className="text-white print:text-black font-bold">
                {rows.length} Subestações
              </strong>
            </div>
          </div>

          {/* Executive KPI Summary */}
          <section className="space-y-2">
            <h3 className="font-display text-sm font-bold uppercase tracking-wider text-[#FFD400] print:text-black">
              1. Sumário Executivo do Sistema
            </h3>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
              <div className="rounded-xl border border-[#222222] bg-[#101010] p-3 text-center print:border-gray-300 print:bg-white">
                <span className="font-mono text-[0.68rem] text-[#8A8A8A] print:text-gray-600 block">
                  Clientes Conectados
                </span>
                <strong className="font-mono text-lg text-white print:text-black font-bold">
                  {formatNumber(totalClients)}
                </strong>
              </div>
              <div className="rounded-xl border border-[#222222] bg-[#101010] p-3 text-center print:border-gray-300 print:bg-white">
                <span className="font-mono text-[0.68rem] text-[#8A8A8A] print:text-gray-600 block">
                  Consumo Total Anual
                </span>
                <strong className="font-mono text-lg text-white print:text-black font-bold">
                  {formatNumber(totalMwh, 1)} MWh
                </strong>
              </div>
              <div className="rounded-xl border border-[#222222] bg-[#101010] p-3 text-center print:border-gray-300 print:bg-white">
                <span className="font-mono text-[0.68rem] text-[#8A8A8A] print:text-gray-600 block">
                  Capacidade GD Conectada
                </span>
                <strong className="font-mono text-lg text-[#FFD400] print:text-black font-bold">
                  {formatNumber(totalGdKw, 1)} kW
                </strong>
              </div>
              <div className="rounded-xl border border-[#222222] bg-[#101010] p-3 text-center print:border-gray-300 print:bg-white">
                <span className="font-mono text-[0.68rem] text-[#8A8A8A] print:text-gray-600 block">
                  Ativos Fora do Normal
                </span>
                <strong className="font-mono text-lg text-[#EF4444] print:text-red-700 font-bold">
                  {criticalRows.length} Ativos
                </strong>
              </div>
            </div>
          </section>

          {/* Critical Assets Evaluation */}
          <section className="space-y-2">
            <h3 className="font-display text-sm font-bold uppercase tracking-wider text-[#FFD400] print:text-black">
              2. Matriz de Criticidade de Geração Distribuída
            </h3>
            <p className="text-xs text-[#A0A0A0] print:text-gray-700 leading-relaxed">
              Ativos com alta taxa de penetração de micro e minigeração distribuída podem apresentar risco de elevação de tensão acima dos limites de conformidade do PRODIST durante períodos de irradiação solar de pico.
            </p>

            <div className="overflow-x-auto rounded-xl border border-[#222222] print:border-black">
              <table className="w-full text-left font-mono text-xs border-collapse">
                <thead>
                  <tr className="border-b border-[#222222] bg-[#141414] print:bg-gray-200 text-[0.66rem] uppercase text-[#8A8A8A] print:text-black">
                    <th className="py-2.5 px-3">Subestação</th>
                    <th className="py-2.5 px-3">ID Técnico</th>
                    <th className="py-2.5 px-3">Clientes</th>
                    <th className="py-2.5 px-3">Potência GD</th>
                    <th className="py-2.5 px-3">Situação</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[#1A1A1A] print:divide-gray-300">
                  {(criticalRows.length > 0 ? criticalRows : rows.slice(0, 5)).map((sub) => (
                    <tr key={sub.id_tecnico} className="print:bg-white">
                      <td className="py-2 px-3 font-semibold text-white print:text-black">
                        {sub.subestacao.split(" (ID:")[0]}
                      </td>
                      <td className="py-2 px-3 text-[#A0A0A0] print:text-gray-700">{sub.id_tecnico}</td>
                      <td className="py-2 px-3 text-[#A0A0A0] print:text-gray-700">
                        {formatNumber(sub.metricas_rede.total_clientes)}
                      </td>
                      <td className="py-2 px-3 text-[#FFD400] print:text-black font-bold">
                        {formatNumber(sub.geracao_distribuida.potencia_total_kw, 1)} kW
                      </td>
                      <td className="py-2 px-3">
                        <span
                          className={`font-bold ${
                            sub.metricas_rede.nivel_criticidade_gd.toUpperCase().includes("CRÍT")
                              ? "text-[#EF4444] print:text-red-700"
                              : "text-[#22C55E] print:text-green-700"
                          }`}
                        >
                          {sub.metricas_rede.nivel_criticidade_gd}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>

          {/* Technical Signatures */}
          <div className="pt-8 border-t border-[#222222] print:border-black grid grid-cols-2 gap-8 text-center font-mono text-xs">
            <div className="border-t border-[#444444] print:border-black pt-2">
              <span className="block font-bold text-white print:text-black">
                ENGENHARIA DE OPERAÇÃO & PLANEJAMENTO
              </span>
              <span className="text-[0.68rem] text-[#8A8A8A] print:text-gray-600">
                GridScope Power Analytics Unit
              </span>
            </div>
            <div className="border-t border-[#444444] print:border-black pt-2">
              <span className="block font-bold text-white print:text-black">
                SISTEMA DE CONFORMIDADE REGULATÓRIA
              </span>
              <span className="text-[0.68rem] text-[#8A8A8A] print:text-gray-600">
                Auditoria de Dados Homologados
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
