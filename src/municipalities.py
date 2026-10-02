"""Catálogo local mínimo de municípios usados pelo escopo geográfico."""

from __future__ import annotations

import re
from typing import Iterable


ESCOPO_TODA_BASE = "all"


# O catálogo é versionado para que o dashboard continue identificando os
# códigos da carga mesmo quando o serviço externo do IBGE estiver indisponível.
MUNICIPIOS_IBGE: dict[str, str] = {
    "2800100": "Amparo do São Francisco",
    "2800209": "Aquidabã",
    "2800308": "Aracaju",
    "2800407": "Arauá",
    "2800506": "Areia Branca",
    "2800605": "Barra dos Coqueiros",
    "2800670": "Boquim",
    "2800704": "Brejo Grande",
    "2801009": "Campo do Brito",
    "2801108": "Canhoba",
    "2801207": "Canindé de São Francisco",
    "2801306": "Capela",
    "2801405": "Carira",
    "2801504": "Carmópolis",
    "2801603": "Cedro de São João",
    "2801702": "Cristinápolis",
    "2801900": "Cumbe",
    "2802007": "Divina Pastora",
    "2802106": "Estância",
    "2802205": "Feira Nova",
    "2802304": "Frei Paulo",
    "2802403": "Gararu",
    "2802502": "General Maynard",
    "2802601": "Graccho Cardoso",
    "2802700": "Ilha das Flores",
    "2802809": "Indiaroba",
    "2802908": "Itabaiana",
    "2803005": "Itabaianinha",
    "2803104": "Itabi",
    "2803203": "Itaporanga d'Ajuda",
    "2803302": "Japaratuba",
    "2803401": "Japoatã",
    "2803500": "Lagarto",
    "2803609": "Laranjeiras",
    "2803708": "Macambira",
    "2803807": "Malhada dos Bois",
    "2803906": "Malhador",
    "2804003": "Maruim",
    "2804102": "Moita Bonita",
    "2804201": "Monte Alegre de Sergipe",
    "2804300": "Muribeca",
    "2804409": "Neópolis",
    "2804458": "Nossa Senhora Aparecida",
    "2804508": "Nossa Senhora da Glória",
    "2804607": "Nossa Senhora das Dores",
    "2804706": "Nossa Senhora de Lourdes",
    "2804805": "Nossa Senhora do Socorro",
    "2804904": "Pacatuba",
    "2805000": "Pedra Mole",
    "2805109": "Pedrinhas",
    "2805208": "Pinhão",
    "2805307": "Pirambu",
    "2805406": "Poço Redondo",
    "2805505": "Poço Verde",
    "2805604": "Porto da Folha",
    "2805703": "Propriá",
    "2805802": "Riachão do Dantas",
    "2805901": "Riachuelo",
    "2806008": "Ribeirópolis",
    "2806107": "Rosário do Catete",
    "2806206": "Salgado",
    "2806305": "Santa Luzia do Itanhy",
    "2806404": "Santana do São Francisco",
    "2806503": "Santa Rosa de Lima",
    "2806602": "Santo Amaro das Brotas",
    "2806701": "São Cristóvão",
    "2806800": "São Domingos",
    "2806909": "São Francisco",
    "2807006": "São Miguel do Aleixo",
    "2807105": "Simão Dias",
    "2807204": "Siriri",
    "2807303": "Telha",
    "2807402": "Tobias Barreto",
    "2807501": "Tomar do Geru",
    "2807600": "Umbaúba",

    # Rio de Janeiro
    "3300100": "Angra dos Reis",
    "3300159": "Aperibé",
    "3300209": "Araruama",
    "3300308": "Armação dos Búzios",
    "3300407": "Barra do Piraí",
    "3300456": "Belford Roxo",
    "3300505": "Bom Jardim",
    "3300604": "Bom Jesus do Itabapoana",
    "3300703": "Cabo Frio",
    "3300802": "Cachoeiras de Macacu",
    "3300901": "Cambuci",
    "3301008": "Campos dos Goytacazes",
    "3301107": "Cantagalo",
    "3301206": "Carmo",
    "3301305": "Casimiro de Abreu",
    "3301404": "Conceição de Macabu",
    "3301503": "Cordeiro",
    "3301602": "Duas Barras",
    "3301701": "Duque de Caxias",
    "3301800": "Engenheiro Paulo de Frontin",
    "3301859": "Guapimirim",
    "3301909": "Itaboraí",
    "3302007": "Itaguaí",
    "3302056": "Italva",
    "3302106": "Itaocara",
    "3302205": "Itaperuna",
    "3302254": "Itatiaia",
    "3302270": "Japeri",
    "3302304": "Laje do Muriaé",
    "3302403": "Macaé",
    "3302452": "Macuco",
    "3302502": "Magé",
    "3302601": "Mangaratiba",
    "3302700": "Maricá",
    "3302809": "Mendes",
    "3302858": "Mesquita",
    "3302908": "Miguel Pereira",
    "3303005": "Miracema",
    "3303104": "Natividade",
    "3303203": "Nilópolis",
    "3303302": "Niterói",
    "3303401": "Nova Friburgo",
    "3303500": "Nova Iguaçu",
    "3303609": "Paracambi",
    "3303708": "Paraíba do Sul",
    "3303807": "Paraty",
    "3303856": "Paty do Alferes",
    "3303906": "Petrópolis",
    "3303955": "Pinheiral",
    "3304003": "Piraí",
    "3304102": "Porciúncula",
    "3304110": "Porto Real",
    "3304128": "Quatis",
    "3304144": "Queimados",
    "3304151": "Quissamã",
    "3304201": "Resende",
    "3304300": "Rio Bonito",
    "3304409": "Rio Claro",
    "3304508": "Rio das Flores",
    "3304524": "Rio das Ostras",
    "3304557": "Rio de Janeiro",
    "3304607": "Santa Maria Madalena",
    "3304706": "Santo Antônio de Pádua",
    "3304755": "São Francisco de Itabapoana",
    "3304805": "São Fidélis",
    "3304904": "São Gonçalo",
    "3305000": "São João da Barra",
    "3305109": "São João de Meriti",
    "3305133": "São José de Ubá",
    "3305158": "São José do Vale do Rio Preto",
    "3305208": "São Pedro da Aldeia",
    "3305307": "São Sebastião do Alto",
    "3305406": "Sapucaia",
    "3305505": "Saquarema",
    "3305554": "Seropédica",
    "3305604": "Silva Jardim",
    "3305703": "Sumidouro",
    "3305752": "Tanguá",
    "3305802": "Teresópolis",
    "3305901": "Trajano de Moraes",
    "3306008": "Três Rios",
    "3306107": "Valença",
    "3306156": "Varre-Sai",
    "3306206": "Vassouras",
    "3306305": "Volta Redonda",
}


def normalizar_codigo_municipio(value: object) -> str | None:
    if value is None:
        return None
    codigo = str(value).strip()
    if codigo.endswith(".0"):
        codigo = codigo[:-2]
    if not codigo or not re.fullmatch(r"\d{7}", codigo):
        return None
    return codigo


def normalizar_escopo(value: object) -> str:
    if value is None:
        return ESCOPO_TODA_BASE
    raw = str(value).strip().casefold()
    if raw in {"", ESCOPO_TODA_BASE, "__all__", "todos", "toda", "toda-base"}:
        return ESCOPO_TODA_BASE
    return normalizar_codigo_municipio(value) or ""


def nome_municipio(codigo: str) -> str:
    return MUNICIPIOS_IBGE.get(codigo, f"Município {codigo}")


def uf_municipio(codigo: str) -> str:
    return {"28": "SE"}.get(codigo[:2], codigo[:2])


def catalogo_por_codigo(codigos: Iterable[str]) -> list[dict[str, str]]:
    return [
        {
            "codigo": codigo,
            "nome": nome_municipio(codigo),
            "uf": uf_municipio(codigo),
        }
        for codigo in sorted(set(codigos), key=lambda item: (nome_municipio(item), item))
    ]
