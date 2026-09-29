import { useEffect, useMemo, useState, type ReactNode } from "react";
import { MetricCard } from "./components/MetricCard";
import { StatusPill } from "./components/StatusPill";
import { SubstationDetail } from "./components/SubstationDetail";
import { SubstationTable } from "./components/SubstationTable";
import { TerritoryMap } from "./components/TerritoryMap";
import { api, type DataStatus, type Substation, type Territories } from "./lib/api";

type View = "overview" | "substations" | "reports" | "assistant";

const navItems: Array<{ id: View; label: string; hint: string }> = [
  { id: "overview", label: "Panorama", hint: "Visão do sistema" },
  { id: "substations", label: "Subestações", hint: "Análise por ativo" },
  { id: "reports", label: "Relatórios", hint: "Exportações técnicas" },
  { id: "assistant", label: "Assistente", hint: "Perguntas sobre a rede" },
];

const eyebrow = "text-[0.66rem] font-bold uppercase tracking-[0.14em] text-[#6fe7d2]";
const panel = "border border-white/10 bg-[#0d202c]/60";

function formatNumber(value: number, maximumFractionDigits = 0) {
  return new Intl.NumberFormat("pt-BR", { maximumFractionDigits }).format(value);
}

function formatDate(value?: string | null) {
  if (!value) return "Ainda não publicada";
  return new Intl.DateTimeFormat("pt-BR", { dateStyle: "medium", timeStyle: "short" }).format(
    new Date(value),
  );
}

function sourceLabel(source: string) {
  if (source === "distributor_http") return "Distribuidora";
  if (source === "local_file") return "Arquivo local";
  return source;
}

function App() {
  const [view, setView] = useState<View>("overview");
  const [rows, setRows] = useState<Substation[]>([]);
  const [selectedSubstationId, setSelectedSubstationId] = useState<string | null>(null);
  const [territories, setTerritories] = useState<Territories | null>(null);
  const [dataStatus, setDataStatus] = useState<DataStatus | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isOnline, setIsOnline] = useState(navigator.onLine);

  useEffect(() => {
    const controller = new AbortController();
    Promise.all([api.getRanking(controller.signal), api.getDataStatus(controller.signal)])
      .then(([ranking, status]) => {
        setRows(ranking);
        setDataStatus(status);
        setError(null);
        api.getTerritories(controller.signal).then(setTerritories).catch(() => setTerritories(null));
      })
      .catch(() => setError("Não foi possível consultar os dados atuais da rede."))
      .finally(() => setIsLoading(false));

    return () => controller.abort();
  }, []);

  useEffect(() => {
    const handleOnline = () => setIsOnline(true);
    const handleOffline = () => setIsOnline(false);
    window.addEventListener("online", handleOnline);
    window.addEventListener("offline", handleOffline);
    return () => {
      window.removeEventListener("online", handleOnline);
      window.removeEventListener("offline", handleOffline);
    };
  }, []);

  const metrics = useMemo(
    () =>
      rows.reduce(
        (total, row) => ({
          substations: total.substations + 1,
          clients: total.clients + row.metricas_rede.total_clientes,
          consumption: total.consumption + row.metricas_rede.consumo_anual_mwh,
          gdPower: total.gdPower + row.geracao_distribuida.potencia_total_kw,
        }),
        { substations: 0, clients: 0, consumption: 0, gdPower: 0 },
      ),
    [rows],
  );

  const criticalRows = useMemo(
    () => rows.filter((row) => row.metricas_rede.nivel_criticidade_gd !== "NORMAL"),
    [rows],
  );

  const selectedSubstation = useMemo(
    () => rows.find((row) => row.id_tecnico === selectedSubstationId) ?? null,
    [rows, selectedSubstationId],
  );

  const selectSubstation = (row: Substation) => {
    setSelectedSubstationId(row.id_tecnico);
    setView("substations");
  };

  return (
    <div className="grid min-h-dvh grid-cols-1 bg-[#08141f] text-[#eef6f3] [background-image:radial-gradient(circle_at_82%_-12%,rgba(111,231,210,0.09),transparent_30rem)] lg:grid-cols-[252px_minmax(0,1fr)]">
      <aside className="sticky top-0 z-20 flex flex-col gap-12 border-b border-white/10 bg-[#07121c]/90 p-3 backdrop-blur-xl lg:min-h-dvh lg:border-b-0 lg:border-r lg:p-7 lg:pb-[calc(24px+env(safe-area-inset-bottom))]">
        <div className="flex items-center gap-3 px-2 py-1">
          <div className="relative h-8 w-8 overflow-hidden rounded-[9px] border border-[#6fe7d2]/45 bg-gradient-to-br from-[#6fe7d2]/20 to-[#ffc857]/[0.08]" aria-hidden="true">
            <span className="absolute left-0 top-[9px] h-px w-7 rotate-[-35deg] bg-[#6fe7d2]" />
            <span className="absolute left-0.5 top-4 h-px w-7 rotate-[-35deg] bg-[#ffc857]" />
            <span className="absolute left-1 top-[23px] h-px w-7 rotate-[-35deg] bg-[#6fe7d2]" />
          </div>
          <div>
            <strong className="block text-base tracking-[-0.02em]">GridScope</strong>
            <span className="mt-0.5 block text-[0.66rem] uppercase tracking-[0.12em] text-[#8ea4a7]">inteligência de rede</span>
          </div>
        </div>

        <nav className="flex gap-1.5 overflow-x-auto lg:grid" aria-label="Navegação principal">
          {navItems.map((item) => {
            const active = view === item.id;
            return (
              <button
                className={`grid min-w-max gap-1 rounded-[10px] border px-3 py-2 text-left transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#6fe7d2] lg:min-w-0 lg:py-3 ${active ? "border-[#6fe7d2]/25 bg-[#6fe7d2]/[0.08] text-[#eef6f3]" : "border-transparent text-[#8ea4a7] hover:border-white/10 hover:bg-white/[0.04] hover:text-[#eef6f3]"}`}
                key={item.id}
                onClick={() => setView(item.id)}
                type="button"
              >
                <span className="text-sm">{item.label}</span>
                <small className={`hidden text-[0.7rem] lg:block ${active ? "text-[#6fe7d2]" : "text-[#587176]"}`}>{item.hint}</small>
              </button>
            );
          })}
        </nav>

        <div className="mt-auto hidden border-t border-white/10 px-2.5 py-3.5 lg:block">
          <StatusPill label={isOnline ? "Conexão disponível" : "Sem conexão"} tone={isOnline ? "good" : "warn"} />
          <p className="mt-3 text-xs leading-relaxed text-[#6f888c]">Os dados operacionais são consultados no backend e não ficam disponíveis offline.</p>
        </div>
      </aside>

      <main className="min-w-0 px-3 py-6 pb-9 md:px-5 lg:px-16 lg:py-8">
        <header className="flex flex-col gap-4 border-b border-white/10 pb-8 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <span className={eyebrow}>Centro de operação</span>
            <h1 className="mt-2 text-[clamp(1.8rem,3vw,2.7rem)] font-semibold leading-none tracking-[-0.055em]">{navItems.find((item) => item.id === view)?.label}</h1>
          </div>
          <div className="flex min-w-[190px] items-center gap-2.5 py-0 sm:py-2.5">
            <span className="h-2 w-2 rounded-full bg-[#6fe7d2] shadow-[0_0_0_5px_rgba(111,231,210,0.1)]" aria-hidden="true" />
            <div>
              <strong className="block text-xs">{sourceLabel(dataStatus?.source ?? "fonte não configurada")}</strong>
              <small className="mt-0.5 block text-[0.7rem] text-[#8ea4a7]">Atualização: {formatDate(dataStatus?.published_at)}</small>
            </div>
          </div>
        </header>

        {!isOnline ? <div className="mt-[18px] rounded-[9px] border border-[#ffc857]/30 bg-[#ffc857]/[0.08] px-3.5 py-3 text-xs text-[#ffc857]" role="status">Sem conexão. A interface continua aberta, mas os dados da rede precisam do backend.</div> : null}
        {isLoading ? <LoadingState /> : null}
        {error && !isLoading ? <ErrorState message={error} /> : null}

        {!isLoading && !error && view === "overview" ? (
          <Overview rows={rows} metrics={metrics} criticalRows={criticalRows} dataStatus={dataStatus} territories={territories} onSelectSubstation={selectSubstation} />
        ) : null}
        {!isLoading && !error && view === "substations" ? (
          <Substations rows={rows} selected={selectedSubstation} selectedId={selectedSubstationId} onSelect={setSelectedSubstationId} onClose={() => setSelectedSubstationId(null)} />
        ) : null}
        {!isLoading && !error && view === "reports" ? <EmptyFeature title="Relatórios técnicos" text="A geração de CSV e PDF será conectada ao contrato de exportação da API." /> : null}
        {!isLoading && !error && view === "assistant" ? <EmptyFeature title="Assistente de rede" text="O chat será migrado após a camada de identidade e autorização estar pronta." /> : null}
      </main>
    </div>
  );
}

function Overview({ rows, metrics, criticalRows, dataStatus, territories, onSelectSubstation }: { rows: Substation[]; metrics: { substations: number; clients: number; consumption: number; gdPower: number }; criticalRows: Substation[]; dataStatus: DataStatus | null; territories: Territories | null; onSelectSubstation: (row: Substation) => void }) {
  return (
    <div className="grid gap-[22px] pt-7">
      <section className={`${panel} flex flex-col justify-end gap-8 bg-gradient-to-br from-[#6fe7d2]/[0.09] via-[#0d202c]/80 to-[#ffc857]/[0.04] p-5 sm:flex-row sm:items-end sm:p-7`}>
        <div>
          <span className={eyebrow}>Leitura da carga publicada</span>
          <h2 className="mt-2.5 max-w-[470px] text-[clamp(1.6rem,3.7vw,3rem)] font-semibold leading-tight tracking-[-0.05em]">Uma visão operacional antes do detalhe.</h2>
          <p className="mt-3.5 max-w-[550px] text-sm leading-relaxed text-[#8ea4a7]">Indicadores calculados exclusivamente a partir da carga vigente. Quando a origem direta estiver configurada, a proveniência aparecerá aqui.</p>
        </div>
        <div className="min-w-40 border-l border-[#6fe7d2]/25 p-3.5 sm:shrink-0">
          <span className="block text-xs text-[#8ea4a7]">carga atual</span>
          <strong className="my-2 block font-mono text-sm text-[#6fe7d2]">{dataStatus?.delivery_id?.slice(0, 12) ?? "aguardando"}</strong>
          <small className="block text-xs text-[#8ea4a7]">{dataStatus?.status ?? "sem metadados"}</small>
        </div>
      </section>

      <section className="grid grid-cols-2 gap-2.5 lg:grid-cols-4" aria-label="Indicadores gerais">
        <MetricCard label="Subestações" value={formatNumber(metrics.substations)} note="carga publicada" />
        <MetricCard label="Clientes" value={formatNumber(metrics.clients)} note="unidades consumidoras" />
        <MetricCard label="Consumo anual" value={`${formatNumber(metrics.consumption, 2)} MWh`} note="período da fonte" />
        <MetricCard label="Potência GD" value={`${formatNumber(metrics.gdPower, 2)} kW`} note="instalada" />
      </section>

      <section className={`${panel} p-3 sm:p-6`}>
        <SectionHeading eyebrowText="Atenção operacional" title="Subestações fora do nível normal">
          <StatusPill label={`${criticalRows.length} identificadas`} tone={criticalRows.length ? "warn" : "good"} />
        </SectionHeading>
        {criticalRows.length ? <SubstationTable rows={criticalRows} onSelect={onSelectSubstation} /> : <p className="m-0 text-sm text-[#8ea4a7]">Nenhuma subestação fora do nível normal na carga atual.</p>}
      </section>

      <section className={`${panel} p-3 sm:p-6`}>
        <SectionHeading eyebrowText="Geografia operacional" title="Territórios publicados">
          <span className="text-xs text-[#8ea4a7]">{territories?.features.length ?? 0} áreas</span>
        </SectionHeading>
        {territories ? <TerritoryMap data={territories} /> : <p className="m-0 text-sm text-[#8ea4a7]">O mapa ficará disponível quando o GeoJSON da carga atual puder ser consultado.</p>}
      </section>

      <section className={`${panel} p-3 sm:p-6`}>
        <SectionHeading eyebrowText="Inventário publicado" title="Resumo por subestação">
          <span className="text-xs text-[#8ea4a7]">{formatDate(dataStatus?.published_at)}</span>
        </SectionHeading>
        <SubstationTable rows={rows.slice(0, 12)} onSelect={onSelectSubstation} />
      </section>
    </div>
  );
}

function Substations({ rows, selected, selectedId, onSelect, onClose }: { rows: Substation[]; selected: Substation | null; selectedId: string | null; onSelect: (id: string) => void; onClose: () => void }) {
  return (
    <div className="grid gap-[22px] pt-7">
      <section className={`${panel} min-h-[460px] p-3 sm:p-6`}>
        <SectionHeading eyebrowText="Exploração" title="Todos os ativos publicados">
          <span className="text-xs text-[#8ea4a7]">{rows.length} registros</span>
        </SectionHeading>
        <SubstationTable rows={rows} selectedId={selectedId ?? undefined} onSelect={(row) => onSelect(row.id_tecnico)} />
      </section>
      {selected ? <SubstationDetail row={selected} onClose={onClose} /> : <p className="m-0 border border-dashed border-white/10 p-[18px] text-center text-sm text-[#8ea4a7]">Selecione uma subestação para abrir o detalhe operacional.</p>}
    </div>
  );
}

function SectionHeading({ eyebrowText, title, children }: { eyebrowText: string; title: string; children?: ReactNode }) {
  return (
    <div className="mb-5 flex flex-col items-start justify-between gap-4 sm:flex-row sm:items-end">
      <div>
        <span className={eyebrow}>{eyebrowText}</span>
        <h2 className="mt-2 text-[clamp(1.1rem,2vw,1.45rem)] font-semibold leading-tight tracking-[-0.035em]">{title}</h2>
      </div>
      {children}
    </div>
  );
}

function LoadingState() {
  return <div className="mx-auto mt-20 grid max-w-[500px] justify-items-center gap-2 rounded-lg border border-white/10 bg-[#0d202c]/70 p-8 text-center text-[#8ea4a7]"><span className="h-7 w-7 animate-spin rounded-full border-2 border-[#6fe7d2]/20 border-t-[#6fe7d2]" aria-hidden="true" /><p className="m-0">Consultando a carga atual...</p></div>;
}

function ErrorState({ message }: { message: string }) {
  return <div className="mx-auto mt-20 grid max-w-[500px] justify-items-center gap-2 rounded-lg border border-[#ff8379]/30 bg-[#0d202c]/70 p-8 text-center"><strong className="text-[#ff8379]">Dados indisponíveis</strong><p className="m-0 text-[#8ea4a7]">{message}</p><small className="text-[#8ea4a7]">Verifique a API e a configuração da fonte de dados.</small></div>;
}

function EmptyFeature({ title, text }: { title: string; text: string }) {
  return <div className="mx-auto mt-20 grid max-w-[500px] justify-items-center gap-2 rounded-lg border border-white/10 bg-[#0d202c]/70 p-8 text-center"><span className={eyebrow}>Próxima etapa</span><strong>{title}</strong><p className="m-0 text-[#8ea4a7]">{text}</p></div>;
}

export default App;
