# Arquivo: Back-End/main.py
#
# Rodar (dentro da pasta Back-End):  python main.py
# Documentação automática das rotas:  http://127.0.0.1:8000/docs

import asyncio
import random
import threading
from contextlib import asynccontextmanager
from datetime import datetime, timedelta
from typing import Optional

import uvicorn
from fastapi import Depends, FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

import schemas
from utils import config
from utils.eventos import manager, notificar_painel, registrar_loop
from utils.security import (
    create_access_token, exigir_portaria, garantir_dono, get_password_hash, morador_do_token, verify_password,
)
from database.setup_db import SessionLocal, init_db
from database.models import (
    AgendamentoVisita, AlertaPainel, LogAcesso, Morador, Unidade, Vaga, Veiculo, Visitante,
)
from mqtt.broker import broker
from services import orchestractor, parking_service, plate_service
from services.face_service import extract_embedding, facial_disponivel, invalidar_cache_moradores

FORMATO_DATA = "%d/%m/%Y %H:%M"


# ==========================
# INICIALIZAÇÃO (LIFESPAN)
# ==========================
@asynccontextmanager
async def lifespan(app: FastAPI):
    config.mostrar_avisos()
    init_db()  # cria banco e tabelas (erro claro se o MySQL estiver desligado)
    registrar_loop(asyncio.get_running_loop())  # threads conseguem avisar o painel via WebSocket

    orchestractor.iniciar_orquestrador()  # MQTT + sensores + fila de entrada/saída
    if config.MONITORAR_VAGAS:
        parking_service.iniciar_monitoramento()
    else:
        print("🅿️  Monitor de vagas desligado (MONITORAR_VAGAS=false).")
    # Carrega YOLO/EasyOCR em segundo plano para o 1º carro não esperar
    threading.Thread(target=plate_service.carregar_modelos, daemon=True).start()

    print("🚀 API ParkSync iniciada. Rotas em http://127.0.0.1:8000/docs")
    yield
    print("🛑 Encerrando API ParkSync...")
    parking_service.parar_monitoramento()
    broker.parar()


app = FastAPI(title="ParkSync API 2.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # na apresentação final, limite aos IPs conhecidos
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _fmt(dt: Optional[datetime]) -> str:
    return dt.strftime("%d/%m/%Y %H:%M:%S") if dt else ""


# ==========================
# SAÚDE DO SISTEMA
# ==========================
@app.get("/")
def status_sistema():
    return {
        "api": "ok",
        "mqtt_conectado": broker.conectado,
        "reconhecimento_facial": facial_disponivel(),
        "leitor_placas_carregado": plate_service._modelo_yolo is not None,
        "token_obrigatorio": config.EXIGIR_TOKEN,
    }


# ==========================
# PAINEL DO PORTEIRO (porteiro.html)
# ==========================
@app.websocket("/ws/portaria")
async def websocket_portaria(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)


@app.post("/api/internal/trigger", dependencies=[Depends(exigir_portaria)])
async def trigger_update(payload: schemas.TriggerEvent):
    await manager.broadcast({"evento": payload.evento})
    return {"status": "ok"}


@app.get("/api/portaria/iniciar-dados")
def carregar_dados_iniciais(db: Session = Depends(get_db)):
    logs = db.query(LogAcesso).order_by(LogAcesso.id.desc()).limit(15).all()
    historico = [{
        "tipo": f"{log.direcao.value}_{log.tipo.value}",  # ex.: ENTRADA_MORADOR, SAIDA_NEGADO
        "data_hora": _fmt(log.data_hora),
        "placa": log.placa_lida or "N/A",
        "sucesso": log.sucesso,
        "motivo": log.motivo,
        "morador": log.morador.nome if log.morador else None,
    } for log in logs]

    alertas_db = db.query(AlertaPainel).filter_by(resolvido=False).order_by(AlertaPainel.id.desc()).all()
    alertas = [{"id": a.id, "tipo": a.tipo, "descricao": a.texto, "data_hora": _fmt(a.criado_em)}
               for a in alertas_db]

    vagas = []
    for vaga in db.query(Vaga).order_by(Vaga.numero).all():
        unidade = vaga.unidade
        dono = unidade.moradores[0] if unidade and unidade.moradores else None
        vagas.append({
            "numero": vaga.numero,
            "conflito": bool(vaga.status_conflito),
            "ocupada": bool(vaga.ocupada),
            "dono_nome": dono.nome if dono else "Sem morador",
            "dono_apt": f"{unidade.apartamento}{unidade.bloco}" if unidade else "N/A",
            "placa_atual": vaga.current_plate or "",
        })
    return {"historico": historico, "alertas": alertas, "vagas": vagas}


@app.post("/api/alertas/{alerta_id}/resolver", dependencies=[Depends(exigir_portaria)])
def resolver_alerta(alerta_id: int, db: Session = Depends(get_db)):
    alerta = db.get(AlertaPainel, alerta_id)
    if not alerta:
        raise HTTPException(status_code=404, detail="Alerta não encontrado.")
    alerta.resolvido = True
    db.commit()
    notificar_painel("NOVO_ALERTA")
    return {"status": "ok"}


@app.post("/api/portaria/cancela/{lado}/abrir", dependencies=[Depends(exigir_portaria)])
def abrir_cancela_manual(lado: str, payload: Optional[schemas.AberturaManual] = None):
    lado = lado.lower()
    if lado not in ("entrada", "saida"):
        raise HTTPException(status_code=400, detail="Lado deve ser 'entrada' ou 'saida'.")
    motivo = payload.motivo if payload and payload.motivo else "Liberação manual pelo porteiro"
    log_id, enviado = orchestractor.abrir_cancela_manual(lado, motivo)
    return {"status": "ok", "id_log": log_id, "comando_enviado": enviado,
            "aviso": None if enviado else "MQTT offline: a cancela não recebeu o comando."}


@app.post("/api/portaria/simular/{lado}", dependencies=[Depends(exigir_portaria)])
def simular_sensor(lado: str):
    """Testa o fluxo completo sem a ESP32 WROOM (faz o papel do sensor ultrassônico)."""
    lado = lado.lower()
    if lado not in ("entrada", "saida"):
        raise HTTPException(status_code=400, detail="Lado deve ser 'entrada' ou 'saida'.")
    aceito = orchestractor.enfileirar("ENTRADA" if lado == "entrada" else "SAIDA")
    return {"status": "ok" if aceito else "ignorado (evento repetido em menos de 3 s)"}


# ==========================
# VAGAS (vagas.html)
# ==========================
@app.get("/api/video_feed")
def video_feed():
    return StreamingResponse(parking_service.gerar_frames_mjpeg(),
                             media_type="multipart/x-mixed-replace; boundary=frame")


@app.get("/api/vagas")
def listar_vagas(db: Session = Depends(get_db)):
    resultado = []
    for v in db.query(Vaga).order_by(Vaga.numero).all():
        dono = v.unidade.moradores[0] if v.unidade and v.unidade.moradores else None
        resultado.append({
            "numero": v.numero,
            "fk_unidade": v.fk_unidade,
            "bloco": v.unidade.bloco if v.unidade else None,
            "apartamento": v.unidade.apartamento if v.unidade else None,
            "fk_morador_dono": dono.id if dono else None,
            "coordenadas": v.coordenadas or [],  # lista plana [x1, y1, ..., x4, y4]
            "ocupada": bool(v.ocupada),
            "conflito": bool(v.status_conflito),
        })
    return resultado


@app.get("/api/vagas/verificar/{numero_vaga}/{morador_id}")
def verificar_vaga(numero_vaga: str, morador_id: int, db: Session = Depends(get_db)):
    vaga = db.query(Vaga).filter(Vaga.numero == numero_vaga).first()
    if not vaga:
        raise HTTPException(status_code=404, detail="Número da vaga não existe.")
    morador = db.get(Morador, morador_id)
    if not morador or morador.fk_unidade != vaga.fk_unidade:
        raise HTTPException(status_code=400, detail="Vaga não pertence a este morador.")
    return {"status": "ok", "morador_nome": morador.nome}


def _salvar_coordenadas(db: Session, numero: str, coordenadas: list) -> Vaga:
    vaga = db.query(Vaga).filter(Vaga.numero == numero).first()
    if not vaga:
        raise HTTPException(status_code=404, detail=f"Vaga {numero} não encontrada.")
    vaga.coordenadas = coordenadas
    return vaga


@app.put("/api/vagas/{numero_vaga}/coordenadas", dependencies=[Depends(exigir_portaria)])
def atualizar_coordenadas_vaga(numero_vaga: str, payload: schemas.CoordenadasVaga,
                               db: Session = Depends(get_db)):
    _salvar_coordenadas(db, numero_vaga, payload.coordenadas)
    db.commit()
    parking_service.forcar_recarga()
    notificar_painel("ATUALIZACAO_VAGAS")
    return {"status": "ok", "mensagem": "Coordenadas atualizadas"}


@app.put("/api/vagas/coordenadas", dependencies=[Depends(exigir_portaria)])
def atualizar_coordenadas_lote(payload: schemas.CoordenadasLote, db: Session = Depends(get_db)):
    for item in payload.vagas:
        _salvar_coordenadas(db, item.numero, item.coordenadas)
    db.commit()
    parking_service.forcar_recarga()
    notificar_painel("ATUALIZACAO_VAGAS")
    return {"status": "ok", "mensagem": f"{len(payload.vagas)} vagas atualizadas"}


@app.post("/api/vagas/calibrar", dependencies=[Depends(exigir_portaria)])
def calibrar_vagas():
    """Chame com o estacionamento VAZIO: recaptura a imagem de fundo de todas as vagas."""
    parking_service.recalibrar()
    return {"status": "ok"}


# ==========================
# MORADOR: CADASTRO, LOGIN E SENHA
# ==========================
@app.post("/api/morador/cadastro", dependencies=[Depends(exigir_portaria)])
def cadastrar_morador(payload: schemas.MoradorCreate, db: Session = Depends(get_db)):
    # Validações ANTES de gravar qualquer coisa
    if db.query(Morador).filter_by(email=payload.email).first():
        raise HTTPException(status_code=400, detail="E-mail já cadastrado.")
    if db.query(Veiculo).filter_by(placa=payload.placa).first():
        raise HTTPException(status_code=400, detail="Placa já cadastrada no sistema.")
    if not facial_disponivel():
        raise HTTPException(status_code=503, detail="Reconhecimento facial indisponível no servidor "
                                                    "(instale face_recognition/dlib).")

    face_vector = extract_embedding(payload.foto_base64)
    if not face_vector:
        raise HTTPException(status_code=400, detail="Nenhum rosto detectado na foto. Tire outra, de frente.")

    try:
        # 1. Unidade (bloco + apartamento): busca ou cria
        unidade = db.query(Unidade).filter_by(bloco=payload.bloco, apartamento=payload.apartamento).first()
        if not unidade:
            unidade = Unidade(bloco=payload.bloco, apartamento=payload.apartamento)
            db.add(unidade)
            db.flush()

        # 2. Morador (senha em hash + rosto)
        novo_morador = Morador(
            nome=payload.nome,
            email=payload.email,
            senha_hash=get_password_hash(payload.senha),
            face_encoding=face_vector,
            fk_unidade=unidade.id,
        )
        db.add(novo_morador)
        db.flush()

        # 3. Veículo
        db.add(Veiculo(placa=payload.placa, marca=payload.marca, modelo=payload.modelo,
                       cor=payload.cor, fk_morador=novo_morador.id))

        # 4. Vaga da unidade (vaga "101A" <-> apto 101 bloco A), só se ainda não existir
        if not unidade.vaga:
            db.add(Vaga(numero=f"{unidade.apartamento}{unidade.bloco}", fk_unidade=unidade.id))

        db.commit()  # tudo junto ou nada
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="Dados duplicados (e-mail, placa ou número de vaga).")
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Erro interno ao cadastrar: {e}")

    invalidar_cache_moradores()  # o rosto novo já vale na próxima passagem pela portaria
    notificar_painel("ATUALIZACAO_VAGAS")
    return {"status": "ok", "mensagem": "Morador cadastrado com sucesso!", "id": novo_morador.id}


@app.post("/api/login")
def login(payload: schemas.MoradorLogin, db: Session = Depends(get_db)):
    user = db.query(Morador).filter(Morador.email == payload.email).first()
    if not user or not verify_password(payload.senha, user.senha_hash):
        raise HTTPException(status_code=401, detail="E-mail ou senha incorretos.")

    token = create_access_token({"sub": user.email, "id": user.id})  # vale 1 semana
    veiculo = user.veiculos[0] if user.veiculos else None
    return {
        "id": user.id,
        "nome": user.nome,
        "email": user.email,
        "apartamento_bloco": f"Apt {user.unidade.apartamento} - Bloco {user.unidade.bloco}",
        "carro": {"modelo": veiculo.modelo, "placa": veiculo.placa} if veiculo else None,
        "token": token,
        "token_type": "bearer",
    }


@app.put("/api/morador/senha")
def alterar_senha(payload: schemas.TrocarSenha, db: Session = Depends(get_db),
                  morador_token: Optional[int] = Depends(morador_do_token)):
    user = db.query(Morador).filter_by(email=payload.email).first()
    if not user or not verify_password(payload.senha_atual, user.senha_hash):
        raise HTTPException(status_code=400, detail="Senha atual incorreta.")
    garantir_dono(morador_token, user.id)

    user.senha_hash = get_password_hash(payload.nova_senha)
    db.commit()
    return {"status": "ok", "mensagem": "Senha alterada com sucesso"}


# Recuperação de senha: o código aparece no terminal da API (não há envio de e-mail).
codigos_recuperacao = {}


def _codigo_valido(email: str, codigo: str):
    dados = codigos_recuperacao.get(email)
    if not dados:
        raise HTTPException(status_code=400, detail="Nenhuma solicitação encontrada.")
    if datetime.now() > dados["expira"]:
        codigos_recuperacao.pop(email, None)
        raise HTTPException(status_code=400, detail="Código expirado.")
    dados["tentativas"] += 1
    if dados["tentativas"] > 5:
        codigos_recuperacao.pop(email, None)
        raise HTTPException(status_code=400, detail="Muitas tentativas. Peça um novo código.")
    if dados["codigo"] != codigo.strip():
        raise HTTPException(status_code=400, detail="Código incorreto.")


@app.post("/api/recuperar-senha/solicitar")
def solicitar_recuperacao_senha(payload: schemas.SolicitacaoRecuperacao, db: Session = Depends(get_db)):
    if not db.query(Morador).filter(Morador.email == payload.email).first():
        raise HTTPException(status_code=404, detail="E-mail não encontrado.")
    codigo = f"{random.SystemRandom().randint(100000, 999999)}"
    codigos_recuperacao[payload.email] = {"codigo": codigo, "expira": datetime.now() + timedelta(minutes=15),
                                          "tentativas": 0}
    print(f"\n[RECUPERAÇÃO] Código de {payload.email}: {codigo}\n")
    return {"status": "ok", "mensagem": "Código enviado para o e-mail."}


@app.post("/api/recuperar-senha/validar")
def validar_codigo_recuperacao(payload: schemas.ValidacaoCodigo):
    _codigo_valido(payload.email, payload.codigo)
    return {"status": "ok", "mensagem": "Código validado."}


@app.post("/api/recuperar-senha/redefinir")
def redefinir_senha(payload: schemas.RedefinicaoSenha, db: Session = Depends(get_db)):
    _codigo_valido(payload.email, payload.codigo)
    morador = db.query(Morador).filter(Morador.email == payload.email).first()
    if not morador:
        raise HTTPException(status_code=404, detail="Morador não encontrado.")
    morador.senha_hash = get_password_hash(payload.nova_senha)
    db.commit()
    codigos_recuperacao.pop(payload.email, None)
    return {"status": "ok", "mensagem": "Senha redefinida com sucesso!"}


# ==========================
# VEÍCULO DO MORADOR
# ==========================
@app.put("/api/veiculos/morador/{morador_id}")
def atualizar_veiculo(morador_id: int, payload: schemas.VeiculoUpdate, db: Session = Depends(get_db),
                      morador_token: Optional[int] = Depends(morador_do_token)):
    garantir_dono(morador_token, morador_id)
    if not db.get(Morador, morador_id):
        raise HTTPException(status_code=404, detail="Morador não encontrado.")

    existente = db.query(Veiculo).filter(Veiculo.placa == payload.placa).first()
    if existente and existente.fk_morador != morador_id:
        raise HTTPException(status_code=400, detail="Placa já usada por outro morador.")

    veiculo = existente or db.query(Veiculo).filter(Veiculo.fk_morador == morador_id).first()
    if veiculo:
        veiculo.placa = payload.placa
        if payload.modelo is not None:
            veiculo.modelo = payload.modelo
        if payload.marca is not None:
            veiculo.marca = payload.marca
        if payload.cor is not None:
            veiculo.cor = payload.cor
    else:
        db.add(Veiculo(placa=payload.placa, modelo=payload.modelo or "Não informado",
                       marca=payload.marca or "Não informada", cor=payload.cor or "Não informada",
                       fk_morador=morador_id))
    db.commit()
    return {"status": "ok", "mensagem": "Veículo atualizado"}


@app.delete("/api/veiculos/morador/{morador_id}")
def remover_veiculo(morador_id: int, placa: Optional[str] = None, db: Session = Depends(get_db),
                    morador_token: Optional[int] = Depends(morador_do_token)):
    garantir_dono(morador_token, morador_id)
    consulta = db.query(Veiculo).filter(Veiculo.fk_morador == morador_id)
    if placa:
        consulta = consulta.filter(Veiculo.placa == placa.upper().replace("-", ""))
    veiculo = consulta.first()
    if not veiculo:
        raise HTTPException(status_code=404, detail="Veículo não encontrado.")
    db.delete(veiculo)
    db.commit()
    return {"status": "ok"}


# ==========================
# VISITANTES
# ==========================
def _calcular_periodo(tipo_visita: str, horario_inicio: Optional[str], horario_fim: Optional[str]):
    agora = datetime.now()
    if tipo_visita == "unica":
        return agora, agora + timedelta(hours=12)
    try:
        inicio = datetime.strptime((horario_inicio or "").strip(), FORMATO_DATA)
        fim = datetime.strptime((horario_fim or "").strip(), FORMATO_DATA)
    except ValueError:
        raise HTTPException(status_code=400, detail="Período inválido. Use dd/mm/aaaa hh:mm.")
    if fim <= inicio:
        raise HTTPException(status_code=400, detail="A saída precisa ser depois da entrada.")
    if fim <= agora:
        raise HTTPException(status_code=400, detail="O período informado já terminou.")
    return inicio, fim


@app.post("/api/visitantes/cadastro")
def cadastrar_visitante(payload: schemas.VisitanteCreate, db: Session = Depends(get_db),
                        morador_token: Optional[int] = Depends(morador_do_token)):
    garantir_dono(morador_token, payload.fk_id_morador)
    morador = db.get(Morador, payload.fk_id_morador)
    if not morador:
        raise HTTPException(status_code=404, detail="Morador anfitrião não encontrado.")

    inicio, fim = _calcular_periodo(payload.tipo_visita, payload.horario_inicio, payload.horario_fim)

    try:
        # Com CPF: reaproveita o cadastro do visitante. Sem CPF: cria um novo (CPF fica NULL).
        visitante = db.query(Visitante).filter_by(cpf=payload.cpf).first() if payload.cpf else None
        if visitante:
            visitante.nome = payload.nome
            if payload.cnh:
                visitante.cnh = payload.cnh
        else:
            visitante = Visitante(nome=payload.nome, cpf=payload.cpf, cnh=payload.cnh)
            db.add(visitante)
            db.flush()

        agendamento = AgendamentoVisita(
            fk_morador=morador.id,
            fk_visitante=visitante.id,
            placa_veiculo=payload.placa_veiculo,
            inicio=inicio,
            fim=fim,
        )
        db.add(agendamento)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="Dados duplicados do visitante.")
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Erro interno ao salvar visitante: {e}")

    notificar_painel("ATUALIZACAO_VAGAS")
    return {"status": "ok", "mensagem": "Visitante cadastrado com sucesso!", "id_agendamento": agendamento.id}


@app.get("/api/visitantes/morador/{morador_id}")
def listar_visitantes_morador(morador_id: int, db: Session = Depends(get_db),
                              morador_token: Optional[int] = Depends(morador_do_token)):
    garantir_dono(morador_token, morador_id)
    agendamentos = db.query(AgendamentoVisita).filter(
        AgendamentoVisita.fk_morador == morador_id,
        AgendamentoVisita.cancelado == False,  # noqa: E712
        AgendamentoVisita.fim >= datetime.now(),
    ).order_by(AgendamentoVisita.inicio).all()

    return [{
        "id_agendamento": ag.id,
        "nome": ag.visitante.nome,
        "placa_veiculo": ag.placa_veiculo,
        "data_entrada": ag.inicio.isoformat(),
        "data_saida": ag.fim.isoformat(),
    } for ag in agendamentos]


def _agendamento_do_morador(db: Session, agendamento_id: int, morador_token: Optional[int]) -> AgendamentoVisita:
    agendamento = db.get(AgendamentoVisita, agendamento_id)
    if not agendamento or agendamento.cancelado:
        raise HTTPException(status_code=404, detail="Agendamento não encontrado.")
    garantir_dono(morador_token, agendamento.fk_morador)
    return agendamento


@app.delete("/api/visitantes/agendamento/{agendamento_id}")
def cancelar_agendamento(agendamento_id: int, db: Session = Depends(get_db),
                         morador_token: Optional[int] = Depends(morador_do_token)):
    agendamento = _agendamento_do_morador(db, agendamento_id, morador_token)
    agendamento.cancelado = True  # não apaga: os logs de acesso continuam apontando para ele
    db.commit()
    return {"status": "ok", "mensagem": "Visita cancelada."}


@app.put("/api/visitantes/agendamento/{agendamento_id}")
def atualizar_agendamento(agendamento_id: int, payload: schemas.AgendamentoUpdate,
                          db: Session = Depends(get_db),
                          morador_token: Optional[int] = Depends(morador_do_token)):
    agendamento = _agendamento_do_morador(db, agendamento_id, morador_token)
    agendamento.inicio, agendamento.fim = _calcular_periodo(
        payload.tipo_visita, payload.horario_inicio, payload.horario_fim)
    if payload.placa_veiculo:
        agendamento.placa_veiculo = payload.placa_veiculo
    db.commit()
    return {"status": "ok", "mensagem": "Atualizado com sucesso"}


# ==========================
# NOTIFICAÇÕES DO APP
# ==========================
_ESTILO_ALERTA = {
    "INVASAO_VAGA": ("Vaga invadida!", "warning", "#EF4444"),
    "VISITANTE_CHEGOU": ("Visitante chegou", "person-add", "#ffa502"),
    "VISITA_EXCEDIDA": ("Visita passou do horário", "time", "#F59E0B"),
    "VEICULO_TEMPORARIO": ("Veículo temporário", "car", "#1e90ff"),
    "VEICULO_DE_OUTRO_MORADOR": ("Seu carro na portaria", "shield", "#EF4444"),
    "ROSTO_NAO_CONFERE": ("Seu carro na portaria", "shield", "#EF4444"),
    "SAIDA_SUSPEITA": ("Saída suspeita", "shield", "#EF4444"),
}


@app.get("/api/notificacoes/morador/{morador_id}")
def listar_notificacoes(morador_id: int, db: Session = Depends(get_db),
                        morador_token: Optional[int] = Depends(morador_do_token)):
    garantir_dono(morador_token, morador_id)
    morador = db.get(Morador, morador_id)
    if not morador:
        raise HTTPException(status_code=404, detail="Morador não encontrado.")

    notificacoes = []
    vaga = morador.unidade.vaga if morador.unidade else None
    if vaga:
        if vaga.status_conflito:
            notificacoes.append({"id": f"vaga_{vaga.id}", "title": "Alerta de Vaga!",
                                 "desc": f"Veículo não autorizado na vaga {vaga.numero}.",
                                 "time": "Agora", "icon": "warning", "color": "#ff4757"})
        elif vaga.ocupada:
            notificacoes.append({"id": f"vaga_{vaga.id}", "title": "Vaga Ocupada",
                                 "desc": f"Vaga {vaga.numero}: veículo estacionado.",
                                 "time": "Ativa", "icon": "car", "color": "#1e90ff"})
        else:
            notificacoes.append({"id": f"vaga_{vaga.id}", "title": "Vaga Livre",
                                 "desc": f"Vaga {vaga.numero} livre.",
                                 "time": "Ativa", "icon": "checkmark-circle", "color": "#2ed573"})

    # Alertas ligados ao morador ou à vaga dele (por chave estrangeira, sem procurar nome no texto)
    filtro = [AlertaPainel.fk_morador == morador_id]
    if vaga:
        filtro.append(AlertaPainel.fk_vaga == vaga.id)
    alertas = db.query(AlertaPainel).filter(or_(*filtro)).order_by(AlertaPainel.criado_em.desc()).limit(15).all()
    for alerta in alertas:
        titulo, icone, cor = _ESTILO_ALERTA.get(alerta.tipo, ("Aviso", "notifications", "#F59E0B"))
        notificacoes.append({"id": f"alerta_{alerta.id}", "title": titulo, "desc": alerta.texto,
                             "time": alerta.criado_em.strftime("%d/%m %H:%M"), "icon": icone, "color": cor})

    if not notificacoes:
        notificacoes.append({"id": "welcome_1", "title": "Boas-vindas!", "desc": "Tudo certo.",
                             "time": "", "icon": "home", "color": "#1e90ff"})
    return notificacoes


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, log_level="info")
