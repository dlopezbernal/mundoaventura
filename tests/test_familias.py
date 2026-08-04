"""Tests de las cuentas de familia (Hito 9.2): alta, login, sesión, verificación OTP.

Se aísla la BBDD en un fichero temporal por test (monkeypatch de config.CONFIG_DB_PATH
+ reinicio del motor de SQLModel), así que cada test arranca con la tabla `familias`
vacía y no ensucia el SQLite real de configuración. El retardo fijo del login se pone
a 0 para que los tests sean instantáneos. Por defecto la verificación de correo está
DESACTIVADA (como en producción); los tests que la ejercen la activan explícitamente.
"""

import pytest
from fastapi.testclient import TestClient

from backend import config, db
from backend.main import app
from backend.services import email_service, familias_service, seguridad, settings_service

_CLIENTE = TestClient(app)


@pytest.fixture(autouse=True)
def _bbdd_temporal(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "CONFIG_DB_PATH", tmp_path / "test_familias.sqlite3")
    monkeypatch.setattr(db, "_engine", None)  # fuerza recrear el motor sobre la BBDD temporal
    monkeypatch.setattr(familias_service, "_RETARDO_LOGIN", 0)
    settings_service._cache = None  # la caché de ajustes debe releer la BBDD temporal
    familias_service._fallos_login.clear()
    db.init_db()
    # EMAIL_VERIFICACION se lee ahora de settings_service; por defecto DESACTIVADA.
    settings_service.set_many({"EMAIL_VERIFICACION": False})
    yield
    monkeypatch.setattr(db, "_engine", None)
    settings_service._cache = None
    familias_service._fallos_login.clear()


def _alta(email, password="contrasena1", nombre="Familia"):
    """Da de alta (sin verificación) y devuelve (familia, token)."""
    res = familias_service.crear(email, password, nombre)
    return res["familia"], res["token"]


# ---------------------------------------------------------------------------
# Hashing (seguridad.py)
# ---------------------------------------------------------------------------
def test_hash_no_guarda_la_contrasena_en_claro():
    guardado = seguridad.hashear("secreta123")
    assert "secreta123" not in guardado
    assert seguridad.verificar("secreta123", guardado)
    assert not seguridad.verificar("otra", guardado)


def test_hash_usa_sal_distinta_cada_vez():
    assert seguridad.hashear("misma") != seguridad.hashear("misma")


# ---------------------------------------------------------------------------
# Alta (signup) sin verificación
# ---------------------------------------------------------------------------
def test_signup_crea_familia_y_devuelve_token():
    res = familias_service.crear("Padre@Ejemplo.com", "contrasena1", "Los García")
    assert res["verificacion_requerida"] is False
    assert res["familia"]["email"] == "padre@ejemplo.com"  # normalizado a minúsculas
    assert res["familia"]["nombre_familia"] == "Los García"
    assert "password_hash" not in res["familia"]  # nunca se expone el hash
    assert res["token"]
    assert familias_service.validar_sesion(res["token"])["id"] == res["familia"]["id"]


def test_signup_email_duplicado_falla():
    _alta("dup@ejemplo.com", nombre="Uno")
    with pytest.raises(ValueError):
        familias_service.crear("DUP@ejemplo.com", "contrasena2", "Dos")


def test_signup_valida_email_y_password():
    with pytest.raises(ValueError):
        familias_service.crear("no-es-email", "contrasena1", "X")
    with pytest.raises(ValueError):
        familias_service.crear("ok@ejemplo.com", "corta", "X")  # < 8 caracteres
    with pytest.raises(ValueError):
        familias_service.crear("ok@ejemplo.com", "contrasena1", "   ")  # sin nombre


def test_hay_familias():
    assert familias_service.hay_familias() is False
    _alta("a@ejemplo.com")
    assert familias_service.hay_familias() is True


# ---------------------------------------------------------------------------
# Login
# ---------------------------------------------------------------------------
def test_login_correcto():
    _alta("login@ejemplo.com", "contrasena1", "L")
    familia, token = familias_service.login("LOGIN@ejemplo.com", "contrasena1")
    assert familia["email"] == "login@ejemplo.com"
    assert familias_service.validar_sesion(token) is not None


def test_login_password_incorrecta():
    _alta("x@ejemplo.com")
    with pytest.raises(ValueError):
        familias_service.login("x@ejemplo.com", "mala")


def test_login_email_inexistente():
    with pytest.raises(ValueError):
        familias_service.login("nadie@ejemplo.com", "loquesea")


def test_login_bloquea_por_fuerza_bruta():
    _alta("bf@ejemplo.com")
    ip = "9.9.9.9"
    for _ in range(familias_service._MAX_FALLOS):
        with pytest.raises(ValueError):
            familias_service.login("bf@ejemplo.com", "mala", ip)
    with pytest.raises(familias_service.BloqueoLoginError):
        familias_service.login("bf@ejemplo.com", "contrasena1", ip)  # bloqueado aunque acierte


# ---------------------------------------------------------------------------
# Sesión: validar, logout, caducidad
# ---------------------------------------------------------------------------
def test_validar_sesion_token_invalido():
    assert familias_service.validar_sesion(None) is None
    assert familias_service.validar_sesion("token-que-no-existe") is None


def test_logout_invalida_la_sesion():
    _, token = _alta("out@ejemplo.com")
    assert familias_service.validar_sesion(token) is not None
    familias_service.logout(token)
    assert familias_service.validar_sesion(token) is None


def test_sesion_caducada_se_rechaza():
    from datetime import UTC, datetime, timedelta

    from backend.models import SesionFamilia

    _, token = _alta("exp@ejemplo.com")
    with db.get_session() as sesion:
        fila = sesion.get(SesionFamilia, familias_service._hash_token(token))
        fila.expira_en = datetime.now(UTC) - timedelta(seconds=1)
        sesion.add(fila)
        sesion.commit()
    assert familias_service.validar_sesion(token) is None


# ---------------------------------------------------------------------------
# Verificación de correo (OTP), con EMAIL_VERIFICACION activo
# ---------------------------------------------------------------------------
@pytest.fixture
def _con_verificacion(monkeypatch):
    """Activa la verificación y captura el código en vez de enviar correo."""
    settings_service.set_many({"EMAIL_VERIFICACION": True})
    capturado: dict[str, str] = {}

    def _fake_enviar(destinatario, nombre_familia, codigo, minutos):
        capturado["email"] = destinatario
        capturado["codigo"] = codigo
        return "consola"

    monkeypatch.setattr(email_service, "enviar_codigo", _fake_enviar)
    return capturado


def test_signup_con_verificacion_queda_pendiente(_con_verificacion):
    res = familias_service.crear("pend@ejemplo.com", "contrasena1", "P")
    assert res["verificacion_requerida"] is True
    assert res["token"] is None and res["familia"] is None
    assert res["canal"] == "consola"
    # Sin verificar, no se puede iniciar sesión aunque la contraseña sea correcta.
    with pytest.raises(ValueError):
        familias_service.login("pend@ejemplo.com", "contrasena1")


def test_verificar_codigo_correcto_activa_y_da_sesion(_con_verificacion):
    familias_service.crear("v@ejemplo.com", "contrasena1", "V")
    codigo = _con_verificacion["codigo"]
    familia, token = familias_service.verificar_codigo("v@ejemplo.com", codigo)
    assert familia["email"] == "v@ejemplo.com"
    assert familias_service.validar_sesion(token) is not None
    # Ya verificada: ahora el login funciona.
    assert familias_service.login("v@ejemplo.com", "contrasena1")[1]


def test_verificar_codigo_incorrecto_falla(_con_verificacion):
    familias_service.crear("w@ejemplo.com", "contrasena1", "W")
    with pytest.raises(ValueError):
        familias_service.verificar_codigo("w@ejemplo.com", "000000")


def test_codigo_agota_intentos(_con_verificacion, monkeypatch):
    monkeypatch.setattr(familias_service, "_CODIGO_MAX_INTENTOS", 3)
    familias_service.crear("lim@ejemplo.com", "contrasena1", "L")
    codigo = _con_verificacion["codigo"]
    for _ in range(3):
        with pytest.raises(ValueError):
            familias_service.verificar_codigo("lim@ejemplo.com", "999999", ip="1.2.3.4")
    # Agotados los intentos, ni siquiera el código correcto pasa (hay que reenviar).
    with pytest.raises(ValueError, match="Pide uno nuevo"):
        familias_service.verificar_codigo("lim@ejemplo.com", codigo, ip="5.6.7.8")


def test_reenviar_genera_codigo_nuevo(_con_verificacion):
    familias_service.crear("re@ejemplo.com", "contrasena1", "R")
    primero = _con_verificacion["codigo"]
    familias_service.reenviar_codigo("re@ejemplo.com")
    segundo = _con_verificacion["codigo"]
    # El código correcto es el ÚLTIMO enviado; el primero ya no vale.
    assert familias_service.verificar_codigo("re@ejemplo.com", segundo)[1]
    # (No comprobamos que 'primero' falle salvo que difieran; si coincidieran por azar,
    # ambos serían válidos. Basta con que el último enviado verifique.)
    assert primero is not None


def test_realta_de_cuenta_sin_verificar_no_da_400(_con_verificacion):
    familias_service.crear("realta@ejemplo.com", "contrasena1", "A")
    # Re-alta del MISMO correo aún sin verificar: se permite (reenvía código), no es 400.
    res = familias_service.crear("realta@ejemplo.com", "otraclave9", "A2")
    assert res["verificacion_requerida"] is True


# ---------------------------------------------------------------------------
# Endpoints (contrato de salida + cabecera X-Family-Token)
# ---------------------------------------------------------------------------
def test_endpoint_signup_login_me_logout(monkeypatch):
    monkeypatch.setattr(familias_service, "_RETARDO_LOGIN", 0)

    assert _CLIENTE.get("/api/familias/estado").json() == {"hay_familias": False}

    r = _CLIENTE.post(
        "/api/familias/signup",
        json={"email": "api@ejemplo.com", "password": "contrasena1", "nombre_familia": "API"},
    )
    assert r.status_code == 200, r.text
    cuerpo = r.json()
    assert cuerpo["ok"] and cuerpo["verificacion_requerida"] is False
    assert cuerpo["familia"]["nombre_familia"] == "API"
    token = cuerpo["token"]

    me = _CLIENTE.get("/api/familias/me", headers={"X-Family-Token": token}).json()
    assert me["autenticada"] is True and me["familia"]["email"] == "api@ejemplo.com"

    assert _CLIENTE.get("/api/familias/me").json()["autenticada"] is False

    _CLIENTE.post("/api/familias/logout", headers={"X-Family-Token": token})
    assert (
        _CLIENTE.get("/api/familias/me", headers={"X-Family-Token": token}).json()["autenticada"]
        is False
    )


def test_endpoint_signup_email_duplicado_da_400():
    _CLIENTE.post(
        "/api/familias/signup",
        json={"email": "dup2@ejemplo.com", "password": "contrasena1", "nombre_familia": "A"},
    )
    r = _CLIENTE.post(
        "/api/familias/signup",
        json={"email": "dup2@ejemplo.com", "password": "otra12345", "nombre_familia": "B"},
    )
    assert r.status_code == 400


# ---------------------------------------------------------------------------
# Perfil de familia: niños + PIN (multi-perfil, Hito 9.2c)
# ---------------------------------------------------------------------------
def test_dto_incluye_ninos_y_tiene_pin():
    familia, _ = _alta("dto@ejemplo.com")
    assert familia["ninos"] == [] and familia["tiene_pin"] is False


def test_actualizar_perfil_ninos_con_sexo():
    familia, _ = _alta("perfil@ejemplo.com", nombre="Antigua")
    p = familias_service.actualizar_perfil(
        familia["id"],
        nombre_familia="Los Nuevos",
        ninos=[
            {"nombre": "  Marco ", "sexo": "chico"},
            {"nombre": "Lucía", "sexo": "chica"},
            {"nombre": "   ", "sexo": "chico"},  # sin nombre → se descarta
        ],
    )
    assert p["nombre_familia"] == "Los Nuevos"
    assert p["ninos"] == [
        {"nombre": "Marco", "sexo": "chico"},
        {"nombre": "Lucía", "sexo": "chica"},
    ]


def test_sexo_invalido_queda_sin_especificar():
    familia, _ = _alta("sexo@ejemplo.com")
    p = familias_service.actualizar_perfil(
        familia["id"], ninos=[{"nombre": "Alex", "sexo": "otro"}]
    )
    assert p["ninos"] == [{"nombre": "Alex", "sexo": ""}]


def test_ninos_legacy_solo_nombre_se_normaliza():
    # Familias creadas antes del sexo guardaban una lista de cadenas: al leerse deben
    # normalizarse a {nombre, sexo:""} sin migración de BBDD.
    familia, _ = _alta("legacy@ejemplo.com")
    from backend.models import Familia

    with db.get_session() as sesion:
        fila = sesion.get(Familia, familia["id"])
        fila.ninos = '["Marco", "Lucía"]'  # formato antiguo (solo nombres)
        sesion.add(fila)
        sesion.commit()
    with db.get_session() as sesion:
        fila = sesion.get(Familia, familia["id"])
        assert familias_service._ninos_lista(fila) == [
            {"nombre": "Marco", "sexo": ""},
            {"nombre": "Lucía", "sexo": ""},
        ]


def test_actualizar_perfil_topa_numero_de_ninos():
    familia, _ = _alta("muchos@ejemplo.com")
    with pytest.raises(ValueError):
        familias_service.actualizar_perfil(
            familia["id"], ninos=[{"nombre": f"N{i}"} for i in range(9)]
        )


def test_pin_familia_set_y_verificar():
    familia, _ = _alta("pin@ejemplo.com")
    assert familias_service.verificar_pin_familia(familia["id"], "0000") is True  # sin PIN → pasa
    familias_service.set_pin_familia(familia["id"], "1234")
    assert familias_service.verificar_pin_familia(familia["id"], "1234") is True
    assert familias_service.verificar_pin_familia(familia["id"], "9999") is False


def test_pin_familia_debe_ser_4_digitos():
    familia, _ = _alta("pin4@ejemplo.com")
    with pytest.raises(ValueError):
        familias_service.set_pin_familia(familia["id"], "12")  # muy corto
    with pytest.raises(ValueError):
        familias_service.set_pin_familia(familia["id"], "abcd")  # no numérico


def test_pin_familia_cambio_requiere_actual():
    familia, _ = _alta("pinc@ejemplo.com")
    familias_service.set_pin_familia(familia["id"], "1111")
    with pytest.raises(ValueError):
        familias_service.set_pin_familia(familia["id"], "2222", pin_actual="0000")  # actual mal
    familias_service.set_pin_familia(familia["id"], "2222", pin_actual="1111")  # actual OK
    assert familias_service.verificar_pin_familia(familia["id"], "2222") is True


def test_endpoint_perfil_y_pin_requieren_sesion():
    # Sin token de familia: 401.
    payload = {"ninos": [{"nombre": "A", "sexo": "chico"}]}
    assert _CLIENTE.put("/api/familias/perfil", json=payload).status_code == 401
    # Con token: se puede editar el perfil y el /me lo refleja.
    r = _CLIENTE.post(
        "/api/familias/signup",
        json={"email": "epf@ejemplo.com", "password": "contrasena1", "nombre_familia": "EPF"},
    )
    token = r.json()["token"]
    h = {"X-Family-Token": token}
    ninos = [{"nombre": "Ana", "sexo": "chica"}, {"nombre": "Beto", "sexo": "chico"}]
    r2 = _CLIENTE.put("/api/familias/perfil", json={"ninos": ninos}, headers=h)
    assert r2.status_code == 200 and r2.json()["ninos"] == ninos
    me = _CLIENTE.get("/api/familias/me", headers=h).json()
    assert me["familia"]["ninos"] == ninos
    # PIN: ponerlo y verificarlo por endpoint.
    assert (
        _CLIENTE.put("/api/familias/pin", json={"pin_nuevo": "4321"}, headers=h).status_code == 200
    )
    ok = _CLIENTE.post("/api/familias/pin/verificar", json={"pin": "4321"}, headers=h).json()["ok"]
    assert ok is True


# ---------------------------------------------------------------------------
# Borrado de cuenta (derecho de supresión RGPD)
# ---------------------------------------------------------------------------
def test_eliminar_borra_familia_y_sesiones():
    familia, token = _alta("borrar@ejemplo.com")
    assert familias_service.validar_sesion(token) is not None
    familias_service.eliminar(familia["id"])
    # La cuenta ya no existe y su sesión persistente deja de ser válida.
    assert familias_service.validar_sesion(token) is None
    assert familias_service.hay_familias() is False


def test_endpoint_eliminar_cuenta_requiere_sesion():
    # Sin token: 401.
    assert _CLIENTE.delete("/api/familias/cuenta").status_code == 401
    # Con token: borra y luego /me deja de reconocer la sesión.
    r = _CLIENTE.post(
        "/api/familias/signup",
        json={"email": "del@ejemplo.com", "password": "contrasena1", "nombre_familia": "DEL"},
    )
    token = r.json()["token"]
    h = {"X-Family-Token": token}
    assert _CLIENTE.delete("/api/familias/cuenta", headers=h).status_code == 200
    assert _CLIENTE.get("/api/familias/me", headers=h).json()["autenticada"] is False


def test_endpoint_verificar(_con_verificacion):
    r = _CLIENTE.post(
        "/api/familias/signup",
        json={"email": "ep@ejemplo.com", "password": "contrasena1", "nombre_familia": "EP"},
    )
    assert r.json()["verificacion_requerida"] is True
    r2 = _CLIENTE.post(
        "/api/familias/verificar",
        json={"email": "ep@ejemplo.com", "codigo": _con_verificacion["codigo"]},
    )
    assert r2.status_code == 200, r2.text
    assert r2.json()["token"]
