"""
Camada de Acesso a Dados (DAL) - Database Access Layer
Centraliza todas as operações com o banco de dados PostgreSQL/PostGIS
"""
import os
import sys
import logging
import json
import geopandas as gpd
import pandas as pd
from sqlalchemy import create_engine, text
from typing import Optional, List
import re

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from config import DATABASE_SCHEMA, DATABASE_URL, DATA_SOURCE, FILE_GDB, get_cidade_alvo

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("Database")

_COLUNAS_PERMITIDAS = {
    "subestacoes": {"COD_ID", "NOME", "geometry"},
    "transformadores": {"COD_ID", "SUB", "MUN", "geometry"},
    "consumidores": {
        "UNI_TR_MT", "CLAS_SUB", "PN_CON", "DAT_CON", "MUN",
        *(f"ENE_{mes:02d}" for mes in range(1, 13)),
    },
    "geracao_gd": {"UNI_TR_MT", "POT_INST", "PN_CON", "DAT_CON", "MUN"},
    "rede_mt": {"COD_ID", "SUB", "geometry"},
    "limites_municipais": {
        "municipio_codigo",
        "nome",
        "uf",
        "fonte",
        "qualidade",
        "revisao",
        "fonte_url",
        "checksum_sha256",
        "obtido_em",
        "geometry",
    },
    "territorios_voronoi_municipais": {
        "municipio_codigo", "COD_ID", "NOM", "SITE_LON", "SITE_LAT",
        "LABEL_LON", "LABEL_LAT", "geometry"
    },
    "territorios_voronoi": {
        "COD_ID", "NOM", "SITE_LON", "SITE_LAT", "LABEL_LON", "LABEL_LAT", "geometry"
    },
}


def _qualified_table(table_name: str) -> str:
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", DATABASE_SCHEMA):
        raise ValueError(f"Schema de banco inválido: {DATABASE_SCHEMA}")
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", table_name):
        raise ValueError(f"Tabela inválida: {table_name}")
    return f'"{DATABASE_SCHEMA}"."{table_name}"'


def _select_columns(table_name: str, columns: Optional[List[str]]) -> str:
    if not columns:
        return "*"

    allowed = _COLUNAS_PERMITIDAS.get(table_name, set())
    invalid = [column for column in columns if column not in allowed]
    if invalid:
        raise ValueError(f"Colunas não permitidas para {table_name}: {', '.join(invalid)}")
    if len(set(columns)) != len(columns):
        raise ValueError(f"Colunas duplicadas para {table_name}")
    return ", ".join(f'"{column}"' for column in columns)


def get_engine():
    """
    Retorna engine SQLAlchemy configurada para PostgreSQL/PostGIS
    
    Returns:
        Engine: SQLAlchemy engine configurado
    """
    try:
        connect_args = {}
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", DATABASE_SCHEMA):
            raise ValueError(f"Schema de banco inválido: {DATABASE_SCHEMA}")
        if DATABASE_SCHEMA != "public":
            connect_args["options"] = f"-csearch_path={DATABASE_SCHEMA},public"

        engine = create_engine(DATABASE_URL, connect_args=connect_args)
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        logger.info("✅ Conexão com banco de dados estabelecida")
        return engine
    except Exception as e:
        logger.error(f"❌ Erro ao conectar no banco de dados: {e}")
        raise


def _inicializar_grid_scope_publication() -> Optional[dict]:
    """Cria e popula grid_scope_publication a partir das tabelas existentes caso o banco tenha sido restaurado sem metadados."""
    try:
        engine = get_engine()
        with engine.begin() as conn:
            conn.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS public.grid_scope_publication (
                        publication_key SMALLINT PRIMARY KEY CHECK (publication_key = 1),
                        publication_id UUID NOT NULL,
                        delivery_id TEXT NOT NULL,
                        source TEXT NOT NULL,
                        reference_period TEXT,
                        city_target TEXT,
                        published_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                        row_counts JSONB NOT NULL DEFAULT '{}'::jsonb,
                        quality_report JSONB NOT NULL DEFAULT '{}'::jsonb
                    )
                    """
                )
            )
            conn.execute(
                text(
                    """
                    ALTER TABLE public.grid_scope_publication
                    ADD COLUMN IF NOT EXISTS publication_id UUID
                    """
                )
            )
            conn.execute(
                text(
                    """
                    UPDATE public.grid_scope_publication
                    SET publication_id = gen_random_uuid()
                    WHERE publication_id IS NULL
                    """
                )
            )
            conn.execute(
                text(
                    """
                    ALTER TABLE public.grid_scope_publication
                    ALTER COLUMN publication_id SET NOT NULL
                    """
                )
            )
            # Verifica se existem subestações carregadas
            sub_count = conn.execute(text("SELECT count(*) FROM public.subestacoes")).scalar()
            if not sub_count:
                return None

            delivery_id = os.path.splitext(FILE_GDB)[0] if FILE_GDB else "GS-PROD-2026"
            city_target = get_cidade_alvo()
            counts = {"subestacoes": int(sub_count)}
            for tbl in ("transformadores", "consumidores", "geracao_gd"):
                try:
                    c = conn.execute(text(f"SELECT count(*) FROM public.{tbl}")).scalar()
                    if c is not None:
                        counts[tbl] = int(c)
                except Exception:
                    pass

            conn.execute(
                text(
                    """
                    INSERT INTO public.grid_scope_publication
                        (publication_key, publication_id, delivery_id, source, reference_period, city_target, published_at, row_counts, quality_report)
                    VALUES
                        (1, gen_random_uuid(), :delivery_id, :source, '2024-12-31', :city_target, NOW(), CAST(:row_counts AS jsonb), '{}'::jsonb)
                    ON CONFLICT (publication_key) DO UPDATE SET
                        city_target = EXCLUDED.city_target
                    """
                ),
                {
                    "delivery_id": delivery_id,
                    "source": DATA_SOURCE or "local_file",
                    "city_target": city_target,
                    "row_counts": json.dumps(counts),
                },
            )
        return carregar_publication_metadata()
    except Exception as exc:
        logger.warning("Não foi possível auto-inicializar grid_scope_publication: %s", exc)
        return None


def carregar_publication_metadata() -> Optional[dict]:
    """Carrega a identificação da última publicação confirmada no banco."""

    engine = None
    try:
        engine = get_engine()
        with engine.begin() as conn:
            conn.execute(
                text(
                    """
                    ALTER TABLE public.grid_scope_publication
                    ADD COLUMN IF NOT EXISTS publication_id UUID
                    """
                )
            )
            conn.execute(
                text(
                    """
                    UPDATE public.grid_scope_publication
                    SET publication_id = gen_random_uuid()
                    WHERE publication_id IS NULL
                    """
                )
            )
            row = conn.execute(
                text(
                    """
                    SELECT
                        publication.publication_id,
                        publication.delivery_id,
                        publication.source,
                        publication.reference_period,
                        to_jsonb(publication) ->> 'city_target' AS city_target,
                        publication.published_at,
                        publication.row_counts,
                        COALESCE(
                            to_jsonb(publication) -> 'quality_report',
                            '{}'::jsonb
                        ) AS quality_report
                    FROM public.grid_scope_publication AS publication
                    WHERE publication.publication_key = 1
                    """
                )
            ).mappings().first()
            if row is None:
                return _inicializar_grid_scope_publication()

            row_counts = row["row_counts"]
            if isinstance(row_counts, str):
                row_counts = json.loads(row_counts)
            quality_report = row["quality_report"]
            if isinstance(quality_report, str):
                quality_report = json.loads(quality_report)
            published_at = row["published_at"]
            city_target = row["city_target"] or get_cidade_alvo()
            return {
                "status": "published",
                "source": row["source"],
                "publication_id": str(row["publication_id"]),
                "delivery_id": row["delivery_id"],
                "reference_period": row["reference_period"],
                "city_target": city_target,
                "published_at": published_at.isoformat() if hasattr(published_at, "isoformat") else published_at,
                "row_counts": row_counts if isinstance(row_counts, dict) else {},
                "quality_report": quality_report if isinstance(quality_report, dict) else {},
            }
    except Exception as error:
        # Banco publicado antes do registro transacional ainda não tem a tabela.
        if getattr(getattr(error, "orig", None), "pgcode", None) == "42P01":
            logger.info("Banco ainda sem registro de publicação (grid_scope_publication)")
            return _inicializar_grid_scope_publication()
        logger.warning("Não foi possível ler metadados da publicação: %s", error)
        return None
    finally:
        if engine is not None:
            engine.dispose()


def carregar_subestacoes(colunas: Optional[List[str]] = None) -> gpd.GeoDataFrame:
    """
    Carrega dados da tabela 'subestacoes' (SUB)
    
    Args:
        colunas: Lista de colunas específicas a carregar. None = todas
        
    Returns:
        GeoDataFrame com dados das subestações
    """
    engine = get_engine()
    
    try:
        if colunas:
            cols_sql = _select_columns("subestacoes", colunas)
            if "geometry" not in colunas:
                cols_sql += ', "geometry"'
            sql = f'SELECT {cols_sql} FROM subestacoes'
        else:
            sql = "SELECT * FROM subestacoes"
        
        gdf = gpd.read_postgis(sql, engine, geom_col='geometry')
        logger.info(f"📥 Carregadas {len(gdf)} subestações do banco")
        return gdf
    except Exception as e:
        logger.error(f"❌ Erro ao carregar subestações: {e}")
        raise
    finally:
        engine.dispose()


def carregar_transformadores(colunas: Optional[List[str]] = None) -> gpd.GeoDataFrame:
    """
    Carrega dados da tabela 'transformadores' (UNTRAT_AT)
    
    Args:
        colunas: Lista de colunas específicas a carregar. None = todas
        
    Returns:
        GeoDataFrame com dados dos transformadores
    """
    engine = get_engine()
    
    try:
        if colunas:
            cols_sql = _select_columns("transformadores", colunas)
            if 'geometry' not in colunas:
                sql = f'SELECT {cols_sql}, "geometry" FROM transformadores'
            else:
                sql = f"SELECT {cols_sql} FROM transformadores"
        else:
            sql = "SELECT * FROM transformadores"
        
        gdf = gpd.read_postgis(sql, engine, geom_col='geometry')
        
        logger.info(f"📥 Carregados {len(gdf)} transformadores do banco")
        return gdf
    except Exception as e:
        logger.error(f"❌ Erro ao carregar transformadores: {e}")
        raise
    finally:
        engine.dispose()


def carregar_consumidores(colunas: Optional[List[str]] = None, ignore_geometry: bool = False) -> pd.DataFrame:
    """
    Carrega dados da tabela 'consumidores' (UCBT_tab)
    NOTA: Esta tabela não possui geometria no PostgreSQL
    
    Args:
        colunas: Lista de colunas específicas a carregar. None = todas
        ignore_geometry: Ignorado, mantido para compatibilidade
        
    Returns:
        DataFrame com dados dos consumidores
    """
    engine = get_engine()
    
    try:
        cols_sql = _select_columns("consumidores", colunas)
        
        sql = f"SELECT {cols_sql} FROM consumidores"
        
        df = pd.read_sql(sql, engine)
        
        logger.info(f"📥 Carregados {len(df)} consumidores do banco")
        return df
    except Exception as e:
        logger.error(f"❌ Erro ao carregar consumidores: {e}")
        raise
    finally:
        engine.dispose()


def carregar_geracao_gd(colunas: Optional[List[str]] = None, ignore_geometry: bool = False) -> pd.DataFrame:
    """
    Carrega dados da tabela 'geracao_gd' (UGBT_tab)
    NOTA: Esta tabela não possui geometria no PostgreSQL
    
    Args:
        colunas: Lista de colunas específicas a carregar. None = todas
        ignore_geometry: Ignorado, mantido para compatibilidade
        
    Returns:
        DataFrame com dados de geração distribuída
    """
    engine = get_engine()
    
    try:
        cols_sql = _select_columns("geracao_gd", colunas)
        
        sql = f"SELECT {cols_sql} FROM geracao_gd"
        
        df = pd.read_sql(sql, engine)
        
        logger.info(f"📥 Carregados {len(df)} registros de GD do banco")
        return df
    except Exception as e:
        logger.error(f"❌ Erro ao carregar geração distribuída: {e}")
        raise
    finally:
        engine.dispose()


def carregar_cobertura_municipios() -> list[dict]:
    """Retorna a cobertura disponível por código IBGE na carga atual."""

    engine = get_engine()
    try:
        consumidores = _qualified_table("consumidores")
        transformadores = _qualified_table("transformadores")
        geracao_gd = _qualified_table("geracao_gd")
        query = text(f"""
            WITH municipios AS (
                SELECT DISTINCT NULLIF(BTRIM(CAST("MUN" AS TEXT)), '') AS codigo
                FROM {consumidores}
                WHERE "MUN" IS NOT NULL
                UNION
                SELECT DISTINCT NULLIF(BTRIM(CAST("MUN" AS TEXT)), '') AS codigo
                FROM {transformadores}
                WHERE "MUN" IS NOT NULL
                UNION
                SELECT DISTINCT NULLIF(BTRIM(CAST("MUN" AS TEXT)), '') AS codigo
                FROM {geracao_gd}
                WHERE "MUN" IS NOT NULL
            ), consumidores_por_municipio AS (
                SELECT BTRIM(CAST("MUN" AS TEXT)) AS codigo, COUNT(*) AS total
                FROM {consumidores}
                WHERE "MUN" IS NOT NULL
                GROUP BY BTRIM(CAST("MUN" AS TEXT))
            ), transformadores_por_municipio AS (
                SELECT
                    BTRIM(CAST("MUN" AS TEXT)) AS codigo,
                    COUNT(DISTINCT "COD_ID") AS total,
                    COUNT(DISTINCT "SUB") AS subestacoes
                FROM {transformadores}
                WHERE "MUN" IS NOT NULL
                GROUP BY BTRIM(CAST("MUN" AS TEXT))
            ), gd_por_municipio AS (
                SELECT BTRIM(CAST("MUN" AS TEXT)) AS codigo, COUNT(*) AS total
                FROM {geracao_gd}
                WHERE "MUN" IS NOT NULL
                GROUP BY BTRIM(CAST("MUN" AS TEXT))
            )
            SELECT
                municipios.codigo,
                COALESCE(consumidores_por_municipio.total, 0) AS consumidores,
                COALESCE(transformadores_por_municipio.total, 0) AS transformadores,
                COALESCE(transformadores_por_municipio.subestacoes, 0) AS subestacoes,
                COALESCE(gd_por_municipio.total, 0) AS unidades_gd
            FROM municipios
            LEFT JOIN consumidores_por_municipio USING (codigo)
            LEFT JOIN transformadores_por_municipio USING (codigo)
            LEFT JOIN gd_por_municipio USING (codigo)
            WHERE municipios.codigo IS NOT NULL
            ORDER BY municipios.codigo
        """)
        with engine.connect() as connection:
            return [dict(row) for row in connection.execute(query).mappings()]
    except Exception as error:
        logger.warning("Não foi possível calcular a cobertura municipal: %s", error)
        return []
    finally:
        engine.dispose()


def carregar_rede_mt(colunas: Optional[List[str]] = None) -> gpd.GeoDataFrame:
    """
    Carrega dados da tabela 'rede_mt' (SSDMT)
    
    Args:
        colunas: Lista de colunas específicas a carregar. None = todas
        
    Returns:
        GeoDataFrame com dados da rede MT
    """
    engine = get_engine()
    
    try:
        if colunas:
            cols_sql = _select_columns("rede_mt", colunas)
            if "geometry" not in colunas:
                cols_sql += ', "geometry"'
            sql = f"SELECT {cols_sql} FROM rede_mt"
        else:
            sql = "SELECT * FROM rede_mt"
        
        gdf = gpd.read_postgis(sql, engine, geom_col='geometry')
        logger.info(f"📥 Carregados {len(gdf)} trechos de rede MT do banco")
        return gdf
    except Exception as e:
        logger.error(f"❌ Erro ao carregar rede MT: {e}")
        raise
    finally:
        engine.dispose()


def carregar_voronoi() -> gpd.GeoDataFrame:
    """
    Carrega dados da tabela 'territorios_voronoi'
    
    Returns:
        GeoDataFrame com territórios de Voronoi das subestações
    """
    engine = get_engine()
    
    try:
        sql = f"SELECT * FROM {_qualified_table('territorios_voronoi')}"
        gdf = gpd.read_postgis(sql, engine, geom_col='geometry')
        logger.info(f"📥 Carregados {len(gdf)} territórios Voronoi do banco")
        return gdf
    except Exception as e:
        logger.error(f"❌ Erro ao carregar Voronoi: {e}")
        raise
    finally:
        engine.dispose()


def carregar_limites_municipais() -> gpd.GeoDataFrame:
    """Carrega a malha municipal da publicação atual."""

    engine = get_engine()
    try:
        gdf = gpd.read_postgis(
            f"SELECT * FROM {_qualified_table('limites_municipais')}",
            engine,
            geom_col="geometry",
        )
        logger.info("📥 Carregados %s limites municipais do banco", len(gdf))
        return gdf
    except Exception as error:
        logger.error("❌ Erro ao carregar limites municipais: %s", error)
        raise
    finally:
        engine.dispose()


def carregar_voronoi_municipal(municipio_codigo: str) -> gpd.GeoDataFrame:
    """Carrega os recortes municipais do Voronoi global."""

    engine = get_engine()
    try:
        query = text(
            f"""
            SELECT *
            FROM {_qualified_table('territorios_voronoi_municipais')}
            WHERE municipio_codigo = :municipio_codigo
            """
        )
        gdf = gpd.read_postgis(
            query,
            engine,
            params={"municipio_codigo": municipio_codigo},
            geom_col="geometry",
        )
        logger.info(
            "📥 Carregados %s territórios municipais para %s",
            len(gdf),
            municipio_codigo,
        )
        return gdf
    except Exception as error:
        logger.error("❌ Erro ao carregar territórios municipais: %s", error)
        raise
    finally:
        engine.dispose()


def _avisar_publicacao_direta() -> None:
    """Avisa quando um job derivado publica no schema operacional fora do pipeline.

    Não bloqueia: execuções manuais e o dashboard continuam funcionando como
    antes. O corte atômico continua sendo o caminho recomendado e o único que
    atualiza ``grid_scope_publication`` e a versão de cache.
    """

    if os.getenv("GRIDSCOPE_DERIVED_STAGING") == "1" or DATABASE_SCHEMA != "public":
        return
    if os.getenv("GRIDSCOPE_ALLOW_DIRECT_PUBLICATION") == "1":
        return
    logger.warning(
        "Publicação direta de derivados detected fora do corte atômico; "
        "grid_scope_publication e o cache Redis não serão atualizados. "
        "Use `python -m src.etl.pipeline` para uma publicação consistente."
    )


def salvar_voronoi(gdf: gpd.GeoDataFrame) -> None:
    """
    Salva territórios Voronoi no banco de dados
    
    Args:
        gdf: GeoDataFrame com territórios de Voronoi
    """
    _avisar_publicacao_direta()
    engine = get_engine()
    
    try:
        if gdf.crs and gdf.crs.to_string() != "EPSG:4326":
            gdf = gdf.to_crs("EPSG:4326")
        
        gdf.to_postgis(
            'territorios_voronoi', 
            engine, 
            schema=DATABASE_SCHEMA,
            if_exists='replace', 
            index=False
        )
        logger.info(f"💾 Salvos {len(gdf)} territórios Voronoi no banco")
    except Exception as e:
        logger.error(f"❌ Erro ao salvar Voronoi: {e}")
        raise
    finally:
        engine.dispose()


def salvar_limites_municipais(gdf: gpd.GeoDataFrame) -> None:
    """Persiste a malha municipal usada para recortar os derivados."""

    _avisar_publicacao_direta()
    engine = get_engine()
    try:
        if gdf.crs and gdf.crs.to_string() != "EPSG:4326":
            gdf = gdf.to_crs("EPSG:4326")
        gdf.to_postgis(
            "limites_municipais",
            engine,
            schema=DATABASE_SCHEMA,
            if_exists="replace",
            index=False,
        )
        logger.info("💾 Salvos %s limites municipais no banco", len(gdf))
    except Exception as error:
        logger.error("❌ Erro ao salvar limites municipais: %s", error)
        raise
    finally:
        engine.dispose()


def salvar_voronoi_municipal(gdf: gpd.GeoDataFrame) -> None:
    """Persiste os recortes municipais do Voronoi global."""

    _avisar_publicacao_direta()
    engine = get_engine()
    try:
        if gdf.crs and gdf.crs.to_string() != "EPSG:4326":
            gdf = gdf.to_crs("EPSG:4326")
        gdf.to_postgis(
            "territorios_voronoi_municipais",
            engine,
            schema=DATABASE_SCHEMA,
            if_exists="replace",
            index=False,
        )
        logger.info("💾 Salvos %s recortes municipais do Voronoi", len(gdf))
    except Exception as error:
        logger.error("❌ Erro ao salvar recortes municipais: %s", error)
        raise
    finally:
        engine.dispose()


def criar_tabela_cache():
    """
    Cria tabela de cache de mercado se não existir
    Usa JSONB para armazenar dados agregados de forma eficiente
    """
    engine = get_engine()
    
    try:
        with engine.connect() as conn:
            conn.execute(text(f"""
                CREATE TABLE IF NOT EXISTS {_qualified_table('cache_mercado')} (
                    municipio_codigo VARCHAR NOT NULL DEFAULT 'all',
                    id_subestacao VARCHAR NOT NULL,
                    dados_json JSONB NOT NULL,
                    data_atualizacao TIMESTAMP DEFAULT NOW(),
                    PRIMARY KEY (municipio_codigo, id_subestacao)
                )
            """))
            cache_table = _qualified_table("cache_mercado")
            conn.execute(text(f"""
                ALTER TABLE {cache_table}
                ADD COLUMN IF NOT EXISTS municipio_codigo VARCHAR
            """))
            conn.execute(text(f"""
                UPDATE {cache_table}
                SET municipio_codigo = 'all'
                WHERE municipio_codigo IS NULL
            """))
            conn.execute(text(f"""
                ALTER TABLE {cache_table}
                ALTER COLUMN municipio_codigo SET DEFAULT 'all',
                ALTER COLUMN municipio_codigo SET NOT NULL
            """))
            # Compatibilidade com a tabela anterior, cuja chave era apenas o
            # identificador da subestação.
            conn.execute(text(f"""
                ALTER TABLE {cache_table}
                DROP CONSTRAINT IF EXISTS cache_mercado_pkey
            """))
            conn.execute(text(f"""
                ALTER TABLE {cache_table}
                ADD CONSTRAINT cache_mercado_pkey
                PRIMARY KEY (municipio_codigo, id_subestacao)
            """))
            conn.commit()
            logger.info("✅ Tabela cache_mercado verificada/criada")
    except Exception as e:
        logger.error(f"❌ Erro ao criar tabela cache: {e}")
        raise
    finally:
        engine.dispose()


def salvar_cache_mercado(dados_mercado: list) -> None:
    """
    Salva dados agregados de mercado no banco de dados
    
    Args:
        dados_mercado: Lista de dicts com dados agregados por subestação
    """
    import json

    _avisar_publicacao_direta()
    engine = get_engine()
    
    try:
        criar_tabela_cache()
        
        with engine.connect() as conn:
            cache_table = _qualified_table("cache_mercado")
            conn.execute(text(f"DELETE FROM {cache_table}"))
            
            for item in dados_mercado:
                id_sub = item.get('id_tecnico', str(item.get('subestacao', '')))
                municipio_codigo = item.get("municipio_codigo", "all") or "all"
                
                item_clean = {k: v for k, v in item.items() if k != 'geometry'}
                
                conn.execute(
                    text(f"""
                        INSERT INTO {cache_table}
                            (municipio_codigo, id_subestacao, dados_json, data_atualizacao)
                        VALUES (:municipio_codigo, :id, CAST(:dados AS jsonb), NOW())
                        ON CONFLICT (municipio_codigo, id_subestacao)
                        DO UPDATE SET dados_json = CAST(:dados AS jsonb), data_atualizacao = NOW()
                    """),
                    {
                        "municipio_codigo": municipio_codigo,
                        "id": id_sub,
                        "dados": json.dumps(item_clean, ensure_ascii=False),
                    }
                )
            
            conn.commit()
            logger.info(f"💾 Salvos {len(dados_mercado)} registros de cache no banco")
            
    except Exception as e:
        logger.error(f"❌ Erro ao salvar cache: {e}")
        raise
    finally:
        engine.dispose()


def carregar_cache_mercado(municipio_codigo: str = "all") -> list:
    """
    Carrega dados agregados de mercado do banco de dados
    
    Returns:
        Lista de dicts com dados agregados por subestação
    """
    import json
    
    engine = get_engine()
    
    try:
        with engine.connect() as conn:
            cache_table = _qualified_table("cache_mercado")
            criar_tabela_cache()
            result = conn.execute(text(f"""
                SELECT dados_json 
                FROM {cache_table}
                WHERE municipio_codigo = :municipio_codigo
                ORDER BY id_subestacao
            """), {"municipio_codigo": municipio_codigo or "all"})
            
            dados = []
            for row in result:
                item = row[0]
                if isinstance(item, str):
                    dados.append(json.loads(item))
                else:
                    dados.append(item)
            
            logger.info(f"📥 Carregados {len(dados)} registros de cache do banco")
            return dados
            
    except Exception as e:
        logger.error(f"❌ Erro ao carregar cache: {e}")
        raise
    finally:
        engine.dispose()


def verificar_cache_atualizado(max_horas: int = 24) -> bool:
    """
    Verifica se o cache está atualizado (menos de X horas)
    
    Args:
        max_horas: Número máximo de horas para considerar cache válido
        
    Returns:
        True se cache está atualizado, False caso contrário
    """
    engine = get_engine()
    
    try:
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT MAX(data_atualizacao) as ultima_atualizacao
                FROM cache_mercado
            """))
            
            row = result.fetchone()
            
            if not row or not row[0]:
                logger.info("⚠️ Cache vazio ou inexistente")
                return False
            
            ultima_atualizacao = row[0]
            
            from datetime import datetime, timedelta
            agora = datetime.now()
            diferenca = agora - ultima_atualizacao
            
            if diferenca.total_seconds() / 3600 < max_horas:
                logger.info(f"✅ Cache atualizado (última atualização: {ultima_atualizacao})")
                return True
            else:
                logger.info(f"⚠️ Cache desatualizado (última atualização: {ultima_atualizacao})")
                return False
                
    except Exception as e:
        logger.warning(f"⚠️ Erro ao verificar cache: {e}")
        return False
    finally:
        engine.dispose()





def verificar_tabelas() -> dict:
    """
    Verifica quais tabelas existem no banco e retorna contagem de registros
    
    Returns:
        Dict com nome da tabela e contagem de registros
    """
    engine = get_engine()
    
    tabelas = [
        'subestacoes',
        'transformadores',
        'consumidores',
        'geracao_gd',
        'rede_mt',
        'territorios_voronoi',
        'limites_municipais',
        'territorios_voronoi_municipais',
        'cache_mercado'
    ]
    
    resultado = {}
    
    try:
        with engine.connect() as conn:
            for tabela in tabelas:
                try:
                    result = conn.execute(text(f'SELECT COUNT(*) FROM "{tabela}"'))
                    count = result.scalar()
                    resultado[tabela] = count
                    logger.info(f"✅ {tabela}: {count} registros")
                except Exception as e:
                    resultado[tabela] = f"Erro: {str(e)}"
                    logger.warning(f"⚠️ {tabela}: não encontrada ou erro")
        
        return resultado
    except Exception as e:
        logger.error(f"❌ Erro ao verificar tabelas: {e}")
        raise
    finally:
        engine.dispose()


if __name__ == "__main__":
    """Testa conexão e lista tabelas disponíveis"""
    print("🔌 Testando conexão com banco de dados...")
    print("=" * 60)
    
    try:
        engine = get_engine()
        print(f"✅ Conectado em: {DATABASE_URL.split('@')[1]}")
        print("=" * 60)
        print("\n📊 Verificando tabelas e contagens:")
        print("=" * 60)
        
        resultado = verificar_tabelas()
        
        print("\n" + "=" * 60)
        print("✅ Teste concluído com sucesso!")
        
    except Exception as e:
        print(f"\n❌ Falha no teste: {e}")
        sys.exit(1)

def criar_tabela_feedback():
    try:
        engine = get_engine()
        with engine.connect() as conn:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS chat_feedback (
                    id SERIAL PRIMARY KEY,
                    auth_user_id UUID REFERENCES auth_users(id) ON DELETE SET NULL,
                    pergunta TEXT NOT NULL,
                    resposta TEXT NOT NULL,
                    feedback BOOLEAN NOT NULL,
                    comentario TEXT,
                    created_at TIMESTAMP DEFAULT NOW()
                )
            """))
            
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_feedback_created 
                ON chat_feedback(created_at)
            """))
            conn.execute(text("""
                ALTER TABLE chat_feedback
                ADD COLUMN IF NOT EXISTS auth_user_id UUID REFERENCES auth_users(id) ON DELETE SET NULL
            """))
            
            conn.commit()
            logger.info("✅ Tabela chat_feedback verificada/criada")
            
    except Exception as e:
        logger.error(f"❌ Erro ao criar tabela chat_feedback: {e}")
        raise


def salvar_feedback_chat(
    pergunta: str,
    resposta: str,
    feedback: bool,
    comentario: str = None,
    usuario_id: str = None,
):
    try:
        engine = get_engine()
        with engine.connect() as conn:
            conn.execute(text("""
                INSERT INTO chat_feedback (auth_user_id, pergunta, resposta, feedback, comentario)
                VALUES (CAST(:usuario_id AS uuid), :pergunta, :resposta, :feedback, :comentario)
            """), {
                "usuario_id": usuario_id,
                "pergunta": pergunta,
                "resposta": resposta,
                "feedback": feedback,
                "comentario": comentario
            })
            conn.commit()
            
            emoji = "👍" if feedback else "👎"
            logger.info("%s Feedback salvo para usuário autenticado", emoji)
            
    except Exception as e:
        logger.warning(f"⚠️ Erro ao salvar feedback: {e}")
        raise


def criar_tabelas_historico():
    try:
        engine = get_engine()
        with engine.connect() as conn:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS chat_conversas (
                    id SERIAL PRIMARY KEY,
                    usuario_id TEXT NOT NULL,
                    auth_user_id UUID REFERENCES auth_users(id) ON DELETE CASCADE,
                    titulo TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT NOW(),
                    updated_at TIMESTAMP DEFAULT NOW()
                )
            """))
            
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS chat_mensagens (
                    id SERIAL PRIMARY KEY,
                    conversa_id INTEGER REFERENCES chat_conversas(id) ON DELETE CASCADE,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT NOW()
                )
            """))
            
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_conversas_usuario 
                ON chat_conversas(usuario_id)
            """))
            conn.execute(text("""
                ALTER TABLE chat_conversas
                ADD COLUMN IF NOT EXISTS auth_user_id UUID REFERENCES auth_users(id) ON DELETE CASCADE
            """))
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_mensagens_conversa 
                ON chat_mensagens(conversa_id)
            """))
            
            conn.commit()
            logger.info("✅ Tabelas de histórico verificadas/criadas")
            
    except Exception as e:
        logger.error(f"❌ Erro ao criar tabelas de histórico: {e}")
        raise


def criar_conversa(usuario_id: str, titulo: str):
    try:
        engine = get_engine()
        with engine.connect() as conn:
            result = conn.execute(text("""
                INSERT INTO chat_conversas (usuario_id, auth_user_id, titulo)
                VALUES (:usuario_id, CAST(:usuario_id AS uuid), :titulo)
                RETURNING id
            """), {
                "usuario_id": usuario_id,
                "titulo": titulo[:100]
            })
            
            conversa_id = result.fetchone()[0]
            conn.commit()
            
            logger.info("📝 Nova conversa criada: %s", conversa_id)
            return conversa_id
            
    except Exception as e:
        logger.warning(f"⚠️ Erro ao criar conversa: {e}")
        return None


def salvar_mensagem(conversa_id: int, role: str, content: str, usuario_id: str) -> bool:
    try:
        engine = get_engine()
        with engine.begin() as conn:
            ownership = conn.execute(text("""
                UPDATE chat_conversas
                SET updated_at = NOW()
                WHERE id = :conversa_id
                  AND auth_user_id = CAST(:usuario_id AS uuid)
            """), {
                "conversa_id": conversa_id,
                "usuario_id": usuario_id,
            })
            if ownership.rowcount != 1:
                return False

            conn.execute(text("""
                INSERT INTO chat_mensagens (conversa_id, role, content)
                VALUES (:conversa_id, :role, :content)
            """), {
                "conversa_id": conversa_id,
                "role": role,
                "content": content
            })
            
            return True
            
    except Exception as e:
        logger.warning(f"⚠️ Erro ao salvar mensagem: {e}")
        return False


def carregar_conversas(usuario_id: str, limite: int = 50):
    """Carrega lista de conversas do usuário"""
    try:
        engine = get_engine()
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT id, titulo, created_at, updated_at
                FROM chat_conversas
                WHERE auth_user_id = CAST(:usuario_id AS uuid)
                ORDER BY updated_at DESC
                LIMIT :limite
            """), {
                "usuario_id": usuario_id,
                "limite": limite
            })
            
            conversas = []
            for row in result:
                conversas.append({
                    "id": row[0],
                    "titulo": row[1],
                    "created_at": row[2].isoformat() if row[2] else None,
                    "updated_at": row[3].isoformat() if row[3] else None
                })
            
            return conversas
            
    except Exception as e:
        logger.warning(f"⚠️ Erro ao carregar conversas: {e}")
        raise


def carregar_mensagens(conversa_id: int, usuario_id: str):
    """Carrega mensagens de uma conversa"""
    try:
        engine = get_engine()
        with engine.connect() as conn:
            owned = conn.execute(text("""
                SELECT 1
                FROM chat_conversas
                WHERE id = :conversa_id
                  AND auth_user_id = CAST(:usuario_id AS uuid)
            """), {
                "conversa_id": conversa_id,
                "usuario_id": usuario_id,
            }).first()
            if not owned:
                return None

            result = conn.execute(text("""
                SELECT role, content, created_at
                FROM chat_mensagens
                WHERE conversa_id = :conversa_id
                ORDER BY created_at ASC
            """), {"conversa_id": conversa_id})
            
            mensagens = []
            for row in result:
                mensagens.append({
                    "role": row[0],
                    "content": row[1]
                })
            
            return mensagens
            
    except Exception as e:
        logger.warning(f"⚠️ Erro ao carregar mensagens: {e}")
        raise
