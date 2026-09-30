export type MetricasRede = {
  total_clientes: number;
  consumo_anual_mwh: number;
  nivel_criticidade_gd: string;
};

export type PerfilClasse = {
  qtd_clientes: number;
  pct: number;
  consumo_anual_mwh?: number;
};

export type GeracaoDistribuida = {
  total_unidades: number;
  potencia_total_kw: number;
  detalhe_por_classe: Record<string, { potencia_kw: number; qtd: number }>;
};

export type EvolucaoTemporal = {
  mes: string;
  clientes: number;
  unidades_mmgd: number;
  potencia_kw: number;
};

export type Substation = {
  subestacao: string;
  id_tecnico: string;
  metricas_rede: MetricasRede;
  geracao_distribuida: GeracaoDistribuida;
  perfil_consumo: Record<string, PerfilClasse>;
  evolucao_temporal: EvolucaoTemporal[];
  geometry?: Record<string, unknown> | null;
};

export type DataStatus = {
  status: string;
  source: string;
  delivery_id?: string | null;
  reference_period?: string | null;
  published_at?: string | null;
  row_counts: Record<string, number>;
};

export type Territories = {
  type: "FeatureCollection";
  features: Array<Record<string, unknown>>;
};

export type SolarSimulation = {
  subestacao: string;
  data_referencia: string;
  fonte_dados: string;
  condicao_tempo: string;
  irradiacao_solar_kwh_m2: number;
  temperatura_max_c: number;
  fator_perda_termica: number;
  potencia_instalada_kw: number;
  geracao_estimada_mwh: number;
  impacto_na_rede: string;
};

export type RankingCsvFilters = {
  busca?: string;
  situacao?: "all" | "normal" | "attention";
};

export class ApiError extends Error {
  readonly status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

export class GridScopeApi {
  private readonly baseUrl: string;

  constructor(baseUrl = import.meta.env.VITE_API_BASE_URL || "/api") {
    this.baseUrl = baseUrl.replace(/\/$/, "");
  }

  async getDataStatus(signal?: AbortSignal): Promise<DataStatus> {
    return this.get<DataStatus>("/data/status", signal);
  }

  async getRanking(signal?: AbortSignal): Promise<Substation[]> {
    return this.get<Substation[]>("/mercado/ranking", signal);
  }

  async getTerritories(signal?: AbortSignal): Promise<Territories> {
    return this.get<Territories>("/mercado/geojson", signal);
  }

  getRankingCsvUrl(filters?: RankingCsvFilters) {
    const params = new URLSearchParams();
    if (filters?.busca?.trim()) params.set("busca", filters.busca.trim());
    if (filters?.situacao && filters.situacao !== "all") params.set("situacao", filters.situacao);
    const query = params.toString();
    return `${this.baseUrl}/mercado/ranking.csv${query ? `?${query}` : ""}`;
  }

  async getSolarSimulation(idTecnico: string, date?: string, signal?: AbortSignal): Promise<SolarSimulation> {
    const query = date ? `?data=${encodeURIComponent(date)}` : "";
    return this.get<SolarSimulation>(`/simulacao/id/${encodeURIComponent(idTecnico)}${query}`, signal);
  }

  private async get<T>(path: string, signal?: AbortSignal): Promise<T> {
    const response = await fetch(`${this.baseUrl}${path}`, {
      headers: { Accept: "application/json" },
      signal,
    });

    if (!response.ok) {
      throw new ApiError(`A API retornou ${response.status}`, response.status);
    }

    return (await response.json()) as T;
  }
}

export const api = new GridScopeApi();
