from cryptography.fernet import Fernet, InvalidToken


class BiometricKeyMissingError(RuntimeError):
    pass


class BiometricTemplateInvalidError(RuntimeError):
    pass


class BiometricCipher:
    def __init__(self, encoded_key: str | None) -> None:
        if not encoded_key:
            raise BiometricKeyMissingError("BIOMETRIC_ENCRYPTION_KEY is not configured")
        try:
            self._fernet = Fernet(encoded_key.encode("ascii"))
        except (ValueError, UnicodeEncodeError) as exc:
            raise BiometricKeyMissingError("BIOMETRIC_ENCRYPTION_KEY is invalid") from exc

    def encrypt(self, value: bytes) -> bytes:
        return self._fernet.encrypt(value)

    def decrypt(self, value: bytes) -> bytes:
        try:
            return self._fernet.decrypt(value)
        except InvalidToken as exc:
            raise BiometricTemplateInvalidError("Stored biometric template cannot be decrypted") from exc
