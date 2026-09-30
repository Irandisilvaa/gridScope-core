"""
Script para atualizar completamente o banco de dados
Útil para executar manualmente ou em pipelines CI/CD
"""
import argparse
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parents[1]))
sys.path.append(str(Path(__file__).resolve().parents[2]))

from src.etl.pipeline import ingest_current_delivery

def atualizar_banco_completo():
    """Executa o corte atômico do snapshot completo com seus derivados."""

    print("=" * 70)
    print("🔄 ATUALIZAÇÃO COMPLETA DO BANCO DE DADOS")
    print("=" * 70)

    resultado = ingest_current_delivery()
    print("\n🎉 ATUALIZAÇÃO CONCLUÍDA COM SUCESSO!")
    print(f"Entrega publicada: {resultado['delivery_id']}")
    print(f"Contagens: {resultado['row_counts']}")
    return resultado


def regenerar_apenas_cache():
    """Regera somente o cache de mercado a partir do banco já publicado."""

    print("=" * 70)
    print("📊 REGENERANDO APENAS O CACHE DE MERCADO")
    print("=" * 70)
    from src.modelos.analise_mercado import analisar_mercado

    analisar_mercado()
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description="Atualiza o banco de dados completo")
    parser.add_argument(
        "--skip-voronoi",
        action="store_true",
        help="mantido por compatibilidade; o corte atômico sempre calcula o Voronoi",
    )
    parser.add_argument(
        "--only-cache",
        action="store_true",
        help="apenas regenera o cache (assume que os dados já estão no banco)",
    )

    args = parser.parse_args()

    if args.only_cache:
        print("📊 Regenerando apenas cache...")
        try:
            regenerar_apenas_cache()
        except Exception as error:
            print(f"❌ Cache não regenerado: {error}", file=sys.stderr)
            return 1
        return 0

    if args.skip_voronoi:
        print(
            "ℹ️  --skip-voronoi não altera o corte: bruto, Voronoi, mercado e "
            "metadados são publicados na mesma transação."
        )

    try:
        atualizar_banco_completo()
    except Exception as error:
        print("\n" + "=" * 70)
        print("❌ ERRO NA ATUALIZAÇÃO")
        print("=" * 70)
        print(f"{type(error).__name__}: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
