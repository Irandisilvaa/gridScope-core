import pandas as pd
from datetime import datetime
import sys
import os

# Ensure src is in path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
try:
    from utils import carregar_dados_cache, limpar_float
except ImportError:
    # Use mocks if utils not found (e.g. testing)
    carregar_dados_cache = lambda: (None, [])
    limpar_float = lambda x: 0.0

def get_report_data(substation_id: str):
    """
    Returns DYNAMIC data for the GridScope report using the actual database cache.
    """
    
    # 1. Load Real Data
    _, dados_lista = carregar_dados_cache()
    if not dados_lista:
        # Fallback if DB empty
        return {} # Should handle error gracefully
        
    df = pd.DataFrame(dados_lista)
    
    # 2. Find Selected Substation Logic
    # Handle matching by ID or Name
    # 'id_tecnico' is often the key, or we matched by 'subestacao' label in UI
    try:
        current_sub = df[df['id_tecnico'].astype(str) == str(substation_id)].iloc[0]
    except (IndexError, KeyError):
        # Fallback: try finding by name if ID failed? 
        # UI passed ID, assume it's valid. If not, pick first.
        current_sub = df.iloc[0]
        
    metricas = current_sub.get('metricas_rede', {})
    if isinstance(metricas, str): metricas = eval(metricas)
    
    dados_gd = current_sub.get('geracao_distribuida', {})
    if isinstance(dados_gd, str): dados_gd = eval(dados_gd)
    
    perfil = current_sub.get('perfil_consumo', {})
    if isinstance(perfil, str): perfil = eval(perfil)

    # 3. Calculate City Totals (Sum of all substations)
    total_clients_city = 0
    total_consumption_city = 0
    total_gd_power_city = 0
    total_gd_energy_city = 0
    
    ranking_list = []
    
    for _, row in df.iterrows():
        m = row.get('metricas_rede', {})
        if isinstance(m, str): m = eval(m)
        gd = row.get('geracao_distribuida', {})
        if isinstance(gd, str): gd = eval(gd)
        
        # Safe float conversion
        cons = limpar_float(m.get('consumo_anual_mwh', 0))
        cli = int(m.get('total_clientes', 0))
        pot = limpar_float(gd.get('potencia_total_kw', 0))
        
        total_consumption_city += cons
        total_clients_city += cli
        total_gd_power_city += pot
        
        # Logic for Ranking List
        criticidade = "NORMAL"
        # Dummy criticality logic based on load or GD penetration (customizable)
        penetration = ((pot * 4.5 * 365 / 1000) / (cons if cons > 0 else 1)) * 100
        if penetration > 20: criticidade = "CRÍTICO"
        elif penetration > 10: criticidade = "MÉDIO"
        
        ranking_list.append({
            "id": str(row.get('id_tecnico', '')),
            "name": str(row.get('subestacao', '')).split(' (')[0], # Clean name
            "capacity_mw": cons, # Using consumption as proxy for 'capacity' display if actual capacity not in data
            "clients": cli,
            "mmgd": int(pot),
            "criticality": criticidade,
            "sort_key": cons # Sort by consumption descending
        })

    # Sort Ranking
    ranking_list.sort(key=lambda x: x['sort_key'], reverse=True)
    # Add Position
    for idx, item in enumerate(ranking_list):
        item['position'] = idx + 1

    # ==========================================
    # BUILD REPORT DICTIONARY
    # ==========================================

    # A. Header
    header_info = {
        "substation_name": str(current_sub.get('subestacao', '')).split(' (')[0],
        "feeder_id": str(current_sub.get('id_tecnico', '0000')),
        "neighborhood": "Área Urbana", # Placeholder or fetch if available
        "covered_area_km2": "N/D", # Placeholder
        "total_clients": int(metricas.get('total_clientes', 0)),
        "report_date": datetime.now().strftime("%d/%m/%Y"),
        "report_number": f"{ranking_list.index(next(filter(lambda x: str(x['id']) == str(substation_id), ranking_list), {})) if ranking_list else 0:02d}-{datetime.now().month:02d}-{datetime.now().year}"
    }

    # B. Consumption Table
    # Extract from 'perfil_consumo'
    consumo_rows = []
    classes_interest = ["Residencial", "Comercial", "Industrial", "Poder Público", "Rural"]
    total_cons_sub = limpar_float(metricas.get('consumo_anual_mwh', 0))
    
    for cls in classes_interest:
        data_cls = perfil.get(cls, {})
        if isinstance(data_cls, str): data_cls = eval(data_cls)
        val = limpar_float(data_cls.get('consumo_anual_mwh', 0))
        pct = (val / total_cons_sub * 100) if total_cons_sub > 0 else 0
        
        consumo_rows.append({
            "class": cls,
            "energy_mwh": val,
            "percentage": pct
        })
    df_consumption = pd.DataFrame(consumo_rows)

    # C. GD Table
    # Extract from 'geracao_distribuida.detalhe_por_classe'
    gd_detalhe = dados_gd.get('detalhe_por_classe', {})
    if isinstance(gd_detalhe, str): gd_detalhe = eval(gd_detalhe)
    gd_rows = []
    
    for cls in classes_interest:
        pot_kw = limpar_float(gd_detalhe.get(cls, 0))
        # Note: 'count' per class might not be available in simple cache, using mock or total
        # We'll use total clients of that class if available, or just omit count logic
        cls_data = perfil.get(cls, {})
        if isinstance(cls_data, str): cls_data = eval(cls_data)
        count_cli = int(cls_data.get('qtd_clientes', 0))
        
        if pot_kw > 0:
            gd_rows.append({
                "class": cls,
                "power_kw": pot_kw,
                "count": count_cli
            })
    df_gd = pd.DataFrame(gd_rows)

    # D. Indicators (Comparison)
    sub_cons = total_cons_sub
    sub_cli = header_info['total_clients']
    sub_gd_kw = limpar_float(dados_gd.get('potencia_total_kw', 0))
    
    # Avoid zero division
    avg_cli = total_clients_city / len(df) if len(df) > 0 else 0
    avg_cons = total_consumption_city / len(df) if len(df) > 0 else 0
    avg_gd = total_gd_power_city / len(df) if len(df) > 0 else 0
    
    indicators_data = [
        {"category": "Escala", "indicator": "Clientes (UCs)", 
         "substation": f"{sub_cli}", "total_city": f"{total_clients_city}", 
         "pct_city": f"{(sub_cli/total_clients_city*100):.1f}%" if total_clients_city else "-", "avg_city": f"{avg_cli:.0f}"},
         
        {"category": "Consumo", "indicator": "Consumo mensal (MWh)", 
         "substation": f"{sub_cons:,.0f}".replace(',','.'), "total_city": f"{total_consumption_city:,.0f}".replace(',','.'), 
         "pct_city": f"{(sub_cons/total_consumption_city*100):.1f}%" if total_consumption_city else "-", "avg_city": f"{avg_cons:,.0f}".replace(',','.')},
         
         # ... Add other calculated KPIs similarly
         {"category": "GD", "indicator": "Potência GD (kW)", 
          "substation": f"{sub_gd_kw:,.0f}".replace(',','.'), "total_city": f"{total_gd_power_city:,.0f}".replace(',','.'),
          "pct_city": f"{(sub_gd_kw/total_gd_power_city*100):.1f}%" if total_gd_power_city else "-", "avg_city": f"{avg_gd:,.0f}".replace(',','.')}
    ]
    df_indicators = pd.DataFrame(indicators_data)

    # E. Ranking Table (Top 10 around the selected one, or just Top 10?)
    # Let's return Top 7 as per image
    df_ranking = pd.DataFrame(ranking_list[:10])

    return {
        "header": header_info,
        "consumption": df_consumption,
        "gd": df_gd,
        "indicators": df_indicators,
        "ranking": df_ranking
    }
