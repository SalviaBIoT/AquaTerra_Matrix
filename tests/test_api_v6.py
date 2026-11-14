"""Pruebas de integración de la API Local FastAPI v6.0 (Fase 1)."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from aquaterra.api import crear_app
from aquaterra.application.contenedor import Contenedor
from aquaterra.config import Configuracion
from aquaterra.core.domain import Rol, TipoEstacion
from aquaterra.infrastructure.db.repositorios import RepositorioUsuarios
from aquaterra.infrastructure.ia import ConfiguracionIA, OrquestadorIA
from aquaterra.infrastructure.seguridad import generar_hash
from tests.conftest import ITERACIONES_TEST


def _crear_cliente(db) -> tuple[TestClient, Contenedor]:
    contenedor = Contenedor(config=Configuracion(ruta_db=Path(":memory:")), conexion=db)
    contenedor.copiloto.orquestador = OrquestadorIA(ConfiguracionIA(proveedor_preferido="local_reglas"))
    with db:
        repo = RepositorioUsuarios(db)
        repo.crear("admin", generar_hash("1234", iteraciones=ITERACIONES_TEST), Rol.ADMIN, "Admin")
        repo.crear("oper", generar_hash("1234", iteraciones=ITERACIONES_TEST), Rol.OPERADOR, "Operador")
    app = crear_app(contenedor)
    return TestClient(app), contenedor


def _auth_headers(client: TestClient, usuario: str, clave: str) -> dict[str, str]:
    resp = client.post("/api/auth/login", json={"usuario": usuario, "clave": clave})
    assert resp.status_code == 200
    token = resp.json()["token"]
    return {"Authorization": f"Bearer {token}"}


def test_api_auth_y_rbac(db) -> None:
    client, _cont = _crear_cliente(db)

    assert client.get("/api/health").status_code == 200

    resp_sin_sesion = client.get("/api/radar")
    assert resp_sin_sesion.status_code == 401
    assert resp_sin_sesion.json()["codigo"] == "sesion_expirada"
    assert "incorrectos" not in resp_sin_sesion.json()["detail"].lower()

    resp_clave_mala = client.post(
        "/api/auth/login", json={"usuario": "admin", "clave": "mala"}
    )
    assert resp_clave_mala.status_code == 401
    assert resp_clave_mala.json()["codigo"] == "credenciales_invalidas"

    hdr_admin = _auth_headers(client, "admin", "1234")
    hdr_oper = _auth_headers(client, "oper", "1234")

    assert client.get("/api/auth/me", headers=hdr_admin).json()["usuario"]["rol"] == "admin"
    assert client.get("/api/auth/me", headers=hdr_oper).json()["usuario"]["rol"] == "operador"

    # Operador no puede mutar infraestructura/parcelas críticas -> 403
    resp_403 = client.post(
        "/api/parcelas",
        headers=hdr_oper,
        json={
            "nombre": "Lote Prohibido",
            "cultivo": "Maiz",
            "area_m2": 100,
            "humedad_pct": 40,
            "tipo_suelo": "Franco",
            "riego_auto": True,
        },
    )
    assert resp_403.status_code == 403

    # Logout revoca el token
    assert client.post("/api/auth/logout", headers=hdr_oper).status_code == 200
    assert client.get("/api/auth/me", headers=hdr_oper).status_code == 401


def test_api_flujo_completo_estaciones_parcelas_riego_copiloto_y_hardware(db, tmp_path: Path) -> None:
    client, _cont = _crear_cliente(db)
    hdr = _auth_headers(client, "admin", "1234")

    # 1. Sembrar estaciones y verificar Radar
    r_seed = client.post("/api/estaciones/sembrar-base", headers=hdr)
    assert r_seed.status_code == 200
    estaciones = r_seed.json()["estaciones"]
    assert len(estaciones) == 2
    est_id = estaciones[0]["id"]

    # 2. Ingesta por tramas radio nRF24L01+ con timestamps distintos
    for idx, trama in enumerate(
        (
            "NRF24|terrabit-nodointi|suelo_a=34.0,suelo_b=52.0,temp_aire=24.0,hum_aire=70.0,voltaje=3.95",
            "NRF24|terrabit-nodointi|suelo_a=31.0,suelo_b=51.0,temp_aire=25.0,hum_aire=68.0,voltaje=3.94",
            "NRF24|terrabit-nodointi|suelo_a=28.0,suelo_b=50.5,temp_aire=26.0,hum_aire=65.0,voltaje=3.92",
        )
    ):
        r_tramas = client.post(
            "/api/hardware/tramas",
            headers=hdr,
            json={"lineas": [trama], "ts_epoch_defecto": 1_760_000_000 + idx * 300},
        )
        assert r_tramas.status_code == 200
        assert r_tramas.json()["total_lecturas_insertadas"] > 0

    # 3. Radar, Pulso, Series, Correlación y Narrativa IA offline
    r_radar = client.get("/api/radar", headers=hdr)
    assert r_radar.status_code == 200
    assert r_radar.json()["resumen"]["total_estaciones"] == 2

    assert client.get(f"/api/estaciones/{est_id}/pulso", headers=hdr).status_code == 200
    r_ser = client.get(f"/api/estaciones/{est_id}/series?horas=24", headers=hdr)
    assert r_ser.status_code == 200
    assert "suelo_a" in r_ser.json()["series"]

    r_corr = client.get(
        f"/api/estaciones/{est_id}/correlacion?var_x=suelo_a&var_y=temp_aire", headers=hdr
    )
    assert r_corr.status_code == 200
    assert r_corr.json()["resultado"]["pares_alineados"] == 3

    r_narrar = client.post(f"/api/estaciones/{est_id}/narrar-24h", headers=hdr)
    assert r_narrar.status_code == 200
    assert r_narrar.json()["proveedor_ia"] == "local_reglas"

    # 4. CRUD Parcelas + validación 422
    r_bad = client.post(
        "/api/parcelas",
        headers=hdr,
        json={
            "nombre": "",
            "cultivo": "Invalido",
            "area_m2": -5,
            "humedad_pct": 140,
            "tipo_suelo": "Franco",
            "riego_auto": True,
        },
    )
    assert r_bad.status_code == 422
    assert len(r_bad.json()["problemas"]) >= 3

    r_par = client.post(
        "/api/parcelas",
        headers=hdr,
        json={
            "nombre": "Lote Experimental V6",
            "cultivo": "Tomate",
            "area_m2": 150,
            "humedad_pct": 28,
            "tipo_suelo": "Franco",
            "riego_auto": True,
            "estacion_id": est_id,
        },
    )
    assert r_par.status_code == 201
    parcela_id = r_par.json()["parcela"]["id"]

    # 5. Contexto Riego (5 Candados), Aplicar, Programar e Incidencia
    r_ctx = client.get(f"/api/parcelas/{parcela_id}/riego/contexto", headers=hdr)
    assert r_ctx.status_code == 200
    assert len(r_ctx.json()["recomendacion"]["veredicto_seguridad"]["candados"]) == 5

    r_ap = client.post(
        f"/api/parcelas/{parcela_id}/riego/aplicar",
        headers=hdr,
        json={"umbral_pct": 45, "litros": 40, "fecha_iso": "2026-11-14", "hora": "06:30"},
    )
    assert r_ap.status_code == 200
    assert r_ap.json()["resultado"]["aplicado"] is True
    evento_id = r_ap.json()["resultado"]["evento"]["id"]

    r_prog = client.post(
        f"/api/parcelas/{parcela_id}/riego/programar",
        headers=hdr,
        json={"fecha_iso": "2026-11-15", "hora": "06:00", "litros_solicitados": 60},
    )
    assert r_prog.status_code == 200

    r_inc = client.post(
        "/api/riego/incidencia",
        headers=hdr,
        json={
            "evento_riego_id": evento_id,
            "humedad_a_antes": 28.0,
            "humedad_a_despues": 44.0,
            "humedad_b_antes": 45.0,
            "humedad_b_despues": 48.0,
        },
    )
    assert r_inc.status_code == 200
    assert r_inc.json()["incidencia"]["efectividad"] == "efectivo"

    # 6. Copiloto IA + Aplicar + Rollback + Dataset JSONL
    r_cop = client.post(
        "/api/copiloto/consultar",
        headers=hdr,
        json={
            "mensaje": "En el último riego nos pasamos con el agua y hubo exceso de percolación",
            "estacion_id": est_id,
            "parcela_id": parcela_id,
        },
    )
    assert r_cop.status_code == 200
    inter_id = r_cop.json()["respuesta"]["interaccion"]["id"]
    ajustes = r_cop.json()["respuesta"]["propuesta"]["ajustes_propuestos"]
    if ajustes:
        assert client.post(
            "/api/copiloto/aplicar", headers=hdr, json={"interaccion_id": inter_id}
        ).status_code == 200
        # Al aplicar otra vez un ajuste o probar rollback si hay >= 2 versiones
        r_est_cop = client.get(
            f"/api/copiloto/estado?estacion_id={est_id}&parcela_id={parcela_id}", headers=hdr
        )
        assert r_est_cop.status_code == 200
        assert r_est_cop.json()["version_actual"] >= 1

    r_jsonl = client.get("/api/copiloto/dataset.jsonl", headers=hdr)
    assert r_jsonl.status_code == 200
    assert len(r_jsonl.content) > 0

    # 7. MicroSD scan + import, Búsqueda Ctrl+K, Exportar XLSX/CSV, Sistema Estado
    csv_sd = tmp_path / "data.csv"
    csv_sd.write_text(
        "Uptime,HumedadA,HumedadB,TempAire,HumAire,Presion,TempRaiz,Voltaje,VPD,SessionID\n"
        "2026/11/14 08:00:00,55.0,62.0,22.5,74.0,852.1,20.0,4.05,0.72,1\n",
        encoding="utf-8",
    )
    r_scan = client.post(
        "/api/hardware/microsd/escanear",
        headers=hdr,
        json={"directorios": [str(tmp_path)]},
    )
    assert r_scan.status_code == 200
    assert len(r_scan.json()["archivos"]) == 1

    r_imp = client.post(
        "/api/hardware/microsd/importar",
        headers=hdr,
        json={"estacion_id": est_id, "ruta_archivo": str(csv_sd)},
    )
    assert r_imp.status_code == 200
    assert r_imp.json()["resultado"]["lecturas_nuevas"] >= 1

    r_busq = client.get("/api/sistema/buscar?q=Experimental", headers=hdr)
    assert r_busq.status_code == 200
    assert r_busq.json()["resultado"]["total_hallazgos"] >= 1

    r_xlsx = client.get(f"/api/exportar/xlsx?estacion_id={est_id}", headers=hdr)
    assert r_xlsx.status_code == 200
    assert len(r_xlsx.content) > 500

    r_csv = client.get(f"/api/exportar/csv?estacion_id={est_id}", headers=hdr)
    assert r_csv.status_code == 200
    assert "suelo_a" in r_csv.text

    # Registrar nueva estación
    r_new_est = client.post(
        "/api/estaciones",
        headers=hdr,
        json={
            "codigo": "polylepis-01",
            "nombre": "Páramo Polylepis",
            "tipo": TipoEstacion.CONSERVACION.value,
        },
    )
    assert r_new_est.status_code == 201

    # Archivar parcela
    assert client.delete(f"/api/parcelas/{parcela_id}", headers=hdr).status_code == 200
    assert client.get(f"/api/parcelas/{parcela_id}", headers=hdr).status_code == 404


def test_sesion_persiste_tras_reinicio_de_app_y_estado_wal(tmp_path: Path) -> None:
    from aquaterra.infrastructure.db import abrir_conexion, aplicar_migraciones

    ruta_db = tmp_path / "persistencia.db"
    conn1 = abrir_conexion(ruta_db)
    aplicar_migraciones(conn1)
    cont1 = Contenedor(config=Configuracion(ruta_db=ruta_db), conexion=conn1)
    with conn1:
        RepositorioUsuarios(conn1).crear(
            "admin", generar_hash("1234", iteraciones=ITERACIONES_TEST), Rol.ADMIN, "Admin"
        )
    client1 = TestClient(crear_app(cont1))

    hdr = _auth_headers(client1, "admin", "1234")
    r_seed = client1.post("/api/estaciones/sembrar-base", headers=hdr)
    assert r_seed.status_code == 200
    est_id = r_seed.json()["estaciones"][0]["id"]

    # Verificar estado WAL real y filtro por familia en minúsculas
    r_estado = client1.get("/api/sistema/estado", headers=hdr)
    assert r_estado.status_code == 200
    assert r_estado.json()["sqlite_wal"] is True

    r_filtrado = client1.get("/api/radar?tipo=terrabit_inti", headers=hdr)
    assert r_filtrado.status_code == 200
    assert len(r_filtrado.json()["entradas"]) >= 1

    # Cambio de contraseña y ventana móvil
    me_id = client1.get("/api/auth/me", headers=hdr).json()["usuario"]["id"]
    assert (
        client1.post(
            f"/api/usuarios/{me_id}/clave", headers=hdr, json={"nueva_clave": "5678"}
        ).status_code
        == 200
    )
    assert (
        client1.get(
            f"/api/estaciones/{est_id}/ventana-movil?variable=suelo_a&ventana=1h",
            headers=hdr,
        ).status_code
        == 200
    )

    # Simular reinicio completo de FastAPI / GestorSesiones sobre la misma DB
    conn1.close()
    conn2 = abrir_conexion(ruta_db)
    cont2 = Contenedor(config=Configuracion(ruta_db=ruta_db), conexion=conn2)
    client2 = TestClient(crear_app(cont2))

    r_me_post_restart = client2.get("/api/auth/me", headers=hdr)
    assert r_me_post_restart.status_code == 200
    assert r_me_post_restart.json()["usuario"]["usuario"] == "admin"

    # Logout debe revocar tanto en RAM como en SQLite
    assert client2.post("/api/auth/logout", headers=hdr).status_code == 200
    conn2.close()

    conn3 = abrir_conexion(ruta_db)
    cont3 = Contenedor(config=Configuracion(ruta_db=ruta_db), conexion=conn3)
    client3 = TestClient(crear_app(cont3))
    assert client3.get("/api/auth/me", headers=hdr).status_code == 401
    conn3.close()
