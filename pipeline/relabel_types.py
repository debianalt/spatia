"""
Replace type_label with interpretable Spanish labels based on cluster profiles.
"""
import os, glob
import pandas as pd

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "output")

LABELS = {
    'environmental_risk': {
        1: 'Pendiente alta, zona baja',
        2: 'Alta deforestacion',
        3: 'Amplitud termica extrema',
        4: 'Zona protegida, bajo riesgo',
        5: 'Pendiente y perdida forestal',
    },
    'climate_comfort': {
        1: 'Calido y humedo',
        2: 'Fresco y seco',
        3: 'Noches frescas, estres moderado',
        4: 'Calido nocturno, lluvioso',
    },
    'green_capital': {
        1: 'Selva densa, dosel cerrado',
        2: 'Productividad media, dosel abierto',
        3: 'Vegetacion escasa o degradada',
    },
    'change_pressure': {
        1: 'Urbanizacion rapida',
        2: 'Zona estable, baja presion',
        3: 'Expansion periurbana',
        4: 'Frente de deforestacion',
        5: 'Expansion construida aislada',
    },
    'location_value': {
        1: 'Urbano bien conectado',
        2: 'Rural aislado, sin servicios',
        3: 'Accesible, topografia suave',
        4: 'Pendiente alta, cerca de ruta',
    },
    'agri_potential': {
        1: 'Suelo fertil, pH optimo',
        2: 'Humedo, arcilloso, fresco',
        3: 'Calido, seco, suelo pobre',
    },
    'forest_health': {
        1: 'Bosque productivo y transpirante',
        2: 'Bosque seco o defoliado',
        3: 'Tendencia NDVI negativa',
        4: 'Bosque estable, baja perdida',
    },
    'forestry_aptitude': {
        1: 'Lluvioso, suelo acido (pino)',
        2: 'Cerca de rutas, accesible',
        3: 'Seco, pendiente, alejado',
    },
    'isolation_index': {
        1: 'Conectado a Posadas',
        2: 'Terreno dificil, muy aislado',
        3: 'Facil acceso, baja friccion',
        4: 'Baja densidad vial',
    },
    'territorial_gap': {
        1: 'Sin cloacas ni agua de red',
        2: 'Aislado, sin agua de red',
        3: 'Urbano conectado',
        4: 'Alta pobreza, con servicios',
    },
    'health_access': {
        1: 'Denso, NBI moderado',
        2: 'Baja vulnerabilidad, rural cubierto',
        3: 'Urbano, cerca de hospital',
        4: 'Alta pobreza, lejos de salud',
        5: 'Baja cobertura sanitaria',
    },
    'education_gap': {
        1: 'Alta desercion y analfabetismo',
        2: 'Alta formacion universitaria',
        3: 'Conectado, solo primaria',
        4: 'Aislado, brecha profunda',
    },
    'land_use': {
        1: 'Paisaje abierto (pastura/cultivo)',
        2: 'Bosque dominante',
        3: 'Cuerpo de agua',
        4: 'Nucleo urbano',
    },
    'flood_risk': {
        1: 'Sin riesgo historico',
        2: 'Inundacion frecuente y actual',
        3: 'Recurrencia moderada',
        4: 'Exposicion leve',
    },
    'sociodemographic': {
        1: 'Clase media difusa',
        2: 'Alta pobreza y hacinamiento',
        3: 'Urbano conectado, no propietario',
    },
    'economic_activity': {
        1: 'Empleo activo, periferia',
        2: 'Centro economico urbano',
        3: 'Baja actividad, rural',
    },
    'accessibility': {
        1: 'Moderadamente aislado',
        2: 'Bien conectado',
        3: 'Extremadamente aislado',
        4: 'Lejos de ruta primaria',
    },
}

def relabel(path, labels):
    df = pd.read_parquet(path)
    if 'type' not in df.columns: return False
    df['type_label'] = df['type'].map(labels).fillna('Otro')
    df.to_parquet(path, index=False)
    return True

for aid, labels in LABELS.items():
    if aid == 'flood_risk':
        main = os.path.join(OUTPUT_DIR, 'hex_flood_risk.parquet')
        pattern = os.path.join(OUTPUT_DIR, 'flood_dpto', 'hex_flood_*.parquet')
    else:
        main = os.path.join(OUTPUT_DIR, f'sat_{aid}.parquet')
        pattern = os.path.join(OUTPUT_DIR, 'sat_dpto', f'sat_{aid}_*.parquet')

    if os.path.exists(main):
        relabel(main, labels)
    for f in glob.glob(pattern):
        relabel(f, labels)
    print(f'{aid}: OK')

print('Done')
