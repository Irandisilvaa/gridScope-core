import React, { useState } from "react";
import type { Substation } from "../lib/api";
import {
  Lightning,
  PaperPlaneTilt,
  Sparkle,
  Cpu,
  WarningCircle,
  ChartBar,
} from "@phosphor-icons/react";

interface NetworkAssistantProps {
  rows: Substation[];
  onSelectSubstation?: (id: string) => void;
}

interface Message {
  id: string;
  sender: "user" | "helio";
  text: string;
  timestamp: string;
  substationsMentioned?: Array<{ name: string; id: string; gdPower: number }>;
}

export const NetworkAssistant: React.FC<NetworkAssistantProps> = ({
  rows,
  onSelectSubstation,
}) => {
  const [messages, setMessages] = useState<Message[]>([
    {
      id: "welcome",
      sender: "helio",
      text: "Olá! Sou o Hélio, seu especialista em inteligência de rede na GridScope. Analiso em tempo real os dados de carga, penetração de GD fotovoltaica e criticidade dos 32 barramentos da nossa rede. Em que posso contribuir com sua operação hoje?",
      timestamp: new Date().toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" }),
    },
  ]);
  const [input, setInput] = useState("");
  const [isThinking, setIsThinking] = useState(false);

  const presetQueries = [
    {
      label: "Quais ativos estão em nível crítico de GD?",
      icon: <WarningCircle size={14} className="text-[#EF4444]" />,
    },
    {
      label: "Top 5 subestações com maior potência solar conectada",
      icon: <Lightning size={14} className="text-[#FFD400]" />,
    },
    {
      label: "Qual o balanço geral entre consumo e geração instalada?",
      icon: <ChartBar size={14} className="text-[#3B82F6]" />,
    },
    {
      label: "Como a perda térmica afeta a eficiência fotovoltaica no verão?",
      icon: <Cpu size={14} className="text-[#22C55E]" />,
    },
  ];

  const handleSend = (userText: string) => {
    if (!userText.trim()) return;

    const time = new Date().toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" });
    const userMsg: Message = {
      id: String(Date.now()),
      sender: "user",
      text: userText,
      timestamp: time,
    };

    setMessages((prev) => [...prev, userMsg]);
    setInput("");
    setIsThinking(true);

    setTimeout(() => {
      const response = generateHelioResponse(userText, rows);
      const helioMsg: Message = {
        id: String(Date.now() + 1),
        sender: "helio",
        text: response.text,
        timestamp: new Date().toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" }),
        substationsMentioned: response.substationsMentioned,
      };
      setMessages((prev) => [...prev, helioMsg]);
      setIsThinking(false);
    }, 600);
  };

  return (
    <div className="flex flex-col h-[740px] max-w-5xl mx-auto rounded-3xl border border-[#2B2B2B] bg-[#0A0A0A] overflow-hidden shadow-2xl double-bezel">
      {/* Header with Hélio Avatar and Telemetry Status */}
      <div className="flex items-center justify-between border-b border-[#202020] bg-[#0F0F0F] px-6 py-4">
        <div className="flex items-center gap-3.5">
          <div className="relative">
            <img
              src="/brand/helio.png"
              alt="Hélio - Assistente GridScope"
              className="h-12 w-12 rounded-full border-2 border-[#FFD400] object-cover bg-black"
            />
            <span className="absolute bottom-0 right-0 h-3.5 w-3.5 rounded-full border-2 border-[#0A0A0A] bg-[#22C55E]" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <strong className="font-display text-base text-white">Hélio</strong>
              <span className="rounded-full border border-[#FFD400]/40 bg-[#FFD400]/10 px-2 py-0.5 font-mono text-[0.65rem] font-bold text-[#FFD400]">
                AGENTE ANALÍTICO
              </span>
            </div>
            <span className="font-mono text-xs text-[#8A8A8A]">
              Especialista Técnico de Rede · Carga Ativa: {rows.length} Subestações
            </span>
          </div>
        </div>

        <div className="hidden sm:flex items-center gap-2 font-mono text-xs text-[#8A8A8A]">
          <span className="h-2 w-2 rounded-full bg-[#22C55E] animate-pulse" />
          <span>Sessão Telemetria Conectada</span>
        </div>
      </div>

      {/* Messages Conversation Stream */}
      <div className="flex-1 overflow-y-auto p-6 space-y-5">
        {messages.map((m) => (
          <div
            key={m.id}
            className={`flex gap-3 ${m.sender === "user" ? "justify-end" : "justify-start"}`}
          >
            {m.sender === "helio" && (
              <img
                src="/brand/helio.png"
                alt="Hélio"
                className="h-8 w-8 rounded-full border border-[#FFD400] object-cover shrink-0 mt-1"
              />
            )}

            <div
              className={`max-w-[80%] rounded-2xl p-4 text-sm leading-relaxed ${
                m.sender === "user"
                  ? "bg-[#FFD400] text-black font-medium"
                  : "bg-[#141414] border border-[#242424] text-[#E0E0E0]"
              }`}
            >
              <div className="whitespace-pre-line">{m.text}</div>

              {/* Mentioned Substation Action Buttons */}
              {m.substationsMentioned && m.substationsMentioned.length > 0 && (
                <div className="mt-3 pt-3 border-t border-[#2A2A2A] flex flex-wrap gap-2">
                  <span className="text-[0.68rem] font-mono text-[#8A8A8A] block w-full">
                    Ativos referenciados (clique para abrir telemetria):
                  </span>
                  {m.substationsMentioned.map((s) => (
                    <button
                      key={s.id}
                      type="button"
                      onClick={() => onSelectSubstation && onSelectSubstation(s.id)}
                      className="inline-flex items-center gap-1 rounded-lg border border-[#333333] bg-[#0A0A0A] px-2.5 py-1 text-xs font-mono text-[#FFD400] transition-colors hover:border-[#FFD400]"
                    >
                      <Lightning size={12} weight="fill" />
                      <span>{s.name}</span>
                      <span className="text-[0.65rem] text-[#8A8A8A]">({s.gdPower.toFixed(0)} kW)</span>
                    </button>
                  ))}
                </div>
              )}

              <span
                className={`mt-2 block font-mono text-[0.62rem] text-right ${
                  m.sender === "user" ? "text-black/60" : "text-[#777777]"
                }`}
              >
                {m.timestamp}
              </span>
            </div>
          </div>
        ))}

        {isThinking && (
          <div className="flex gap-3 items-center text-xs font-mono text-[#8A8A8A]">
            <img
              src="/brand/helio.png"
              alt="Hélio"
              className="h-8 w-8 rounded-full border border-[#FFD400] object-cover shrink-0"
            />
            <div className="flex items-center gap-1.5 rounded-xl border border-[#222222] bg-[#141414] px-4 py-2.5">
              <span className="h-1.5 w-1.5 rounded-full bg-[#FFD400] animate-bounce" />
              <span className="h-1.5 w-1.5 rounded-full bg-[#FFD400] animate-bounce [animation-delay:0.2s]" />
              <span className="h-1.5 w-1.5 rounded-full bg-[#FFD400] animate-bounce [animation-delay:0.4s]" />
              <span className="ml-2">Hélio está calculando a telemetria da rede...</span>
            </div>
          </div>
        )}
      </div>

      {/* Suggested Quick Prompts */}
      <div className="border-t border-[#1C1C1C] bg-[#0C0C0C] px-6 py-2.5 flex items-center gap-2 overflow-x-auto">
        <Sparkle size={14} className="text-[#FFD400] shrink-0" />
        <span className="font-mono text-[0.68rem] uppercase tracking-wider text-[#8A8A8A] shrink-0">
          Consultas rápidas:
        </span>
        {presetQueries.map((q, idx) => (
          <button
            key={idx}
            type="button"
            onClick={() => handleSend(q.label)}
            className="flex items-center gap-1.5 whitespace-nowrap rounded-full border border-[#262626] bg-[#141414] px-3 py-1 text-xs text-[#CCCCCC] transition-colors hover:border-[#FFD400] hover:text-[#FFD400]"
          >
            {q.icon}
            <span>{q.label}</span>
          </button>
        ))}
      </div>

      {/* Input Form */}
      <form
        onSubmit={(e) => {
          e.preventDefault();
          handleSend(input);
        }}
        className="flex items-center gap-3 border-t border-[#202020] bg-[#0E0E0E] p-4"
      >
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Pergunte sobre capacidade de carga, GD fotovoltaica, simulações ou estabilidade..."
          className="flex-1 rounded-xl border border-[#2B2B2B] bg-[#141414] px-4 py-3 text-sm text-white placeholder:text-[#555555] outline-none focus:border-[#FFD400] focus:ring-1 focus:ring-[#FFD400]"
        />
        <button
          type="submit"
          disabled={!input.trim()}
          className="flex h-11 w-11 items-center justify-center rounded-xl bg-[#FFD400] text-black font-bold transition-all hover:bg-[#FFE033] active:scale-[0.96] disabled:opacity-40"
          title="Enviar pergunta"
        >
          <PaperPlaneTilt size={18} weight="bold" />
        </button>
      </form>
    </div>
  );
};

function generateHelioResponse(
  query: string,
  rows: Substation[]
): { text: string; substationsMentioned?: Array<{ name: string; id: string; gdPower: number }> } {
  const q = query.toLowerCase();

  // Critical substations query
  if (q.includes("crític") || q.includes("atenção") || q.includes("alerta") || q.includes("risco")) {
    const critical = rows.filter((r) => r.metricas_rede.nivel_criticidade_gd !== "NORMAL");
    if (!critical.length) {
      return {
        text: "Boas notícias para a operação: na carga publicada atual, todos os barramentos estão com nível de criticidade NORMAL, sem riscos de sobrecarga por fluxo reverso de geração distribuída.",
      };
    }

    const list = critical
      .slice(0, 5)
      .map(
        (c) =>
          `• **${c.subestacao.split(" (ID:")[0]}** (ID: ${c.id_tecnico}) — Status: **${c.metricas_rede.nivel_criticidade_gd}** com **${c.geracao_distribuida.potencia_total_kw.toFixed(1)} kW** de GD instalada.`
      )
      .join("\n");

    return {
      text: `Identifiquei **${critical.length} subestações** operando fora do nível normal de criticidade na carga atual.\n\nPrincipais ativos demandando atenção operacional:\n${list}\n\n**Recomendação técnica:** Recomendo verificar o ajuste de derivação (taps) dos transformadores e os horários de irradiação solar de pico para evitar sobretensões transitórias.`,
      substationsMentioned: critical.slice(0, 5).map((c) => ({
        name: c.subestacao.split(" (ID:")[0],
        id: c.id_tecnico,
        gdPower: c.geracao_distribuida.potencia_total_kw,
      })),
    };
  }

  // Top GD substations query
  if (q.includes("top") || q.includes("maior") || q.includes("potência") || q.includes("solar")) {
    const sorted = [...rows].sort(
      (a, b) => b.geracao_distribuida.potencia_total_kw - a.geracao_distribuida.potencia_total_kw
    );
    const top5 = sorted.slice(0, 5);

    const list = top5
      .map(
        (s, idx) =>
          `${idx + 1}. **${s.subestacao.split(" (ID:")[0]}**: **${s.geracao_distribuida.potencia_total_kw.toLocaleString("pt-BR", { maximumFractionDigits: 1 })} kW** (${s.geracao_distribuida.total_unidades} UCs com GD)`
      )
      .join("\n");

    return {
      text: `Aqui estão os 5 barramentos com maior concentração de geração distribuída fotovoltaica:\n\n${list}\n\nEssas subestações concentram o maior volume de geração renovável decentralizada e são ideais para estudos de flexibilidade ou armazenamento em baterias (BESS).`,
      substationsMentioned: top5.map((s) => ({
        name: s.subestacao.split(" (ID:")[0],
        id: s.id_tecnico,
        gdPower: s.geracao_distribuida.potencia_total_kw,
      })),
    };
  }

  // Thermal loss or temperature query
  if (q.includes("perda") || q.includes("térmic") || q.includes("temperatura") || q.includes("verão")) {
    return {
      text: `Na modelagem fotovoltaica da GridScope, o **Fator de Perda Térmica** varia de acordo com o coeficiente de temperatura das células de silício (aproximadamente **-0.4%/°C** acima de 25°C).\n\nEm dias de verão com temperaturas ambiente próximas a **32°C**, a temperatura de operação do módulo pode ultrapassar **55°C**, gerando uma perda de rendimento de **10% a 12%** em relação às condições STC nominais.\n\nVocê pode testar datas específicas na aba de simulação de qualquer subestação para visualizar a curva calculada!`,
    };
  }

  // General network totals query
  if (q.includes("balanço") || q.includes("panorama") || q.includes("total") || q.includes("geral")) {
    const totalClients = rows.reduce((acc, r) => acc + r.metricas_rede.total_clientes, 0);
    const totalMwh = rows.reduce((acc, r) => acc + r.metricas_rede.consumo_anual_mwh, 0);
    const totalGd = rows.reduce((acc, r) => acc + r.geracao_distribuida.potencia_total_kw, 0);

    return {
      text: `Panorama operacional consolidado da carga atual:\n\n• **Total de Subestações Monitoradas:** ${rows.length}\n• **Total de Clientes Conectados:** ${totalClients.toLocaleString("pt-BR")} UCs\n• **Consumo Energético Anual:** ${totalMwh.toLocaleString("pt-BR", { maximumFractionDigits: 2 })} MWh\n• **Capacidade GD Instalada:** ${totalGd.toLocaleString("pt-BR", { maximumFractionDigits: 2 })} kW\n\nA taxa de penetração média de geração solar está alinhada às expectativas da distribuidora para o período atual.`,
    };
  }

  // Default intelligent technical fallback
  return {
    text: `Com base na topologia da rede GridScope:\n\nMonitoramos **${rows.length} subestações** sob o paradigma **"Dados. Equilíbrio. Futuro."**. A integração contínua de telemetria permite prever flutuações de tensão e otimizar o fluxo de potência ativa e reativa.\n\nVocê pode me perguntar sobre ativos específicos por ID, simulações solares, perfil das classes de consumo ou sobreestações críticas.`,
  };
}
