"""Errores propios del paquete de contratos, sin dependencias web."""


class ContractViolation(Exception):  # noqa: N818 - nombre del contrato (P-U0-02, P-U0-03)
    """Se intento usar el contrato de una forma que el diseno prohibe."""


class DataIntegrityError(RuntimeError):
    """Un archivo de datos no coincide con su checksum (NFR-U0-20)."""
