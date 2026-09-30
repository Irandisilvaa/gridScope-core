import requests
import os
import sys
import re

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

from config import ANEEL_API_HUB_URL, DISTRIBUIDORA_ALVO


def _selecionar_candidato(resultados):
    candidatos = []
    termos = DISTRIBUIDORA_ALVO.upper().split()

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
    return f"https://dadosabertos-aneel.opendata.arcgis.com/datasets/{id_arquivo}_0.geodatabase"

def verificar_aneel():
    print("Monitor ANEEL (somente consulta; não publica dados)")
    print(f"Alvo: '{DISTRIBUIDORA_ALVO}'")
    
    try:
        params = {"q": DISTRIBUIDORA_ALVO, "limit": 30}
        response = requests.get(ANEEL_API_HUB_URL, params=params, timeout=15)
        
        if response.status_code != 200:
            print(f"Erro API: {response.status_code}")
            return

        resultados = response.json().get('features', [])
        if not resultados:
            print("Nenhum resultado encontrado.")
            return

        print(f"Analisando {len(resultados)} itens...")

        vencedor = _selecionar_candidato(resultados)
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
        print("Nenhum arquivo foi baixado e nenhum dado operacional foi alterado.")
        return referencia

    except Exception as error:
        print(f"Erro na consulta ANEEL: {error}")
        return None

if __name__ == "__main__":
    verificar_aneel()
