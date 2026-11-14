# 🤖 Guía Maestra de Integración IA (De 0 a 100): Google AI Studio (`Gemini 4`) y `Ollama` Local en AquaTerra Matrix

**Proyecto:** AquaTerra Matrix (`v4.1.0`) — Ecosistema TerraBit  
**Autor:** Daniel Felipe Duque Lizarralde  

---

## 1. Arquitectura ya Incorporada en tu Código

El motor de Inteligencia Artificial ya está **100 % programado, probado y conectado** en tu contenedor principal (`cont.copiloto`):

- **Dominio y Guardarraíles:** [`aquaterra/core/copiloto/`](../aquaterra/core/copiloto/)
- **Conectores Nube y Local:** [`aquaterra/infrastructure/ia/proveedores.py`](../aquaterra/infrastructure/ia/proveedores.py)
- **Servicio Orquestador:** [`aquaterra/application/copiloto_servicio.py`](../aquaterra/application/copiloto_servicio.py)

El sistema opera en **Cascada Automática de 3 Niveles (`AQUATERRA_IA_PROVEEDOR="auto"`)**:
1. **Nivel 1 (Nube):** Si detecta tu clave `GEMINI_API_KEY`, consulta a **`gemini-4-hydrogen`** en Google AI Studio usando la API moderna **Interactions** con esquema JSON estricto (`ESQUEMA_JSON_RESPUESTA_COPILOTO`).
2. **Nivel 2 (PC Local Offline):** Si no hay internet o no hay `GEMINI_API_KEY`, verifica en `1.2 segundos` si tienes **Ollama** encendido en `http://127.0.0.1:11434` y consulta al modelo local (`gemma3:4b` por defecto).
3. **Nivel 3 (Determinista Nativo):** Si estás en el páramo o en una finca sin red y sin Ollama corriendo, responde al instante con `AsesorDeterministaCopiloto` (`local_reglas`).
4. **Filtro Anti-Alucinación Siempre Activo:** Sea cual sea el modelo que responda, `auditar_y_acotar_ajustes()` intercepta la salida antes de guardarla en SQLite y recorta cualquier parámetro fuera de rango físico.

---

## 2. Paso a Paso (De 0 a 100): Conectar Google AI Studio (`Gemini`)

### Paso 1: Obtener tu API Key en Google AI Studio
1. Ingresa a **[https://aistudio.google.com/apikey](https://aistudio.google.com/apikey)** con tu cuenta de Google.
2. Haz clic en **"Create API Key"**.
3. Copia la cadena generada (comienza por `AIzaSy...`). *Nunca la pegues directamente dentro de archivos `.py` que subas a GitHub.*

### Paso 2: Instalar el SDK Oficial Moderno (`google-genai`) en tu `.venv`
Nota importante: `AquaTerra Matrix` ya incluye un cliente HTTP REST nativo (`urllib.request`) que habla con `/v1beta/interactions` incluso sin instalar paquetes adicionales. Sin embargo, para máxima velocidad y soporte de futuras funciones multimodales, instala el SDK oficial **`google-genai`** (nunca el antiguo `google-generativeai` que está deprecado):

```powershell
Set-Location "C:\Users\danie\Developer\AquaTerra_Matrix"
.\.venv\Scripts\pip.exe install -U "google-genai>=3.2.0"
```

### Paso 3: Configurar la Variable de Entorno en Windows (PowerShell)
Para probarla en tu sesión actual de terminal:
```powershell
$env:GEMINI_API_KEY = "AIzaSyTU_CLAVE_AQUI"
$env:AQUATERRA_IA_PROVEEDOR = "auto"           # "auto" | "gemini" | "ollama" | "local_reglas"
$env:AQUATERRA_GEMINI_MODEL = "gemini-4-hydrogen" # También puedes usar "gemini-3.5-flash-lite" o "gemini-4-argon"
```

Si quieres dejarla guardada de forma permanente en tu usuario de Windows (para que funcione siempre que abras VS Code o el ejecutable):
```powershell
[System.Environment]::SetEnvironmentVariable("GEMINI_API_KEY", "AIzaSyTU_CLAVE_AQUI", "User")
```

### Paso 4: Probar el Copiloto en Vivo desde tu Terminal
Ejecuta este comando de una sola línea en PowerShell para verificar que tu estación habla con Gemini AI Studio y pasa por los guardarraíles:

```powershell
Set-Location "C:\Users\danie\Developer\AquaTerra_Matrix"
.\.venv\Scripts\python.exe -c "from aquaterra.application.contenedor import construir_contenedor; c = construir_contenedor(); r = c.copiloto.consultar_copiloto('En el último riego se nos pasó la mano con el agua, ¿cómo ajustamos?', parcela_id=1); print('Proveedor:', r.propuesta.proveedor_ia); print('Diagnóstico:', r.propuesta.diagnostico_tecnico); print('Ajustes seguros:', r.propuesta.ajustes_propuestos); c.cerrar()"
```

---

## 3. Paso a Paso (De 0 a 100): Configurar `Ollama` para Operación 100 % Offline en Finca

Cuando lleves tu portátil a una finca cafetera/platanera o al páramo sin internet y quieras inferencia generativa local:

### Paso 1: Instalar Ollama en Windows
1. Descarga el instalador oficial desde **[https://ollama.com/download/windows](https://ollama.com/download/windows)** o instálalo por `winget`:
   ```powershell
   winget install Ollama.Ollama
   ```

### Paso 2: Descargar un Modelo Ligero Especializado en Razonamiento Técnico
En PowerShell, descarga uno de estos dos modelos (pesan entre `2.0 GB` y `3.3 GB` y corren fluido en CPU/GPU de portátil):
```powershell
# Opción A (Recomendada — Familia Gemma de Google, 4B parámetros):
ollama pull gemma3:4b

# Opción B (Alternativa ultraligera y muy precisa en JSON, 3B parámetros):
ollama pull qwen2.5:3b
```

### Paso 3: Conectar `AquaTerra Matrix` con tu Ollama Local
Si estás sin internet (o sin `GEMINI_API_KEY`), `AquaTerra Matrix` en modo `"auto"` detectará automáticamente a Ollama en `http://127.0.0.1:11434`. Si deseas forzar el uso exclusivo de Ollama aunque tengas internet:
```powershell
$env:AQUATERRA_IA_PROVEEDOR = "ollama"
$env:AQUATERRA_OLLAMA_MODEL = "gemma3:4b"
```

---

## 4. Cómo Entrenar / Afinar tu Propio Modelo Especializado en el Futuro (Fine-Tuning)

Cada vez que usas `c.copiloto.consultar_copiloto(...)` y aplicas una calibración que resulta exitosa en campo, SQLite almacena la interacción completa en la tabla `conversaciones_copiloto`.

Cuando acumules entre **300 y 500 casos reales**, exporta tu dataset limpio con una sola llamada:

```powershell
Set-Location "C:\Users\danie\Developer\AquaTerra_Matrix"
.\.venv\Scripts\python.exe -c "from aquaterra.application.contenedor import construir_contenedor; c = construir_contenedor(); n = c.copiloto.exportar_dataset_entrenamiento_jsonl('data/runtime/terrabit_sft_dataset.jsonl', solo_con_ajustes=True); print(f'Exportados {n} ejemplos de entrenamiento'); c.cerrar()"
```

Ese archivo `terrabit_sft_dataset.jsonl` contiene la `system_instruction`, el contexto del operador y la respuesta JSON auditada, listo para subir a **Google AI Studio (Tune a model)** o a un notebook de **Google Colab (con Unsloth)** para afinar tu propio modelo `terrabit-agro-v1`.
