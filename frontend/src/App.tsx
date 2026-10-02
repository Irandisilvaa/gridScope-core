import React, { useEffect, useMemo, useState } from "react";
import { BrandLogo, BrandSymbol } from "./components/BrandLogo";
import { MetricCard } from "./components/MetricCard";
import { StatusPill } from "./components/StatusPill";
import { SubstationDetail } from "./components/SubstationDetail";
import { SubstationTable } from "./components/SubstationTable";
import { TerritoryMap } from "./components/TerritoryMap";
import { OverviewRankingChart, CriticalityMatrix } from "./components/EnergyCharts";
import { NetworkAssistant } from "./components/NetworkAssistant";
import { CommandPalette } from "./components/CommandPalette";
import { ReportDossierModal } from "./components/ReportDossierModal";
import { Select } from "./components/Select";
import { AuthModal } from "./components/auth/AuthModal";
import { OperatorBadge } from "./components/auth/OperatorBadge";
import { UserAdminPanel } from "./components/auth/UserAdminPanel";
import { authService } from "./lib/authService";
import type { UserProfile } from "./types/auth";
import {
  api,
  type DataStatus,
  type MunicipalityCoverage,
  type Substation,
  type Territories,
} from "./lib/api";
import {
  SquaresFour,
  Lightning,
  FileText,
  ChatCircleDots,
  MagnifyingGlass,
  ArrowClockwise,
  WarningCircle,
  FilePdf,
  DownloadSimple,
  Printer,
  Sparkle,
  CaretLeft,
  CaretRight,
  SidebarSimple,
  User,
  UsersThree,
} from "@phosphor-icons/react";

type View = "overview" | "substations" | "reports" | "assistant" | "users";
type SubstationStatusFilter = "all" | "normal" | "attention" | "critical";

const navItems: Array<{ id: View; label: string; hint: string; icon: React.ReactNode }> = [
  { id: "overview", label: "Panorama", hint: "Visão sistêmica da rede", icon: <SquaresFour size={18} /> },
  { id: "substations", label: "Subestações", hint: "Telemetria e detalhe por ativo", icon: <Lightning size={18} /> },
  { id: "reports", label: "Relatórios", hint: "Exportações e dossiês técnicos", icon: <FileText size={18} /> },
  { id: "assistant", label: "Assistente Hélio", hint: "Inteligência analítica da rede", icon: <ChatCircleDots size={18} /> },
  { id: "users", label: "Usuários", hint: "Acesso e credenciais", icon: <UsersThree size={18} /> },
];

function formatNumber(value: number, maximumFractionDigits = 0) {
  return new Intl.NumberFormat("pt-BR", { maximumFractionDigits }).format(value);
}

function formatDate(value?: string | null) {
  if (!value) return "Carga atual publicada";
  return new Intl.DateTimeFormat("pt-BR", { dateStyle: "medium", timeStyle: "short" }).format(
    new Date(value)
  );
}

function countDiscardedRecords(dataStatus: DataStatus | null) {
  return (
    dataStatus?.quality_report?.discarded_records?.reduce(
      (total, event) => total + event.count,
      0
    ) ?? 0
  );
}

export function App() {
  const [view, setView] = useState<View>("overview");
  const [rows, setRows] = useState<Substation[]>([]);
  const [municipalities, setMunicipalities] = useState<MunicipalityCoverage[]>([]);
  const [municipalityCode, setMunicipalityCode] = useState("all");
  const [selectedSubstationId, setSelectedSubstationId] = useState<string | null>(null);
  const [territories, setTerritories] = useState<Territories | null>(null);
  const [dataStatus, setDataStatus] = useState<DataStatus | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isOnline, setIsOnline] = useState(navigator.onLine);
  const [isCommandPaletteOpen, setIsCommandPaletteOpen] = useState(false);
  const [isDossierOpen, setIsDossierOpen] = useState(false);
  const [currentTime, setCurrentTime] = useState("");
  const [currentUser, setCurrentUser] = useState<UserProfile | null>(null);
  const [authChecked, setAuthChecked] = useState(false);
  const [isAuthModalOpen, setIsAuthModalOpen] = useState(false);
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState<boolean>(() => {
    try {
      return localStorage.getItem("gridscope_sidebar_collapsed") === "true";
    } catch {
      return false;
    }
  });

  const handleOpenAuth = () => {
    setIsAuthModalOpen(true);
  };

  const handleAuthenticated = (user: UserProfile) => {
    setCurrentUser(user);
    setIsAuthModalOpen(false);
  };

  const handleLogout = () => {
    void authService.logout().finally(() => {
      setCurrentUser(null);
      setRows([]);
      setTerritories(null);
      setDataStatus(null);
      setError(null);
      setIsLoading(false);
      setView("overview");
    });
  };

  const toggleSidebar = () => {
    setIsSidebarCollapsed((prev) => {
      const next = !prev;
      try {
        localStorage.setItem("gridscope_sidebar_collapsed", String(next));
      } catch {
        // storage disabled
      }
      return next;
    });
  };

  const loadData = () => {
    setIsLoading(true);
    const controller = new AbortController();
    Promise.all([
      api.getMunicipalities(controller.signal).catch(() => []),
      api.getRanking(municipalityCode, controller.signal),
      api.getDataStatus(controller.signal),
    ])
      .then(([coverage, ranking, status]) => {
        if (controller.signal.aborted) return;
        setMunicipalities(coverage);
        setRows(ranking);
        setDataStatus(status);
        setError(null);
        return api
          .getTerritories(municipalityCode, controller.signal)
          .then((territoryData) => {
            if (!controller.signal.aborted) setTerritories(territoryData);
          })
          .catch((error) => {
            if (!controller.signal.aborted) {
              console.error("Falha ao carregar territórios:", error);
              setTerritories(null);
            }
          });
      })
      .catch((err) => {
        if (controller.signal.aborted) return;
        console.error("Falha ao consultar dados:", err);
        setError("Não foi possível carregar os dados operacionais da rede.");
      })
      .finally(() => {
        if (!controller.signal.aborted) setIsLoading(false);
      });

    return () => controller.abort();
  };

  useEffect(() => {
    let cancelled = false;
    void authService
      .getCurrentUser()
      .then((user) => {
        if (cancelled) return;
        setCurrentUser(user);
        if (!user) {
          setIsLoading(false);
          setIsAuthModalOpen(true);
        }
      })
      .finally(() => {
        if (!cancelled) setAuthChecked(true);
      });
    const handleOnline = () => setIsOnline(true);
    const handleOffline = () => setIsOnline(false);
    window.addEventListener("online", handleOnline);
    window.addEventListener("offline", handleOffline);

    const updateClock = () => {
      const now = new Date();
      setCurrentTime(
        now.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit", second: "2-digit" })
      );
    };
    updateClock();
    const timer = setInterval(updateClock, 1000);

    return () => {
      cancelled = true;
      window.removeEventListener("online", handleOnline);
      window.removeEventListener("offline", handleOffline);
      clearInterval(timer);
    };
  }, []);

  useEffect(() => {
    if (!currentUser) return;
    setSelectedSubstationId(null);
    setTerritories(null);
    return loadData();
  }, [currentUser, municipalityCode]);

  const metrics = useMemo(
    () =>
      rows.reduce(
        (total, row) => ({
          substations: total.substations + 1,
          clients: total.clients + row.metricas_rede.total_clientes,
          consumption: total.consumption + row.metricas_rede.consumo_anual_mwh,
          gdPower: total.gdPower + row.geracao_distribuida.potencia_total_kw,
          gdUnits: total.gdUnits + row.geracao_distribuida.total_unidades,
        }),
        { substations: 0, clients: 0, consumption: 0, gdPower: 0, gdUnits: 0 }
      ),
    [rows]
  );

  const criticalRows = useMemo(
    () => rows.filter((row) => row.metricas_rede.nivel_criticidade_gd.toUpperCase() !== "NORMAL"),
    [rows]
  );

  const selectedSubstation = useMemo(
    () => rows.find((row) => row.id_tecnico === selectedSubstationId) ?? null,
    [rows, selectedSubstationId]
  );
  const discardedRecordCount = countDiscardedRecords(dataStatus);
  const selectedMunicipality = municipalities.find((item) => item.codigo === municipalityCode);
  const selectedMunicipalityLabel = selectedMunicipality
    ? `${selectedMunicipality.nome} · ${selectedMunicipality.uf}`
    : "Toda a base";

  const selectSubstation = (id: string) => {
    setSelectedSubstationId(id);
    setView("substations");
  };

  if (!authChecked) {
    return (
      <div className="flex min-h-dvh items-center justify-center bg-grid-black text-white">
        <div className="flex flex-col items-center gap-3">
          <BrandSymbol size={42} animated />
          <span className="font-mono text-xs text-grid-gray">Validando sessão GridScope...</span>
        </div>
      </div>
    );
  }

  if (!currentUser) {
    return (
      <div className="flex min-h-dvh items-center justify-center bg-grid-black px-4 text-white">
        <div className="text-center">
          <BrandLogo variant="full" size="lg" animated />
          <p className="mt-4 max-w-sm font-mono text-xs leading-relaxed text-grid-gray">
            A plataforma é restrita a usuários provisionados por um administrador.
          </p>
          <button
            type="button"
            onClick={handleOpenAuth}
            className="mt-6 rounded-xl bg-grid-yellow px-5 py-3 font-display text-xs font-bold text-black"
          >
            Entrar na plataforma
          </button>
        </div>
        <AuthModal
          isOpen={isAuthModalOpen}
          onClose={() => setIsAuthModalOpen(false)}
          onAuthenticated={handleAuthenticated}
        />
      </div>
    );
  }

  return (
    <div className="min-h-dvh bg-grid-black text-white selection:bg-grid-yellow selection:text-black">
      {/* Fixed Sidebar Navigation */}
      <aside
        className={`fixed top-0 left-0 bottom-0 z-40 flex flex-col justify-between border-r border-grid-border-subtle bg-grid-surface/95 backdrop-blur-xl transition-[width,padding] duration-300 ease-[cubic-bezier(0.32,0.72,0,1)] overflow-y-auto overflow-x-hidden ${
          isSidebarCollapsed ? "w-[76px] p-3" : "w-[270px] p-5 lg:p-6"
        } max-lg:relative max-lg:w-full max-lg:h-auto max-lg:border-b max-lg:border-r-0`}
      >
        <div className="space-y-6">
          {/* Brand Header & Toggle */}
          <div
            className={`flex items-center ${
              isSidebarCollapsed ? "flex-col justify-center gap-4" : "justify-between"
            }`}
          >
            {isSidebarCollapsed ? (
              <div title="GridScope — Dados. Equilíbrio. Futuro.">
                <BrandSymbol size={32} animated />
              </div>
            ) : (
              <div className="flex items-center gap-2">
                <BrandLogo variant="full" size="md" animated />
              </div>
            )}

            {/* Toggle Collapse/Expand Button */}
            <button
              type="button"
              onClick={toggleSidebar}
              className="flex h-8 w-8 items-center justify-center rounded-lg border border-grid-border-card bg-grid-surface-elevated text-grid-gray transition-all hover:border-grid-yellow hover:text-grid-yellow active:scale-[0.96]"
              title={isSidebarCollapsed ? "Expandir barra lateral" : "Recolher barra lateral"}
              aria-label={isSidebarCollapsed ? "Expandir barra lateral" : "Recolher barra lateral"}
            >
              {isSidebarCollapsed ? <CaretRight size={16} /> : <CaretLeft size={16} />}
            </button>
          </div>

          {/* Primary Navigation */}
          <nav
            className="flex gap-2 overflow-x-auto lg:flex-col lg:overflow-visible"
            aria-label="Navegação principal"
          >
            {navItems.filter((item) => item.id !== "users" || currentUser.role === "admin").map((item) => {
              const active = view === item.id;
              return (
                <button
                  key={item.id}
                  onClick={() => setView(item.id)}
                  type="button"
                  title={isSidebarCollapsed ? `${item.label} — ${item.hint}` : undefined}
                  className={`group flex items-center rounded-xl border transition-all duration-200 ${
                    isSidebarCollapsed
                      ? "justify-center p-2.5 w-full"
                      : "gap-3 px-3.5 py-2.5 text-left w-full"
                  } ${
                    active
                      ? "border-grid-yellow/40 bg-grid-yellow/[0.08] text-white shadow-[0_0_15px_rgba(255,212,0,0.06)]"
                      : "border-transparent text-grid-gray hover:border-grid-border hover:bg-grid-surface-raised hover:text-white"
                  }`}
                >
                  <span
                    className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border transition-colors ${
                      active
                        ? "border-grid-yellow/30 bg-grid-yellow/15 text-grid-yellow"
                        : "border-grid-graphite-light bg-grid-surface-elevated text-grid-gray group-hover:text-white"
                    }`}
                  >
                    {item.icon}
                  </span>
                  {!isSidebarCollapsed && (
                    <div className="truncate">
                      <strong className="block font-display text-xs font-semibold leading-tight truncate">
                        {item.label}
                      </strong>
                      <span
                        className={`text-[0.68rem] block truncate ${
                          active ? "text-grid-yellow" : "text-grid-gray-dim"
                        }`}
                      >
                        {item.hint}
                      </span>
                    </div>
                  )}
                </button>
              );
            })}
          </nav>
        </div>

        {/* Sidebar Footer: Telemetry Status */}
        <div className="mt-8 space-y-3 border-t border-grid-border-subtle pt-4 hidden lg:block">
          {/* Quick Search Shortcut */}
          <button
            type="button"
            onClick={() => setIsCommandPaletteOpen(true)}
            title="Busca Rápida (Cmd+K)"
            className={`flex items-center rounded-xl border border-grid-border-card bg-grid-surface-raised text-xs font-medium text-grid-gray-subtle transition-colors hover:border-grid-yellow hover:text-grid-yellow ${
              isSidebarCollapsed
                ? "justify-center h-10 w-full p-0"
                : "w-full justify-between px-3 py-2"
            }`}
          >
            <span className="flex items-center gap-2">
              <MagnifyingGlass size={16} className="text-grid-yellow" />
              {!isSidebarCollapsed && <span>Busca Rápida</span>}
            </span>
            {!isSidebarCollapsed && (
              <kbd className="rounded border border-grid-border-strong bg-grid-surface px-1 py-0.5 font-mono text-[0.6rem] text-grid-gray">
                Cmd+K
              </kbd>
            )}
          </button>

          {/* Operator Access / Sign In Shortcut */}
          <button
            type="button"
            onClick={() => (currentUser ? handleLogout() : handleOpenAuth())}
            title={
              currentUser
                ? `Operador: ${currentUser.name} (${currentUser.email}) - Clique para encerrar sessão`
                : "Entrar"
            }
            className={`flex items-center rounded-xl border border-grid-border-card bg-grid-surface-raised text-xs font-medium text-grid-gray-subtle transition-colors hover:border-grid-yellow hover:text-grid-yellow ${
              isSidebarCollapsed
                ? "justify-center h-10 w-full p-0"
                : "w-full justify-between px-3 py-2"
            }`}
          >
            <span className="flex items-center gap-2 truncate">
              <User size={16} className="text-grid-yellow shrink-0" />
              {!isSidebarCollapsed && (
                <span className="truncate">
                  {currentUser ? currentUser.name : "Acesso Operador"}
                </span>
              )}
            </span>
            {!isSidebarCollapsed && (
              <span className="font-mono text-[0.65rem] text-grid-gray">
                {currentUser ? "Sair" : "Entrar"}
              </span>
            )}
          </button>
        </div>
      </aside>

      {/* Main Content Area */}
      <main
        className={`min-w-0 p-4 md:p-6 lg:p-10 transition-[margin-left] duration-300 ease-[cubic-bezier(0.32,0.72,0,1)] ${
          isSidebarCollapsed ? "lg:ml-[76px]" : "lg:ml-[270px]"
        }`}
      >
        {/* Top Operational Status Bar */}
        <header className="flex flex-col gap-4 border-b border-grid-graphite-light pb-6 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <div className="flex items-center gap-2">
              <span className="font-mono text-[0.68rem] font-bold uppercase tracking-[0.16em] text-grid-yellow">
                CENTRO DE OPERAÇÕES GRIDSCAN
              </span>
              <span className="text-grid-border-strong">|</span>
              <span className="font-mono text-xs text-grid-gray">UTC-3 {currentTime}</span>
            </div>
            <h1 className="mt-1 font-display text-2xl font-bold tracking-tight text-white md:text-3xl lg:text-4xl">
              {navItems.find((item) => item.id === view)?.label}
            </h1>
          </div>

          <div className="flex flex-wrap items-center gap-2.5 sm:gap-3">
            <Select
              aria-label="Selecionar cobertura municipal"
              value={municipalityCode}
              onChange={setMunicipalityCode}
              label="Cobertura:"
              searchable
              options={[
                { value: "all", label: "Toda a base" },
                ...municipalities.map((municipality) => ({
                  value: municipality.codigo,
                  label: `${municipality.nome} · ${municipality.uf}`,
                })),
              ]}
              className="max-w-[260px]"
            />

            {/* Quick Search Button */}
            <button
              type="button"
              onClick={() => setIsCommandPaletteOpen(true)}
              className="flex items-center gap-2 rounded-xl border border-grid-border-card bg-grid-surface-raised px-3.5 py-2 font-mono text-xs text-grid-gray-light transition-colors hover:border-grid-yellow hover:text-white"
            >
              <MagnifyingGlass size={15} className="text-grid-yellow" />
              <span className="hidden sm:inline">Buscar ativo...</span>
              <kbd className="rounded border border-grid-border-strong bg-grid-surface px-1 py-0.5 text-[0.6rem] text-grid-gray">
                ⌘K
              </kbd>
            </button>

            <button
              type="button"
              onClick={loadData}
              disabled={isLoading}
              className="flex items-center gap-1.5 rounded-xl border border-grid-border bg-grid-surface-raised px-3.5 py-2 font-mono text-xs text-grid-gray transition-colors hover:border-grid-yellow hover:text-white"
              title="Atualizar dados operacionais"
            >
              <ArrowClockwise size={14} className={isLoading ? "animate-spin text-grid-yellow" : ""} />
              <span>Sincronizar</span>
            </button>


            {/* Operator Identity Badge / Login Trigger */}
            <OperatorBadge
              user={currentUser}
              onOpenAuth={handleOpenAuth}
              onLogout={handleLogout}
            />
          </div>
        </header>

        {/* Brand Graphic Flow Strip: DADOS → ANÁLISE → EQUILÍBRIO → ENERGIA → FUTURO */}
        <div className="my-5 flex flex-wrap items-center justify-between gap-2 rounded-xl border border-grid-border-subtle bg-grid-surface px-4 py-2.5 font-mono text-[0.68rem] text-grid-gray">
          <div className="flex items-center gap-2">
            <span className="font-bold text-grid-yellow">FLUXO GRID</span>
            <span className="text-white">DADOS</span>
            <span className="text-grid-yellow">→</span>
            <span className="text-white">ANÁLISE</span>
            <span className="text-grid-yellow">→</span>
            <span className="text-white">EQUILÍBRIO</span>
            <span className="text-grid-yellow">→</span>
            <span className="text-white">ENERGIA</span>
            <span className="text-grid-yellow">→</span>
            <strong className="text-grid-yellow">FUTURO</strong>
          </div>
          <div className="text-grid-gray-dim">
            Assinatura institucional: <span className="text-white">Dados. Equilíbrio. Futuro.</span>
          </div>
        </div>

        {/* Offline Notice */}
        {!isOnline && (
          <div className="mb-6 rounded-xl border border-status-warning/40 bg-status-warning/10 p-3.5 text-xs text-status-warning">
            Modo offline ativo. Os dados operacionais não estão disponíveis até a conexão ser restabelecida.
          </div>
        )}

        {/* Loading State */}
        {isLoading && (
          <div className="flex h-64 flex-col items-center justify-center gap-3 rounded-2xl border border-grid-graphite-light bg-grid-surface">
            <BrandSymbol size={36} animated />
            <span className="font-mono text-xs text-grid-gray">
              Carregando telemetria operacional da rede...
            </span>
          </div>
        )}

        {/* Error State with Retry */}
        {error && !isLoading && (
          <div className="my-6 rounded-2xl border border-status-danger/30 bg-red-950/20 p-6 text-center">
            <WarningCircle size={32} className="mx-auto text-status-danger" />
            <h3 className="mt-2 font-display text-base font-semibold text-white">
              Falha na comunicação de telemetria
            </h3>
            <p className="mt-1 text-xs text-grid-gray">{error}</p>
            <button
              type="button"
              onClick={loadData}
              className="mt-4 rounded-xl border border-status-danger bg-status-danger/20 px-4 py-2 font-mono text-xs font-bold text-white transition-colors hover:bg-status-danger/30"
            >
              Tentar novamente
            </button>
          </div>
        )}

        {/* Active Views */}
        {!isLoading && !error && view === "overview" && (
          <OverviewView
            rows={rows}
            metrics={metrics}
            criticalRows={criticalRows}
            territories={territories}
            dataStatus={dataStatus}
            scopeLabel={selectedMunicipalityLabel}
            onSelectSubstation={selectSubstation}
          />
        )}

        {!isLoading && !error && view === "substations" && (
          <SubstationsView
            rows={rows}
            selected={selectedSubstation}
            selectedId={selectedSubstationId}
            onSelect={(id) => setSelectedSubstationId(id)}
            onClose={() => setSelectedSubstationId(null)}
            municipalityCode={municipalityCode}
          />
        )}

        {!isLoading && !error && view === "reports" && (
          <ReportsView
            rows={rows}
            dataStatus={dataStatus}
            scopeLabel={selectedMunicipalityLabel}
            onOpenDossier={() => setIsDossierOpen(true)}
          />
        )}

        {!isLoading && !error && view === "assistant" && (
          <NetworkAssistant
            rows={rows}
            onSelectSubstation={selectSubstation}
            municipalityCode={municipalityCode}
          />
        )}

        {!isLoading && !error && view === "users" && currentUser.role === "admin" && <UserAdminPanel />}
      </main>

      {/* Quick Search Command Palette Modal (Cmd+K) */}
      <CommandPalette
        isOpen={isCommandPaletteOpen}
        onClose={() => setIsCommandPaletteOpen(false)}
        substations={rows}
        onSelectSubstation={selectSubstation}
      />

      {/* Executive Technical Dossier Modal */}
      <ReportDossierModal
        isOpen={isDossierOpen}
        onClose={() => setIsDossierOpen(false)}
        rows={rows}
        dataStatus={dataStatus}
        scopeLabel={selectedMunicipalityLabel}
      />

      {/* Authentication Modal */}
      <AuthModal
        isOpen={isAuthModalOpen}
        onClose={() => setIsAuthModalOpen(false)}
        onAuthenticated={handleAuthenticated}
      />
    </div>
  );
}

// ----------------- OVERVIEW VIEW -----------------
function OverviewView({
  rows,
  metrics,
  criticalRows,
  territories,
  dataStatus,
  scopeLabel,
  onSelectSubstation,
}: {
  rows: Substation[];
  metrics: { substations: number; clients: number; consumption: number; gdPower: number; gdUnits: number };
  criticalRows: Substation[];
  territories: Territories | null;
  dataStatus: DataStatus | null;
  scopeLabel: string;
  onSelectSubstation: (id: string) => void;
}) {
  return (
    <div className="space-y-8 pt-2">
      {/* Hero Operational Banner */}
      <section className="relative overflow-hidden rounded-3xl border border-grid-border-card bg-gradient-to-br from-grid-surface-raised via-grid-surface to-grid-black p-6 md:p-8 double-bezel">
        <div className="absolute right-0 top-0 h-64 w-64 rounded-full bg-grid-yellow/[0.03] blur-3xl pointer-events-none" />

        <div className="relative z-10 flex flex-col justify-between gap-6 md:flex-row md:items-end">
          <div className="max-w-2xl">
            <div className="flex items-center gap-2">
              <span className="h-2 w-2 rounded-full bg-grid-yellow energy-glow" />
              <span className="font-mono text-[0.68rem] font-bold uppercase tracking-[0.14em] text-grid-yellow">
                PANORAMA ENERGÉTICO INTEGRADO
              </span>
            </div>
            <h2 className="mt-2 font-display text-2xl font-bold tracking-tight text-white md:text-3xl lg:text-4xl leading-tight">
              Transformando dados da rede em inteligência para decisões de alta precisão.
            </h2>
            <p className="mt-3 text-sm leading-relaxed text-grid-gray-light">
              Indicadores consolidados a partir da carga vigente de distribuição. Monitoramento em tempo real de alimentadores, fluxo reverso e capacidade solar instalada.
            </p>
          </div>

          <div className="min-w-[220px] rounded-2xl border border-grid-border bg-grid-surface-elevated p-4 font-mono text-xs shrink-0">
            <span className="text-[0.66rem] uppercase text-grid-gray block">ESCOPO ATIVO</span>
            <strong className="mt-1 block break-words text-sm font-bold text-grid-yellow">
              {scopeLabel}
            </strong>
            <span className="mt-2 text-[0.68rem] text-grid-gray block break-all">
              Carga {dataStatus?.delivery_id ?? "GS-PROD-2026"}
            </span>
            <span className="mt-0.5 text-[0.68rem] text-grid-gray-light block">
              {formatDate(dataStatus?.published_at)}
            </span>
            {countDiscardedRecords(dataStatus) > 0 && (
              <span className="mt-2 block text-[0.68rem] text-status-warning">
                {formatNumber(countDiscardedRecords(dataStatus))} registros descartados com auditoria
              </span>
            )}
          </div>
        </div>
      </section>

      {/* Primary KPI Metric Cards Grid */}
      <section className="grid grid-cols-2 gap-3 lg:grid-cols-4" aria-label="Indicadores operacionais">
        <MetricCard
          label="Subestações Monitoradas"
          value={formatNumber(metrics.substations)}
          unit="Ativos"
          note="Barramentos lógicos"
        />
        <MetricCard
          label="Unidades Consumidoras"
          value={formatNumber(metrics.clients)}
          unit="UCs"
          note="Base cadastral total"
        />
        <MetricCard
          label="Consumo Energético Anual"
          value={formatNumber(metrics.consumption, 1)}
          unit="MWh"
          note="Demanda consolidada"
        />
        <MetricCard
          label="Potência GD Conectada"
          value={formatNumber(metrics.gdPower, 1)}
          unit="kW"
          note={`${formatNumber(metrics.gdUnits)} sistemas instalados`}
          accent
        />
      </section>

      {/* Visual Analytics Grid: Top GD Ranking & Criticality Distribution */}
      <section className="grid gap-6 lg:grid-cols-2">
        <OverviewRankingChart
          substations={rows}
          topN={7}
          onSelectSubstation={onSelectSubstation}
        />
        <CriticalityMatrix substations={rows} />
      </section>

      {/* Critical Assets Alert Card */}
      {criticalRows.length > 0 && (
        <section className="rounded-2xl border border-status-danger/40 bg-red-950/20 p-5 double-bezel">
          <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between border-b border-red-950/40 pb-3 mb-4">
            <div className="flex items-center gap-2.5">
              <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-status-danger/20 text-status-danger">
                <WarningCircle size={18} />
              </span>
              <div>
                <h3 className="font-display text-sm font-bold text-white">
                  Atenção Operacional Requerida
                </h3>
                <span className="font-mono text-xs text-grid-gray">
                  {criticalRows.length} subestações com penetração crítica de GD identificadas
                </span>
              </div>
            </div>
            <StatusPill label={`${criticalRows.length} Ativos fora do normal`} tone="critical" />
          </div>

          <SubstationTable
            rows={criticalRows}
            onSelect={(sub) => onSelectSubstation(sub.id_tecnico)}
          />
        </section>
      )}

      {/* Geospatial Telemetry Territory Map */}
      <section className="space-y-4">
        <div className="flex items-center justify-between">
          <div>
            <span className="font-mono text-[0.66rem] font-bold uppercase tracking-[0.14em] text-grid-yellow">
              DISTRIBUIÇÃO GEOGRÁFICA
            </span>
            <h3 className="font-display text-lg font-bold text-white">
              Territórios Operacionais & Cobertura
            </h3>
          </div>
          <span className="font-mono text-xs text-grid-gray">
            {territories?.features.length ?? 0} polígonos mapeados
          </span>
        </div>

        {territories ? (
          <TerritoryMap
            data={territories}
            substations={rows}
            onSelectSubstation={onSelectSubstation}
          />
        ) : (
          <div className="flex h-56 items-center justify-center rounded-2xl border border-grid-graphite-light bg-grid-surface text-xs text-grid-gray">
            Carregando polígonos geoespaciais...
          </div>
        )}
      </section>

      {/* Top 10 Substation Ranking Table */}
      <section className="space-y-4">
        <div className="flex items-center justify-between">
          <div>
            <span className="font-mono text-[0.66rem] font-bold uppercase tracking-[0.14em] text-grid-yellow">
              INVENTÁRIO COMPLETO DA CARGA
            </span>
            <h3 className="font-display text-lg font-bold text-white">
              Ranking de Subestações por Potência GD
            </h3>
          </div>
          <span className="font-mono text-xs text-grid-gray">
            Total de {rows.length} registros cadastrados (7 por página)
          </span>
        </div>

        <SubstationTable
          rows={rows}
          pageSize={7}
          onSelect={(sub) => onSelectSubstation(sub.id_tecnico)}
        />
      </section>
    </div>
  );
}

// ----------------- SUBSTATIONS EXPLORER VIEW -----------------
function SubstationsView({
  rows,
  selected,
  selectedId,
  onSelect,
  onClose,
  municipalityCode,
}: {
  rows: Substation[];
  selected: Substation | null;
  selectedId: string | null;
  onSelect: (id: string) => void;
  onClose: () => void;
  municipalityCode: string;
}) {
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<SubstationStatusFilter>("all");

  const filteredRows = useMemo(() => {
    const q = search.trim().toLowerCase();
    return rows.filter((r) => {
      const matchText = `${r.subestacao} ${r.id_tecnico}`.toLowerCase();
      const matchQuery = !q || matchText.includes(q);
      const crit = r.metricas_rede.nivel_criticidade_gd.toUpperCase();

      let matchStatus = true;
      if (statusFilter === "normal") matchStatus = crit === "NORMAL";
      else if (statusFilter === "critical") matchStatus = crit.includes("CRÍT");
      else if (statusFilter === "attention") matchStatus = crit.includes("ATEN") || crit.includes("MÉD");

      return matchQuery && matchStatus;
    });
  }, [rows, search, statusFilter]);

  return (
    <div className="space-y-8 pt-2">
      {/* Search & Filters Bar */}
      <section className="rounded-2xl border border-grid-surface-border bg-grid-surface p-4 md:p-5 double-bezel">
        <div className="flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
          <div className="flex flex-1 flex-col gap-3 sm:flex-row sm:items-center">
            {/* Search Input */}
            <div className="relative flex-1">
              <MagnifyingGlass
                size={16}
                className="pointer-events-none absolute left-3 top-3 text-grid-gray"
              />
              <input
                type="search"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Buscar por nome da subestação ou ID técnico..."
                className="w-full rounded-xl border border-grid-border-card bg-grid-surface-elevated py-2.5 pl-9 pr-4 text-xs font-mono text-white placeholder:text-grid-gray-dim outline-none focus:border-grid-yellow focus:ring-1 focus:ring-grid-yellow"
              />
            </div>

            {/* Status Filter */}
            <Select<SubstationStatusFilter>
              value={statusFilter}
              onChange={setStatusFilter}
              label="Status:"
              options={[
                { value: "all", label: "Todas as Situações" },
                {
                  value: "normal",
                  label: "Normal",
                  badge: <span className="inline-block h-2 w-2 rounded-full bg-status-success" />,
                },
                {
                  value: "attention",
                  label: "Atenção",
                  badge: <span className="inline-block h-2 w-2 rounded-full bg-status-warning" />,
                },
                {
                  value: "critical",
                  label: "Crítico",
                  badge: <span className="inline-block h-2 w-2 rounded-full bg-status-danger" />,
                },
              ]}
              buttonClassName="bg-grid-surface-elevated"
            />
          </div>

          <div className="flex items-center gap-2 text-xs font-mono text-grid-gray">
            <span>
              Exibindo <strong className="text-white">{filteredRows.length}</strong> de{" "}
              {rows.length} subestações
            </span>
            {(search || statusFilter !== "all") && (
              <button
                type="button"
                onClick={() => {
                  setSearch("");
                  setStatusFilter("all");
                }}
                className="text-xs text-grid-yellow underline ml-2"
              >
                Limpar filtros
              </button>
            )}
          </div>
        </div>
      </section>

      {/* Detailed Substation Telemetry Drawer (when selected) */}
      {selected ? (
        <SubstationDetail row={selected} onClose={onClose} municipalityCode={municipalityCode} />
      ) : (
        <div className="rounded-2xl border border-dashed border-grid-border bg-grid-surface p-6 text-center text-xs text-grid-gray">
          Nenhuma subestação selecionada. Clique em um ativo na tabela ou no mapa para abrir a telemetria detalhada e simulação solar.
        </div>
      )}

      {/* All Filtered Rows Table */}
      <section className="space-y-4">
        <h3 className="font-display text-base font-bold text-white">
          Registros Operacionais ({filteredRows.length})
        </h3>
        {filteredRows.length > 0 ? (
          <SubstationTable
            rows={filteredRows}
            selectedId={selectedId ?? undefined}
            onSelect={(sub) => onSelect(sub.id_tecnico)}
          />
        ) : (
          <div className="rounded-2xl border border-grid-graphite-light bg-grid-surface p-8 text-center text-xs text-grid-gray">
            Nenhuma subestação encontrada com os filtros especificados.
          </div>
        )}
      </section>
    </div>
  );
}

// ----------------- REPORTS VIEW -----------------
function ReportsView({
  rows,
  dataStatus,
  scopeLabel,
  onOpenDossier,
}: {
  rows: Substation[];
  dataStatus: DataStatus | null;
  scopeLabel: string;
  onOpenDossier: () => void;
}) {
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<SubstationStatusFilter>("all");
  const [isExporting, setIsExporting] = useState(false);

  const handleDownloadCsv = async () => {
    setIsExporting(true);
    try {
      const csvContent = await api.exportCsvClientSide(rows, {
        busca: search,
        situacao: statusFilter === "critical" ? "attention" : (statusFilter as any),
      });

      const blob = new Blob(["\uFEFF" + csvContent], { type: "text/csv;charset=utf-8;" });
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.setAttribute("href", url);
      link.setAttribute("download", `gridscope-ranking-${new Date().toISOString().split("T")[0]}.csv`);
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
    } finally {
      setIsExporting(false);
    }
  };

  return (
    <div className="space-y-8 pt-2">
      {/* CSV Export Card */}
      <section className="rounded-3xl border border-grid-border-card bg-grid-surface p-6 md:p-8 double-bezel space-y-6">
        <div>
          <span className="font-mono text-[0.68rem] font-bold uppercase tracking-[0.14em] text-grid-yellow">
            EXPORTAÇÃO TÉCNICA
          </span>
          <h2 className="mt-1 font-display text-2xl font-bold text-white">
            Exportação do Ranking de Subestações
          </h2>
          <p className="mt-2 text-sm text-grid-gray-light max-w-2xl leading-relaxed">
            Faça download dos indicadores de telemetria agregados por subestação em formato CSV UTF-8. Compatível com Excel, QGIS, Python e softwares de modelagem de rede.
          </p>
        </div>

        {/* Filter Bar for Export */}
        <div className="grid gap-3 sm:grid-cols-2 md:grid-cols-3 border-y border-grid-border-subtle py-4">
          <label className="grid gap-1 font-mono text-xs text-grid-gray">
            <span>Filtrar por nome ou ID</span>
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Ex: SUBESTA1 ou 3029"
              className="rounded-xl border border-grid-border-card bg-grid-surface-elevated px-3 py-2 text-xs text-white outline-none focus:border-grid-yellow"
            />
          </label>

          <div className="grid gap-1 font-mono text-xs text-grid-gray">
            <span>Situação Operacional</span>
            <Select<SubstationStatusFilter>
              value={statusFilter}
              onChange={setStatusFilter}
              options={[
                { value: "all", label: "Todas as Subestações" },
                {
                  value: "normal",
                  label: "Apenas Nível Normal",
                  badge: <span className="inline-block h-2 w-2 rounded-full bg-status-success" />,
                },
                {
                  value: "attention",
                  label: "Atenção e Crítico",
                  badge: <span className="inline-block h-2 w-2 rounded-full bg-status-warning" />,
                },
              ]}
              buttonClassName="bg-grid-surface-elevated"
            />
          </div>

          <div className="flex items-end">
            <button
              type="button"
              disabled={isExporting}
              onClick={handleDownloadCsv}
              className="flex w-full items-center justify-center gap-2 rounded-xl border border-grid-yellow bg-grid-yellow px-5 py-2.5 font-display text-xs font-bold text-black transition-all hover:bg-grid-yellow-hover active:scale-[0.98] disabled:opacity-50"
            >
              <DownloadSimple size={16} weight="bold" />
              <span>{isExporting ? "Gerando CSV..." : "Baixar Ranking CSV"}</span>
            </button>
          </div>
        </div>

        <div className="flex items-center justify-between text-xs font-mono text-grid-gray">
           <span>{scopeLabel} · Fonte: {dataStatus?.source ?? "Carga Institucional"}</span>
          <span>Codificação: UTF-8 com delimitador ponto-e-vírgula (;)</span>
        </div>
      </section>

      {/* PDF Technical Report Module */}
      <section className="rounded-3xl border border-grid-surface-border bg-grid-surface p-6 md:p-8 space-y-4">
        <div className="flex items-center justify-between flex-wrap gap-4">
          <div className="flex items-center gap-3">
            <span className="flex h-10 w-10 items-center justify-center rounded-xl border border-grid-yellow/30 bg-grid-yellow/10 text-grid-yellow">
              <FilePdf size={22} />
            </span>
            <div>
              <span className="font-mono text-[0.66rem] font-bold uppercase tracking-[0.14em] text-grid-yellow">
                DOCUMENTAÇÃO TÉCNICA
              </span>
              <h3 className="font-display text-lg font-bold text-white">
                Dossiê Operacional GridScope (PDF Institucional)
              </h3>
            </div>
          </div>

          <button
            type="button"
            onClick={onOpenDossier}
            className="flex items-center gap-2 rounded-xl border border-grid-yellow bg-grid-yellow/15 px-4 py-2 font-display text-xs font-bold text-grid-yellow transition-colors hover:bg-grid-yellow/25"
          >
            <Printer size={16} />
            <span>Visualizar e Imprimir Dossiê</span>
          </button>
        </div>

        <p className="text-xs text-grid-gray-light max-w-2xl leading-relaxed">
          Geração de relatórios executivos no padrão visual GridScope — com cabeçalho institucional, tipografia Sora, paleta Preto/Amarelo e sumário de conformidade regulatória.
        </p>

        <div className="rounded-xl border border-grid-graphite-light bg-grid-surface-elevated p-4 text-xs font-mono text-grid-gray space-y-2">
          <div className="flex items-center justify-between text-white font-semibold">
            <span>Dossiê da Rede — Carga {dataStatus?.delivery_id ?? "GS-PROD-2026"}</span>
            <span className="text-status-success">Pronto para emissão</span>
          </div>
          <p>
            Inclui: 32 barramentos, curva de demanda agregada, penetração de MMGD e análise de sobretensão.
          </p>
        </div>
      </section>
    </div>
  );
}

export default App;
