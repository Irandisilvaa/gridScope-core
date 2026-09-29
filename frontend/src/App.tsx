import { useEffect, useMemo, useState } from "react";
import { MetricCard } from "./components/MetricCard";
import { StatusPill } from "./components/StatusPill";
import { SubstationTable } from "./components/SubstationTable";
import { TerritoryMap } from "./components/TerritoryMap";
import { SubstationDetail } from "./components/SubstationDetail";
import { api, type DataStatus, type Substation, type Territories } from "./lib/api";

type View = "overview" | "substations" | "reports" | "assistant";

const navItems: Array<{ id: View; label: string; hint: string }> = [
  { id: "overview", label: "Panorama", hint: "Visão do sistema" },
  { id: "substations", label: "Subestações", hint: "Análise por ativo" },
  { id: "reports", label: "Relatórios", hint: "Exportações técnicas" },
  { id: "assistant", label: "Assistente", hint: "Perguntas sobre a rede" },
];

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

  const metrics = useMemo(() => {
    return rows.reduce(
      (total, row) => ({
        substations: total.substations + 1,
        clients: total.clients + row.metricas_rede.total_clientes,
        consumption: total.consumption + row.metricas_rede.consumo_anual_mwh,
        gdPower: total.gdPower + row.geracao_distribuida.potencia_total_kw,
      }),
      { substations: 0, clients: 0, consumption: 0, gdPower: 0 },
    );
  }, [rows]);

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
    <div className="app-shell min-h-dvh">
      <aside className="sidebar min-h-dvh">
        <div className="brand-lockup">
          <div className="brand-mark" aria-hidden="true">
            <span />
            <span />
            <span />
          </div>
          <div>
            <strong>GridScope</strong>
            <span>inteligência de rede</span>
          </div>
        </div>

        <nav aria-label="Navegação principal">
          {navItems.map((item) => (
            <button
              className={`nav-item ${view === item.id ? "nav-item--active" : ""}`}
              key={item.id}
              onClick={() => setView(item.id)}
              type="button"
            >
              <span>{item.label}</span>
              <small>{item.hint}</small>
            </button>
          ))}
        </nav>

        <div className="sidebar-footer">
          <StatusPill
            label={isOnline ? "Conexão disponível" : "Sem conexão"}
            tone={isOnline ? "good" : "warn"}
          />
          <p>Os dados operacionais são consultados no backend e não ficam disponíveis offline.</p>
        </div>
      </aside>

      <main className="main-content">
        <header className="topbar">
          <div>
            <span className="eyebrow">Centro de operação</span>
            <h1>{navItems.find((item) => item.id === view)?.label}</h1>
          </div>
          <div className="source-status">
            <span className="source-dot" aria-hidden="true" />
            <div>
              <strong>{sourceLabel(dataStatus?.source ?? "fonte não configurada")}</strong>
              <small>Atualização: {formatDate(dataStatus?.published_at)}</small>
            </div>
          </div>
        </header>

        {!isOnline ? (
          <div className="offline-banner" role="status">
            Sem conexão. A interface continua aberta, mas os dados da rede precisam do backend.
          </div>
        ) : null}

        {isLoading ? <LoadingState /> : null}
        {error && !isLoading ? <ErrorState message={error} /> : null}

        {!isLoading && !error && view === "overview" ? (
          <Overview rows={rows} metrics={metrics} criticalRows={criticalRows} dataStatus={dataStatus} territories={territories} onSelectSubstation={selectSubstation} />
        ) : null}
        {!isLoading && !error && view === "substations" ? <Substations rows={rows} selected={selectedSubstation} selectedId={selectedSubstationId} onSelect={setSelectedSubstationId} onClose={() => setSelectedSubstationId(null)} /> : null}
        {!isLoading && !error && view === "reports" ? <EmptyFeature title="Relatórios técnicos" text="A geração de CSV e PDF será conectada ao contrato de exportação da API." /> : null}
        {!isLoading && !error && view === "assistant" ? <EmptyFeature title="Assistente de rede" text="O chat será migrado após a camada de identidade e autorização estar pronta." /> : null}
      </main>
    </div>
  );
}

function Overview({ rows, metrics, criticalRows, dataStatus, territories, onSelectSubstation }: { rows: Substation[]; metrics: { substations: number; clients: number; consumption: number; gdPower: number }; criticalRows: Substation[]; dataStatus: DataStatus | null; territories: Territories | null; onSelectSubstation: (row: Substation) => void }) {
  return (
    <div className="content-stack">
      <section className="intro-panel">
        <div>
          <span className="eyebrow">Leitura da carga publicada</span>
          <h2>Uma visão operacional antes do detalhe.</h2>
          <p>Indicadores calculados exclusivamente a partir da carga vigente. Quando a origem direta estiver configurada, a proveniência aparecerá aqui.</p>
        </div>
        <div className="load-stamp">
          <span>carga atual</span>
          <strong>{dataStatus?.delivery_id?.slice(0, 12) ?? "aguardando"}</strong>
          <small>{dataStatus?.status ?? "sem metadados"}</small>
        </div>
      </section>

      <section className="metric-grid" aria-label="Indicadores gerais">
        <MetricCard label="Subestações" value={formatNumber(metrics.substations)} note="carga publicada" />
        <MetricCard label="Clientes" value={formatNumber(metrics.clients)} note="unidades consumidoras" />
        <MetricCard label="Consumo anual" value={`${formatNumber(metrics.consumption, 2)} MWh`} note="período da fonte" />
        <MetricCard label="Potência GD" value={`${formatNumber(metrics.gdPower, 2)} kW`} note="instalada" />
      </section>

      <section className="section-block">
        <div className="section-heading">
          <div>
            <span className="eyebrow">Atenção operacional</span>
            <h2>Subestações fora do nível normal</h2>
          </div>
          <StatusPill label={`${criticalRows.length} identificadas`} tone={criticalRows.length ? "warn" : "good"} />
        </div>
        {criticalRows.length ? <SubstationTable rows={criticalRows} onSelect={onSelectSubstation} /> : <p className="empty-copy">Nenhuma subestação fora do nível normal na carga atual.</p>}
      </section>

      <section className="section-block">
        <div className="section-heading">
          <div>
            <span className="eyebrow">Geografia operacional</span>
            <h2>Territórios publicados</h2>
          </div>
          <span className="section-meta">{territories?.features.length ?? 0} áreas</span>
        </div>
        {territories ? (
          <TerritoryMap data={territories} />
        ) : (
          <p className="empty-copy">O mapa ficará disponível quando o GeoJSON da carga atual puder ser consultado.</p>
        )}
      </section>

      <section className="section-block">
        <div className="section-heading">
          <div>
            <span className="eyebrow">Inventário publicado</span>
            <h2>Resumo por subestação</h2>
          </div>
          <span className="section-meta">{formatDate(dataStatus?.published_at)}</span>
        </div>
        <SubstationTable rows={rows.slice(0, 12)} onSelect={onSelectSubstation} />
      </section>
    </div>
  );
}

function Substations({ rows, selected, selectedId, onSelect, onClose }: { rows: Substation[]; selected: Substation | null; selectedId: string | null; onSelect: (id: string) => void; onClose: () => void }) {
  return (
    <div className="content-stack">
      <section className="section-block section-block--large">
        <div className="section-heading">
          <div>
            <span className="eyebrow">Exploração</span>
            <h2>Todos os ativos publicados</h2>
          </div>
          <span className="section-meta">{rows.length} registros</span>
        </div>
        <SubstationTable rows={rows} selectedId={selectedId ?? undefined} onSelect={(row) => onSelect(row.id_tecnico)} />
      </section>
      {selected ? <SubstationDetail row={selected} onClose={onClose} /> : <p className="detail-hint">Selecione uma subestação para abrir o detalhe operacional.</p>}
    </div>
  );
}

function LoadingState() {
  return <div className="state-panel"><span className="loader" aria-hidden="true" /><p>Consultando a carga atual...</p></div>;
}

function ErrorState({ message }: { message: string }) {
  return <div className="state-panel state-panel--error"><strong>Dados indisponíveis</strong><p>{message}</p><small>Verifique a API e a configuração da fonte de dados.</small></div>;
}

function EmptyFeature({ title, text }: { title: string; text: string }) {
  return <div className="state-panel"><span className="eyebrow">Próxima etapa</span><strong>{title}</strong><p>{text}</p></div>;
}

export default App;
