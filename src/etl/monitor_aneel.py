import argparse
import json
import logging
import os
import re
import shutil
import sys
from pathlib import Path
from urllib.parse import urlparse

import requests

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

from config import (
    ANEEL_API_HUB_URL,
    DATA_MAX_ARCHIVE_ENTRIES,
    DATA_MAX_DOWNLOAD_BYTES,
    DATA_SOURCE_TIMEOUT_SECONDS,
    DIR_DADOS,
    DISTRIBUIDORA_ALVO,
)
try:
    from .fontes.exceptions import DataSourceError
    from .fontes.http import HttpFileSource
except ImportError:
    from etl.fontes.exceptions import DataSourceError
    from etl.fontes.http import HttpFileSource


def _selecionar_candidato(resultados, distribuidora=None):
    candidatos = []
    termos = (distribuidora or DISTRIBUIDORA_ALVO).upper().split()

    for item in resultados:
        props = item.get('properties', {})
        nome = props.get('title', 'Sem Nome').upper()

        if all(termo in nome for termo in termos):
            candidatos.append(props)

    if not candidatos:
        return None

    def criterio(item):
        nome = item.get('title', '')
        ano = 0
        match = re.search(r'202[0-9]', nome)
        if match:
            ano = int(match.group(0))
        tem_link = 1 if " - Link" in nome else 0
        return (ano, tem_link, nome)

    candidatos.sort(key=criterio, reverse=True)
    return candidatos[0]


def _url_de_referencia(item):
    nome = item.get('title', '')
    id_arquivo = item.get('id')
    url_original = str(item.get('url') or '')

    if " - Link" in nome and '/documents/' in url_original:
        return f"https://www.arcgis.com/sharing/rest/content/items/{id_arquivo}/data"
    if " - Link" in nome:
        return url_original
    # Itens "File Geodatabase" são arquivos armazenados no próprio ArcGIS.
    # A URL antiga do Hub termina em .geodatabase, mas entrega uma página HTML.
    return f"https://www.arcgis.com/sharing/rest/content/items/{id_arquivo}/data"


def _encontrar_url_download(payload):
    """Encontra uma URL de arquivo dentro do documento de referência ArcGIS."""

    prioridades = ("url", "sourceUrl", "downloadUrl", "href", "link")
    if isinstance(payload, dict):
        for chave in prioridades:
            encontrada = _encontrar_url_download(payload.get(chave))
            if encontrada:
                return encontrada
        for valor in payload.values():
            encontrada = _encontrar_url_download(valor)
            if encontrada:
                return encontrada
    elif isinstance(payload, list):
        for valor in payload:
            encontrada = _encontrar_url_download(valor)
            if encontrada:
                return encontrada
    elif isinstance(payload, str):
        valor = payload.strip()
        if valor.startswith("https://"):
            return valor
    return None


def resolver_url_download(referencia, session=requests):
    """Resolve itens de referência ArcGIS para o ZIP/GDB efetivamente baixável."""

    url = str(referencia.get("url") or "").strip()
    if not url or urlparse(url).scheme != "https":
        raise DataSourceError("A referência ANEEL não contém uma URL HTTPS válida")

    if not referencia.get("name", "").endswith(" - Link"):
        return url

    try:
        response = session.get(url, timeout=30)
        response.raise_for_status()
        content_type = response.headers.get("Content-Type", "").casefold()
        if "json" in content_type:
            payload = response.json()
        else:
            try:
                payload = response.json()
            except ValueError:
                payload = response.text
    except requests.RequestException as error:
        raise DataSourceError("Falha ao resolver o link de referência ANEEL") from error

    resolved = _encontrar_url_download(payload)
    if not resolved:
        raise DataSourceError("O item ANEEL não informou uma URL de download")
    if urlparse(resolved).scheme != "https":
        raise DataSourceError("A URL de download ANEEL deve usar HTTPS")
    return resolved

def verificar_aneel(distribuidora=None, *, somente_consulta=True):
    alvo = distribuidora or DISTRIBUIDORA_ALVO
    print("Monitor ANEEL (somente consulta; não publica dados)")
    print(f"Alvo: '{alvo}'")
    
    try:
        # O catálogo mistura itens genéricos e entregas históricas; 30 resultados
        # não bastam para algumas distribuidoras, como a Light.
        params = {"q": alvo, "limit": 100}
        response = requests.get(ANEEL_API_HUB_URL, params=params, timeout=15)
        
        if response.status_code != 200:
            print(f"Erro API: {response.status_code}")
            return

        resultados = response.json().get('features', [])
        if not resultados:
            print("Nenhum resultado encontrado.")
            return

        print(f"Analisando {len(resultados)} itens...")

        vencedor = _selecionar_candidato(resultados, alvo)
        if vencedor is not None and not re.search(r"20\d{2}", vencedor.get("title", "")):
            response_bdgd = requests.get(
                ANEEL_API_HUB_URL,
                params={"q": f"{alvo} BDGD", "limit": 100},
                timeout=15,
            )
            if response_bdgd.status_code == 200:
                adicionais = response_bdgd.json().get("features", [])
                por_id = {
                    feature.get("properties", {}).get("id"): feature
                    for feature in [*resultados, *adicionais]
                }
                resultados = list(por_id.values())
                vencedor = _selecionar_candidato(resultados, alvo)
        if vencedor is None:
            print("Nenhum arquivo compatível.")
            return None

        nome_final = vencedor.get('title')
        id_arquivo = vencedor.get('id')
        data_raw = vencedor.get('updated')
        url_referencia = _url_de_referencia(vencedor)
        
        print(f"\nARQUIVO VENCEDOR:")
        print(f"{nome_final}")

        referencia = {
            'name': nome_final,
            'last_updated': str(data_raw),
            'url': url_referencia,
            'id': id_arquivo,
        }
        print(f"Referência encontrada: {url_referencia}")
        if somente_consulta:
            print("Nenhum arquivo foi baixado e nenhum dado operacional foi alterado.")
        else:
            print("Referência selecionada. Iniciando aquisição segura...")
        return referencia

    except Exception as error:
        print(f"Erro na consulta ANEEL: {error}")
        return None


def adquirir_aneel(distribuidora, *, publicar=False, destino=None):
    """Consulta, baixa e opcionalmente publica uma BDGD selecionada da ANEEL."""

    logger = logging.getLogger(__name__)
    logger.info("[ETAPA 1] Consultando catálogo ANEEL para %s...", distribuidora)
    referencia = verificar_aneel(distribuidora, somente_consulta=False)
    if referencia is None:
        raise DataSourceError(f"Nenhuma entrega ANEEL encontrada para {distribuidora}")
    download_url = resolver_url_download(referencia)
    period_match = re.search(r"(20\d{2}-\d{2}-\d{2})", referencia.get("name", ""))
    source = HttpFileSource(
        download_url,
        timeout_seconds=DATA_SOURCE_TIMEOUT_SECONDS,
        max_download_bytes=DATA_MAX_DOWNLOAD_BYTES,
        max_archive_entries=DATA_MAX_ARCHIVE_ENTRIES,
        source_name="aneel",
        reference_period=period_match.group(1) if period_match else None,
    )
    logger.info("[ETAPA 2] Baixando, validando e extraindo a entrega...")
    delivery = source.fetch()
    logger.info("[ETAPA 2] Entrega adquirida: %s", str(delivery.delivery_id)[:12])
    if publicar:
        try:
            from .pipeline import ingest_delivery
        except ImportError:
            from etl.pipeline import ingest_delivery
        # ingest_delivery assume a responsabilidade pelo cleanup, inclusive em falha.
        logger.info("[ETAPA 3] Iniciando publicação transacional...")
        result = ingest_delivery(delivery)
        logger.info(
            "[CONCLUÍDO] Publicação %s disponível para uso",
            result.get("publication_id", "desconhecida"),
        )
        return result

    try:
        target_root = Path(destino or DIR_DADOS)
        target_root.mkdir(parents=True, exist_ok=True)
        safe_name = re.sub(r"[^A-Za-z0-9._-]+", "_", distribuidora).strip("_")
        target = target_root / f"{safe_name}-{delivery.delivery_id[:12]}.gdb"
        if target.exists():
            raise DataSourceError(f"Destino já existe: {target}")
        shutil.copytree(delivery.local_path, target)
        logger.info("[CONCLUÍDO] GDB preservado em %s", target)
        return {
            "delivery_id": delivery.delivery_id,
            "distribuidora": distribuidora,
            "local_path": str(target),
            "source_url": download_url,
        }
    finally:
        delivery.cleanup()


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Consulta ou adquire uma base BDGD publicada no catálogo ANEEL"
    )
    parser.add_argument("--distribuidora", default=DISTRIBUIDORA_ALVO)
    action = parser.add_mutually_exclusive_group()
    action.add_argument("--baixar", action="store_true", help="baixa o GDB para dados/")
    action.add_argument(
        "--publicar",
        action="store_true",
        help="baixa e publica atomicamente no banco operacional",
    )
    parser.add_argument("--destino", help="diretório usado com --baixar")
    args = parser.parse_args(argv)

    if not args.baixar and not args.publicar:
        referencia = verificar_aneel(args.distribuidora)
        if referencia:
            print(json.dumps(referencia, ensure_ascii=False, indent=2))
        return 0 if referencia else 1

    try:
        resultado = adquirir_aneel(
            args.distribuidora,
            publicar=args.publicar,
            destino=args.destino,
        )
    except KeyboardInterrupt:
        logging.getLogger(__name__).warning(
            "[CANCELADO] Operação interrompida pelo usuário; a publicação vigente foi preservada"
        )
        return 130
    print(json.dumps(_resumo_publicacao(resultado), ensure_ascii=False, indent=2, default=str))
    return 0


def _resumo_publicacao(resultado: dict) -> dict:
    """Reduz a resposta a um resumo legível.

    A resposta completa carrega a proveniência de cada município e a lista de
    identificadores de cada descarte; despejar isso no console transforma o
    resultado da publicação em um muro de texto. O detalhe continua no arquivo
    de metadados e nos diagnósticos.
    """

    quality_report = resultado.get("quality_report") or {}
    descartes = quality_report.get("discarded_records") or []
    resumo: dict = {
        "delivery_id": resultado.get("delivery_id"),
        "publication_id": resultado.get("publication_id"),
        "city_target": resultado.get("city_target"),
        "row_counts": resultado.get("row_counts"),
        "descartes": [
            {"table": registro.get("table"), "reason": registro.get("reason"), "count": registro.get("count")}
            for registro in descartes
        ],
    }
    geoespacial = quality_report.get("geospatial") or {}
    if "status" in geoespacial:
        resumo["geoespacial"] = {
            chave: geoespacial[chave]
            for chave in (
                "status",
                "municipality_count",
                "inside_count",
                "outside_within_tolerance_count",
                "outside_above_tolerance_count",
                "tolerance_m",
            )
            if chave in geoespacial
        }
        resumo["geoespacial"]["provenance"] = {
            "municipios": geoespacial.get("municipality_count"),
            "qualidade": sorted({m.get("qualidade") for m in geoespacial.get("boundary_provenance", []) if m.get("qualidade")}),
            "checksums": sorted({m.get("checksum_sha256") for m in geoespacial.get("boundary_provenance", []) if m.get("checksum_sha256")}),
        }
    return resumo

if __name__ == "__main__":
    raise SystemExit(main())
