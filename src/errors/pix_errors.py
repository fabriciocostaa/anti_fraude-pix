from errors.base_error import QIException


class PixNotFound(QIException):
    code = "PIX000001"
    def __init__(self):
        super().__init__("Pix not found", self.code, 404, "No analysis exists for this Pix ID.", "Análise Pix não encontrada.")


class PixConflict(QIException):
    code = "PIX000002"
    def __init__(self):
        super().__init__("Pix conflict", self.code, 409, "This Pix ID already has different content.", "O ID do Pix já foi utilizado com outro conteúdo.")


class DependencyUnavailable(QIException):
    code = "PIX000003"
    def __init__(self, provider):
        super().__init__("Dependency unavailable", self.code, 503, f"Could not obtain a valid response from {provider}.", "Não foi possível consultar a fonte necessária para a análise.")
