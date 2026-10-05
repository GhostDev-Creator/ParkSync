from sqlalchemy import String, Boolean, DateTime, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func
from typing import List, Optional
from datetime import datetime
from database.setup_db import Base
import enum

class StatusEnum(enum.Enum):
    DENTRO = "DENTRO"
    SAIU = "SAIU"

class AcessoEnum(enum.Enum):
    MORADOR = "MORADOR"
    VISITANTE = "VISITANTE"
    NEGADO = "NEGADO"
    MANUAL = "MANUAL"

class MoradorModel(Base):
    __tablename__ = "moradores"
    id: Mapped[int] = mapped_column(primary_key=True, index=True, autoincrement=True)
    nome: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str] = mapped_column(String(100), index=True, nullable=False, unique=True)
    senha: Mapped[str] = mapped_column(String(255), nullable=False)
    apartamento: Mapped[str] = mapped_column(String(10), nullable=False)
    bloco: Mapped[str] = mapped_column(String(10), nullable=False)
    face_encoding: Mapped[dict] = mapped_column(JSON, nullable=False)
    criado_em: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    veiculos: Mapped[List["VeiculoModel"]] = relationship(back_populates="morador_dono")
    vaga: Mapped[Optional["VagaModel"]] = relationship(back_populates="morador_dono")

class VeiculoModel(Base):
    __tablename__ = 'veiculos'
    id: Mapped[int] = mapped_column(primary_key=True, index=True, autoincrement=True)
    marca: Mapped[str] = mapped_column(String(50), nullable=False)
    modelo: Mapped[str] = mapped_column(String(50), nullable=False)
    placa: Mapped[str] = mapped_column(String(10), unique=True, index=True, nullable=False)
    cor: Mapped[str] = mapped_column(String(30), nullable=False)
    fk_morador_dono: Mapped[int] = mapped_column(ForeignKey("moradores.id", ondelete="CASCADE"), nullable=False)
    morador_dono: Mapped["MoradorModel"] = relationship(back_populates="veiculos")

class VagaModel(Base):
    __tablename__ = 'vagas'
    id: Mapped[int] = mapped_column(primary_key=True, index=True, autoincrement=True)
    numero: Mapped[str] = mapped_column(String(10), unique=True, index=True, nullable=False)
    ocupado: Mapped[bool] = mapped_column(Boolean, default=False)
    current_plate: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    status_conflito: Mapped[bool] = mapped_column(Boolean, default=False)
    coordenadas: Mapped[dict] = mapped_column(JSON, nullable=True)
    fk_morador_dono: Mapped[int] = mapped_column(ForeignKey("moradores.id", ondelete="RESTRICT"), unique=True, nullable=False)
    morador_dono: Mapped["MoradorModel"] = relationship(back_populates="vaga")

class VeiculoTemporario(Base):
    __tablename__ = 'veiculos_temporarios'
    id_veiculo_temporario: Mapped[int] = mapped_column(primary_key=True, index=True, autoincrement=True)
    placa_veiculo_temporario: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    horario_entrada: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    status: Mapped[StatusEnum] = mapped_column(default=StatusEnum.DENTRO, nullable=False)
    fk_morador_dono: Mapped[int] = mapped_column(ForeignKey("moradores.id", ondelete="CASCADE"), index=True,nullable=False)

class VisitanteModel(Base):
    __tablename__ = 'visitantes'
    id: Mapped[int] = mapped_column(primary_key=True, index=True, autoincrement=True)
    nome: Mapped[str] = mapped_column(String(100), nullable=False)
    cpf: Mapped[str] = mapped_column(String(14), unique=True, nullable=False)
    cnh: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    placa_veiculo: Mapped[str] = mapped_column(String(10), nullable=False)
    criado_em: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    agendamentos: Mapped[List["AgendamentoVisita"]] = relationship(back_populates="visitante", cascade="all, delete-orphan")

class AgendamentoVisita(Base):
    __tablename__ = 'agendamentos_visita'
    id_agendamento: Mapped[int] = mapped_column(primary_key=True, index=True, autoincrement=True)
    fk_id_morador: Mapped[int] = mapped_column(ForeignKey("moradores.id", ondelete="CASCADE"), index=True,nullable=False)
    fk_id_visitante: Mapped[int] = mapped_column(ForeignKey("visitantes.id", ondelete="CASCADE"), index=True,nullable=False)
    data_entrada_prevista: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    data_saida_prevista: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    ativo: Mapped[bool] = mapped_column(Boolean, default=False)
    visitante: Mapped["VisitanteModel"] = relationship(back_populates="agendamentos")

class AlertaPainel(Base):
    __tablename__ = 'alertas_painel'
    id_alerta: Mapped[int] = mapped_column(primary_key=True, index=True, autoincrement=True)
    texto: Mapped[str] = mapped_column(String(255), nullable=False)
    ativo: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    resolvido: Mapped[bool] = mapped_column(Boolean, default=False)
    tipo_alerta: Mapped[str] = mapped_column(String(255), nullable=False)
    criado_em: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

class LogVisitante(Base):
    __tablename__ = 'logs_visitantes'
    id_log_visitante: Mapped[int] = mapped_column(primary_key=True, index=True, autoincrement=True)
    data_hora_entrada: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    path_foto_capturada: Mapped[str] = mapped_column(String(255), nullable=False)
    visitante_nome: Mapped[str] = mapped_column(String(45), nullable=False)
    visitante_cpf: Mapped[str] = mapped_column(String(14), nullable=False)
    visitante_cnh: Mapped[str] = mapped_column(String(20), nullable=False)
    visitante_placa: Mapped[str] = mapped_column(String(10), nullable=False)
    morador_anfitriao_nome: Mapped[str] = mapped_column(String(45), nullable=False)
    apartamento_visitado: Mapped[str] = mapped_column(String(10), nullable=False)
    bloco_visitado: Mapped[str] = mapped_column(String(10), nullable=False)

class LogAcessoExterno(Base):
    __tablename__ = 'logs_externos'
    id_log: Mapped[int] = mapped_column(primary_key=True, index=True, autoincrement=True)
    data_hora: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    placa_detectada: Mapped[str] = mapped_column(String(10), nullable=False)
    tipo_acesso: Mapped[AcessoEnum] = mapped_column(nullable=False, index=True)
    path_foto_capturada: Mapped[str] = mapped_column(String(255), nullable=False)

class LogAcessoModel(Base):
    __tablename__ = 'logs_acesso'
    id: Mapped[int] = mapped_column(primary_key=True, index=True, autoincrement=True)
    tipo: Mapped[AcessoEnum] = mapped_column(nullable=False)
    placa: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    fk_morador_dono: Mapped[Optional[int]] = mapped_column(ForeignKey("moradores.id", ondelete="SET NULL"),nullable=True)
    sucesso: Mapped[bool] = mapped_column(Boolean, default=False)
    motivo: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), index=True)