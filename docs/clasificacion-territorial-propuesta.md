# Propuesta de clasificación territorial hexagonal para Spatia: tres alternativas desde la economía ecológica, la antropología ecológica y la sociología relacional

**Documento de trabajo — marzo 2026**
**Plataforma Spatia · Inteligencia Territorial · Misiones, Argentina**

---

## 1. Introducción: insuficiencia del scoring lineal ponderado

El sistema de clasificación actualmente implementado en Spatia opera mediante un promedio lineal ponderado de variables percentilizadas (0–100), donde cada una de las 62 dimensiones disponibles por hexágono H3 (resolución 9, ~174 m de lado) se ordena independientemente en el espacio de la muestra y se pondera con coeficientes fijos determinados de manera heurística. Este procedimiento, si bien computacionalmente eficiente y fácil de comunicar, presenta limitaciones estructurales que comprometen la validez analítica de la tipología resultante.

En primer lugar, la percentilización independiente destruye la estructura de covarianza entre variables: dos indicadores que en la realidad territorial se manifiestan conjuntamente —como la pérdida de cobertura forestal (`c_hansen_loss`) y la frecuencia de incendios (`c_fire_count`)— son tratados como dimensiones ortogonales, lo cual impide capturar configuraciones multivariadas que definen patrones territoriales reales. En segundo lugar, la aditividad lineal supone que las contribuciones de cada variable al puntaje total son proporcionales e independientes del nivel de las demás; este supuesto resulta difícil de sostener cuando, por ejemplo, un alto `c_npp` combinado con alto `c_deforest` indica un régimen metabólico cualitativamente distinto al de un hexágono con alto `c_npp` y baja perturbación. En tercer lugar, los pesos asignados manualmente carecen de fundamentación teórica explícita y no pueden ser sometidos a validación empírica ni a análisis de sensibilidad robustos. Finalmente, la reducción a un puntaje único colapsa la multidimensionalidad del territorio en una escala ordinal que, si bien permite rankings, impide la identificación de tipos cualitativamente diferenciados —esto es, de configuraciones territoriales que podrían informar políticas diferenciadas.

Se proponen a continuación tres sistemas alternativos de clasificación, cada uno enraizado en una tradición académica consolidada, con técnicas estadísticas específicas, variables mapeadas desde el repositorio de Spatia y tipologías esperadas para la provincia de Misiones. Las tres alternativas comparten un principio común: sustituir la lógica del ranking unidimensional por la lógica de la clasificación multivariada, donde los hexágonos no se ordenan en un continuo sino que se agrupan en tipos definidos por la co-ocurrencia de múltiples atributos.

---

## 2. Alternativa 1: Perfiles Metabólicos Territoriales (Economía Ecológica)

### 2.1 Fundamentación teórica

La primera alternativa se inscribe en la tradición del metabolismo social y el análisis de flujos de materiales y energía (MEFA), desarrollada desde la década de 1990 en la confluencia entre la economía ecológica y la ecología industrial. El concepto central es el de *Human Appropriation of Net Primary Production* (HANPP), formalizado por Haberl et al. (2007) en un estudio publicado en *Proceedings of the National Academy of Sciences* que cuantificó por primera vez la apropiación humana de la productividad ecosistémica a escala global. El marco teórico más amplio corresponde a las *transiciones socioecológicas* de Fischer-Kowalski y Haberl (2007), que proponen que las sociedades atraviesan regímenes metabólicos diferenciados —cazadores-recolectores, agrarios, industriales— cada uno con un patrón característico de uso de energía, materiales y territorio.

A escala subnacional, la operacionalización más influyente del metabolismo territorial proviene del marco MuSIASEM (*Multi-Scale Integrated Analysis of Societal and Ecosystem Metabolism*) de Giampietro et al. (2009), que permite analizar simultáneamente los flujos biofísicos y las actividades humanas a múltiples escalas. La actualización de Krausmann et al. (2013) sobre trayectorias globales de uso de materiales, así como el marco de *environmental footprint analysis* de Wiedmann y Lenzen (2018), completan el sustrato teórico. La idea nuclear aplicada a Spatia es clasificar cada hexágono según su *configuración sociometabólica*: cuánta productividad ecosistémica se genera, cuánta es apropiada por actividades humanas, y a través de qué mecanismo (urbanización, agricultura, extracción forestal, fuego).

### 2.2 Técnica estadística

Se propone un análisis de agrupamiento (*clustering*) sobre indicadores metabólicos estandarizados. El procedimiento consta de tres etapas:

1. **Estandarización**: las variables seleccionadas se transforman a puntuaciones *z* (media 0, desviación estándar 1) para eliminar efectos de escala, utilizando `sklearn.preprocessing.StandardScaler`.
2. **Agrupamiento**: se aplica el algoritmo de Ward (clasificación ascendente jerárquica con criterio de varianza mínima intra-grupo) implementado en `scipy.cluster.hierarchy.linkage(method='ward')`. Alternativamente, se evalúa *k*-means (`sklearn.cluster.KMeans`) con inicialización `k-means++` y 100 réplicas aleatorias.
3. **Selección del número de grupos**: se determina *k* óptimo mediante el índice de Calinski-Harabasz (`sklearn.metrics.calinski_harabasz_score`) y el coeficiente de silueta (`sklearn.metrics.silhouette_score`), privilegiando soluciones con 5 a 8 grupos que resulten interpretables en el contexto misionero.

**Librerías Python**: `scikit-learn` (StandardScaler, KMeans, calinski_harabasz_score, silhouette_score), `scipy` (linkage, fcluster, dendrogram), `numpy`, `pandas`.

### 2.3 Variables de Spatia

| Variable | Rol metabólico |
|---|---|
| `c_npp` | Productividad primaria neta — oferta ecosistémica |
| `c_ndvi`, `c_lai`, `c_vcf` | Estado de la vegetación — capital biofísico disponible |
| `frac_trees`, `frac_crops`, `frac_built`, `frac_bare` | Cobertura del suelo — modo de apropiación territorial |
| `c_deforest`, `c_hansen_loss`, `c_loss_ratio` | Tasas de conversión — intensidad de la transformación |
| `c_fire`, `c_fire_count` | Perturbación por fuego — mecanismo de apropiación |
| `c_viirs_trend`, `c_ghsl_change` | Tendencias de urbanización — presión antrópica |
| `c_nightlights` | Intensidad lumínica — proxy de metabolismo energético |

Se seleccionan 15 variables que capturan los tres ejes del metabolismo territorial: oferta biofísica, modo de apropiación y dinámica de transformación.

### 2.4 Sistemas de referencia

- **JRC LUISA** (Joint Research Centre, Comisión Europea): plataforma de modelado territorial que integra HANPP y uso del suelo para la Unión Europea.
- **UN SEEA-EA** (System of Environmental-Economic Accounting — Ecosystem Accounting): estándar de Naciones Unidas que operacionaliza la contabilidad ecosistémica incluyendo flujos de servicios y condición.
- **EEA MAES** (Mapping and Assessment of Ecosystem Services): marco de la Agencia Europea de Medio Ambiente para la evaluación del estado ecosistémico.
- **IFF Vienna HANPP Database** (Institute of Social Ecology, BOKU): base de datos global de apropiación humana de productividad primaria neta.

### 2.5 Tipología esperada para Misiones

1. **Selva continua de alta productividad** — hexágonos con `c_npp` y `frac_trees` elevados, baja apropiación humana; corresponden a remanentes de selva paranaense en el corredor verde central y áreas protegidas (Parque Nacional Iguazú, Reserva de Biósfera Yabotí).
2. **Matriz agroforestal yerbatera** — productividad moderada, `frac_crops` significativo con `frac_trees` residual; corresponde a la zona yerbatera y tealera del centro-sur donde la apropiación es parcial y el paisaje retiene fragmentos forestales.
3. **Frente de deforestación activo** — alto `c_hansen_loss`, elevado `c_fire_count`, caída de `c_ndvi_trend`; localizado en el frente agrícola del noreste y sectores de avance tabacalero.
4. **Núcleo urbano-periurbano** — `frac_built` dominante, alto `c_nightlights` y `c_ghsl_change`, NPP muy bajo; Posadas, Oberá, Eldorado y sus periferias.
5. **Plantación forestal industrial** — `frac_trees` alto pero `c_npp` moderado (monocultivos de pino/eucalipto vs. selva nativa), baja diversidad de cobertura; concentrada en el sur provincial.
6. **Humedal y planicie aluvial** — `frac_flooded` y `frac_water` elevados, `c_npp` moderado-alto, baja apropiación; márgenes del Paraná y el Uruguay, bañados interiores.
7. **Chacra de subsistencia periférica** — `frac_crops` bajo-moderado, alto `c_isolation`, bajo `c_nightlights`; colonias rurales dispersas del interior con baja integración metabólica.

### 2.6 Ventajas y limitaciones

**Ventajas**: fundamentación teórica sólida en una tradición con más de tres décadas de desarrollo; variables directamente disponibles en Spatia sin necesidad de datos externos adicionales; tipología intuitiva para actores de política ambiental y ordenamiento territorial; compatibilidad con marcos internacionales (SEEA-EA, IPBES).

**Limitaciones**: la ausencia de datos directos de flujos de materiales y energía obliga a utilizar *proxies* de teledetección; la HANPP calculada desde NPP satelital subestima la apropiación subterránea y los flujos exportados; la técnica de agrupamiento es sensible a la selección de variables y al número de grupos; los perfiles metabólicos no capturan dimensiones sociales (pobreza, acceso a servicios) salvo indirectamente a través de la luminosidad nocturna.

---

## 3. Alternativa 2: Arquetipos Socioecológicos (Antropología Ecológica / Ciencia de Sistemas Territoriales)

### 3.1 Fundamentación teórica

La segunda alternativa se enmarca en la tradición de los *Land System Archetypes*, formalizada por Václavík et al. (2013) en *Global Environmental Change*, donde se propuso una metodología basada en mapas autoorganizados (SOM) para identificar arquetipos recurrentes de sistemas territoriales a escala global. El concepto de arquetipo —un patrón recurrente de co-ocurrencia de atributos biofísicos y socioeconómicos— se distingue del tipo estadístico convencional en que busca configuraciones que se repiten en contextos geográficos diversos, sugiriendo mecanismos causales compartidos.

El marco teórico más amplio proviene de tres fuentes convergentes: el *SES Framework* de Ostrom (2009), publicado en *Science*, que identifica las variables diagnósticas de los sistemas socioecológicos; la teoría de sistemas humano-naturales acoplados (*Coupled Human and Natural Systems*, CHANS) de Liu et al. (2007); y la sistematización del *archetype analysis* como metodología de investigación por Eisenack et al. (2019). Contribuciones adicionales incluyen la aplicación de arquetipos a vulnerabilidad por Sietz et al. (2019) y la síntesis de Magliocca et al. (2018) sobre cambio de uso del suelo.

La idea nuclear para Spatia consiste en tratar cada hexágono como una unidad de un sistema socioecológico acoplado y clasificarlo según el arquetipo al que pertenece, utilizando la totalidad del espacio de variables disponible para capturar la configuración completa del sistema.

### 3.2 Técnica estadística

Se propone un procedimiento en cuatro etapas que sigue la metodología canónica de Václavík et al. (2013):

1. **Reducción de dimensionalidad**: se aplica PCA (`sklearn.decomposition.PCA`) sobre las 62 variables estandarizadas, reteniendo las componentes que explican al menos el 80% de la varianza acumulada. Esto típicamente reduce el espacio a 8–15 componentes principales.
2. **Mapa autoorganizado (SOM)**: se entrena un SOM rectangular (por ejemplo, 10×10 neuronas) sobre los componentes principales, utilizando la librería `minisom` (`MiniSom(x=10, y=10, input_len=n_components, sigma=1.5, learning_rate=0.5, neighborhood_function='gaussian')`). El SOM preserva la topología del espacio multivariado y permite identificar regiones densas y transiciones.
3. **Agrupamiento de neuronas**: se aplica *k*-means o Ward sobre los vectores de pesos de las neuronas del SOM (no sobre los datos originales), determinando *k* mediante el coeficiente de silueta. Esto produce arquetipos que son agrupaciones de neuronas topológicamente contiguas.
4. **Asignación**: cada hexágono se asigna al arquetipo correspondiente a su neurona ganadora (*Best Matching Unit*).

**Alternativa simplificada**: si el SOM introduce complejidad excesiva para la primera implementación, se puede sustituir por *k*-means directamente sobre los componentes principales, con validación por silueta y Calinski-Harabasz. La ventaja del SOM reside en la preservación topológica, que permite visualizar transiciones graduales entre arquetipos.

**Librerías Python**: `minisom` (MiniSom), `scikit-learn` (PCA, KMeans, silhouette_score, calinski_harabasz_score), `scipy`, `numpy`, `pandas`, `matplotlib` (para U-matrix del SOM).

### 3.3 Variables de Spatia

Se utilizan las **62 variables completas** del repositorio de Spatia. La justificación teórica es que el enfoque de arquetipos busca capturar la *configuración completa* del sistema socioecológico; la selección a priori de subconjuntos de variables introduciría sesgos teóricos que el método busca precisamente evitar. La reducción de dimensionalidad por PCA cumple la función de extraer las dimensiones latentes sin descartar información.

Las 62 variables cubren los subsistemas del marco SES de Ostrom: el sistema de recursos (variables ambientales, forestales, agrícolas), las unidades de recurso (coberturas del suelo), el sistema de gobernanza (accesibilidad, infraestructura) y los usuarios (densidad poblacional, indicadores censales).

### 3.4 Sistemas de referencia

- **IIASA Global Land Programme**: programa internacional que desarrolló y validó la metodología de arquetipos territoriales a escala global.
- **PBL Netherlands — GLOBIO**: modelo de biodiversidad integrado que utiliza arquetipos de uso del suelo como insumo.
- **IPBES**: la Plataforma Intergubernamental de Biodiversidad y Servicios Ecosistémicos adopta el enfoque de arquetipos en sus evaluaciones regionales.
- **GLP (Global Land Programme)**: red científica que ha endosado la metodología de arquetipos como estándar para el análisis comparativo de sistemas territoriales.

### 3.5 Tipología esperada para Misiones

1. **Selva densa subtropical con baja accesibilidad** — alta productividad, alta cobertura arbórea, baja luminosidad, alta fricción de desplazamiento; corredor verde y áreas protegidas remotas.
2. **Mosaico agroforestal periurbano** — mezcla de coberturas, accesibilidad moderada, tendencias de cambio activas; cinturón periurbano de ciudades intermedias (Oberá, Eldorado, Montecarlo).
3. **Paisaje yerbatero-ganadero consolidado** — dominancia de cultivos perennes, suelos con pH y SOC moderados, baja pérdida forestal reciente; zona central productiva.
4. **Frente pionero con alta presión de cambio** — alta deforestación, tendencia creciente de luminosidad nocturna, caída de NDVI, suelos de aptitud moderada; expansión agrícola activa.
5. **Núcleo urbano denso** — alta fracción construida, alta luminosidad, bajo déficit de infraestructura, alta accesibilidad; Posadas y Garupá.
6. **Periferia rural con déficit social** — alto NBI, baja cobertura de salud, alta deserción educativa, aislamiento elevado; colonias del interior profundo.
7. **Corredor fluvial y humedales** — dominancia de agua y vegetación inundable, alta evapotranspiración, baja población; valles del Paraná, Uruguay e Iguazú.

### 3.6 Ventajas y limitaciones

**Ventajas**: utilización de la totalidad del espacio de variables, lo que maximiza la información capturada; metodología validada internacionalmente con más de 500 citaciones del artículo fundacional; capacidad de identificar configuraciones emergentes no anticipadas por la teoría; el SOM permite visualizar transiciones graduales entre arquetipos, lo cual resulta particularmente útil para territorios de frontera agrícola como Misiones.

**Limitaciones**: la interpretación de los arquetipos requiere análisis ex post de las variables dominantes en cada grupo, lo que puede resultar menos transparente que una clasificación basada en variables preseleccionadas; el SOM introduce hiperparámetros adicionales (tamaño de grilla, tasa de aprendizaje, función de vecindad) cuya calibración demanda experimentación; con 319.871 hexágonos y 62 variables, el costo computacional del SOM puede ser significativo —aunque se mitiga parcialmente al operar sobre componentes principales—; la inclusión de todas las variables implica que variables ruidosas o redundantes pueden distorsionar la clasificación si no se controla adecuadamente la reducción dimensional.

---

## 4. Alternativa 3: Tipología Factorial del Territorio (Sociología Relacional / Escuela Francesa de Análisis de Datos)

### 4.1 Fundamentación teórica

La tercera alternativa se inscribe en la tradición del *Analyse des Données* francesa, cuyo desarrollo se asocia a la obra de Benzécri (1992) y su escuela, y que fue integrada en el programa sociológico de Bourdieu (1979) a través del concepto de *espacio social* multidimensional. La formalización contemporánea corresponde al *Geometric Data Analysis* (GDA) de Le Roux y Rouanet (2004), que establece los fundamentos algebraicos y geométricos del análisis factorial como herramienta de descripción de espacios de posiciones.

En el ámbito territorial, esta tradición ha sido aplicada extensamente por el INSEE (Institut National de la Statistique et des Études Économiques) de Francia para producir tipologías comunales que informan la política pública desde la década de 1980. El Observatoire des Territoires de la ANCT (Agence Nationale de la Cohésion des Territoires) publica periódicamente tipologías de comunas y departamentos basadas en la combinación PCA + CAH (Clasificación Ascendente Jerárquica). Prétéceille (2006) aplicó esta metodología al análisis de la segregación socio-espacial en metrópolis, y Banos y Huot (2021) extendieron el enfoque combinando MCA (Análisis de Correspondencias Múltiples) con variables socio-espaciales.

La idea nuclear consiste en concebir el territorio como un espacio de posiciones —análogo al espacio social de Bourdieu— donde cada hexágono ocupa una posición definida por sus coordenadas en los ejes factoriales principales. La clasificación resulta de la agrupación de posiciones cercanas en este espacio, produciendo tipos que se definen por su oposición mutua en los ejes estructurantes.

### 4.2 Técnica estadística

El procedimiento sigue la secuencia canónica PCA + CAH de la tradición francesa, implementada en cinco etapas:

1. **Selección y estandarización de variables activas**: se seleccionan las variables continuas que participarán del análisis factorial y se estandarizan (puntuaciones *z*). Las variables categóricas (cobertura dominante del suelo, clasificación urbano-rural) se tratan como variables suplementarias o, si se desea incorporarlas activamente, se aplica MCA en lugar de PCA.
2. **Análisis en Componentes Principales (ACP)**: se ejecuta PCA (`sklearn.decomposition.PCA`) sobre la matriz estandarizada. Se retienen los componentes cuyo eigenvalue supera 1 (criterio de Kaiser) o, preferentemente, los que acumulan ≥80% de la varianza explicada. Se interpretan los ejes factoriales mediante las correlaciones variable-componente (*loadings*) y las contribuciones de las variables a cada eje.
3. **Clasificación Ascendente Jerárquica (CAH)**: se aplica el método de Ward (`scipy.cluster.hierarchy.linkage(method='ward')`) sobre las coordenadas factoriales de los hexágonos en los componentes retenidos. El uso de coordenadas factoriales en lugar de las variables originales cumple dos funciones: eliminar el ruido de las dimensiones menores y ponderar las variables según su contribución a la estructura factorial.
4. **Corte óptimo del dendrograma**: se determina el número de clases mediante el índice de Calinski-Harabasz (`sklearn.metrics.calinski_harabasz_score`), complementado con el análisis visual de la pérdida de inercia intra-clase en el dendrograma. Se privilegian soluciones con 5 a 8 clases.
5. **Consolidación por *k*-means**: los centroides de la CAH se utilizan como inicialización para un *k*-means final (`sklearn.cluster.KMeans(n_clusters=k, init=centroids, n_init=1)`) que optimiza la asignación de los hexágonos fronterizos.
6. **Caracterización de las clases**: cada clase se describe mediante sus coordenadas medias en los ejes factoriales, los valores-test de las variables activas y suplementarias, y la cartografía de su distribución espacial.

**Extensión MCA**: si se incorporan variables categóricas —como la clase dominante de cobertura del suelo derivada de las fracciones `frac_*`, o una clasificación urbano-rural a partir de umbrales de `c_nightlights`—, el PCA se sustituye por un Análisis de Correspondencias Múltiples implementado con la librería `prince` (`prince.MCA(n_components=k)`), seguido de la misma secuencia CAH + consolidación.

**Librerías Python**: `scikit-learn` (PCA, KMeans, AgglomerativeClustering, calinski_harabasz_score, silhouette_score), `prince` (MCA), `scipy.cluster.hierarchy` (linkage, fcluster, dendrogram), `numpy`, `pandas`, `matplotlib`.

### 4.3 Variables de Spatia

Se propone una selección de variables activas que cubra las principales dimensiones de diferenciación territorial, organizada en bloques temáticos:

| Bloque | Variables activas | Rol en el espacio factorial |
|---|---|---|
| Capital ecosistémico | `c_ndvi`, `c_npp`, `c_treecover`, `c_lai`, `c_gpp`, `c_et` | Eje de dotación biofísica |
| Presión antrópica | `c_nightlights`, `c_ghsl_change`, `c_viirs_trend`, `frac_built` | Eje de urbanización e intensificación |
| Degradación | `c_deforest`, `c_hansen_loss`, `c_fire`, `c_fire_count`, `c_ndvi_trend` | Eje de transformación y pérdida |
| Aptitud productiva | `c_soc`, `c_ph_optimal`, `c_clay`, `c_gdd`, `c_precipitation` | Eje de potencial agrícola |
| Accesibilidad | `c_access_20k`, `c_access_100k`, `c_road_dist`, `c_friction`, `c_isolation` | Eje de integración territorial |
| Déficit social | `c_nbi`, `c_sin_agua`, `c_sin_cloacas`, `c_no_instruction`, `c_dropout_13_18` | Eje de vulnerabilidad social |
| Cobertura del suelo | `frac_trees`, `frac_crops`, `frac_grass`, `frac_water`, `frac_flooded` | Variables suplementarias o activas |

Se incluyen ~30 variables activas, una cifra compatible con la tradición del GDA donde se recomienda que el número de variables sea sustancialmente menor que el número de observaciones (30 << 319.871).

### 4.4 Sistemas de referencia

- **INSEE (Francia)**: la tipología comunal del INSEE constituye el referente canónico de la metodología PCA + CAH aplicada al territorio; se actualiza periódicamente con datos censales y administrativos.
- **Observatoire des Territoires / ANCT**: publica tipologías de dinámicas territoriales para el conjunto de las comunas francesas, utilizando exactamente la secuencia factorial + clasificación jerárquica aquí propuesta.
- **EUROSTAT**: la tipología urbano-rural de EUROSTAT y las clasificaciones regionales del *Urban Audit* emplean procedimientos factoriales similares.
- **OECD Regional Well-being**: el indicador de bienestar regional de la OCDE utiliza PCA para sintetizar dimensiones y clasificar regiones.

### 4.5 Tipología esperada para Misiones

1. **Polo urbano integrado** — coordenadas altas en el eje de urbanización, bajas en capital ecosistémico, bajo déficit social, alta accesibilidad; Posadas, Garupá, y en menor medida Oberá y Eldorado.
2. **Corona periurbana en transición** — posición intermedia en todos los ejes, alta dinámica de cambio (`c_ghsl_change`, `c_viirs_trend`); anillos de expansión alrededor de las ciudades principales.
3. **Interior productivo consolidado** — aptitud productiva alta, capital ecosistémico moderado (paisaje transformado pero estable), accesibilidad media; zona yerbatera y tealera central.
4. **Interior vulnerable con déficit** — alto déficit social (NBI, falta de agua y cloacas, baja instrucción), baja accesibilidad, capital ecosistémico variable; colonias rurales del interior con baja integración al sistema productivo formal.
5. **Reserva forestal de alta integridad** — máximas coordenadas en capital ecosistémico, mínimas en presión antrópica y accesibilidad; áreas protegidas y corredor verde.
6. **Frente agrícola activo** — altas coordenadas en el eje de degradación, aptitud productiva moderada, accesibilidad creciente; zonas de avance de la frontera agropecuaria.
7. **Paisaje ribereño y humedal** — posición singular definida por `frac_water` y `frac_flooded`, baja aptitud agrícola, baja población; valles fluviales.

### 4.6 Ventajas y limitaciones

**Ventajas**: la secuencia PCA + CAH constituye uno de los procedimientos más maduros y reproducibles del análisis multivariado, con décadas de aplicación en tipologías territoriales oficiales; la interpretación de los ejes factoriales proporciona una narrativa estructural del territorio (qué opone a qué) antes de la clasificación, lo que enriquece la comprensión más allá de la mera asignación a tipos; la extensión MCA permite incorporar variables categóricas sin forzar supuestos de linealidad; la consolidación por *k*-means estabiliza la clasificación en los bordes entre grupos.

**Limitaciones**: la interpretación de los ejes factoriales requiere expertise analítico y puede resultar ambigua cuando las variables cargan en múltiples componentes; el criterio de retención de ejes (Kaiser, varianza acumulada) es parcialmente arbitrario; la CAH con método de Ward tiende a producir grupos esféricos y de tamaño similar, lo cual puede no corresponder a la estructura real de los datos si existen arquetipos de muy diferente prevalencia; el costo computacional de la CAH es *O(n²)* en memoria, lo que con 319.871 hexágonos requiere implementaciones optimizadas o submuestreo previo con posterior reasignación —una solución estándar consiste en aplicar la CAH sobre una muestra aleatoria estratificada de 10.000–50.000 hexágonos y luego asignar el resto por proximidad a los centroides consolidados.

---

## 5. Tabla comparativa

| Criterio | Alt. 1: Perfiles Metabólicos | Alt. 2: Arquetipos Socioecológicos | Alt. 3: Tipología Factorial |
|---|---|---|---|
| **Tradición** | Economía ecológica (MEFA, HANPP) | Antropología ecológica / Land System Science | Sociología relacional / Escuela francesa |
| **Autores clave** | Haberl, Fischer-Kowalski, Giampietro, Krausmann | Václavík, Ostrom, Eisenack, Liu | Benzécri, Le Roux, Bourdieu, Prétéceille |
| **Técnica central** | Ward / *k*-means sobre variables metabólicas | SOM + *k*-means sobre PCA (full space) | PCA + CAH + consolidación *k*-means |
| **N.º variables** | ~15 (selección metabólica) | 62 (espacio completo) | ~30 (selección multidimensional) |
| **Reducción dimensional** | No (variables directas) | PCA previo al SOM | PCA como paso analítico central |
| **Software** | scikit-learn, scipy | minisom, scikit-learn | scikit-learn, prince, scipy |
| **Complejidad computacional** | Baja | Media-alta (SOM iterativo) | Media (CAH *O(n²)*, mitigable) |
| **Interpretabilidad** | Alta (variables con significado biofísico directo) | Media (requiere análisis ex post) | Alta (ejes factoriales narrables) |
| **Dimensión social** | Baja (solo proxies) | Alta (incluye todas las variables) | Alta (incluye variables censales) |
| **Referentes institucionales** | JRC, UN SEEA-EA, EEA | IIASA, IPBES, GLP | INSEE, ANCT, EUROSTAT, OECD |
| **Mejor para** | Política ambiental y ordenamiento territorial | Investigación y diagnóstico integral | Tipologías oficiales y política pública |
| **Datos temporales** | Sí (tendencias de cambio como variables) | Sí (variantes _baseline y _current) | Sí (con PCA separado por período) |

---

## 6. Consideraciones de implementación transversales

Independientemente de la alternativa seleccionada, se señalan cuatro consideraciones comunes de implementación:

**Tratamiento de la autocorrelación espacial**. Los hexágonos H3 contiguos presentan alta autocorrelación espacial en la mayoría de las variables, lo cual viola el supuesto de independencia de las observaciones en las técnicas de agrupamiento convencionales. Se sugiere evaluar la incorporación de una penalización por contigüidad espacial —por ejemplo, mediante *spatially constrained clustering* implementado en `sklearn.cluster.AgglomerativeClustering(connectivity=adjacency_matrix)`— que fuerce a los grupos a ser espacialmente coherentes; o bien, aceptar la clasificación no espacial y evaluar ex post la coherencia geográfica de los tipos resultantes.

**Estabilidad y robustez**. Se recomienda evaluar la estabilidad de las clasificaciones mediante *bootstrap* (remuestreo con reemplazo, por ejemplo 100 réplicas) y el cálculo de la frecuencia con que cada par de hexágonos es clasificado en el mismo grupo (*consensus clustering*). Hexágonos con baja estabilidad de asignación constituyen zonas de transición que pueden mapearse explícitamente.

**Dimensión temporal**. Las variantes `_baseline` (2019–2021) y `_current` (últimos 6 meses) de las bandas dinámicas permiten construir una clasificación diacrónica: aplicar la misma metodología a ambos períodos y analizar las transiciones entre tipos. Esto convertiría la tipología estática en un instrumento de monitoreo de trayectorias territoriales.

**Complementariedad de las tres alternativas**. Las tres clasificaciones no son mutuamente excluyentes; de hecho, su aplicación conjunta podría resultar particularmente informativa. La clasificación metabólica ofrece una lectura ambiental directa; la clasificación por arquetipos proporciona un diagnóstico integral; la tipología factorial explicita las dimensiones estructurantes del territorio. Un hexágono podría ser simultáneamente un "frente de deforestación activo" (Alt. 1), un "frente pionero con alta presión de cambio" (Alt. 2) y un "frente agrícola activo" (Alt. 3), y la convergencia o divergencia de las tres clasificaciones constituiría en sí misma un dato analítico relevante.

---

## Referencias

- Banos, A. y Huot, T. (2021). Socio-spatial analysis using geometric data analysis: methodological perspectives. *Cybergeo: European Journal of Geography*.
- Benzécri, J.-P. (1992). *Correspondence Analysis Handbook*. Marcel Dekker.
- Bourdieu, P. (1979). *La Distinction: critique sociale du jugement*. Les Éditions de Minuit.
- Eisenack, K., Villamayor-Tomas, S., Epstein, G., Kimmich, C., Magliocca, N., Manuel-Navarrete, D., Oberlack, C., Pérez-Ibarra, I. y Sietz, D. (2019). Design and quality criteria for archetype analysis. *Ecology and Society*, 24(3), 6.
- Fischer-Kowalski, M. y Haberl, H. (2007). *Socioecological Transitions and Global Change: Trajectories of Social Metabolism and Land Use*. Edward Elgar.
- Giampietro, M., Mayumi, K. y Sorman, A. H. (2009). *The Metabolic Pattern of Societies: Where Economists Fall Short*. Routledge.
- Haberl, H., Erb, K. H., Krausmann, F., Gaube, V., Bondeau, A., Plutzar, C., Gingrich, S., Lucht, W. y Fischer-Kowalski, M. (2007). Quantifying and mapping the human appropriation of net primary production in Earth's terrestrial ecosystems. *Proceedings of the National Academy of Sciences*, 104(31), 12942–12947.
- Krausmann, F., Wiedenhofer, D., Lauk, C., Haas, W., Tanikawa, H., Fishman, T., Miatto, A., Schandl, H. y Haberl, H. (2017). Global socioeconomic material stocks rise 23-fold over the 20th century and require half of annual resource use. *Proceedings of the National Academy of Sciences*, 114(8), 1880–1885.
- Le Roux, B. y Rouanet, H. (2004). *Geometric Data Analysis: From Correspondence Analysis to Structured Data Analysis*. Kluwer Academic Publishers.
- Liu, J., Dietz, T., Carpenter, S. R., Alberti, M., Folke, C., Moran, E., Pell, A. N., Deadman, P., Kratz, T., Lubchenco, J., Ostrom, E., Ouyang, Z., Provencher, W., Redman, C. L., Schneider, S. H. y Taylor, W. W. (2007). Complexity of coupled human and natural systems. *Science*, 317(5844), 1513–1516.
- Magliocca, N. R., Ellis, E. C., Allington, G. R., de Bremond, A., Dell'Angelo, J., Mertz, O., Unruh, J. D. y Václavík, T. (2018). Closing global knowledge gaps: producing generalized knowledge from case studies of social-ecological systems. *Global Environmental Change*, 50, 1–14.
- Ostrom, E. (2009). A general framework for analyzing sustainability of social-ecological systems. *Science*, 325(5939), 419–422.
- Prétéceille, E. (2006). La ségrégation sociale a-t-elle augmenté? La métropole parisienne entre polarisation et mixité. *Sociétés Contemporaines*, 62, 69–93.
- Sietz, D., Ordoñez, J. C., Kok, M. T. J., Hizsnyik, E. y Van Loon, M. P. (2019). Nested archetypes of vulnerability in African drylands: where lies potential for sustainable agricultural intensification? *Environmental Research Letters*, 14(1), 015005.
- Václavík, T., Lautenbach, S., Kuemmerle, T. y Seppelt, R. (2013). Mapping global land system archetypes. *Global Environmental Change*, 23(6), 1637–1647.
- Wiedmann, T. y Lenzen, M. (2018). Environmental and social footprints of international trade. *Nature Geoscience*, 11(5), 314–321.
