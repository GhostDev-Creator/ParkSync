# Arquivo: Back-End/database/models.py
#
# Modelo em 3FN:
# - Bloco/apartamento ficam só em Unidade (morador aponta para a unidade).
# - Vaga pertence à Unidade (1 vaga por unidade): "vaga N <-> apto N".
# - Placa do visitante fica no agendamento (cada visita pode vir com um carro).
# - Logs e alertas apontam por FK (sem procurar nome dentro de texto).

import enum
from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, DateTime, JSON, UniqueConstraint, Enum
from sqlalchemy.orm import relationship
from database.setup_db import Base


class DirecaoEnum(str, enum.Enum):
    ENTRADA = "ENTRADA"
    SAIDA = "SAIDA"


class TipoAcessoEnum(str, enum.Enum):
    MORADOR = "MORADOR"
    VISITANTE = "VISITANTE"
    TEMPORARIO = "TEMPORARIO"
    NEGADO = "NEGADO"
    MANUAL = "MANUAL"


class StatusTemporarioEnum(str, enum.Enum):
    DENTRO = "DENTRO"
    SAIU = "SAIU"


class Unidade(Base):
    __tablename__ = "unidades"
    id = Column(Integer, primary_key=True, index=True)
    bloco = Column(String(50), nullable=False)
    apartamento = Column(String(50), nullable=False)

    __table_args__ = (UniqueConstraint("bloco", "apartamento", name="uix_bloco_apto"),)

    moradores = relationship("Morador", back_populates="unidade")
    vaga = relationship("Vaga", back_populates="unidade", uselist=False)


class Morador(Base):
    __tablename__ = "moradores"
    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String(100), nullable=False)
    email = Column(String(100), unique=True, index=True, nullable=False)
    senha_hash = Column(String(255), nullable=False)
    # Vetor de 128 números do face_recognition. É um valor atômico para o sistema
    # (sempre lido e comparado inteiro), por isso não fere a 1FN.
    face_encoding = Column(JSON, nullable=True)
    fk_unidade = Column(Integer, ForeignKey("unidades.id"), nullable=False)
    criado_em = Column(DateTime, default=datetime.now)

    unidade = relationship("Unidade", back_populates="moradores")
    veiculos = relationship("Veiculo", back_populates="dono", cascade="all, delete-orphan")
    agendamentos = relationship("AgendamentoVisita", back_populates="morador")


class Veiculo(Base):
    __tablename__ = "veiculos"
    id = Column(Integer, primary_key=True, index=True)
    placa = Column(String(10), unique=True, index=True, nullable=False)
    marca = Column(String(50))
    modelo = Column(String(50))
    cor = Column(String(50))
    fk_morador = Column(Integer, ForeignKey("moradores.id"), nullable=False)

    dono = relationship("Morador", back_populates="veiculos")


class Vaga(Base):
    __tablename__ = "vagas"
    id = Column(Integer, primary_key=True, index=True)
    numero = Column(String(50), unique=True, nullable=False)
    fk_unidade = Column(Integer, ForeignKey("unidades.id"), unique=True, nullable=True)
    # Lista PLANA [x1, y1, x2, y2, x3, y3, x4, y4] na escala da tela do vagas.html (800x600)
    coordenadas = Column(JSON, nullable=True)
    ocupada = Column(Boolean, default=False)
    current_plate = Column(String(10), nullable=True)
    status_conflito = Column(Boolean, default=False)

    unidade = relationship("Unidade", back_populates="vaga")


class Visitante(Base):
    __tablename__ = "visitantes"
    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String(100), nullable=False)
    # CPF opcional. NULL não conflita com o UNIQUE (vários visitantes sem CPF podem existir).
    cpf = Column(String(11), unique=True, index=True, nullable=True)
    cnh = Column(String(20), nullable=True)

    agendamentos = relationship("AgendamentoVisita", back_populates="visitante")


class AgendamentoVisita(Base):
    __tablename__ = "agendamentos_visita"
    id = Column(Integer, primary_key=True, index=True)
    fk_morador = Column(Integer, ForeignKey("moradores.id"), nullable=False)
    fk_visitante = Column(Integer, ForeignKey("visitantes.id"), nullable=False)
    placa_veiculo = Column(String(10), nullable=True, index=True)
    inicio = Column(DateTime, nullable=False)
    fim = Column(DateTime, nullable=False)
    cancelado = Column(Boolean, default=False)

    morador = relationship("Morador", back_populates="agendamentos")
    visitante = relationship("Visitante", back_populates="agendamentos")


class LogAcesso(Base):
    __tablename__ = "logs_acesso"
    id = Column(Integer, primary_key=True, index=True)
    data_hora = Column(DateTime, default=datetime.now, index=True)
    direcao = Column(Enum(DirecaoEnum), nullable=False)
    tipo = Column(Enum(TipoAcessoEnum), nullable=False)
    placa_lida = Column(String(10), nullable=True)
    fk_morador = Column(Integer, ForeignKey("moradores.id"), nullable=True)
    fk_agendamento = Column(Integer, ForeignKey("agendamentos_visita.id"), nullable=True)
    path_foto_rosto = Column(String(255), nullable=True)
    path_foto_placa = Column(String(255), nullable=True)
    sucesso = Column(Boolean, default=True)
    motivo = Column(String(255), nullable=True)

    morador = relationship("Morador")
    agendamento = relationship("AgendamentoVisita")


class VeiculoTemporario(Base):
    """Carro que NÃO é do morador, mas entrou com ele (rosto reconhecido)."""
    __tablename__ = "veiculos_temporarios"
    id = Column(Integer, primary_key=True, index=True)
    placa = Column(String(10), nullable=False, index=True)
    fk_morador = Column(Integer, ForeignKey("moradores.id"), nullable=False)
    fk_log_entrada = Column(Integer, ForeignKey("logs_acesso.id"), nullable=False)
    fk_log_saida = Column(Integer, ForeignKey("logs_acesso.id"), nullable=True)
    status = Column(Enum(StatusTemporarioEnum), default=StatusTemporarioEnum.DENTRO, nullable=False)

    morador = relationship("Morador")


class AlertaPainel(Base):
    __tablename__ = "alertas_painel"
    id = Column(Integer, primary_key=True, index=True)
    tipo = Column(String(50), nullable=False)
    texto = Column(String(255), nullable=False)
    fk_vaga = Column(Integer, ForeignKey("vagas.id"), nullable=True)
    fk_morador = Column(Integer, ForeignKey("moradores.id"), nullable=True)
    fk_log = Column(Integer, ForeignKey("logs_acesso.id"), nullable=True)
    resolvido = Column(Boolean, default=False)
    criado_em = Column(DateTime, default=datetime.now)
