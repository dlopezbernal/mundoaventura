"""Tests del anti-fuerza-bruta del login de admin (H2, tarea 6).

Se stubea el hash guardado y la verificación para no tocar la BBDD: lo que se
prueba es la lógica de bloqueo por IP, no el hashing (ya cubierto aparte).
El retardo fijo del login se pone a 0 para que los tests sean instantáneos.
"""

import pytest

from backend.services import admin_service


@pytest.fixture(autouse=True)
def _entorno(monkeypatch):
    admin_service._fallos_login.clear()
    monkeypatch.setattr(admin_service, "_RETARDO_LOGIN", 0)  # sin espera en tests
    monkeypatch.setattr(admin_service, "_leer_hash", lambda: "salt$hash")  # hay contraseña
    yield
    admin_service._fallos_login.clear()


def test_bloqueo_tras_demasiados_fallos(monkeypatch):
    monkeypatch.setattr(admin_service, "_verificar", lambda secreto, guardado: False)
    ip = "1.2.3.4"
    # Los primeros _MAX_FALLOS intentos fallan con "Contraseña incorrecta" (400).
    for _ in range(admin_service._MAX_FALLOS):
        with pytest.raises(ValueError):
            admin_service.login("0000", ip)
    # El siguiente ya está bloqueado temporalmente (→ 429).
    with pytest.raises(admin_service.BloqueoLoginError):
        admin_service.login("0000", ip)


def test_el_bloqueo_es_por_ip(monkeypatch):
    monkeypatch.setattr(admin_service, "_verificar", lambda secreto, guardado: False)
    for _ in range(admin_service._MAX_FALLOS):
        with pytest.raises(ValueError):
            admin_service.login("0000", "1.1.1.1")
    # Otra IP arranca con la cuenta limpia: sigue siendo ValueError, no bloqueo.
    with pytest.raises(ValueError):
        admin_service.login("0000", "2.2.2.2")


def test_login_correcto_limpia_los_fallos(monkeypatch):
    veredictos = iter([False, False, True])  # 2 fallos y luego acierto
    monkeypatch.setattr(admin_service, "_verificar", lambda secreto, guardado: next(veredictos))
    monkeypatch.setattr(admin_service, "_crear_token", lambda: "tok")
    ip = "3.3.3.3"
    for _ in range(2):
        with pytest.raises(ValueError):
            admin_service.login("x", ip)
    assert admin_service.login("x", ip) == "tok"
    assert ip not in admin_service._fallos_login  # el acierto borra los fallos
