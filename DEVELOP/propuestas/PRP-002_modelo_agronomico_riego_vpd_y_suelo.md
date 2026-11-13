# PRP-002: Modelo Agronómico de Riego por Propiedades Físicas del Suelo (CC / PMP) y VPD

- **Código:** `PRP-002`
- **Versión Objetivo:** `v5.0.0`
- **Estado:** Propuesta de Evolución Científica
- **Autor:** Daniel Felipe Duque Lizarralde

---

## 1. Motivación Científica
En `AquaUTP v3.2` (y preservado por compatibilidad en `aquaterra/core/agronomia/hidrico.py` bajo la constante explícita `HUMEDAD_POST_RIEGO_SIMULADA_PCT = 95.0`), aplicar un riego asume que la humedad de cualquier parcela salta instantáneamente al $95\%$ sin importar el área ($\text{m}^2$), la lámina de agua aplicada ($\text{L}$) ni la textura del suelo (`Franco`, `Arenoso`, `Arcilloso`).

Para que **AquaTerra Matrix** sea una herramienta de ingeniería agronómica rigurosa acoplada al **Nodo INTI**, se propone reemplazar esa simulación por un modelo físico de balance hídrico en la zona radicular.

---

## 2. Formulación Física Propuesta

### 2.1. Parámetros Hidrodinámicos por Textura (`TipoSuelo`)
| Tipo de Suelo | Capacidad de Campo $\theta_{CC}$ (%) | Punto de Marchitez Permanente $\theta_{PMP}$ (%) | Agua Disponible Total $ADT$ ($\text{mm/m}$) | Profundidad Efectiva Radicular $Z_r$ ($\text{m}$) |
|---|---|---|---|---|
| **Arenoso** | $15 - 20\%$ | $6 - 8\%$ | $\sim 80\text{ mm/m}$ | $0.30 - 0.50\text{ m}$ |
| **Franco** | $28 - 32\%$ | $12 - 15\%$ | $\sim 160\text{ mm/m}$ | $0.40 - 0.60\text{ m}$ |
| **Arcilloso** | $38 - 42\%$ | $20 - 24\%$ | $\sim 180\text{ mm/m}$ | $0.30 - 0.50\text{ m}$ |

### 2.2. Cálculo de Lámina y Volumen de Riego Recomendado
Dado un área de parcela $A$ ($\text{m}^2$), una profundidad radicular $Z_r$ ($\text{m}$) y una eficiencia de aplicación $\eta$ (p. ej. $\eta = 0.90$ en goteo), el volumen de agua $V$ en litros necesario para llevar el suelo desde la humedad actual $\theta_{\text{actual}}$ hasta Capacidad de Campo $\theta_{CC}$ es:

$$V_{\text{litros}} = \frac{(\theta_{CC} - \theta_{\text{actual}})}{100} \cdot Z_r \cdot A \cdot \frac{1000}{\eta}$$

*(Recordando que $1\text{ mm}$ de lámina de agua sobre $1\text{ m}^2$ equivale exactamente a $1\text{ Litro}$).*

### 2.3. Modulación del Umbral por Déficit de Presión de Vapor ($VPD$)
Cuando la estación **Nodo INTI** asociada a la parcela (`parcelas.estacion_id`) reporta un $VPD > 1.6\text{ kPa}$ (`ZonaVPD.ESTRES_HIDRICO`), la demanda evaporativa atmosférica es crítica y el umbral de agotamiento permisible ($RAW$) se ajusta preventivamente para evitar cierre estomático.
