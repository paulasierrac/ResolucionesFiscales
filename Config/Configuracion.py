from azure.identity import ClientSecretCredential
from azure.keyvault.secrets import SecretClient
import os

# NOTA: este modulo NO llama load_dotenv() ni lee os.getenv(...) a nivel de
# modulo. Antes lo hacia una sola vez, en el primer import, y quedaba
# cacheado -- si ese primer import ocurria antes de que el .env estuviera
# cargado (o si su propio load_dotenv() encontraba otro archivo .env por el
# camino), _CLIENT_ID etc. quedaban vacios para el resto del proceso aunque
# despues el .env se cargara bien. Ahora se lee os.environ en cada llamada a
# CargarVault(), y quien llama (Funciones.utils.obtener_config) es responsable
# de haber cargado el .env correcto antes.


# ─────────────────────────────────────────────
#  CARGA DE SECRETOS DESDE VAULT
# ─────────────────────────────────────────────
def CargarVault(filtro_tags: dict = None, strip_prefix: str = None, nombres: list[str] = None) -> dict:
    """
    Conecta al Key Vault y descarga secretos.

    Parámetros:
      filtro_tags  : Solo descarga secretos que tengan TODAS estas etiquetas.
                     Ej: {"project": "AutorizacionesMasivo", "environment": "dev"}
      strip_prefix : Elimina este prefijo del nombre antes de convertirlo a clave.
                     Ej: "AutorizacionesMasivo-SAPUser" → "SAPUSER"

    Retorna dict { clave: valor }
    """
    vault_url     = os.getenv("VAULT_URL")
    tenant_id     = os.getenv("TENANT_ID")
    client_id     = os.getenv("CLIENT_ID")
    client_secret = os.getenv("CLIENT_SECRET")

    faltantes = [n for n, v in (("VAULT_URL", vault_url), ("TENANT_ID", tenant_id),
                                 ("CLIENT_ID", client_id), ("CLIENT_SECRET", client_secret)) if not v]
    if faltantes:
        raise ValueError(
            f"CargarVault: faltan variables de entorno {faltantes}. "
            f"Verificar que el .env se cargo antes de llamar CargarVault()."
        )

    credential = ClientSecretCredential(
        tenant_id     = tenant_id,
        client_id     = client_id,
        client_secret = client_secret,
    )
    client   = SecretClient(vault_url=vault_url, credential=credential)
    secretos = {}

    for prop in client.list_properties_of_secrets():

        # ── Filtrar por etiquetas ──
        if filtro_tags:
            tags_secreto = prop.tags or {}
            if not all(tags_secreto.get(k) == v for k, v in filtro_tags.items()):
                continue

        # ── Filtrar por nombre exacto ──
        if nombres:
            if prop.name not in nombres:
                continue

        # ── Limpiar prefijo del nombre ──
        nombre = prop.name
        if strip_prefix and nombre.upper().startswith(strip_prefix.upper()):
            nombre = nombre[len(strip_prefix):]
            nombre = nombre.lstrip("-")

        valor  = client.get_secret(prop.name).value
        clave  = nombre.replace("-", "_").upper()
        secretos[clave] = valor

    return secretos