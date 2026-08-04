"""Tests de las DOS barreras de los endpoints caros del niño (chat, generación, voz).

1. Candado del túnel (H2, tarea 5): cuando ACCESS_CODE está configurado se exige la
   cabecera X-Access-Code correcta; si no, 401. Con ACCESS_CODE vacío queda desactivado.
2. Sesión de familia (despliegue en servidor): con EXIGIR_SESION_FAMILIA=true se exige
   ADEMÁS un X-Family-Token válido, porque ACCESS_CODE viaja dentro del bundle de la SPA
   y por tanto no es un secreto de verdad.

Se usa TestClient SIN context manager (no dispara el lifespan → ni red ni seeding); el
401 lo produce la dependencia antes de llegar al cuerpo del endpoint. El fixture autouse
de conftest.py deja EXIGIR_SESION_FAMILIA en false; los tests de la barrera 2 lo activan.
"""

import pytest
from fastapi.testclient import TestClient

from backend import config, db
from backend.main import app
from backend.services import familias_service, settings_service

_CLIENTE = TestClient(app)


def test_sin_codigo_es_401(monkeypatch):
    monkeypatch.setattr(config, "ACCESS_CODE", "secreto")
    r = _CLIENTE.post("/api/ask", json={"personaje_id": "t-rex", "pregunta": "hola"})
    assert r.status_code == 401


def test_codigo_incorrecto_es_401(monkeypatch):
    monkeypatch.setattr(config, "ACCESS_CODE", "secreto")
    r = _CLIENTE.post(
        "/api/ask",
        json={"personaje_id": "t-rex", "pregunta": "hola"},
        headers={"X-Access-Code": "otro"},
    )
    assert r.status_code == 401


def test_generate_tambien_esta_protegido(monkeypatch):
    monkeypatch.setattr(config, "ACCESS_CODE", "secreto")
    r = _CLIENTE.post(
        "/api/generate", json={"personaje_id": "t-rex", "ubicacion_id": "laboratorio"}
    )
    assert r.status_code == 401


def test_codigo_correcto_pasa_el_candado(monkeypatch):
    # Con el código correcto, el candado deja pasar y ya se aplica la validación
    # del cuerpo: una pregunta demasiado larga da 422 (NO 401), lo que prueba que
    # el candado se superó.
    monkeypatch.setattr(config, "ACCESS_CODE", "secreto")
    r = _CLIENTE.post(
        "/api/ask",
        json={"personaje_id": "t-rex", "pregunta": "x" * 1000},
        headers={"X-Access-Code": "secreto"},
    )
    assert r.status_code == 422


def test_candado_desactivado_no_pide_codigo(monkeypatch):
    # ACCESS_CODE vacío = sin candado: sin cabecera NO da 401 (llega a validación).
    monkeypatch.setattr(config, "ACCESS_CODE", "")
    r = _CLIENTE.post("/api/ask", json={"personaje_id": "t-rex", "pregunta": "x" * 1000})
    assert r.status_code == 422  # 422 por la pregunta larga, no 401


# ---------------------------------------------------------------------------
# Barrera 2: sesión de familia en los endpoints caros (EXIGIR_SESION_FAMILIA)
# ---------------------------------------------------------------------------
@pytest.fixture
def _con_sesion_de_familia(tmp_path, monkeypatch):
    """Activa la puerta y devuelve el token de una familia real recién creada.

    Se aísla la BBDD en un fichero temporal (mismo patrón que test_familias.py) para
    no ensuciar el SQLite de configuración con familias de prueba.
    """
    monkeypatch.setattr(config, "ACCESS_CODE", "")  # aquí probamos la barrera 2, no la 1
    monkeypatch.setattr(config, "EXIGIR_SESION_FAMILIA", True)
    monkeypatch.setattr(config, "CONFIG_DB_PATH", tmp_path / "test_acceso.sqlite3")
    monkeypatch.setattr(db, "_engine", None)
    settings_service._cache = None
    db.init_db()
    settings_service.set_many({"EMAIL_VERIFICACION": False})
    token = familias_service.crear("padre@ejemplo.com", "contrasena1", "Familia")["token"]
    yield token
    monkeypatch.setattr(db, "_engine", None)
    settings_service._cache = None


@pytest.mark.parametrize(
    ("ruta", "cuerpo"),
    [
        ("/api/ask", {"personaje_id": "t-rex", "pregunta": "hola"}),
        ("/api/ask/stream", {"personaje_id": "t-rex", "pregunta": "hola"}),
        ("/api/generate", {"personaje_id": "t-rex", "ubicacion_id": "laboratorio"}),
    ],
)
def test_endpoints_caros_exigen_sesion_de_familia(_con_sesion_de_familia, ruta, cuerpo):
    # Sin X-Family-Token, los tres endpoints que gastan dinero cortan con 401 antes
    # de llamar a ningún proveedor. Es lo que impide que un desconocido con curl
    # queme el saldo de Replicate/ElevenLabs conociendo solo la URL pública.
    assert _CLIENTE.post(ruta, json=cuerpo).status_code == 401


def test_token_de_familia_invalido_es_401(_con_sesion_de_familia):
    r = _CLIENTE.post(
        "/api/ask",
        json={"personaje_id": "t-rex", "pregunta": "hola"},
        headers={"X-Family-Token": "inventado"},
    )
    assert r.status_code == 401


def test_token_de_familia_valido_pasa_la_puerta(_con_sesion_de_familia):
    # Con sesión válida se supera la puerta y ya actúa la validación del cuerpo:
    # un 422 por pregunta demasiado larga prueba que el 401 quedó atrás.
    r = _CLIENTE.post(
        "/api/ask",
        json={"personaje_id": "t-rex", "pregunta": "x" * 1000},
        headers={"X-Family-Token": _con_sesion_de_familia},
    )
    assert r.status_code == 422


def test_toggle_desactivado_devuelve_el_comportamiento_previo(monkeypatch):
    # EXIGIR_SESION_FAMILIA=false reproduce el comportamiento anterior al despliegue
    # en servidor: sin sesión NO hay 401 (se llega a la validación del cuerpo).
    monkeypatch.setattr(config, "ACCESS_CODE", "")
    monkeypatch.setattr(config, "EXIGIR_SESION_FAMILIA", False)
    r = _CLIENTE.post("/api/ask", json={"personaje_id": "t-rex", "pregunta": "x" * 1000})
    assert r.status_code == 422


def test_los_catalogos_siguen_siendo_publicos(monkeypatch):
    # La puerta es SOLO para los endpoints caros. Los catálogos que el frontend
    # necesita para pintar la pantalla de login siguen abiertos, o la app no
    # arrancaría antes de tener sesión.
    monkeypatch.setattr(config, "EXIGIR_SESION_FAMILIA", True)
    assert _CLIENTE.get("/health").status_code == 200
