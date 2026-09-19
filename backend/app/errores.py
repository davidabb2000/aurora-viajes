class ErrorDeDominio(Exception):
    codigo = "error_de_dominio"

    def __init__(self, mensaje: str):
        self.mensaje = mensaje
        super().__init__(mensaje)


class RecursoNoEncontrado(ErrorDeDominio):
    codigo = "recurso_no_encontrado"

    def __init__(self, recurso: str, identificador: int | str):
        super().__init__(f"No existe {recurso} con identificador {identificador}.")


class ConflictoDeNegocio(ErrorDeDominio):
    codigo = "conflicto_de_negocio"


class NoAutenticado(ErrorDeDominio):
    codigo = "no_autenticado"

    def __init__(self, mensaje: str = "Credenciales ausentes o inválidas."):
        super().__init__(mensaje)


class PermisoDenegado(ErrorDeDominio):
    codigo = "permiso_denegado"

    def __init__(self, mensaje: str = "No tiene permiso para realizar esta operación."):
        super().__init__(mensaje)


class DemasiadasPeticiones(ErrorDeDominio):
    """El cliente supero el numero de intentos permitidos en la ventana."""

    codigo = "demasiadas_peticiones"

    def __init__(self, segundos_restantes: int):
        self.segundos_restantes = segundos_restantes
        super().__init__(
            f"Demasiados intentos. Espera {segundos_restantes} segundos antes de volver a intentarlo."
        )
