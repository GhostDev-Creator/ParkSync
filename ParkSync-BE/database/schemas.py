from pydantic import BaseModel, EmailStr, Field, ConfigDict, field_validator
from typing import List, Optional
from datetime import datetime

class VeiculoBase(BaseModel):
    marca: str = Field(..., min_length=2, max_length=50, example="Toyota")
    modelo: str = Field(..., min_length=2, max_length=50, example="Corolla")
    placa: str = Field(..., min_length=7, max_length=10, example="ABC1D23")
    cor: str = Field(..., min_length=2, max_length=30, example="Prata")

class VeiculoResponse(VeiculoBase):
    id: int
    fk_morador_dono: int

    model_config = ConfigDict(from_attributes=True)

class VagaBase(BaseModel):
    numero: str = Field(..., min_length=1, max_length=10, example="A-12")
    coordenadas: List[int] = Field(..., min_items=4, max_items=8, example=[150, 100, 300, 200, 450, 500, 200, 150])

class VagaResponse(VagaBase):
    id: int
    ocupado: bool
    current_plate: Optional[str] = None
    status_conflito: bool
    fk_morador_dono: int

    model_config = ConfigDict(from_attributes=True)

class MoradorBase(BaseModel):
    nome: str = Field(..., min_length=2, max_length=100)
    email: EmailStr
    apartamento: str = Field(..., min_length=1, max_length=10)
    bloco: str = Field(..., min_length=1, max_length=10)

class MoradorResponse(MoradorBase):
    id: int
    criado_em: datetime

    model_config = ConfigDict(from_attributes=True)

class CadastroCompletoRequest(BaseModel):
    nome: str
    email: EmailStr
    senha: str
    apartamento: str
    bloco: str
    marca: str
    modelo: str
    cor: str
    placa: str
    foto_base64: str

    @field_validator('placa')
    @classmethod
    def limpar_placa(cls, value: str) -> str:
        valor_limpo = value.replace("-", "").replace(" ", "").upper()
        if len(valor_limpo) != 7:
            raise ValueError("A placa deve conter exatamente 7 caracteres")
        return valor_limpo

class CoordenadasUpdate(BaseModel):
    coordenadas: List[int] = Field(
        ...,
        description="Lista de coordenadas dos 4 pontos marcados no canvas [x1,y1,x2,y2...]"
    )

class VeiculoTemporarioBase(BaseModel):
    placa_veiculo_temporario: str = Field(..., min_length=7, max_length=10)
    status: str = Field(default="DENTRO")

class VisitanteBase(BaseModel):
    nome: str = Field(..., min_length=2, max_length=100)
    cpf: str = Field(..., min_length=11, max_length=14, example="123.456.789-00")
    cnh: Optional[str] = Field(None, max_length=20)
    placa_veiculo: str = Field(..., min_length=7, max_length=10)

class AgendamentoVisitaBase(BaseModel):
    data_entrada_prevista: datetime
    data_saida_prevista: datetime
    ativo: bool = True

class LogAcessoExternoBase(BaseModel):
    placa_detectada: str
    tipo_acesso: str
    path_foto_capturada: str

class LogVisitanteBase(BaseModel):
    path_foto_capturada: str
    visitante_nome: str
    visitante_cpf: str
    visitante_cnh: str
    visitante_placa: str
    morador_anfitriao_nome: str
    apartamento_visitado: str
    bloco_visitado: str

class AlertaPainelBase(BaseModel):
    texto: str = Field(..., max_length=255)
    ativo: bool = False

class TriggerEvent(BaseModel):
    evento: str

class LoginRequest(BaseModel):
    email: EmailStr
    senha: str

class UpdateSenhaRequest(BaseModel):
    email: EmailStr
    nova_senha: str

class VeiculoUpdate(BaseModel):
    modelo: str
    placa: str

class VisitanteCadastroRequest(BaseModel):
    fk_id_morador: int
    nome: str
    cnh: Optional[str] = None
    cpf: str
    placa_veiculo: str
    tipo_visita: str
    horario_inicio: Optional[str] = None
    horario_fim: Optional[str] = None

class AgendamentoUpdate(BaseModel):
    tipo_visita: str
    horario_inicio: Optional[str] = None
    horario_fim: Optional[str] = None