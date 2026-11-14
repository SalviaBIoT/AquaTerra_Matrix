# ADR-003: Hashing de Contraseñas con PBKDF2-HMAC-SHA256 y Bitácora de Auditoría

- **Estado:** Aceptado e Implementado (`v4.0.0a1`)
- **Fecha:** `2026-11-13`
- **Autor:** Daniel Felipe Duque Lizarralde

---

## 1. Contexto
`AquaUTP v3.2` almacenaba las contraseñas en texto plano (`"pass": "1234"`) dentro de `data/usuarios.json` y las comparaba con `==`. Tampoco existía registro de quién ejecutó un riego o modificó una parcela.

## 2. Decisión
1. **Derivación Criptográfica Estándar (`aquaterra/infrastructure/seguridad/hashing.py`):**
   - Algoritmo: `PBKDF2-HMAC-SHA256` provisto por `hashlib` (librería estándar, acelerado por OpenSSL en C).
   - Costo por defecto: **600,000 iteraciones** (recomendación OWASP vigente).
   - Salt: 16 bytes aleatorios por usuario generados con `secrets.token_bytes(16)`.
   - Comparación: `hmac.compare_digest()` en tiempo constante.
   - Formato persistido: `pbkdf2_sha256$<iteraciones>$<salt_b64>$<hash_b64>`.
   - **Actualización transparente (`requiere_rehash`):** Si un usuario inicia sesión con un hash generado con menos iteraciones, `ServicioAutenticacion.iniciar_sesion()` actualiza el hash automáticamente.
2. **Tabla `auditoria` en SQLite:**
   - Registra `ts_iso`, `usuario_id`, `accion`, `entidad`, `entidad_id` y `detalle` (JSON) en la misma transacción de cada caso de uso.

## 3. Consecuencias
- Cero contraseñas en claro en disco (incluso los usuarios migrados desde `v3.2` se hashean al importarse).
- Trazabilidad forense completa de accesos y operaciones sobre parcelas y riegos.
