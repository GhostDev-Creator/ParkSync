from fastapi import FastAPI, Depends, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional
from database.setup_db import SessionLocal, init_db
from database import models, schemas
from sqlalchemy.orm import Session
from sqlalchemy import desc
from database.models import LogAcessoExterno, AlertaPainel, VagaModel, MoradorModel
from database.schemas import TriggerEvent
import uvicorn
from datetime import datetime, timedelta
from services.face_service import extract_embedding
import cv2
import os
from orchestractor import ParkSyncOrchestrator
import threading
import time
import requests
import random

app = FastAPI(title="ParkSync API")
init_db()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# Estrutura em memória para armazenar códigos de recuperação temporários
# Estrutura: { email: {"codigo": "123456", "expira": datetime_obj} }
codigos_recuperacao = {}


# Modelos Pydantic para os fluxos de recuperação e alteração de senha
class SolicitacaoRecuperacaoRequest(BaseModel):
    email: str


class ValidacaoCodigoRequest(BaseModel):
    email: str
    codigo: str


class RedefinicaoSenhaRequest(BaseModel):
    email: str
    codigo: str
    nova_senha: str


class UpdateSenhaPerfilRequest(BaseModel):
    email: str
    senha_atual: Optional[str] = None
    nova_senha: str


class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except:
                pass


manager = ConnectionManager()


@app.websocket("/ws/portaria")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)


@app.post("/api/internal/trigger")
async def trigger_update(payload: TriggerEvent):
    await manager.broadcast({"evento": payload.evento})
    return {"status": "ok"}


def gen_frames():
    # Verifica a variável de ambiente. Se não existir, utiliza "0" (webcam padrão)
    cam_env = os.getenv("PM_PARK_CAM", "0")

    # Converte para inteiro se for um número (webcam local), mantém string se for IP/RTSP
    camera_estacionamento = int(cam_env) if cam_env.isdigit() else cam_env

    cap = cv2.VideoCapture(camera_estacionamento)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)

    while True:
        success, frame = cap.read()
        if not success:
            break
        else:
            frame = cv2.resize(frame, (1920, 1080))
            # Comprime o frame para JPEG
            ret, buffer = cv2.imencode('.jpg', frame)
            frame = buffer.tobytes()
            # Retorna o frame no formato multipart (stream de vídeo contínuo)
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')


@app.get("/api/video_feed")
def video_feed():
    return StreamingResponse(gen_frames(), media_type="multipart/x-mixed-replace; boundary=frame")


@app.get("/api/vagas")
def listar_vagas(db: Session = Depends(get_db)):
    vagas_db = db.query(VagaModel).all()
    resultado = []
    for vaga in vagas_db:
        resultado.append({
            "numero": vaga.numero,
            "fk_morador_dono": vaga.fk_morador_dono,
            "coordenadas": vaga.coordenadas if vaga.coordenadas else []
        })
    return resultado


@app.get("/api/portaria/iniciar-dados")
def carregar_dados_iniciais(db: Session = Depends(get_db)):
    logs_db = db.query(LogAcessoExterno).order_by(desc(LogAcessoExterno.id_log)).limit(15).all()
    historico = []
    for log in logs_db:
        historico.append({
            "tipo": log.tipo_acesso.name if hasattr(log, 'tipo_acesso') and log.tipo_acesso else "ENTRADA_APROVADA",
            "data_hora": log.data_hora.strftime("%d/%m/%Y %H:%M:%S") if getattr(log, 'data_hora',
                                                                                None) else "Desconhecido",
            "placa": getattr(log, 'placa_detectada', "N/A")
        })

    alertas_db = db.query(AlertaPainel).filter_by(resolvido=False).order_by(desc(AlertaPainel.id_alerta)).all()
    alertas = []
    for alerta in alertas_db:
        alertas.append({
            "tipo": alerta.tipo_alerta,
            "descricao": alerta.texto,
            "data_hora": alerta.criado_em.strftime("%d/%m/%Y %H:%M:%S") if getattr(alerta, 'criado_em',
                                                                                   None) else datetime.now().strftime(
                "%d/%m/%Y %H:%M:%S")
        })

    vagas_db = db.query(VagaModel).all()
    vagas = []
    for vaga in vagas_db:
        morador = db.query(MoradorModel).filter(MoradorModel.id == vaga.fk_morador_dono).first()

        vagas.append({
            "numero": vaga.numero,
            "conflito": vaga.status_conflito,
            "ocupada": vaga.ocupado,
            "dono_nome": morador.nome if morador else "Desconhecido",
            "dono_apt": morador.apartamento if morador else "N/A",
            "placa_atual": vaga.current_plate or ""
        })

    return {
        "historico": historico,
        "alertas": alertas,
        "vagas": vagas
    }


@app.post("/api/morador/cadastro")
def cadastrar_morador_completo(payload: schemas.CadastroCompletoRequest, db: Session = Depends(get_db)):
    if db.query(models.MoradorModel).filter_by(email=payload.email).first():
        raise HTTPException(status_code=400, detail="E-mail já cadastrado!")

    face_vector = extract_embedding(payload.foto_base64)
    if not face_vector:
        raise HTTPException(status_code=400, detail="Nenhum rosto detectado na foto. Tente novamente.")

    novo_morador = models.MoradorModel(
        nome=payload.nome,
        email=payload.email,
        senha=payload.senha,
        apartamento=payload.apartamento,
        bloco=payload.bloco,
        face_encoding=face_vector
    )
    db.add(novo_morador)
    db.commit()
    db.refresh(novo_morador)

    novo_veiculo = models.VeiculoModel(
        marca=payload.marca,
        modelo=payload.modelo,
        placa=payload.placa,
        cor=payload.cor,
        fk_morador_dono=novo_morador.id
    )
    db.add(novo_veiculo)

    numero_vaga = payload.apartamento + payload.bloco
    nova_vaga = models.VagaModel(
        numero=numero_vaga,
        ocupado=False,
        current_plate=None,
        status_conflito=False,
        coordenadas=None,
        fk_morador_dono=novo_morador.id
    )
    db.add(nova_vaga)
    db.commit()

    return {"status": "ok", "mensagem": "Morador cadastrado com sucesso!", "id": novo_morador.id}


@app.get("/api/vagas/verificar/{numero_vaga}/{morador_id}")
def verificar_vaga(numero_vaga: str, morador_id: int, db: Session = Depends(get_db)):
    vaga = db.query(models.VagaModel).filter(models.VagaModel.numero == numero_vaga).first()
    if not vaga:
        raise HTTPException(status_code=404, detail="Número da vaga não existe.")
    if vaga.fk_morador_dono != morador_id:
        raise HTTPException(status_code=400, detail="Vaga não pertence a este morador.")
    morador = db.query(models.MoradorModel).filter(models.MoradorModel.id == morador_id).first()
    return {"status": "ok", "morador_nome": morador.nome}


@app.put("/api/vagas/{numero_vaga}/coordenadas")
def atualizar_coordenadas_vaga(numero_vaga: str, payload: schemas.CoordenadasUpdate, db: Session = Depends(get_db)):
    vaga = db.query(models.VagaModel).filter(models.VagaModel.numero == numero_vaga).first()
    if not vaga:
        raise HTTPException(status_code=404, detail="Vaga não encontrada.")
    vaga.coordenadas = payload.coordenadas
    db.commit()
    return {"status": "ok", "mensagem": "Coordenadas atualizadas"}


@app.post("/api/visitantes/cadastro")
def cadastrar_visitante_app(payload: schemas.VisitanteCadastroRequest, db: Session = Depends(get_db)):
    visitante = db.query(models.VisitanteModel).filter(models.VisitanteModel.cpf == payload.cpf).first()

    if not visitante:
        visitante = models.VisitanteModel(
            nome=payload.nome,
            cpf=payload.cpf,
            cnh=payload.cnh,
            placa_veiculo=payload.placa_veiculo
        )
        db.add(visitante)
        db.commit()
        db.refresh(visitante)
    else:
        visitante.nome = payload.nome
        visitante.placa_veiculo = payload.placa_veiculo
        if payload.cnh:
            visitante.cnh = payload.cnh
        db.commit()

    agora = datetime.now()
    data_entrada = agora

    if payload.tipo_visita == 'unica':
        data_saida = agora + timedelta(hours=12)
    else:
        try:
            h_inicio, m_inicio = map(int, payload.horario_inicio.split(':'))
            h_fim, m_fim = map(int, payload.horario_fim.split(':'))

            data_entrada = agora.replace(hour=h_inicio, minute=m_inicio, second=0)
            data_saida = agora.replace(hour=h_fim, minute=m_fim, second=0)

            if data_saida < data_entrada:
                data_saida += timedelta(days=1)
        except:
            data_saida = agora + timedelta(days=1)

    novo_agendamento = models.AgendamentoVisita(
        fk_id_morador=payload.fk_id_morador,
        fk_id_visitante=visitante.id,
        data_entrada_prevista=data_entrada,
        data_saida_prevista=data_saida,
        ativo=True
    )
    db.add(novo_agendamento)
    db.commit()

    try:
        requests.post("http://127.0.0.1:8000/api/internal/trigger", json={"evento": "ATUALIZACAO_VAGAS"})
    except:
        pass

    return {"status": "ok", "mensagem": "Visitante cadastrado e visita agendada com sucesso!"}


@app.post("/api/login")
def login_morador(payload: schemas.LoginRequest, db: Session = Depends(get_db)):
    morador = db.query(models.MoradorModel).filter(models.MoradorModel.email == payload.email).first()

    if not morador or morador.senha != payload.senha:
        raise HTTPException(status_code=401, detail="Usuário ou Senha incorretos.")

    veiculo = db.query(models.VeiculoModel).filter(models.VeiculoModel.fk_morador_dono == morador.id).first()

    resposta = {
        "id": morador.id,
        "nome": morador.nome,
        "email": morador.email,
        "apartamento_bloco": f"Apt {morador.apartamento} - Bloco {morador.bloco}",
        "carro": None
    }

    if veiculo:
        resposta["carro"] = {
            "modelo": veiculo.modelo,
            "placa": veiculo.placa
        }

    return resposta


@app.put("/api/morador/senha")
def atualizar_senha(payload: UpdateSenhaPerfilRequest, db: Session = Depends(get_db)):
    morador = db.query(models.MoradorModel).filter(models.MoradorModel.email == payload.email).first()

    if not morador:
        raise HTTPException(status_code=404, detail="Morador não encontrado.")

    if payload.senha_atual and morador.senha != payload.senha_atual:
        raise HTTPException(status_code=400, detail="Senha atual incorreta.")

    morador.senha = payload.nova_senha
    db.commit()

    return {"status": "ok", "mensagem": "Senha atualizada com sucesso!"}


# --- ENDPOINTS DE RECUPERAÇÃO DE SENHA ---

@app.post("/api/recuperar-senha/solicitar")
def solicitar_recuperacao_senha(payload: SolicitacaoRecuperacaoRequest, db: Session = Depends(get_db)):
    morador = db.query(models.MoradorModel).filter(models.MoradorModel.email == payload.email).first()

    if not morador:
        raise HTTPException(status_code=404, detail="E-mail não encontrado no sistema.")

    # Gera um código numérico aleatório de 6 dígitos
    codigo = f"{random.randint(100000, 999999)}"

    # Define validade do código por 15 minutos
    codigos_recuperacao[payload.email] = {
        "codigo": codigo,
        "expira": datetime.now() + timedelta(minutes=15)
    }

    print(f"\n[RECUPERAÇÃO DE SENHA] Código gerado para {payload.email}: {codigo}\n")

    return {"status": "ok", "mensagem": "Código enviado para o e-mail cadastrado."}


@app.post("/api/recuperar-senha/validar")
def validar_codigo_recuperacao(payload: ValidacaoCodigoRequest):
    dados = codigos_recuperacao.get(payload.email)

    if not dados:
        raise HTTPException(status_code=400, detail="Nenhuma solicitação de recuperação encontrada para este e-mail.")

    if datetime.now() > dados["expira"]:
        codigos_recuperacao.pop(payload.email, None)
        raise HTTPException(status_code=400, detail="Código expirado. Solicite um novo código.")

    if dados["codigo"] != payload.codigo:
        raise HTTPException(status_code=400, detail="Código incorreto. Verifique o código recebido.")

    return {"status": "ok", "mensagem": "Código validado com sucesso."}


@app.post("/api/recuperar-senha/redefinir")
def redefinir_senha(payload: RedefinicaoSenhaRequest, db: Session = Depends(get_db)):
    dados = codigos_recuperacao.get(payload.email)

    if not dados or dados["codigo"] != payload.codigo:
        raise HTTPException(status_code=400, detail="Código inválido ou expirado.")

    if datetime.now() > dados["expira"]:
        codigos_recuperacao.pop(payload.email, None)
        raise HTTPException(status_code=400, detail="Código expirado. Solicite um novo código.")

    morador = db.query(models.MoradorModel).filter(models.MoradorModel.email == payload.email).first()

    if not morador:
        raise HTTPException(status_code=404, detail="Morador não encontrado.")

    morador.senha = payload.nova_senha
    db.commit()

    # Invalida o código após o uso
    codigos_recuperacao.pop(payload.email, None)

    return {"status": "ok", "mensagem": "Senha redefinida com sucesso!"}


# -----------------------------------------

@app.get("/api/visitantes/morador/{morador_id}")
def listar_visitantes_morador(morador_id: int, db: Session = Depends(get_db)):
    agendamentos = db.query(models.AgendamentoVisita).filter(
        models.AgendamentoVisita.fk_id_morador == morador_id,
        models.AgendamentoVisita.ativo == True
    ).all()

    visitantes_formatados = []
    for agendamento in agendamentos:
        visitantes_formatados.append({
            "id_agendamento": agendamento.id_agendamento,
            "nome": agendamento.visitante.nome,
            "placa_veiculo": agendamento.visitante.placa_veiculo,
            "data_entrada": agendamento.data_entrada_prevista.isoformat(),
            "data_saida": agendamento.data_saida_prevista.isoformat()
        })
    return visitantes_formatados


@app.delete("/api/visitantes/agendamento/{agendamento_id}")
def cancelar_agendamento(agendamento_id: int, db: Session = Depends(get_db)):
    agendamento = db.query(models.AgendamentoVisita).filter(
        models.AgendamentoVisita.id_agendamento == agendamento_id).first()
    if not agendamento:
        raise HTTPException(status_code=404, detail="Agendamento não encontrado.")

    db.delete(agendamento)
    db.commit()
    return {"status": "ok", "mensagem": "Agendamento cancelado com sucesso"}


@app.put("/api/visitantes/agendamento/{agendamento_id}")
def atualizar_agendamento(agendamento_id: int, payload: schemas.AgendamentoUpdate, db: Session = Depends(get_db)):
    agendamento = db.query(models.AgendamentoVisita).filter(
        models.AgendamentoVisita.id_agendamento == agendamento_id).first()
    if not agendamento:
        raise HTTPException(status_code=404, detail="Agendamento não encontrado.")

    agora = datetime.now()
    if payload.tipo_visita == 'unica':
        agendamento.data_entrada_prevista = agora
        agendamento.data_saida_prevista = agora + timedelta(hours=12)
    else:
        try:
            h_inicio, m_inicio = map(int, payload.horario_inicio.split(':'))
            h_fim, m_fim = map(int, payload.horario_fim.split(':'))

            data_entrada = agora.replace(hour=h_inicio, minute=m_inicio, second=0)
            data_saida = agora.replace(hour=h_fim, minute=m_fim, second=0)

            if data_saida < data_entrada:
                data_saida += timedelta(days=1)

            agendamento.data_entrada_prevista = data_entrada
            agendamento.data_saida_prevista = data_saida
        except Exception:
            raise HTTPException(status_code=400, detail="Formato de hora inválido.")

    db.commit()
    return {"status": "ok", "mensagem": "Agendamento atualizado com sucesso"}


@app.put("/api/veiculos/morador/{morador_id}")
def atualizar_veiculo_app(morador_id: int, payload: schemas.VeiculoUpdate, db: Session = Depends(get_db)):
    veiculo = db.query(models.VeiculoModel).filter(models.VeiculoModel.fk_morador_dono == morador_id).first()

    if veiculo:
        veiculo.modelo = payload.modelo
        veiculo.placa = payload.placa
        db.commit()
    else:
        novo_veiculo = models.VeiculoModel(
            marca="Não informada",
            modelo=payload.modelo,
            placa=payload.placa,
            cor="Não informada",
            fk_morador_dono=morador_id
        )
        db.add(novo_veiculo)
        db.commit()

    return {"status": "ok", "mensagem": "Veículo atualizado"}


@app.delete("/api/veiculos/morador/{morador_id}")
def remover_veiculo_app(morador_id: int, db: Session = Depends(get_db)):
    veiculo = db.query(models.VeiculoModel).filter(models.VeiculoModel.fk_morador_dono == morador_id).first()
    if veiculo:
        db.delete(veiculo)
        db.commit()
        return {"status": "ok", "mensagem": "Veículo removido com sucesso"}
    raise HTTPException(status_code=404, detail="Nenhum veículo encontrado para este morador.")


@app.get("/api/notificacoes/morador/{morador_id}")
def listar_notificacoes_app(morador_id: int, db: Session = Depends(get_db)):
    notificacoes = []

    morador = db.query(models.MoradorModel).filter(models.MoradorModel.id == morador_id).first()
    if not morador:
        raise HTTPException(status_code=404, detail="Morador não encontrado.")

    vaga = db.query(models.VagaModel).filter(models.VagaModel.fk_morador_dono == morador_id).first()
    if vaga:
        if vaga.status_conflito:
            notificacoes.append({
                "id": f"vaga_{vaga.id}",
                "title": "Alerta de Vaga!",
                "desc": f"Veículo invasor ({vaga.current_plate}) na vaga {vaga.numero}.",
                "time": "Agora",
                "icon": "warning",
                "color": "#ff4757"  # Vermelho
            })
        elif vaga.ocupado:
            notificacoes.append({
                "id": f"vaga_{vaga.id}",
                "title": "Vaga Ocupada",
                "desc": f"Seu veículo está estacionado com segurança.",
                "time": "Ativa",
                "icon": "car",
                "color": "#1e90ff"  # Azul
            })
        else:
            notificacoes.append({
                "id": f"vaga_{vaga.id}",
                "title": "Vaga Livre",
                "desc": f"Sua vaga {vaga.numero} está disponível.",
                "time": "Ativa",
                "icon": "checkmark-circle",
                "color": "#2ed573"  # Verde
            })

    visitantes = db.query(models.LogVisitante).filter(
        models.LogVisitante.apartamento_visitado == morador.apartamento,
        models.LogVisitante.bloco_visitado == morador.bloco
    ).order_by(desc(models.LogVisitante.id_log_visitante)).limit(3).all()

    for log in visitantes:
        notificacoes.append({
            "id": f"vis_{log.id_log_visitante}",
            "title": "Visitante Chegou",
            "desc": f"{log.visitante_nome} acessou o condomínio.",
            "time": log.data_hora_entrada.strftime("%H:%M") if log.data_hora_entrada else "Recente",
            "icon": "person-add",
            "color": "#ffa502"  # Laranja
        })

    alertas = db.query(models.AlertaPainel).filter(models.AlertaPainel.resolvido == False).all()

    for alerta in alertas:
        if morador.nome in alerta.texto or (vaga and vaga.numero in alerta.texto) or (
                f"Apt: {morador.apartamento}" in alerta.texto):
            notificacoes.append({
                "id": f"alerta_{alerta.id_alerta}",
                "title": "Aviso de Segurança",
                "desc": alerta.texto,
                "time": alerta.criado_em.strftime("%d/%m") if alerta.criado_em else "Recente",
                "icon": "shield",
                "color": "#ff4757"
            })

    if len(notificacoes) == 0:
        notificacoes.append({
            "id": "welcome_1",
            "title": "Boas-vindas!",
            "desc": "Seu app está conectado.",
            "time": "",
            "icon": "home",
            "color": "#1e90ff"
        })

    return notificacoes


def iniciar_orquestrador():
    time.sleep(2)
    maestro = ParkSyncOrchestrator()

    while True:
        time.sleep(1)


@app.on_event("startup")
async def startup_event():
    thread = threading.Thread(target=iniciar_orquestrador, daemon=True)
    thread.start()


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, log_level="info")