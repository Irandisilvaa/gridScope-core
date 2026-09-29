"""Adaptadores de aquisição de dados externos e locais."""

from .contratos import DataDelivery, DataSource


def create_data_source() -> DataSource:
    """Cria a fonte configurada sem importar configuração ao carregar o pacote."""

    from .factory import create_data_source as build_data_source

    return build_data_source()


__all__ = ["DataDelivery", "DataSource", "create_data_source"]
