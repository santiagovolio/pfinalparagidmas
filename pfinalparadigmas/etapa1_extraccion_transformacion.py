"""
ETAPA 1: EXTRACCION Y TRANSFORMACION DE DATOS

A. Extraccion declarativa CON SQLITE3
B. Transformacion funcional (funciones puras + map / filter / lambda SIN USAR CICLOS)

"""
import re
import sqlite3
from datetime import datetime, timezone
from functools import reduce

DB_NAME = "fintech_transacciones.db"

# A. EXTRACCION 

QUERY_EXTRACCION = """
SELECT
    t.id            AS id_transaccion,
    u.pais          AS pais_usuario,
    c.categoria     AS categoria_comercio,
    t.monto_original,
    t.moneda,
    t.fecha_hora,
    t.estado
FROM Transacciones AS t
LEFT JOIN Usuarios  AS u ON t.usuario_id  = u.id
LEFT JOIN Comercios AS c ON t.comercio_id = c.id
ORDER BY t.id;
"""


def fila_a_dict(cursor, fila):
    """row_factory: convierte cada fila en diccionario {columna: valor}."""
    columnas = map(lambda d: d[0], cursor.description)
    return dict(zip(columnas, fila))


def extraer(db_path=DB_NAME):
    """Ejecuta la consulta SQL y devuelve una tupla de diccionarios."""
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = fila_a_dict
        return tuple(conn.execute(QUERY_EXTRACCION).fetchall())

# B. TRANSFORMACION (Logica funcional)

# Fechas corruptas: None, 'N/A', timestamps UNIX

def fecha_valida(registro):
    """True si fecha_hora no es None ni 'N/A'."""
    fecha = registro["fecha_hora"]
    return fecha is not None and str(fecha).strip().upper() != "N/A"


def es_timestamp_unix(valor):
    """True si el valor contiene solo digitos."""
    return str(valor).strip().isdigit()


def unix_a_iso(valor):
    """Convierte un timestamp UNIX a texto ISO 8601.
    Se usa UTC para que el resultado no dependa de la zona horaria del equipo."""
    return (
        datetime.fromtimestamp(int(valor), tz=timezone.utc)
        .replace(tzinfo=None)
        .isoformat()
    )


def normalizar_fecha(registro):
    """Devuelve un registro nuevo con fecha_hora en ISO 8601."""
    fecha = registro["fecha_hora"]
    return {
        **registro,
        "fecha_hora": unix_a_iso(fecha) if es_timestamp_unix(fecha) else str(fecha),
    }


# Montos corruptos: strings con simbolo, negativos, basura

def limpiar_texto_monto(valor):
    """Despoja todo caracter que no sea digito, punto o signo negativo."""
    return re.sub(r"[^0-9.\-]", "", str(valor))


def parsear_monto(valor):
    """Convierte el monto a float absoluto. Devuelve None si no es parseable."""
    texto = limpiar_texto_monto(valor)
    return abs(float(texto)) if re.fullmatch(r"-?\d+(\.\d+)?", texto) else None


def normalizar_monto(registro):
    """Devuelve un registro nuevo con monto_original como float positivo."""
    return {**registro, "monto_original": parsear_monto(registro["monto_original"])}


def monto_valido(registro):
    """Descarta montos que no pudieron convertirse a numero."""
    return registro["monto_original"] is not None


# Datos faltantes del usuario 

def normalizar_pais(registro):
    """Devuelve un registro nuevo con pais_usuario = 'Internacional' si es nulo."""
    pais = registro["pais_usuario"]
    return {**registro, "pais_usuario": pais if pais is not None else "Internacional"}


# Pipeline de transformacion

PASOS = (
    lambda datos: filter(fecha_valida, datos),
    lambda datos: map(normalizar_fecha, datos),
    lambda datos: map(normalizar_monto, datos),
    lambda datos: filter(monto_valido, datos),
    lambda datos: map(normalizar_pais, datos),
)


def transformar(registros):
    """Aplica los pasos en orden y devuelve una tupla de registros limpios."""
    return tuple(reduce(lambda acumulado, paso: paso(acumulado), PASOS, registros))

# EJECUCION

def contar(predicado, datos):
    """Cuenta elementos que cumplen un predicado."""
    return sum(map(lambda r: 1 if predicado(r) else 0, datos))


if __name__ == "__main__":
    crudos = extraer()
    limpios = transformar(crudos)

    resumen = (
        ("Registros extraidos", len(crudos)),
        ("Fechas None / 'N/A' descartadas", contar(lambda r: not fecha_valida(r), crudos)),
        ("Timestamps UNIX convertidos", contar(lambda r: fecha_valida(r) and es_timestamp_unix(r["fecha_hora"]), crudos)),
        ("Montos string con simbolo", contar(lambda r: isinstance(r["monto_original"], str), crudos)),
        ("Montos negativos corregidos", contar(lambda r: isinstance(r["monto_original"], (int, float)) and r["monto_original"] < 0, crudos)),
        ("Paises nulos -> 'Internacional'", contar(lambda r: r["pais_usuario"] is None, crudos)),
        ("Registros limpios finales", len(limpios)),
    )
    print("\n".join(map(lambda par: f"{par[0]:<35}: {par[1]:>6}", resumen)))

    print("\nMuestra:")
    print("\n".join(map(str, limpios[:5])))
