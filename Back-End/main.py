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
from services.face_service import extract_embedding, invalidar_cache_moradores
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


codigos_recuperacao = {}


class SolicitacaoRecuperacaoRequest(BaseModel): email: str


class ValidacaoCodigoRequest(BaseModel): email: str; codigo: str


class RedefinicaoSenhaRequest(BaseModel): email: str; codigo: str; nova_senha: str


class UpdateSenhaPerfilRequest(BaseModel): email: str; senha_atual: str; nova_senha: str


class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections: self.active_connections.remove(websocket)

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
        while True: await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)


@app.post("/api/internal/trigger")
async def trigger_update(payload: TriggerEvent):
    await manager.broadcast({"evento": payload.evento})
    return {"status": "ok"}


def gen_frames():
    cam_env = os.getenv("PM_PARK_CAM", "0")
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
            ret, buffer = cv2.imencode('.jpg', frame)
            frame = buffer.tobytes()
            yield (b'--frame\r\n' b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')


@app.get("/api/video_feed")
def video_feed():
    return StreamingResponse(gen_frames(), media_type="multipart/x-mixed-replace; boundary=frame")


@app.get("/api/vagas")
def listar_vagas(db: Session = Depends(get_db)):
    vagas_db = db.query(VagaModel).all()
    resultado = [{"numero": v.numero, "fk_morador_dono": v.fk_morador_dono,
                  "coordenadas": v.coordenadas if v.coordenadas else []} for v in vagas_db]
    return resultado


@app.get("/api/portaria/iniciar-dados")
def carregar_dados_iniciais(db: Session = Depends(get_db)):
    logs_db = db.query(LogAcessoExterno).order_by(desc(LogAcessoExterno.id_log)).limit(15).all()
    historico = [
        {"tipo": log.tipo_acesso.name if hasattr(log, 'tipo_acesso') and log.tipo_acesso else "ENTRADA_APROVADA",
         "data_hora": log.data_hora.strftime("%d/%m/%Y %H:%M:%S") if getattr(log, 'data_hora',
                                                                             None) else "Desconhecido",
         "placa": getattr(log, 'placa_detectada', "N/A")} for log in logs_db]

    alertas_db = db.query(AlertaPainel).filter_by(resolvido=False).order_by(desc(AlertaPainel.id_alerta)).all()
    alertas = [{"tipo": a.tipo_alerta, "descricao": a.texto,
                "data_hora": a.criado_em.strftime("%d/%m/%Y %H:%M:%S") if getattr(a, 'criado_em',
                                                                                  None) else datetime.now().strftime(
                    "%d/%m/%Y %H:%M:%S")} for a in alertas_db]

    vagas_db = db.query(VagaModel).all()
    vagas = []
    for vaga in vagas_db:
        morador = db.query(MoradorModel).filter(MoradorModel.id == vaga.fk_morador_dono).first()
        vagas.append({"numero": vaga.numero, "conflito": vaga.status_conflito, "ocupada": vaga.ocupado,
                      "dono_nome": morador.nome if morador else "Desconhecido",
                      "dono_apt": morador.apartamento if morador else "N/A", "placa_atual": vaga.current_plate or ""})

    return {"historico": historico, "alertas": alertas, "vagas": vagas}


@app.post("/api/morador/cadastro")
def cadastrar_morador_completo(payload: schemas.CadastroCompletoRequest, db: Session = Depends(get_db)):
    if db.query(models.MoradorModel).filter_by(email=payload.email).first():
        raise HTTPException(status_code=400, detail="E-mail já cadastrado!")

    if db.query(models.VeiculoModel).filter_by(placa=payload.placa).first():
        raise HTTPException(status_code=400, detail="Placa já cadastrada no sistema!")

    numero_vaga = payload.apartamento + payload.bloco
    if db.query(models.VagaModel).filter_by(numero=numero_vaga).first():
        raise HTTPException(status_code=400, detail="Vaga do Apartamento já cadastrada!")

    face_vector = extract_embedding(payload.foto_base64)
    if not face_vector:
        raise HTTPException(status_code=400, detail="Nenhum rosto detectado na foto.")

    try:
        novo_morador = models.MoradorModel(nome=payload.nome, email=payload.email, senha=payload.senha,
                                           apartamento=payload.apartamento, bloco=payload.bloco,
                                           face_encoding=face_vector)
        db.add(novo_morador)
        db.flush()  # Salva ID sem commitar

        novo_veiculo = models.VeiculoModel(marca=payload.marca, modelo=payload.modelo, placa=payload.placa,
                                           cor=payload.cor, fk_morador_dono=novo_morador.id)
        db.add(novo_veiculo)

        nova_vaga = models.VagaModel(numero=numero_vaga, ocupado=False, status_conflito=False,
                                     fk_morador_dono=novo_morador.id)
        db.add(nova_vaga)

        db.commit()  # Efetiva os 3 juntos
        invalidar_cache_moradores()
        return {"status": "ok", "mensagem": "Morador cadastrado com sucesso!", "id": novo_morador.id}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Erro interno de banco: {e}")


@app.get("/api/vagas/verificar/{numero_vaga}/{morador_id}")
def verificar_vaga(numero_vaga: str, morador_id: int, db: Session = Depends(get_db)):
    vaga = db.query(models.VagaModel).filter(models.VagaModel.numero == numero_vaga).first()
    if not vaga: raise HTTPException(status_code=404, detail="Número da vaga não existe.")
    if vaga.fk_morador_dono != morador_id: raise HTTPException(status_code=400,
                                                               detail="Vaga não pertence a este morador.")
    morador = db.query(models.MoradorModel).filter(models.MoradorModel.id == morador_id).first()
    return {"status": "ok", "morador_nome": morador.nome}


@app.put("/api/vagas/{numero_vaga}/coordenadas")
def atualizar_coordenadas_vaga(numero_vaga: str, payload: schemas.CoordenadasUpdate, db: Session = Depends(get_db)):
    vaga = db.query(models.VagaModel).filter(models.VagaModel.numero == numero_vaga).first()
    if not vaga: raise HTTPException(status_code=404, detail="Vaga não encontrada.")
    vaga.coordenadas = payload.coordenadas
    db.commit()
    return {"status": "ok", "mensagem": "Coordenadas atualizadas"}


def calcular_periodo_visita(tipo_visita, horario_inicio, horario_fim):
    agora = datetime.now()
    if tipo_visita == 'unica': return agora, agora + timedelta(hours=12)
    formato = "%d/%m/%Y %H:%M"
    try:
        data_entrada = datetime.strptime(horario_inicio, formato)
        data_saida = datetime.strptime(horario_fim, formato)
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="Período inválido. Use dd/mm/aaaa e hh:mm.")
    if data_saida <= data_entrada: raise HTTPException(status_code=400, detail="Saída anterior à entrada.")
    return data_entrada, data_saida


@app.post("/api/visitantes/cadastro")
def cadastrar_visitante_app(payload: schemas.VisitanteCadastroRequest, db: Session = Depends(get_db)):
    visitante = db.query(models.VisitanteModel).filter(models.VisitanteModel.cpf == payload.cpf).first()
    if not visitante:
        visitante = models.VisitanteModel(nome=payload.nome, cpf=payload.cpf, cnh=payload.cnh,
                                          placa_veiculo=payload.placa_veiculo)
        db.add(visitante)
        db.commit()
        db.refresh(visitante)
    else:
        visitante.nome = payload.nome
        visitante.placa_veiculo = payload.placa_veiculo
        if payload.cnh: visitante.cnh = payload.cnh
        db.commit()

    data_entrada, data_saida = calcular_periodo_visita(payload.tipo_visita, payload.horario_inicio, payload.horario_fim)
    novo_agendamento = models.AgendamentoVisita(fk_id_morador=payload.fk_id_morador, fk_id_visitante=visitante.id,
                                                data_entrada_prevista=data_entrada, data_saida_prevista=data_saida,
                                                ativo=True)
    db.add(novo_agendamento)
    db.commit()
    try:
        requests.post("http://127.0.0.1:8000/api/internal/trigger", json={"evento": "ATUALIZACAO_VAGAS"})
    except:
        pass
    return {"status": "ok", "mensagem": "Visitante cadastrado com sucesso!"}


@app.post("/api/login")
def login_morador(payload: schemas.LoginRequest, db: Session = Depends(get_db)):
    morador = db.query(models.MoradorModel).filter(models.MoradorModel.email == payload.email).first()
    if not morador or morador.senha != payload.senha: raise HTTPException(status_code=401,
                                                                          detail="Usuário ou Senha incorretos.")
    veiculo = db.query(models.VeiculoModel).filter(models.VeiculoModel.fk_morador_dono == morador.id).first()
    resposta = {"id": morador.id, "nome": morador.nome, "email": morador.email,
                "apartamento_bloco": f"Apt {morador.apartamento} - Bloco {morador.bloco}", "carro": None}
    if veiculo: resposta["carro"] = {"modelo": veiculo.modelo, "placa": veiculo.placa}
    return resposta


@app.put("/api/morador/senha")
def atualizar_senha(payload: UpdateSenhaPerfilRequest, db: Session = Depends(get_db)):
    if not payload.senha_atual: raise HTTPException(status_code=400, detail="Senha atual obrigatória.")
    morador = db.query(models.MoradorModel).filter(models.MoradorModel.email == payload.email).first()
    if not morador: raise HTTPException(status_code=404, detail="Morador não encontrado.")
    if morador.senha != payload.senha_atual: raise HTTPException(status_code=400, detail="Senha atual incorreta.")
    morador.senha = payload.nova_senha
    db.commit()
    return {"status": "ok", "mensagem": "Senha atualizada com sucesso!"}


@app.post("/api/recuperar-senha/solicitar")
def solicitar_recuperacao_senha(payload: SolicitacaoRecuperacaoRequest, db: Session = Depends(get_db)):
    morador = db.query(models.MoradorModel).filter(models.MoradorModel.email == payload.email).first()
    if not morador: raise HTTPException(status_code=404, detail="E-mail não encontrado.")
    codigo = f"{random.randint(100000, 999999)}"
    codigos_recuperacao[payload.email] = {"codigo": codigo, "expira": datetime.now() + timedelta(minutes=15)}
    print(f"\n[RECUPERAÇÃO] Código de {payload.email}: {codigo}\n")
    return {"status": "ok", "mensagem": "Código enviado para o e-mail."}


@app.post("/api/recuperar-senha/validar")
def validar_codigo_recuperacao(payload: ValidacaoCodigoRequest):
    dados = codigos_recuperacao.get(payload.email)
    if not dados: raise HTTPException(status_code=400, detail="Nenhuma solicitação encontrada.")
    if datetime.now() > dados["expira"]:
        codigos_recuperacao.pop(payload.email, None)
        raise HTTPException(status_code=400, detail="Código expirado.")
    if dados["codigo"] != payload.codigo: raise HTTPException(status_code=400, detail="Código incorreto.")
    return {"status": "ok", "mensagem": "Código validado."}


@app.post("/api/recuperar-senha/redefinir")
def redefinir_senha(payload: RedefinicaoSenhaRequest, db: Session = Depends(get_db)):
    dados = codigos_recuperacao.get(payload.email)
    if not dados or dados["codigo"] != payload.codigo: raise HTTPException(status_code=400, detail="Código inválido.")
    if datetime.now() > dados["expira"]:
        codigos_recuperacao.pop(payload.email, None)
        raise HTTPException(status_code=400, detail="Código expirado.")
    morador = db.query(models.MoradorModel).filter(models.MoradorModel.email == payload.email).first()
    if not morador: raise HTTPException(status_code=404, detail="Morador não encontrado.")
    morador.senha = payload.nova_senha
    db.commit()
    codigos_recuperacao.pop(payload.email, None)
    return {"status": "ok", "mensagem": "Senha redefinida com sucesso!"}


@app.get("/api/visitantes/morador/{morador_id}")
def listar_visitantes_morador(morador_id: int, db: Session = Depends(get_db)):
    agendamentos = db.query(models.AgendamentoVisita).filter(models.AgendamentoVisita.fk_id_morador == morador_id,
                                                             models.AgendamentoVisita.ativo == True).all()
    visitantes_formatados = [
        {"id_agendamento": a.id_agendamento, "nome": a.visitante.nome, "placa_veiculo": a.visitante.placa_veiculo,
         "data_entrada": a.data_entrada_prevista.isoformat(), "data_saida": a.data_saida_prevista.isoformat()} for a in
        agendamentos]
    return visitantes_formatados


@app.delete("/api/visitantes/agendamento/{agendamento_id}")
def cancelar_agendamento(agendamento_id: int, db: Session = Depends(get_db)):
    agendamento = db.query(models.AgendamentoVisita).filter(
        models.AgendamentoVisita.id_agendamento == agendamento_id).first()
    if not agendamento: raise HTTPException(status_code=404, detail="Agendamento não encontrado.")
    db.delete(agendamento)
    db.commit()
    return {"status": "ok", "mensagem": "Agendamento cancelado"}


@app.put("/api/visitantes/agendamento/{agendamento_id}")
def atualizar_agendamento(agendamento_id: int, payload: schemas.AgendamentoUpdate, db: Session = Depends(get_db)):
    agendamento = db.query(models.AgendamentoVisita).filter(
        models.AgendamentoVisita.id_agendamento == agendamento_id).first()
    if not agendamento: raise HTTPException(status_code=404, detail="Agendamento não encontrado.")
    data_entrada, data_saida = calcular_periodo_visita(payload.tipo_visita, payload.horario_inicio, payload.horario_fim)
    agendamento.data_entrada_prevista = data_entrada
    agendamento.data_saida_prevista = data_saida
    db.commit()
    return {"status": "ok", "mensagem": "Atualizado com sucesso"}


@app.put("/api/veiculos/morador/{morador_id}")
def atualizar_veiculo_app(morador_id: int, payload: schemas.VeiculoUpdate, db: Session = Depends(get_db)):
    v_existente = db.query(models.VeiculoModel).filter(models.VeiculoModel.placa == payload.placa).first()
    if v_existente and v_existente.fk_morador_dono != morador_id:
        raise HTTPException(status_code=400, detail="Placa já usada.")
    veiculo = db.query(models.VeiculoModel).filter(models.VeiculoModel.fk_morador_dono == morador_id).first()
    if veiculo:
        veiculo.modelo = payload.modelo;
        veiculo.placa = payload.placa;
        db.commit()
    else:
        novo_veiculo = models.VeiculoModel(marca="N/A", modelo=payload.modelo, placa=payload.placa, cor="N/A",
                                           fk_morador_dono=morador_id)
        db.add(novo_veiculo);
        db.commit()
    return {"status": "ok", "mensagem": "Veículo atualizado"}


@app.delete("/api/veiculos/morador/{morador_id}")
def remover_veiculo_app(morador_id: int, db: Session = Depends(get_db)):
    veiculo = db.query(models.VeiculoModel).filter(models.VeiculoModel.fk_morador_dono == morador_id).first()
    if veiculo:
        db.delete(veiculo);
        db.commit()
        return {"status": "ok"}
    raise HTTPException(status_code=404, detail="Não encontrado.")


@app.get("/api/notificacoes/morador/{morador_id}")
def listar_notificacoes_app(morador_id: int, db: Session = Depends(get_db)):
    notificacoes = []
    morador = db.query(models.MoradorModel).filter(models.MoradorModel.id == morador_id).first()
    if not morador: raise HTTPException(status_code=404, detail="Morador não encontrado.")
    vaga = db.query(models.VagaModel).filter(models.VagaModel.fk_morador_dono == morador_id).first()

    if vaga:
        if vaga.status_conflito:
            notificacoes.append(
                {"id": f"vaga_{vaga.id}", "title": "Alerta de Vaga!", "desc": f"Veículo invasor na vaga {vaga.numero}.",
                 "time": "Agora", "icon": "warning", "color": "#ff4757"})
        elif vaga.ocupado:
            notificacoes.append(
                {"id": f"vaga_{vaga.id}", "title": "Vaga Ocupada", "desc": "Veículo estacionado.", "time": "Ativa",
                 "icon": "car", "color": "#1e90ff"})
        else:
            notificacoes.append(
                {"id": f"vaga_{vaga.id}", "title": "Vaga Livre", "desc": f"Vaga {vaga.numero} livre.", "time": "Ativa",
                 "icon": "checkmark-circle", "color": "#2ed573"})

    visitantes = db.query(models.LogVisitante).filter(models.LogVisitante.apartamento_visitado == morador.apartamento,
                                                      models.LogVisitante.bloco_visitado == morador.bloco).order_by(
        desc(models.LogVisitante.id_log_visitante)).limit(3).all()
    for log in visitantes: notificacoes.append(
        {"id": f"vis_{log.id_log_visitante}", "title": "Visitante Chegou", "desc": f"{log.visitante_nome} acessou.",
         "time": log.data_hora_entrada.strftime("%H:%M"), "icon": "person-add", "color": "#ffa502"})

    alertas = db.query(models.AlertaPainel).filter(models.AlertaPainel.resolvido == False).all()
    for alerta in alertas:
        if morador.nome in alerta.texto or (vaga and vaga.numero in alerta.texto):
            notificacoes.append({"id": f"alerta_{alerta.id_alerta}", "title": "Aviso", "desc": alerta.texto,
                                 "time": alerta.criado_em.strftime("%d/%m"), "icon": "shield", "color": "#ff4757"})

    if not notificacoes: notificacoes.append(
        {"id": "welcome_1", "title": "Boas-vindas!", "desc": "Tudo certo.", "time": "", "icon": "home",
         "color": "#1e90ff"})
    return notificacoes


def iniciar_orquestrador():
    time.sleep(2)
    maestro = ParkSyncOrchestrator()
    while True: time.sleep(1)


@app.on_event("startup")
async def startup_event():
    threading.Thread(target=iniciar_orquestrador, daemon=True).start()


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, log_level="info")