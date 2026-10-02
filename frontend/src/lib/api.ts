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
  municipio_codigo?: string | null;
  metricas_rede: MetricasRede;
  geracao_distribuida: GeracaoDistribuida;
  perfil_consumo: Record<string, PerfilClasse>;
  evolucao_temporal: EvolucaoTemporal[];
  geometry?: Record<string, unknown> | null;
};

export type MunicipalityCoverage = {
  codigo: string;
  nome: string;
  uf: string;
  consumidores: number;
  transformadores: number;
  subestacoes: number;
  unidades_gd: number;
};

export type DataStatus = {
  status: string;
  source: string;
  publication_id?: string | null;
  delivery_id?: string | null;
  reference_period?: string | null;
  city_target?: string | null;
  published_at?: string | null;
  row_counts: Record<string, number>;
  quality_report?: {
    discarded_records?: Array<{
      table: string;
      reason: string;
      count: number;
      ids?: string[];
      transformer_ids?: string[];
    }>;
    geospatial?: {
      policy?: string;
      outside_tolerance_m?: number;
      outside_official_boundary_count?: number;
      outside_official_boundary?: Array<{
        transformador_id: string;
        subestacao_id: string;
        municipio_codigo?: string | null;
        distance_m: number;
        action: string;
      }>;
    };
  };
  mode?: "live";
};

export type AuthUser = {
  id: string;
  email: string;
  name: string;
  role: "admin" | "user";
  is_active: boolean;
  created_at?: string | null;
  last_login_at?: string | null;
};

export type ChatMessage = {
  role: "user" | "model";
  content: string;
};

export type ChatResponse = {
  resposta: string;
  historico_atualizado: ChatMessage[];
  conversa_id?: number | null;
  graficos?: Array<Record<string, unknown>> | null;
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
  municipio?: string;
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
    const data = await this.get<DataStatus>("/data/status", signal);
    return { ...data, mode: "live" };
  }

  async getMunicipalities(signal?: AbortSignal): Promise<MunicipalityCoverage[]> {
    return this.get<MunicipalityCoverage[]>("/coverage/municipalities", signal);
  }

  async getRanking(municipio = "all", signal?: AbortSignal): Promise<Substation[]> {
    return this.get<Substation[]>(`/mercado/ranking?municipio=${encodeURIComponent(municipio)}`, signal);
  }

  async getTerritories(municipio = "all", signal?: AbortSignal): Promise<Territories> {
    return this.get<Territories>(`/mercado/geojson?municipio=${encodeURIComponent(municipio)}`, signal);
  }

  getRankingCsvUrl(filters?: RankingCsvFilters) {
    const params = new URLSearchParams();
    if (filters?.busca?.trim()) params.set("busca", filters.busca.trim());
    if (filters?.situacao && filters.situacao !== "all") params.set("situacao", filters.situacao);
    if (filters?.municipio && filters.municipio !== "all") params.set("municipio", filters.municipio);
    const query = params.toString();
    return `${this.baseUrl}/mercado/ranking.csv${query ? `?${query}` : ""}`;
  }

  async exportCsvClientSide(rows: Substation[], filters?: RankingCsvFilters): Promise<string> {
    const query = (filters?.busca ?? "").toLowerCase().trim();
    const situacao = filters?.situacao ?? "all";

    const filtered = rows.filter((r) => {
      const matchesSearch = !query || r.subestacao.toLowerCase().includes(query) || r.id_tecnico.includes(query);
      const isNormal = r.metricas_rede.nivel_criticidade_gd.toUpperCase() === "NORMAL";
      const matchesStatus = situacao === "all" || (situacao === "normal" ? isNormal : !isNormal);
      return matchesSearch && matchesStatus;
    });

    const headers = [
      "ID_TECNICO",
      "SUBESTACAO",
      "TOTAL_CLIENTES",
      "CONSUMO_ANUAL_MWH",
      "POTENCIA_GD_KW",
      "UNIDADES_GD",
      "CRITICIDADE_GD",
    ];

    const lines = filtered.map((r) => [
      r.id_tecnico,
      `"${r.subestacao.replace(/"/g, '""')}"`,
      r.metricas_rede.total_clientes,
      r.metricas_rede.consumo_anual_mwh.toFixed(2),
      r.geracao_distribuida.potencia_total_kw.toFixed(2),
      r.geracao_distribuida.total_unidades,
      r.metricas_rede.nivel_criticidade_gd,
    ].join(";"));

    return [headers.join(";"), ...lines].join("\n");
  }

  async getSolarSimulation(
    idTecnico: string,
    date?: string,
    municipio = "all",
    signal?: AbortSignal,
  ): Promise<SolarSimulation> {
    const params = new URLSearchParams({ municipio });
    if (date) params.set("data", date);
    const query = `?${params.toString()}`;
    return this.get<SolarSimulation>(`/simulacao/id/${encodeURIComponent(idTecnico)}${query}`, signal);
  }

  private async get<T>(path: string, signal?: AbortSignal): Promise<T> {
    return this.request<T>(path, { method: "GET", signal });
  }

  private csrfToken() {
    if (typeof document === "undefined") return "";
    const token = document.cookie
      .split(";")
      .map((item) => item.trim())
      .find((item) => item.startsWith("gridscope_csrf="));
    return token ? decodeURIComponent(token.slice("gridscope_csrf=".length)) : "";
  }

  private async request<T>(path: string, init: RequestInit = {}): Promise<T> {
    const method = (init.method || "GET").toUpperCase();
    const headers = new Headers(init.headers);
    headers.set("Accept", "application/json");
    if (method !== "GET" && method !== "HEAD") {
      const csrf = this.csrfToken();
      if (csrf) headers.set("X-CSRF-Token", csrf);
    }

    const response = await fetch(`${this.baseUrl}${path}`, {
      ...init,
      headers,
      credentials: "include",
    });

    if (!response.ok) {
      let detail = `A API retornou ${response.status}`;
      try {
        const payload = (await response.json()) as { detail?: unknown };
        if (typeof payload.detail === "string" && payload.detail.trim()) detail = payload.detail;
      } catch {
        // Keep the status-based message when the response is not JSON.
      }
      throw new ApiError(detail, response.status);
    }

    if (response.status === 204) return undefined as T;
    return (await response.json()) as T;
  }

  async login(email: string, password: string, signal?: AbortSignal): Promise<AuthUser> {
    const response = await this.request<{ user: AuthUser }>("/auth/login", {
      method: "POST",
      signal,
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    });
    return response.user;
  }

  async logout(): Promise<void> {
    await this.request<void>("/auth/logout", { method: "POST" });
  }

  async getCurrentUser(signal?: AbortSignal): Promise<AuthUser> {
    const response = await this.request<{ user: AuthUser }>("/auth/me", { method: "GET", signal });
    return response.user;
  }

  async listUsers(): Promise<AuthUser[]> {
    return this.get<AuthUser[]>("/auth/admin/users");
  }

  async createUser(payload: { email: string; name: string; password: string; role: "admin" | "user" }) {
    return this.request<AuthUser>("/auth/admin/users", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
  }

  async updateUser(userId: string, payload: { name?: string; role?: "admin" | "user"; is_active?: boolean }) {
    return this.request<AuthUser>(`/auth/admin/users/${encodeURIComponent(userId)}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
  }

  async resetUserPassword(userId: string, password: string) {
    await this.request<void>(`/auth/admin/users/${encodeURIComponent(userId)}/reset-password`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ password }),
    });
  }

  async sendChat(
    message: string,
    history: ChatMessage[] = [],
    conversationId?: number | null,
    municipio = "all",
  ) {
    return this.request<ChatResponse>("/chat/message", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        mensagem: message,
        historico: history,
        conversa_id: conversationId ?? undefined,
        municipio,
      }),
    });
  }
}

export const api = new GridScopeApi();
