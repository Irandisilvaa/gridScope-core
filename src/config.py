DIR_SRC = os.path.dirname(os.path.abspath(__file__))
DIR_RAIZ = os.path.dirname(DIR_SRC)

NOME_GDB = "Energisa_SE_6587_2023-12-31_V11_20250701-0833.gdb"
NOME_GEOJSON = "subestacoes_logicas_aracaju.geojson"
NOME_JSON_MERCADO = "perfil_mercado_aracaju.json"

PATH_GDB = os.path.join(DIR_RAIZ, "dados", NOME_GDB)

PATH_GEOJSON = os.path.join(DIR_RAIZ, NOME_GEOJSON)

PATH_JSON_MERCADO = os.path.join(DIR_RAIZ, NOME_JSON_MERCADO)

CIDADE_ALVO = "Aracaju, Sergipe, Brazil"
CRS_PROJETADO = "EPSG:31984