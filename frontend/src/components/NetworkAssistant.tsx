import React, { useState } from "react";
import { api, type ChatMessage, type Substation } from "../lib/api";
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
  municipalityCode?: string;
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
  municipalityCode = "all",
}) => {
  const [messages, setMessages] = useState<Message[]>([
    {
      id: "welcome",
      sender: "helio",
      text: "Olá! Sou o Hélio, seu especialista em inteligência de rede na GridScope. Analiso os dados publicados de carga, penetração de GD fotovoltaica e criticidade da rede. Em que posso contribuir com sua operação hoje?",
      timestamp: new Date().toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" }),
    },
  ]);
  const [input, setInput] = useState("");
  const [isThinking, setIsThinking] = useState(false);
  const [conversationId, setConversationId] = useState<number | null>(null);

  const presetQueries = [
    {
      label: "Quais ativos estão em nível crítico de GD?",
      icon: <WarningCircle size={14} className="text-status-danger" />,
    },
    {
      label: "Top 5 subestações com maior potência solar conectada",
      icon: <Lightning size={14} className="text-grid-yellow" />,
    },
    {
      label: "Qual o balanço geral entre consumo e geração instalada?",
      icon: <ChartBar size={14} className="text-status-info" />,
    },
    {
      label: "Como a perda térmica afeta a eficiência fotovoltaica no verão?",
      icon: <Cpu size={14} className="text-status-success" />,
    },
  ];

  const handleSend = async (userText: string) => {
    if (!userText.trim() || isThinking) return;

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

    try {
      const history: ChatMessage[] = messages
        .filter((message) => message.id !== "welcome")
        .map((message) => ({
          role: message.sender === "user" ? "user" : "model",
          content: message.text,
        }));
      const response = await api.sendChat(userText, history, conversationId, municipalityCode);
      setConversationId(response.conversa_id ?? conversationId);
      setMessages((prev) => [...prev, {
        id: String(Date.now() + 1),
        sender: "helio",
        text: response.resposta,
        timestamp: new Date().toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" }),
      }]);
    } catch (error) {
      setMessages((prev) => [...prev, {
        id: String(Date.now() + 1),
        sender: "helio",
        text: error instanceof Error ? error.message : "Não foi possível consultar o assistente.",
        timestamp: new Date().toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" }),
      }]);
    } finally {
      setIsThinking(false);
    }
  };

  return (
    <div className="flex flex-col h-[740px] max-w-5xl mx-auto rounded-3xl border border-grid-border-card bg-grid-surface overflow-hidden shadow-2xl double-bezel">
      {/* Header with Hélio Avatar and Telemetry Status */}
      <div className="flex items-center justify-between border-b border-grid-border-subtle bg-grid-surface px-6 py-4">
        <div className="flex items-center gap-3.5">
          <div className="relative">
            <img
              src="/brand/helio.png"
              alt="Hélio - Assistente GridScope"
              className="h-12 w-12 rounded-full border-2 border-grid-yellow object-cover bg-black"
            />
            <span className="absolute bottom-0 right-0 h-3.5 w-3.5 rounded-full border-2 border-grid-surface bg-status-success" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <strong className="font-display text-base text-white">Hélio</strong>
              <span className="rounded-full border border-grid-yellow/40 bg-grid-yellow/10 px-2 py-0.5 font-mono text-[0.65rem] font-bold text-grid-yellow">
                AGENTE ANALÍTICO
              </span>
            </div>
            <span className="font-mono text-xs text-grid-gray">
              Especialista Técnico de Rede · Carga Ativa: {rows.length} Subestações
            </span>
          </div>
        </div>

        <div className="hidden sm:flex items-center gap-2 font-mono text-xs text-grid-gray">
          <span className="h-2 w-2 rounded-full bg-status-success animate-pulse" />
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
                className="h-8 w-8 rounded-full border border-grid-yellow object-cover shrink-0 mt-1"
              />
            )}

            <div
              className={`max-w-[80%] rounded-2xl p-4 text-sm leading-relaxed ${
                m.sender === "user"
                  ? "bg-grid-yellow text-black font-medium"
                  : "bg-grid-surface-elevated border border-grid-surface-border text-grid-gray-subtle"
              }`}
            >
              <div className="whitespace-pre-line">{m.text}</div>

              {/* Mentioned Substation Action Buttons */}
              {m.substationsMentioned && m.substationsMentioned.length > 0 && (
                <div className="mt-3 pt-3 border-t border-grid-border flex flex-wrap gap-2">
                  <span className="text-[0.68rem] font-mono text-grid-gray block w-full">
                    Ativos referenciados (clique para abrir telemetria):
                  </span>
                  {m.substationsMentioned.map((s) => (
                    <button
                      key={s.id}
                      type="button"
                      onClick={() => onSelectSubstation && onSelectSubstation(s.id)}
                      className="inline-flex items-center gap-1 rounded-lg border border-grid-border-strong bg-grid-surface px-2.5 py-1 text-xs font-mono text-grid-yellow transition-colors hover:border-grid-yellow"
                    >
                      <Lightning size={12} weight="fill" />
                      <span>{s.name}</span>
                      <span className="text-[0.65rem] text-grid-gray">({s.gdPower.toFixed(0)} kW)</span>
                    </button>
                  ))}
                </div>
              )}

              <span
                className={`mt-2 block font-mono text-[0.62rem] text-right ${
                  m.sender === "user" ? "text-black/60" : "text-grid-gray-muted"
                }`}
              >
                {m.timestamp}
              </span>
            </div>
          </div>
        ))}

        {isThinking && (
          <div className="flex gap-3 items-center text-xs font-mono text-grid-gray">
            <img
              src="/brand/helio.png"
              alt="Hélio"
              className="h-8 w-8 rounded-full border border-grid-yellow object-cover shrink-0"
            />
            <div className="flex items-center gap-1.5 rounded-xl border border-grid-graphite-light bg-grid-surface-elevated px-4 py-2.5">
              <span className="h-1.5 w-1.5 rounded-full bg-grid-yellow animate-bounce" />
              <span className="h-1.5 w-1.5 rounded-full bg-grid-yellow animate-bounce [animation-delay:0.2s]" />
              <span className="h-1.5 w-1.5 rounded-full bg-grid-yellow animate-bounce [animation-delay:0.4s]" />
              <span className="ml-2">Hélio está calculando a telemetria da rede...</span>
            </div>
          </div>
        )}
      </div>

      {/* Suggested Quick Prompts */}
      <div className="border-t border-grid-border-subtle bg-grid-surface px-6 py-2.5 flex items-center gap-2 overflow-x-auto">
        <Sparkle size={14} className="text-grid-yellow shrink-0" />
        <span className="font-mono text-[0.68rem] uppercase tracking-wider text-grid-gray shrink-0">
          Consultas rápidas:
        </span>
        {presetQueries.map((q, idx) => (
          <button
            key={idx}
            type="button"
            onClick={() => handleSend(q.label)}
            className="flex items-center gap-1.5 whitespace-nowrap rounded-full border border-grid-border bg-grid-surface-elevated px-3 py-1 text-xs text-grid-gray-subtle transition-colors hover:border-grid-yellow hover:text-grid-yellow"
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
        className="flex items-center gap-3 border-t border-grid-border-subtle bg-grid-surface p-4"
      >
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Pergunte sobre capacidade de carga, GD fotovoltaica, simulações ou estabilidade..."
          className="flex-1 rounded-xl border border-grid-border-card bg-grid-surface-elevated px-4 py-3 text-sm text-white placeholder:text-grid-gray-dim outline-none focus:border-grid-yellow focus:ring-1 focus:ring-grid-yellow"
        />
        <button
          type="submit"
          disabled={!input.trim() || isThinking}
          className="flex h-11 w-11 items-center justify-center rounded-xl bg-grid-yellow text-black font-bold transition-all hover:bg-grid-yellow-hover active:scale-[0.96] disabled:opacity-40"
          title="Enviar pergunta"
        >
          <PaperPlaneTilt size={18} weight="bold" />
        </button>
      </form>
    </div>
  );
};
