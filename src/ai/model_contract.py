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

MODEL_CONTRACT_VERSION = "1"
MODEL_CONTRACT_ATTRIBUTE = "gridscope_model_contract_version"
MODEL_FEATURES_ATTRIBUTE = "gridscope_feature_columns"


def annotate_model(model):
    """Registra no artefato o contrato usado para treiná-lo."""

    setattr(model, MODEL_CONTRACT_ATTRIBUTE, MODEL_CONTRACT_VERSION)
    setattr(model, MODEL_FEATURES_ATTRIBUTE, tuple(FEATURE_COLUMNS))
    return model


def model_is_compatible(model) -> bool:
    """Verifica contrato explícito e nomes de features aprendidos pelo modelo."""

    contract_version = getattr(model, MODEL_CONTRACT_ATTRIBUTE, None)
    contract_features = tuple(getattr(model, MODEL_FEATURES_ATTRIBUTE, ()))
    learned_features = tuple(getattr(model, "feature_names_in_", ()))
    return (
        contract_version == MODEL_CONTRACT_VERSION
        and contract_features == FEATURE_COLUMNS
        and learned_features == FEATURE_COLUMNS
    )
