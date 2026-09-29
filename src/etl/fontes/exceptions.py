"""Erros de aquisição de dados, separados por responsabilidade."""


class DataSourceError(RuntimeError):
    """Falha ao obter ou validar uma entrega da fonte."""


class UnsupportedDataSourceError(DataSourceError):
    """A fonte configurada não possui adaptador disponível."""


class UnsafeArchiveError(DataSourceError):
    """O arquivo compactado viola as regras de segurança da ingestão."""
