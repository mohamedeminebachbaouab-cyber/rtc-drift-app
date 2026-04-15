"""
crypto.py — Chiffrement / dechiffrement des tokens API avec Fernet.
La cle est derivee de la passphrase via PBKDF2 avec un sel aleatoire.
Les tokens chiffres sont embarques directement dans le code (pas de fichier externe).
"""

import os
import hashlib
import base64
from cryptography.fernet import Fernet

_ITERATIONS = 600_000
_SALT_LENGTH = 16
_PASSPHRASE_ENV_VAR = "RCC_TOKEN_PASSPHRASE"
_DEFAULT_PASSPHRASE = "rcc_app_default_passphrase"

# ── Tokens chiffres embarques ──────────────────────────
# Genere par tools/generate_config.py — NE PAS MODIFIER MANUELLEMENT
_ENCRYPTED_TOKENS = {
    "flespi_token": "E3FF8tikk8iKUOs+phj3Pw==.gAAAAABp3gFHME8x7RhnGfDIxHhkofcwOFFKMbFvlr5jn8MZWL3aIBrNDtVaro5jVxVerqFbCfykv7VeIkDiXxCCbu38JRsRvcoB0IDOVHJRGsjY0N-F2IOV22NzzvwjQ2GpNds0RgD5mQ1j5LyGFr3auVlt-fwr9w8Uuesqocjq9TYdTqJMQPU="
}


def derive_key(passphrase: str, salt: bytes) -> bytes:
    """Derive une cle Fernet a partir de la passphrase et d'un sel."""
    key = hashlib.pbkdf2_hmac(
        'sha256',
        passphrase.encode(),
        salt=salt,
        iterations=_ITERATIONS,
    )
    return base64.urlsafe_b64encode(key)


def encrypt_token(token: str, passphrase: str) -> str:
    """Chiffre un token avec un sel aleatoire. Retourne 'base64(salt).ciphertext'."""
    salt = os.urandom(_SALT_LENGTH)
    fernet = Fernet(derive_key(passphrase, salt))
    ciphertext = fernet.encrypt(token.encode()).decode()
    salt_b64 = base64.b64encode(salt).decode()
    return f"{salt_b64}.{ciphertext}"


def decrypt_token(encrypted: str, passphrase: str) -> str:
    """Dechiffre un token au format 'base64(salt).ciphertext'."""
    if '.' not in encrypted:
        raise ValueError("Format de token invalide (format legacy non supporte)")
    salt_b64, ciphertext = encrypted.split('.', 1)
    salt = base64.b64decode(salt_b64)
    fernet = Fernet(derive_key(passphrase, salt))
    return fernet.decrypt(ciphertext.encode()).decode()


def _get_passphrase() -> str:
    """Retourne la passphrase applicative depuis l'environnement ou la valeur par défaut."""
    return os.environ.get(_PASSPHRASE_ENV_VAR, _DEFAULT_PASSPHRASE)


def get_tokens(passphrase: str | None = None) -> dict:
    """Dechiffre tous les tokens embarques et retourne le dict en clair."""
    passphrase = passphrase or _get_passphrase()
    tokens = {}
    for token_name, encrypted_value in _ENCRYPTED_TOKENS.items():
        tokens[token_name] = decrypt_token(encrypted_value, passphrase)
    return tokens
