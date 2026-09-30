"""Contrato de features compartilhado pelo treino, validação e inferência."""

FEATURE_COLUMNS = (
    "hora",
    "mes",
    "dia_semana",
    "eh_feriado",
    "eh_fim_semana",
    "pct_residencial",
    "pct_comercial",
    "pct_industrial",
    "pct_rural",
)

TARGET_COLUMN = "fator_consumo"
