"""
Generate professional multi-page PDF reports per department.

Academic/scientific style: white background, black text, monospace font,
detailed methodology, explicit sources, statistical distributions.

5-7 pages per report:
  1. Cover (branding, question, department, executive summary)
  2. Provincial context (ranking table, component comparison)
  3. Score distribution (histogram, boxplot, statistics)
  4-5. Component deep-dive (one section per component)
  6. Methodology (formula, normalisation, sources, limitations)
  7. References and credits

Usage:
  python pipeline/generate_dept_report.py
  python pipeline/generate_dept_report.py --only agri_potential --dept Capital
"""

import argparse
import json
import os
import sys
import time
from datetime import date

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
import numpy as np
import pandas as pd

from config import OUTPUT_DIR

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SRC_DATA_DIR = os.path.join(SCRIPT_DIR, "..", "src", "lib", "data")
REPORT_DIR = os.path.join(OUTPUT_DIR, "reports")

plt.rcParams.update({
    'font.family': 'monospace',
    'font.size': 9,
    'axes.titlesize': 11,
    'axes.labelsize': 9,
    'xtick.labelsize': 8,
    'ytick.labelsize': 8,
    'figure.facecolor': 'white',
    'axes.facecolor': 'white',
    'axes.edgecolor': '#cccccc',
    'axes.grid': True,
    'grid.color': '#eeeeee',
    'grid.linewidth': 0.5,
    'text.color': '#000000',
    'axes.labelcolor': '#333333',
    'xtick.color': '#666666',
    'ytick.color': '#666666',
})

ALL_ANALYSES = [
    "environmental_risk", "climate_comfort", "green_capital",
    "change_pressure", "location_value", "agri_potential",
    "forest_health", "forestry_aptitude", "isolation_index",
    "territorial_gap", "health_access", "education_gap", "land_use",
]

ANALYSIS_META = {
    "environmental_risk": {
        "title": "¿Es seguro vivir acá?",
        "subtitle": "Riesgo ambiental integrado",
        "components": {
            "c_fire": {"name": "Frecuencia de incendios", "source": "MODIS MCD64A1 (500m, 2019-2024)", "desc": "Fracción quemada promedio anual. Mayor valor indica mayor frecuencia de incendios forestales y pastizales.", "unit": "percentil"},
            "c_deforest": {"name": "Pérdida forestal acumulada", "source": "Hansen GFC v1.11 (30m, 2000-2024)", "desc": "Fracción de cobertura arbórea perdida desde el año 2000. Refleja presión de deforestación histórica.", "unit": "percentil"},
            "c_thermal_amp": {"name": "Amplitud térmica", "source": "MODIS LST MOD11A2 (1km, 2019-2024)", "desc": "Diferencia entre temperatura superficial diurna y nocturna promedio. Valores altos indican estrés térmico.", "unit": "percentil"},
            "c_slope": {"name": "Pendiente del terreno", "source": "FABDEM bare-earth DEM (30m)", "desc": "Pendiente media en grados. Terrenos empinados son más susceptibles a erosión y deslizamientos.", "unit": "percentil"},
            "c_hand": {"name": "Altura sobre drenaje (HAND)", "source": "MERIT Hydro (90m)", "desc": "Metros sobre el cauce más cercano (invertido). Menor HAND = mayor exposición a inundación.", "unit": "percentil (inv.)"},
        },
        "weights": "Incendios 25% + Deforestación 25% + Amplitud térmica 20% + Pendiente 15% + HAND invertido 15%",
        "interpretation_high": "presenta vulnerabilidad ambiental múltiple con alta frecuencia de incendios, suelos inestables y exposición a inundaciones",
        "interpretation_low": "tiene bajo riesgo ambiental con pocas perturbaciones históricas y topografía favorable",
    },
    "climate_comfort": {
        "title": "¿Es confortable el clima?",
        "subtitle": "Índice de confort térmico-hídrico",
        "components": {
            "c_heat_day": {"name": "Temperatura diurna", "source": "MODIS LST MOD11A2 (1km, 2019-2024)", "desc": "Temperatura superficial media diurna en °C (invertida). Menor calor = mayor confort.", "unit": "percentil (inv.)"},
            "c_heat_night": {"name": "Temperatura nocturna", "source": "MODIS LST MOD11A2 (1km, 2019-2024)", "desc": "Temperatura superficial media nocturna en °C (invertida). Noches frescas favorecen el descanso.", "unit": "percentil (inv.)"},
            "c_precipitation": {"name": "Precipitación anual", "source": "CHIRPS v2.0 (5km, 2019-2024)", "desc": "Precipitación total anual en mm. Valores >1200mm son favorables para actividades agropecuarias.", "unit": "percentil"},
            "c_frost": {"name": "Días de helada", "source": "ERA5-Land (9km, 2019-2024)", "desc": "Promedio anual de días con temperatura mínima <0°C (invertido). Menos heladas = mayor confort.", "unit": "percentil (inv.)"},
            "c_water_stress": {"name": "Balance hídrico (ET/PET)", "source": "MODIS MOD16A2GF (500m, 2019-2024)", "desc": "Ratio evapotranspiración real / potencial. Valores cercanos a 1 indican ausencia de estrés hídrico.", "unit": "percentil"},
        },
        "weights": "Calor diurno inv. 25% + Calor nocturno inv. 20% + Precipitación 20% + Heladas inv. 15% + ET/PET 20%",
        "interpretation_high": "presenta condiciones climáticas favorables con temperaturas moderadas, buena precipitación y bajo estrés hídrico",
        "interpretation_low": "presenta estrés climático con extremos térmicos, heladas frecuentes o déficit hídrico",
    },
    "green_capital": {
        "title": "¿Hay verde acá?",
        "subtitle": "Capital natural y cobertura vegetal",
        "components": {
            "c_ndvi": {"name": "Índice de vegetación (NDVI)", "source": "MODIS MOD13Q1 (250m, 2019-2024)", "desc": "NDVI medio anual. Proxy de verdor y productividad fotosintética. Valores 0.6-0.8 indican bosque denso.", "unit": "percentil"},
            "c_treecover": {"name": "Cobertura arbórea 2000", "source": "Hansen GFC (30m, baseline 2000)", "desc": "Porcentaje de cobertura arbórea en el año 2000. Referencia histórica pre-deforestación reciente.", "unit": "percentil"},
            "c_npp": {"name": "Productividad neta (NPP)", "source": "MODIS MOD17A3H (500m, 2019-2024)", "desc": "Productividad primaria neta en gC/m²/año. Mide la capacidad del ecosistema de fijar carbono.", "unit": "percentil"},
            "c_lai": {"name": "Índice de área foliar (LAI)", "source": "MODIS MOD15A2H (500m, 2019-2024)", "desc": "Superficie foliar por unidad de suelo. Mayor LAI indica dosel más denso y cerrado.", "unit": "percentil"},
            "c_vcf": {"name": "Fracción arbórea (VCF)", "source": "MODIS MOD44B (250m, 2019-2024)", "desc": "Porcentaje de cobertura arbórea continua. Complementa Hansen con datos temporales más recientes.", "unit": "percentil"},
        },
        "weights": "NDVI 25% + Cobertura arbórea 20% + NPP 20% + LAI 15% + VCF 20%",
        "interpretation_high": "conserva alto capital natural con bosque denso, alta productividad y cobertura arbórea íntegra",
        "interpretation_low": "presenta bajo capital natural con cobertura vegetal reducida y baja productividad ecosistémica",
    },
    "change_pressure": {
        "title": "¿Se está transformando esta zona?",
        "subtitle": "Presión de cambio territorial",
        "components": {
            "c_viirs_trend": {"name": "Tendencia de luces nocturnas", "source": "VIIRS DNB (500m, 2016-2025)", "desc": "Pendiente de regresión lineal de radiancia nocturna. Tendencia positiva indica urbanización o actividad creciente.", "unit": "percentil"},
            "c_ghsl_change": {"name": "Expansión de superficie construida", "source": "GHSL-BUILT (100m, 2000 vs 2020)", "desc": "Diferencia en fracción construida entre 2000 y 2020. Mayor valor indica mayor expansión urbana.", "unit": "percentil"},
            "c_hansen_loss": {"name": "Pérdida forestal total", "source": "Hansen GFC v1.11 (30m, 2000-2024)", "desc": "Fracción acumulada de cobertura arbórea perdida. Indica presión sobre el bosque nativo.", "unit": "percentil"},
            "c_ndvi_trend": {"name": "Tendencia de verdor (NDVI)", "source": "MODIS MOD13Q1 (250m, 2019-2024)", "desc": "Pendiente de regresión del NDVI (invertida). Tendencia negativa = pérdida de vegetación = más transformación.", "unit": "percentil (inv.)"},
            "c_fire_count": {"name": "Actividad de fuego", "source": "MODIS MCD64A1 (500m, 2019-2024)", "desc": "Conteo acumulado de eventos de quema. Mayor actividad de fuego indica perturbación intensa.", "unit": "percentil"},
        },
        "weights": "Luces nocturnas 25% + Expansión urbana 25% + Pérdida forestal 20% + NDVI inv. 15% + Fuego 15%",
        "interpretation_high": "está en plena transformación con urbanización creciente, pérdida de cobertura vegetal y alta perturbación",
        "interpretation_low": "permanece estable con pocas señales de transformación territorial reciente",
    },
    "location_value": {
        "title": "¿Cuánto vale esta localización?",
        "subtitle": "Valor posicional del territorio",
        "components": {
            "c_access_20k": {"name": "Acceso a ciudad de 20.000 hab.", "source": "Nelson et al. 2019 (1km)", "desc": "Tiempo de viaje motorizado a la ciudad más cercana de ≥20k habitantes (invertido). Menor tiempo = mejor posición.", "unit": "percentil (inv.)"},
            "c_healthcare": {"name": "Acceso a servicios de salud", "source": "Oxford MAP 2019 (1km)", "desc": "Tiempo de viaje al centro de salud más cercano (invertido). Fundamental para habitabilidad.", "unit": "percentil (inv.)"},
            "c_nightlights": {"name": "Actividad económica nocturna", "source": "VIIRS DNB (500m, 2022-2024)", "desc": "Radiancia media nocturna como proxy de actividad económica y densidad de infraestructura.", "unit": "percentil"},
            "c_slope": {"name": "Pendiente del terreno", "source": "FABDEM (30m)", "desc": "Pendiente media en grados (invertida). Terrenos planos son más aptos para construcción y producción.", "unit": "percentil (inv.)"},
            "c_road_dist": {"name": "Distancia a ruta principal", "source": "OpenStreetMap 2024", "desc": "Distancia euclidiana a la ruta primaria más cercana (invertida). Menor distancia = mejor logística.", "unit": "percentil (inv.)"},
        },
        "weights": "Acceso 20k inv. 25% + Salud inv. 20% + VIIRS 25% + Pendiente inv. 15% + Ruta inv. 15%",
        "interpretation_high": "tiene excelente posición territorial: buena accesibilidad, servicios cercanos y actividad económica visible",
        "interpretation_low": "está en posición territorial desfavorable: lejos de centros urbanos, servicios y con restricciones topográficas",
    },
    "agri_potential": {
        "title": "¿Qué potencial agrícola tiene?",
        "subtitle": "Aptitud agroclimática del suelo",
        "components": {
            "c_soc": {"name": "Carbono orgánico del suelo", "source": "SoilGrids ISRIC (250m, 0-5cm)", "desc": "Contenido de materia orgánica. Mayor carbono = mayor fertilidad, retención hídrica y actividad biológica.", "unit": "percentil"},
            "c_ph_optimal": {"name": "pH óptimo", "source": "SoilGrids ISRIC (250m, 0-5cm)", "desc": "Distancia al pH óptimo (6.25). Valores cercanos a 1 indican pH ideal para la mayoría de cultivos.", "unit": "percentil"},
            "c_clay": {"name": "Contenido de arcilla", "source": "SoilGrids ISRIC (250m, 0-5cm)", "desc": "Porcentaje de arcilla. Mayor arcilla mejora retención de nutrientes y agua, pero dificulta drenaje.", "unit": "percentil"},
            "c_precipitation": {"name": "Precipitación anual", "source": "CHIRPS v2.0 (5km, 2019-2024)", "desc": "Lluvia total anual en mm. >1200mm es suficiente para cultivos sin riego en Misiones.", "unit": "percentil"},
            "c_gdd": {"name": "Grados-día de crecimiento", "source": "ERA5-Land (9km, 2019-2024)", "desc": "Calor acumulado sobre base 10°C. Mayor GDD permite más ciclos de cultivo y mayor productividad.", "unit": "percentil"},
            "c_slope": {"name": "Pendiente del terreno", "source": "FABDEM (30m)", "desc": "Pendiente media en grados (invertida). <15° permite mecanización; >25° requiere terrazas o es no apta.", "unit": "percentil (inv.)"},
        },
        "weights": "Carbono orgánico 20% + pH óptimo 15% + Arcilla 15% + Precipitación 20% + GDD 15% + Pendiente inv. 15%",
        "interpretation_high": "presenta condiciones edafoclimáticas óptimas para producción agropecuaria: suelos fértiles, lluvia suficiente y terreno manejable",
        "interpretation_low": "tiene limitaciones para la producción agrícola: suelos pobres, pendiente excesiva o déficit climático",
    },
    "forest_health": {
        "title": "¿Cuán sano está el bosque?",
        "subtitle": "Integridad y salud forestal",
        "components": {
            "c_ndvi_trend": {"name": "Tendencia de verdor (5 años)", "source": "MODIS MOD13Q1 (250m, 2019-2024)", "desc": "Pendiente de regresión lineal del NDVI. Tendencia positiva indica bosque en recuperación; negativa indica degradación.", "unit": "percentil"},
            "c_loss_ratio": {"name": "Ratio pérdida/cobertura", "source": "Hansen GFC (30m)", "desc": "Pérdida acumulada dividida por cobertura original 2000 (invertida). Valores altos indican bosque muy degradado.", "unit": "percentil (inv.)"},
            "c_fire": {"name": "Frecuencia de incendios", "source": "MODIS MCD64A1 (500m, 2019-2024)", "desc": "Fracción quemada promedio (invertida). Menos fuego = bosque más saludable.", "unit": "percentil (inv.)"},
            "c_gpp": {"name": "Productividad primaria (GPP)", "source": "MODIS MOD17A2H (500m, 2019-2024)", "desc": "Productividad bruta en gC/m²/año. Mayor GPP indica bosque más activo fotosintéticamente.", "unit": "percentil"},
            "c_et": {"name": "Evapotranspiración", "source": "MODIS MOD16A2GF (500m, 2019-2024)", "desc": "ET real en mm/año. Mayor transpiración indica bosque activo con dosel cerrado.", "unit": "percentil"},
        },
        "weights": "Tendencia NDVI 25% + Ratio pérdida inv. 25% + Fuego inv. 20% + GPP 15% + ET 15%",
        "interpretation_high": "conserva bosque íntegro con tendencia estable, baja perturbación y alta productividad",
        "interpretation_low": "presenta bosque degradado con pérdida de cobertura, incendios recurrentes o productividad en declive",
    },
    "forestry_aptitude": {
        "title": "¿Es rentable forestar acá?",
        "subtitle": "Aptitud para plantaciones forestales comerciales",
        "components": {
            "c_ph": {"name": "pH del suelo (ácido = mejor)", "source": "SoilGrids ISRIC (250m, 0-5cm)", "desc": "pH del suelo (invertido). Pinus y Eucalyptus prefieren suelos ácidos (pH 4.5-5.5).", "unit": "percentil (inv.)"},
            "c_clay": {"name": "Contenido de arcilla (menos = mejor)", "source": "SoilGrids ISRIC (250m, 0-5cm)", "desc": "Porcentaje de arcilla (invertido). Suelos arenosos con buen drenaje son preferidos para pinos.", "unit": "percentil (inv.)"},
            "c_precipitation": {"name": "Precipitación anual", "source": "CHIRPS v2.0 (5km, 2019-2024)", "desc": "Lluvia total anual. >1200mm es necesario para crecimiento forestal comercial en Misiones.", "unit": "percentil"},
            "c_slope": {"name": "Pendiente del terreno", "source": "FABDEM (30m)", "desc": "Pendiente media (invertida). <15° permite cosecha mecanizada y reduce costos de extracción.", "unit": "percentil (inv.)"},
            "c_road_dist": {"name": "Distancia a ruta principal", "source": "OpenStreetMap 2024", "desc": "Distancia a ruta primaria (invertida). Menor distancia = menor costo de flete de rollizos.", "unit": "percentil (inv.)"},
            "c_access_50k": {"name": "Acceso a ciudad de 50.000 hab.", "source": "Nelson et al. 2019 (1km)", "desc": "Tiempo de viaje a ciudad ≥50k (invertido). Cercanía a aserraderos y mercados reduce costos.", "unit": "percentil (inv.)"},
        },
        "weights": "pH inv. 15% + Arcilla inv. 10% + Precipitación 25% + Pendiente inv. 20% + Ruta inv. 15% + Acceso 50k inv. 15%",
        "interpretation_high": "reúne condiciones óptimas para forestación comercial: suelo ácido, lluvia abundante, terreno mecanizable y buena logística",
        "interpretation_low": "presenta limitaciones para forestación: suelo inadecuado, pendiente excesiva o aislamiento logístico",
    },
    "isolation_index": {
        "title": "¿Cuán aislado está este lugar?",
        "subtitle": "Índice de aislamiento territorial",
        "components": {
            "c_access_100k": {"name": "Tiempo a ciudad de 100.000 hab.", "source": "Nelson et al. 2019 (1km)", "desc": "Minutos de viaje motorizado a la ciudad más cercana de ≥100k habitantes. Mayor tiempo = mayor aislamiento.", "unit": "percentil"},
            "c_travel_posadas": {"name": "Tiempo a Posadas", "source": "Superficie de fricción custom (1km)", "desc": "Minutos de viaje motorizado a la capital provincial. Determinante para acceso a servicios especializados.", "unit": "percentil"},
            "c_road_density": {"name": "Densidad vial", "source": "OpenStreetMap 2024", "desc": "Kilómetros de ruta por km² (invertida). Menor densidad = menor conectividad = mayor aislamiento.", "unit": "percentil (inv.)"},
            "c_nightlights": {"name": "Actividad nocturna", "source": "VIIRS DNB (500m, 2022-2024)", "desc": "Radiancia nocturna (invertida). Ausencia de luces indica baja densidad poblacional e infraestructura.", "unit": "percentil (inv.)"},
            "c_friction": {"name": "Fricción de desplazamiento", "source": "Oxford MAP 2019 (1km)", "desc": "Costo de atravesar cada píxel en transporte motorizado. Mayor fricción = terreno más difícil de transitar.", "unit": "percentil"},
        },
        "weights": "Acceso 100k 25% + Posadas 25% + Densidad vial inv. 20% + VIIRS inv. 15% + Fricción 15%",
        "interpretation_high": "se encuentra altamente aislado: lejos de centros urbanos, con baja conectividad vial y difícil acceso",
        "interpretation_low": "tiene buena conectividad territorial con acceso rápido a centros urbanos y servicios",
    },
    "territorial_gap": {
        "title": "¿Dónde hay mayor desigualdad?",
        "subtitle": "Brecha territorial entre economía y servicios",
        "components": {
            "c_nightlights": {"name": "Actividad económica nocturna", "source": "VIIRS DNB (500m, 2022-2024)", "desc": "Radiancia nocturna (invertida en el score). Zonas con luces pero sin servicios representan la mayor brecha.", "unit": "percentil (inv.)"},
            "c_nbi": {"name": "Necesidades básicas insatisfechas", "source": "INDEC Censo 2022 (radio censal)", "desc": "Porcentaje de hogares con NBI. Indicador estructural de pobreza multidimensional.", "unit": "percentil"},
            "c_sin_agua": {"name": "Sin red de agua", "source": "INDEC Censo 2022 (radio censal)", "desc": "Porcentaje de hogares sin acceso a red pública de agua potable.", "unit": "percentil"},
            "c_sin_cloacas": {"name": "Sin red de cloacas", "source": "INDEC Censo 2022 (radio censal)", "desc": "Porcentaje de hogares sin conexión a red cloacal. Indicador de déficit sanitario.", "unit": "percentil"},
            "c_isolation": {"name": "Aislamiento (tiempo a ciudad)", "source": "Nelson et al. 2019 (1km)", "desc": "Tiempo de viaje a ciudad de ≥20k habitantes. Amplifica el efecto de los déficits de servicios.", "unit": "percentil"},
        },
        "weights": "VIIRS inv. 15% + NBI 25% + Sin agua 25% + Sin cloacas 20% + Aislamiento 15%",
        "interpretation_high": "presenta alta brecha territorial: la actividad económica no se traduce en acceso a servicios básicos",
        "interpretation_low": "tiene bajo nivel de brecha: los servicios básicos están alineados con el nivel de actividad económica",
    },
    "health_access": {
        "title": "¿Dónde faltan servicios de salud?",
        "subtitle": "Brecha de acceso a servicios sanitarios",
        "components": {
            "c_healthcare_time": {"name": "Tiempo motorizado a salud", "source": "Oxford MAP 2019 (1km)", "desc": "Minutos de viaje motorizado al centro de salud más cercano.", "unit": "percentil"},
            "c_healthcare_walk": {"name": "Tiempo a pie a salud", "source": "Oxford MAP 2019 (1km)", "desc": "Minutos de caminata al centro de salud más cercano.", "unit": "percentil"},
            "c_pop_density": {"name": "Densidad poblacional", "source": "INDEC Censo 2022 (radio censal)", "desc": "Habitantes por km². Mayor densidad = mayor demanda de servicios.", "unit": "percentil"},
            "c_health_coverage": {"name": "Cobertura de salud", "source": "INDEC Censo 2022 (radio censal)", "desc": "Porcentaje de población con cobertura de salud (invertido). Menor cobertura = mayor brecha.", "unit": "percentil (inv.)"},
            "c_nbi": {"name": "NBI", "source": "INDEC Censo 2022 (radio censal)", "desc": "Porcentaje de hogares con necesidades básicas insatisfechas. Vulnerabilidad social amplifica déficit sanitario.", "unit": "percentil"},
        },
        "weights": "Tiempo motor 30% + Tiempo a pie 20% + Densidad 15% + Cobertura inv. 15% + NBI 20%",
        "interpretation_high": "presenta alto déficit de acceso a salud: lejanía a centros, alta demanda y baja cobertura",
        "interpretation_low": "tiene buen acceso a servicios de salud con cobertura adecuada y cercanía a centros sanitarios",
    },
    "education_gap": {
        "title": "¿Dónde hay mayor brecha educativa?",
        "subtitle": "Déficit educativo territorial",
        "components": {
            "c_no_instruction": {"name": "Sin instrucción", "source": "INDEC Censo 2022 (radio censal)", "desc": "Porcentaje de población sin ningún nivel educativo completado.", "unit": "percentil"},
            "c_dropout_13_18": {"name": "Deserción 13-18 años", "source": "INDEC Censo 2022 (radio censal)", "desc": "Tasa de inasistencia escolar en el rango 13-18 años.", "unit": "percentil"},
            "c_only_primary": {"name": "Solo primaria completa", "source": "INDEC Censo 2022 (radio censal)", "desc": "Porcentaje de población cuyo máximo nivel es primario completo.", "unit": "percentil"},
            "c_university": {"name": "Universitarios", "source": "INDEC Censo 2022 (radio censal)", "desc": "Porcentaje con título universitario (invertido). Más universitarios = menor brecha.", "unit": "percentil (inv.)"},
            "c_isolation": {"name": "Aislamiento", "source": "Nelson et al. 2019 (1km)", "desc": "Tiempo de viaje a ciudad de ≥20k habitantes. Aislamiento dificulta acceso a educación superior.", "unit": "percentil"},
        },
        "weights": "Sin instrucción 25% + Deserción 25% + Solo primaria 20% + Universitarios inv. 15% + Aislamiento 15%",
        "interpretation_high": "presenta alta brecha educativa con deserción, bajo nivel máximo y aislamiento que limita el acceso",
        "interpretation_low": "tiene indicadores educativos favorables con baja deserción y acceso a formación superior",
    },
    "land_use": {
        "title": "¿Qué uso de suelo tiene esta zona?",
        "subtitle": "Cobertura y diversidad de uso del suelo",
        "components": {
            "frac_trees": {"name": "Bosque", "source": "Google Dynamic World v1 (Sentinel-2, 10m, 2024)", "desc": "Fracción del hexágono cubierta por árboles. Incluye bosque nativo y plantaciones.", "unit": "fracción (0-1)"},
            "frac_crops": {"name": "Cultivos", "source": "Google Dynamic World v1 (Sentinel-2, 10m, 2024)", "desc": "Fracción cubierta por cultivos agrícolas activos.", "unit": "fracción (0-1)"},
            "frac_built": {"name": "Construido", "source": "Google Dynamic World v1 (Sentinel-2, 10m, 2024)", "desc": "Fracción cubierta por superficies construidas (urbano, industrial, infraestructura).", "unit": "fracción (0-1)"},
            "frac_grass": {"name": "Pasturas/pasto", "source": "Google Dynamic World v1 (Sentinel-2, 10m, 2024)", "desc": "Fracción cubierta por pastizales y pasturas.", "unit": "fracción (0-1)"},
            "frac_water": {"name": "Agua", "source": "Google Dynamic World v1 (Sentinel-2, 10m, 2024)", "desc": "Fracción cubierta por cuerpos de agua permanentes.", "unit": "fracción (0-1)"},
            "frac_shrub": {"name": "Arbustos", "source": "Google Dynamic World v1 (Sentinel-2, 10m, 2024)", "desc": "Fracción cubierta por vegetación arbustiva baja.", "unit": "fracción (0-1)"},
        },
        "weights": "Score = índice de diversidad de Shannon normalizado sobre 9 clases LULC × 100",
        "interpretation_high": "presenta alta diversidad de uso del suelo — mosaico agro-forestal con múltiples actividades coexistiendo",
        "interpretation_low": "presenta uso homogéneo — dominado por una sola cobertura (bosque denso o monocultivo)",
    },
}

# Analyses where each hexagon has its own pixel-derived value (zonal stats),
# as opposed to radio-level analyses where hexagons inherit radio censal values.
PIXEL_LEVEL_ANALYSES = {
    "environmental_risk", "climate_comfort", "green_capital",
    "change_pressure", "agri_potential", "forest_health", "land_use",
}


def safe_filename(dpto: str) -> str:
    return (dpto.lower().replace(" ", "_")
            .replace("á", "a").replace("é", "e").replace("í", "i")
            .replace("ó", "o").replace("ú", "u").replace("ñ", "n").replace("ü", "u"))


def add_header(fig, text, y=0.96, size=14, weight='bold'):
    fig.text(0.5, y, text, ha='center', va='top', fontsize=size, fontweight=weight, color='#000000')


def add_footer(fig):
    fig.text(0.5, 0.02, f"Generado por Spatia — spatia.ar  |  {date.today().strftime('%d/%m/%Y')}",
             ha='center', va='bottom', fontsize=7, color='#999999')
    fig.text(0.05, 0.02, "spatia.ar", ha='left', va='bottom', fontsize=7, fontweight='bold', color='#999999')


def new_page(pdf, title=None):
    fig = plt.figure(figsize=(8.5, 11))
    fig.patch.set_facecolor('white')
    if title:
        add_header(fig, title, y=0.96, size=12)
    add_footer(fig)
    return fig


def generate_report(analysis_id, dept_name, dept_df, prov_df, summary, output_path):
    meta = ANALYSIS_META[analysis_id]
    component_cols = [c for c in dept_df.columns if c.startswith("c_")]
    dept_avg = dept_df["score"].mean()
    prov_avg = prov_df["score"].mean()
    n_hex = len(dept_df)

    # Provincial rank
    dept_avgs = [(d["dpto"], d["avg_score"]) for d in summary["departments"]]
    dept_avgs.sort(key=lambda x: x[1], reverse=True)
    rank = next((i + 1 for i, (name, _) in enumerate(dept_avgs) if name == dept_name), 0)

    with PdfPages(output_path) as pdf:

        # ══════ PAGE 1: COVER ══════
        fig = new_page(pdf)
        fig.text(0.5, 0.88, "spatia.ar", ha='center', fontsize=24, fontweight='bold', color='#000000')
        fig.text(0.5, 0.84, "Inteligencia Territorial para Misiones", ha='center', fontsize=10, color='#666666')
        fig.text(0.5, 0.74, meta["title"], ha='center', fontsize=18, fontweight='bold', color='#000000')
        fig.text(0.5, 0.70, meta["subtitle"], ha='center', fontsize=11, color='#666666')
        fig.text(0.5, 0.62, dept_name, ha='center', fontsize=22, fontweight='bold', color='#333333')
        fig.text(0.5, 0.58, date.today().strftime('%d de %B de %Y'), ha='center', fontsize=10, color='#999999')

        # Executive summary
        if dept_avg >= 60:
            interp = meta["interpretation_high"]
        elif dept_avg <= 40:
            interp = meta["interpretation_low"]
        else:
            interp = "presenta valores intermedios en este indicador, con heterogeneidad interna significativa"

        summary_text = (
            f"Resumen ejecutivo\n\n"
            f"El departamento {dept_name} obtiene un score promedio de {dept_avg:.1f} sobre 100 "
            f"en el análisis \"{meta['title']}\", ubicándose en la posición {rank} de 17 departamentos "
            f"de la provincia de Misiones. El promedio provincial es {prov_avg:.1f}. "
            f"Con {n_hex:,} hexágonos H3 (resolución 9, ~0.1 km² cada uno), "
            f"{dept_name} {interp}.\n\n"
            f"Este informe presenta la distribución espacial del score, el análisis detallado "
            f"de cada componente, la comparación con el promedio provincial, y la metodología "
            f"completa de cálculo con fuentes de datos explícitas."
        )
        fig.text(0.1, 0.48, summary_text, ha='left', va='top', fontsize=9,
                 color='#333333', wrap=True, transform=fig.transFigure,
                 fontfamily='monospace', linespacing=1.6,
                 bbox=dict(boxstyle='square,pad=0.5', facecolor='#f5f5f5', edgecolor='#cccccc'))
        pdf.savefig(fig); plt.close(fig)

        # ══════ PAGE 2: PROVINCIAL CONTEXT ══════
        fig = new_page(pdf, f"Contexto provincial — {meta['title']}")

        # Ranking table
        ax_table = fig.add_axes([0.08, 0.55, 0.84, 0.35])
        ax_table.axis('off')
        table_data = []
        for i, (name, score) in enumerate(dept_avgs):
            marker = "  ►" if name == dept_name else "   "
            table_data.append([f"{i+1}", f"{marker} {name}", f"{score:.1f}"])

        table = ax_table.table(cellText=table_data, colLabels=["#", "Departamento", "Score"],
                              loc='center', cellLoc='left')
        table.auto_set_font_size(False)
        table.set_fontsize(8)
        table.scale(1, 1.3)
        for key, cell in table.get_celld().items():
            cell.set_edgecolor('#cccccc')
            cell.set_linewidth(0.5)
            if key[0] == 0:
                cell.set_facecolor('#e0e0e0')
                cell.set_text_props(fontweight='bold')
            elif table_data[key[0]-1][1].strip().startswith("►"):
                cell.set_facecolor('#f0f0f0')
                cell.set_text_props(fontweight='bold')
            else:
                cell.set_facecolor('white')

        # Component comparison bars
        if component_cols:
            ax_comp = fig.add_axes([0.12, 0.08, 0.76, 0.38])
            dept_means = [dept_df[c].mean() for c in component_cols]
            prov_means = [prov_df[c].mean() for c in component_cols]
            labels = [meta["components"].get(c, {}).get("name", c.replace("c_", "")) for c in component_cols]

            x = np.arange(len(component_cols))
            width = 0.35
            ax_comp.barh(x - width/2, dept_means, width, label=dept_name, color='#333333')
            ax_comp.barh(x + width/2, prov_means, width, label='Provincia', color='#bbbbbb')
            ax_comp.set_yticks(x)
            ax_comp.set_yticklabels(labels, fontsize=7)
            ax_comp.set_xlabel('Percentil (0-100)')
            ax_comp.set_xlim(0, 100)
            ax_comp.set_title(f'Componentes: {dept_name} vs Provincia', fontsize=10)
            ax_comp.legend(fontsize=8, framealpha=0.9)

        pdf.savefig(fig); plt.close(fig)

        # ══════ PAGE 3: DISTRIBUTION ══════
        fig = new_page(pdf, f"Distribución de scores — {dept_name}")

        scores = dept_df["score"].dropna()
        prov_scores = prov_df["score"].dropna()

        # Histogram
        ax_hist = fig.add_axes([0.12, 0.55, 0.76, 0.30])
        ax_hist.hist(scores, bins=25, range=(0, 100), color='#555555', edgecolor='white', alpha=0.9)
        ax_hist.axvline(dept_avg, color='#000000', linewidth=2, linestyle='--', label=f'{dept_name}: {dept_avg:.1f}')
        ax_hist.axvline(prov_avg, color='#999999', linewidth=1.5, linestyle=':', label=f'Provincia: {prov_avg:.1f}')
        ax_hist.set_xlabel('Score')
        ax_hist.set_ylabel('Hexágonos')
        ax_hist.set_title('Distribución de scores en el departamento')
        ax_hist.legend(fontsize=8)

        # Box plot comparison
        ax_box = fig.add_axes([0.12, 0.28, 0.76, 0.18])
        bp = ax_box.boxplot([scores, prov_scores], vert=False, labels=[dept_name, 'Provincia'],
                           widths=0.6, patch_artist=True,
                           boxprops=dict(facecolor='#e0e0e0', edgecolor='#666666'),
                           medianprops=dict(color='#000000', linewidth=2))
        ax_box.set_xlabel('Score')
        ax_box.set_title('Comparación de distribución')

        # Statistics table
        stats = {
            'Media': f"{scores.mean():.1f}",
            'Mediana': f"{scores.median():.1f}",
            'Desv. est.': f"{scores.std():.1f}",
            'P10': f"{scores.quantile(0.10):.1f}",
            'P25': f"{scores.quantile(0.25):.1f}",
            'P75': f"{scores.quantile(0.75):.1f}",
            'P90': f"{scores.quantile(0.90):.1f}",
            'Mínimo': f"{scores.min():.1f}",
            'Máximo': f"{scores.max():.1f}",
        }
        stats_text = "Estadísticas descriptivas\n\n" + "\n".join(f"  {k:12s}  {v}" for k, v in stats.items())
        fig.text(0.12, 0.22, stats_text, fontsize=8, fontfamily='monospace', va='top',
                 bbox=dict(boxstyle='square,pad=0.5', facecolor='#f8f8f8', edgecolor='#cccccc'))

        pdf.savefig(fig); plt.close(fig)

        # ══════ PAGES 4-5: COMPONENT DEEP-DIVE ══════
        for comp_col in component_cols:
            comp_meta = meta["components"].get(comp_col, {})
            comp_name = comp_meta.get("name", comp_col)
            comp_source = comp_meta.get("source", "No especificada")
            comp_desc = comp_meta.get("desc", "")
            comp_unit = comp_meta.get("unit", "percentil")

            fig = new_page(pdf, f"Componente: {comp_name}")

            comp_dept = dept_df[comp_col].dropna()
            comp_prov = prov_df[comp_col].dropna()

            # Description
            desc_text = (
                f"{comp_desc}\n\n"
                f"Fuente: {comp_source}\n"
                f"Unidad: {comp_unit}\n"
                f"Promedio departamental: {comp_dept.mean():.1f}  |  Provincial: {comp_prov.mean():.1f}"
            )
            fig.text(0.1, 0.88, desc_text, fontsize=9, va='top', fontfamily='monospace',
                     color='#333333', linespacing=1.5,
                     bbox=dict(boxstyle='square,pad=0.5', facecolor='#f8f8f8', edgecolor='#cccccc'))

            # Histogram
            ax = fig.add_axes([0.12, 0.35, 0.76, 0.30])
            ax.hist(comp_dept, bins=25, range=(0, 100), color='#555555', edgecolor='white', alpha=0.9)
            ax.axvline(comp_dept.mean(), color='#000000', linewidth=2, linestyle='--',
                      label=f'{dept_name}: {comp_dept.mean():.1f}')
            ax.axvline(comp_prov.mean(), color='#999999', linewidth=1.5, linestyle=':',
                      label=f'Provincia: {comp_prov.mean():.1f}')
            ax.set_xlabel(f'{comp_name} (percentil)')
            ax.set_ylabel('Hexágonos')
            ax.set_title(f'Distribución de {comp_name}')
            ax.legend(fontsize=8)

            # Mini stats
            mini_stats = (
                f"  Media: {comp_dept.mean():.1f}   Mediana: {comp_dept.median():.1f}   "
                f"Desv: {comp_dept.std():.1f}   P10: {comp_dept.quantile(0.1):.1f}   "
                f"P90: {comp_dept.quantile(0.9):.1f}"
            )
            fig.text(0.12, 0.28, mini_stats, fontsize=7, fontfamily='monospace', color='#666666')

            pdf.savefig(fig); plt.close(fig)

        # ══════ PAGE 6: METHODOLOGY ══════
        fig = new_page(pdf, "Metodología")

        is_pixel = analysis_id in PIXEL_LEVEL_ANALYSES

        if is_pixel:
            norm_text = (
                f"de {len(component_cols)} componentes, cada uno normalizado mediante percentil\n"
                f"rank (0-100) sobre los {summary['province']['total_hexes']:,} hexágonos de la provincia."
            )
            grid_text = (
                f"Grilla espacial:\n"
                f"  Se utiliza el sistema H3 de Uber a resolución 9, que genera\n"
                f"  hexágonos regulares de ~0.105 km² (~174 m de lado). Misiones\n"
                f"  contiene {summary['province']['total_hexes']:,} hexágonos en esta resolución.\n"
                f"  Cada hexágono recibe el promedio de los píxeles satelitales\n"
                f"  contenidos en su superficie mediante estadísticas zonales\n"
                f"  (zonal stats). Cada hexágono tiene un valor único."
            )
            limit_text = (
                f"Limitaciones:\n"
                f"  • Las fuentes satelitales tienen resoluciones de 30m a 9km\n"
                f"    según el sensor. Varios píxeles se promedian dentro de cada\n"
                f"    hexágono; la resolución efectiva es sub-hexagonal.\n"
                f"  • Baseline satelital construido con datos 2019-2024. Representa\n"
                f"    condiciones medias del período, no el estado actual. Se\n"
                f"    recalcula cuando hay nuevas versiones de los datasets fuente.\n"
                f"  • Para decisiones a escala parcela, verificar con datos\n"
                f"    de campo y relevamiento in situ."
            )
        else:
            norm_text = (
                f"de {len(component_cols)} componentes, cada uno normalizado mediante percentil\n"
                f"rank (0-100) sobre los 2.012 radios censales de la provincia."
            )
            grid_text = (
                f"Grilla espacial:\n"
                f"  Se utiliza el sistema H3 de Uber a resolución 9, que genera\n"
                f"  hexágonos regulares de ~0.105 km² (~174 m de lado). Misiones\n"
                f"  contiene {summary['province']['total_hexes']:,} hexágonos en esta resolución.\n"
                f"  Cada hexágono hereda los valores de su radio censal contenedor\n"
                f"  mediante un crosswalk areal ponderado por superficie."
            )
            limit_text = (
                f"Limitaciones:\n"
                f"  • Los datos de origen son a nivel radio censal (2.012 unidades).\n"
                f"    Hexágonos dentro del mismo radio comparten valores idénticos.\n"
                f"    La resolución efectiva es la del radio censal.\n"
                f"  • Baseline censal construido con datos del Censo 2022 y fuentes\n"
                f"    de accesibilidad (Nelson 2019, Oxford MAP 2019). Representa\n"
                f"    un corte temporal fijo. Se actualizará con el próximo censo.\n"
                f"  • Para decisiones a escala parcela, verificar con datos\n"
                f"    de campo y relevamiento in situ."
            )

        method_text = (
            f"Cálculo del score compuesto\n\n"
            f"El score de \"{meta['title']}\" se construye como un promedio ponderado\n"
            f"{norm_text}\n\n"
            f"Fórmula:\n"
            f"  Score = {meta['weights']}\n\n"
            f"Normalización:\n"
            f"  Cada componente se transforma a su rango percentil provincial.\n"
            f"  Para componentes invertidos (ej. pendiente, distancia), el valor\n"
            f"  se niega antes del ranking, de modo que menor valor original\n"
            f"  produce mayor score.\n\n"
            f"{grid_text}\n\n"
            f"{limit_text}"
        )
        fig.text(0.08, 0.88, method_text, fontsize=8, va='top', fontfamily='monospace',
                 color='#333333', linespacing=1.5)
        pdf.savefig(fig); plt.close(fig)

        # ══════ PAGE 7: SOURCES ══════
        fig = new_page(pdf, "Fuentes de datos y referencias")

        sources = set()
        for comp_meta in meta["components"].values():
            sources.add(comp_meta["source"])

        sources_text = "Fuentes de datos utilizadas en este análisis:\n\n"
        for i, src in enumerate(sorted(sources), 1):
            sources_text += f"  {i}. {src}\n"

        sources_text += (
            f"\n\nReferencias metodológicas:\n\n"
            f"  • Hansen, M.C. et al. (2013). High-Resolution Global Maps of\n"
            f"    21st-Century Forest Cover Change. Science 342(6160):850-853.\n"
            f"  • Nelson, A. et al. (2019). A suite of global accessibility\n"
            f"    indicators. Scientific Data 6:266.\n"
            f"  • Poggio, L. et al. (2021). SoilGrids 2.0: producing soil\n"
            f"    information for the globe. SOIL 7:217-240.\n"
            f"  • Brown, C.F. et al. (2022). Dynamic World, Near real-time\n"
            f"    global 10m land use land cover mapping. Scientific Data 9:251.\n"
            f"  • Uber Technologies (2018). H3: Hexagonal hierarchical\n"
            f"    geospatial indexing system. https://h3geo.org/\n\n"
            f"Generado por Spatia — Inteligencia Territorial para Misiones\n"
            f"https://spatia.ar\n"
            f"Fecha de generación: {date.today().strftime('%d/%m/%Y')}\n"
            f"Contacto: Raimundo Elías Gómez — CONICET"
        )
        fig.text(0.08, 0.88, sources_text, fontsize=8, va='top', fontfamily='monospace',
                 color='#333333', linespacing=1.5)
        pdf.savefig(fig); plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description="Generate professional PDF reports per department")
    parser.add_argument("--only", default=None, help="Comma-separated analysis IDs")
    parser.add_argument("--dept", default=None, help="Single department name")
    args = parser.parse_args()

    analyses = ALL_ANALYSES
    if args.only:
        analyses = [a for a in args.only.split(",") if a in ALL_ANALYSES]

    os.makedirs(REPORT_DIR, exist_ok=True)
    t0 = time.time()
    total = 0

    for analysis_id in analyses:
        prov_path = os.path.join(OUTPUT_DIR, f"sat_{analysis_id}.parquet")
        if not os.path.exists(prov_path):
            print(f"  SKIP {analysis_id}: parquet not found")
            continue

        prov_df = pd.read_parquet(prov_path)

        summary_path = os.path.join(SRC_DATA_DIR, f"sat_{analysis_id}_dept_summary.json")
        if not os.path.exists(summary_path):
            continue

        with open(summary_path, "r", encoding="utf-8") as f:
            summary = json.load(f)

        print(f"\n[{analysis_id}]")

        for dept in summary["departments"]:
            dept_name = dept["dpto"]
            if args.dept and dept_name != args.dept:
                continue

            safe = safe_filename(dept_name)
            dept_parquet = os.path.join(OUTPUT_DIR, "sat_dpto", f"sat_{analysis_id}_{safe}.parquet")
            if not os.path.exists(dept_parquet):
                continue

            dept_df = pd.read_parquet(dept_parquet)
            out_path = os.path.join(REPORT_DIR, f"sat_{analysis_id}_{safe}.pdf")
            generate_report(analysis_id, dept_name, dept_df, prov_df, summary, out_path)
            size_kb = os.path.getsize(out_path) / 1024
            n_pages = 6 + len([c for c in dept_df.columns if c.startswith("c_")])
            print(f"  {dept_name}: {n_pages} páginas, {size_kb:.0f} KB")
            total += 1

    elapsed = time.time() - t0
    print(f"\n{'=' * 50}")
    print(f"  {total} informes generados en {elapsed:.0f}s")
    print(f"  Directorio: {REPORT_DIR}")
    print(f"{'=' * 50}")


if __name__ == "__main__":
    sys.exit(main() or 0)
