# Arquivo: Back-End/schemas.py

import re
from typing import List, Optional, Union

from pydantic import BaseModel, EmailStr, Field, field_validator

from utils.placa import limpar_placa_digitada


def normalizar_coordenadas(coords):
    """
    Aceita os dois formatos e devolve SEMPRE a lista plana de 8 inteiros:
      [x1, y1, x2, y2, x3, y3, x4, y4]   (o que o vagas.html envia)
      [[x1, y1], [x2, y2], ...]          (formato de pontos)
    Devolve None se não houver exatamente 4 pontos válidos.
    """
    if not coords:
        return None
    if all(isinstance(p, (list, tuple)) for p in coords):
        if any(len(p) != 2 for p in coords):
            return None
        plano = [v for p in coords for v in p]
    else:
        plano = list(coords)
    try:
        plano = [int(round(float(v))) for v in plano]
    except (TypeError, ValueError):
        return None
    return plano if len(plano) == 8 else None


def _normalizar_tipo_visita(v: str) -> str:
    v = (v or "").strip().lower()
    if v in ("single", "unica", "única"):
        return "unica"
    if v in ("period", "periodo", "período"):
        return "periodo"
    raise ValueError("tipo_visita deve ser 'single' (única) ou 'period' (período).")


def _validar_placa(valor: str) -> str:
    placa = limpar_placa_digitada(valor)
    if not placa:
        raise ValueError("Placa inválida. Use o formato ABC1D23 (Mercosul) ou ABC1234.")
    return placa


# ==========================
# MORADOR
# ==========================
class MoradorCreate(BaseModel):
    nome: str = Field(..., min_length=2, max_length=100)
    email: EmailStr
    senha: str = Field(..., min_length=4)
    bloco: str = Field(..., min_length=1, max_length=50)
    apartamento: str = Field(..., min_length=1, max_length=50)
    placa: str
    marca: Optional[str] = "Não informada"
    modelo: Optional[str] = "Não informado"
    cor: Optional[str] = "Não informada"
    foto_base64: str

    @field_validator("placa")
    @classmethod
    def placa_valida(cls, v):
        return _validar_placa(v)

    @field_validator("bloco", "apartamento", "nome")
    @classmethod
    def sem_espacos_sobrando(cls, v):
        return v.strip()

    @field_validator("bloco")
    @classmethod
    def bloco_maiusculo(cls, v):
        return v.upper()


class MoradorLogin(BaseModel):
    email: EmailStr
    senha: str


class TrocarSenha(BaseModel):
    email: EmailStr
    senha_atual: str = Field(..., min_length=1)
    nova_senha: str = Field(..., min_length=4)


class SolicitacaoRecuperacao(BaseModel):
    email: EmailStr


class ValidacaoCodigo(BaseModel):
    email: EmailStr
    codigo: str


class RedefinicaoSenha(BaseModel):
    email: EmailStr
    codigo: str
    nova_senha: str = Field(..., min_length=4)


# ==========================
# VEÍCULO
# ==========================
class VeiculoUpdate(BaseModel):
    placa: str
    modelo: Optional[str] = None
    marca: Optional[str] = None
    cor: Optional[str] = None

    @field_validator("placa")
    @classmethod
    def placa_valida(cls, v):
        return _validar_placa(v)


# ==========================
# VISITANTE
# ==========================
class VisitanteCreate(BaseModel):
    nome: str = Field(..., min_length=2, max_length=100)
    cpf: Optional[str] = None  # opcional: vazio ou "00000000000" vira NULL
    cnh: Optional[str] = None
    placa_veiculo: str
    tipo_visita: str  # "single"/"unica" (12 h a partir de agora) ou "period"/"periodo"
    fk_id_morador: int
    horario_inicio: Optional[str] = None  # "dd/mm/aaaa hh:mm"
    horario_fim: Optional[str] = None

    @field_validator("placa_veiculo")
    @classmethod
    def placa_valida(cls, v):
        return _validar_placa(v)

    @field_validator("cpf")
    @classmethod
    def cpf_opcional(cls, v):
        if v is None:
            return None
        digitos = re.sub(r"\D", "", v)
        if digitos == "" or set(digitos) == {"0"}:
            return None
        if len(digitos) != 11:
            raise ValueError("CPF deve ter 11 dígitos (ou deixe em branco).")
        return digitos

    @field_validator("cnh")
    @classmethod
    def cnh_opcional(cls, v):
        return (v or "").strip() or None

    @field_validator("tipo_visita")
    @classmethod
    def tipo_valido(cls, v):
        return _normalizar_tipo_visita(v)


class AgendamentoUpdate(BaseModel):
    tipo_visita: str
    horario_inicio: Optional[str] = None
    horario_fim: Optional[str] = None
    placa_veiculo: Optional[str] = None

    @field_validator("tipo_visita")
    @classmethod
    def tipo_valido(cls, v):
        return _normalizar_tipo_visita(v)

    @field_validator("placa_veiculo")
    @classmethod
    def placa_valida(cls, v):
        return _validar_placa(v) if v else None


# ==========================
# VAGAS
# ==========================
class CoordenadasVaga(BaseModel):
    """
    Aceita os dois formatos e guarda sempre a lista PLANA de 8 inteiros:
      {"coordenadas": [x1, y1, x2, y2, x3, y3, x4, y4]}      <- o vagas.html manda assim
      {"coordenadas": [[x1, y1], [x2, y2], [x3, y3], [x4, y4]]}
    """
    coordenadas: List[Union[int, float, List[Union[int, float]]]]

    @field_validator("coordenadas")
    @classmethod
    def quatro_pontos(cls, v):
        plano = normalizar_coordenadas(v)
        if plano is None:
            raise ValueError("Envie exatamente 4 pontos (8 números: x1, y1, ..., x4, y4).")
        if any(n < 0 for n in plano):
            raise ValueError("Coordenadas não podem ser negativas.")
        return plano


class VagaMapeada(CoordenadasVaga):
    numero: str


class CoordenadasLote(BaseModel):
    """Salva várias vagas de uma vez: [{"numero": "101A", "coordenadas": [...]}, ...]"""
    vagas: List[VagaMapeada] = Field(..., min_length=1)


# ==========================
# PORTARIA / INTERNO
# ==========================
class TriggerEvent(BaseModel):
    evento: str


class AberturaManual(BaseModel):
    motivo: Optional[str] = "Liberação manual pelo porteiro"
