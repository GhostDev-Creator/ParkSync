# Arquivo: Back-End/services/orchestractor.py
#
# Fluxo da portaria (um carro por vez, numa fila):
#   1. ESP32 WROOM publica "DETECTADO" em parksync/sensor/entrada (ou saida)
#   2. Backend acorda a ESP32-CAM daquele lado (parksync/camera/<lado>/acordar)
#   3. Ao mesmo tempo: foto da ESP32-CAM (/capture) -> YOLO + OCR  |  webcam -> reconhecimento facial
#   4. Aplica as regras abaixo, grava o log e, se liberado, manda "ABRIR" para a cancela.
#
# REGRAS DE ENTRADA
#   - Rosto de morador + placa de um veículo DELE ...................... libera (MORADOR)
#   - Placa com visita agendada ativa (com ou sem rosto) ............... libera (VISITANTE)
#   - Rosto de morador + placa desconhecida (carro emprestado/alugado) .. libera como TEMPORARIO
#       se PERMITIR_VEICULO_TEMPORARIO=true e o morador não tiver outro temporário dentro
#   - Rosto de morador + placa de OUTRO morador ......................... nega e avisa o dono do carro
#   - Rosto de morador + placa não lida ................................. nega (porteiro pode abrir manual)
#   - Placa de morador sem rosto reconhecido ............................ nega e avisa o dono do carro
#   - Resto ............................................................. nega
# REGRAS DE SAÍDA
#   - Rosto de morador (placa dele, temporária dele ou não lida) ........ libera
#   - Rosto de morador + placa de OUTRO morador ......................... nega e avisa o dono do carro
#   - Placa de visitante com agendamento (mesmo vencido) ................ libera (avisa se passou do horário)
#   - Resto ............................................................. nega (saída suspeita)

import base64
import os
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from queue import Queue

import cv2
import numpy as np
import requests

from utils import config
from utils.eventos import notificar_painel
from database.setup_db import SessionLocal
from database.models import (
    LogAcesso, VeiculoTemporario, AgendamentoVisita, AlertaPainel, Veiculo,
    DirecaoEnum, TipoAcessoEnum, StatusTemporarioEnum,
)
from services.face_service import identificar_morador, abrir_camera
from services.plate_service import extrair_placa_de_recorte
from mqtt.broker import (
    broker, TOPICO_SENSOR_ENTRADA, TOPICO_SENSOR_SAIDA, TOPICO_CANCELA, TOPICO_ACORDAR_CAMERA,
)

fila_eventos = Queue()
_ultimo_evento = {"ENTRADA": 0.0, "SAIDA": 0.0}
_lock_evento = threading.Lock()
_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="ocr-placa")
_iniciado = False

DEBOUNCE_SEGUNDOS = 3.0


# ==========================================
# INICIALIZAÇÃO E EVENTOS
# ==========================================
def iniciar_orquestrador():
    """Registra os tópicos dos sensores, conecta no MQTT e liga a thread da fila."""
    global _iniciado
    if _iniciado:
        return
    _iniciado = True
    broker.cadastrar_assunto(TOPICO_SENSOR_ENTRADA, adicionar_evento_sensor)
    broker.cadastrar_assunto(TOPICO_SENSOR_SAIDA, adicionar_evento_sensor)
    broker.iniciar()
    threading.Thread(target=_processar_fila, daemon=True, name="orquestrador").start()
    print("🧠 Orquestrador iniciado: aguardando sensores (MQTT).")


def adicionar_evento_sensor(topico, mensagem):
    """Callback do MQTT para parksync/sensor/entrada e parksync/sensor/saida."""
    if str(mensagem).strip().upper() != "DETECTADO":
        return
    direcao = "ENTRADA" if topico.endswith("entrada") else "SAIDA"
    enfileirar(direcao)


def enfileirar(direcao: str) -> bool:
    """Coloca um evento na fila (também usado pela rota de simulação). Ignora repetição em 3 s."""
    direcao = direcao.upper()
    with _lock_evento:
        agora = time.time()
        if agora - _ultimo_evento[direcao] < DEBOUNCE_SEGUNDOS:
            print(f"⏭️  Evento de {direcao} repetido ignorado.")
            return False
        _ultimo_evento[direcao] = agora

    lado = "entrada" if direcao == "ENTRADA" else "saida"
    broker.enviar_mensagem(TOPICO_ACORDAR_CAMERA.format(lado=lado), "ACORDA")
    fila_eventos.put({"direcao": direcao, "timestamp": time.time()})
    print(f"📥 Evento de {direcao} na fila.")
    return True


def _processar_fila():
    while True:
        evento = fila_eventos.get()
        try:
            with SessionLocal() as db:
                try:
                    if evento["direcao"] == "ENTRADA":
                        _processar_entrada(db)
                    else:
                        _processar_saida(db)
                except Exception:
                    db.rollback()
                    raise
        except Exception as e:
            print(f"❌ Erro ao processar evento de {evento.get('direcao')}: {e}")
        finally:
            fila_eventos.task_done()


# ==========================================
# CAPTURA DE IMAGENS
# ==========================================
def _url_captura(camera):
    url = camera if camera.startswith("http") else f"http://{camera}"
    url = url.rstrip("/")
    return url if url.endswith("/capture") else f"{url}/capture"


def _capturar_foto_placa(camera):
    """ESP32-CAM via HTTP GET /capture. Se for um número, usa uma webcam (útil para testes)."""
    if camera is None:
        print("⚠️  Câmera de placa não configurada no .env.")
        return None

    if isinstance(camera, int):
        cap = abrir_camera(camera)
        try:
            if not cap.isOpened():
                return None
            for _ in range(5):
                cap.read()  # descarta frames escuros do início
            ret, frame = cap.read()
            return frame if ret else None
        finally:
            cap.release()

    url = _url_captura(camera)
    time.sleep(0.4)  # tempo para a ESP32-CAM acordar e ajustar exposição
    # (conectar, ler) em segundos: a 1ª tentativa espera mais pela foto, depois 2 tentativas curtas
    for tentativa, timeout in enumerate(((3, 10), (3, 5), (3, 5))):
        inicio = time.time()
        try:
            resposta = requests.get(url, timeout=timeout, headers={"Connection": "close"})
            if resposta.status_code == 200:
                frame = cv2.imdecode(np.frombuffer(resposta.content, np.uint8), cv2.IMREAD_COLOR)
                if frame is not None:
                    print(f"   📷 Foto da placa: {len(resposta.content) // 1024} KB em {time.time() - inicio:.1f} s")
                    return frame
                print(f"⚠️  ESP32-CAM ({url}) tentativa {tentativa + 1}: JPEG inválido")
            else:
                print(f"⚠️  ESP32-CAM ({url}) tentativa {tentativa + 1}: HTTP {resposta.status_code}")
        except requests.RequestException as e:
            print(f"⚠️  ESP32-CAM ({url}) tentativa {tentativa + 1}: {e}")
        time.sleep(0.3)
    return None


def _ler_placa(camera):
    frame = _capturar_foto_placa(camera)
    placa = extrair_placa_de_recorte(frame) if frame is not None else None
    return frame, placa


def _capturar_rosto_webcam(db, tempo_limite=None):
    """Mantém a webcam (a mesma da entrada e da saída) aberta alguns segundos procurando um morador."""
    tempo_limite = tempo_limite or config.TEMPO_BUSCA_ROSTO
    cap = abrir_camera(config.FACE_CAM)
    if not cap.isOpened():
        print(f"⚠️  Não abri a webcam facial (FACE_CAM={config.FACE_CAM}).")
        return None, None

    morador, ultimo_frame = None, None
    inicio = time.time()
    try:
        while time.time() - inicio < tempo_limite:
            ret, frame = cap.read()
            if not ret:
                time.sleep(0.05)
                continue
            ultimo_frame = frame
            morador = identificar_morador(frame, db)
            if morador:
                break
    finally:
        cap.release()
    return morador, ultimo_frame


def _salvar_imagem_disco(frame, prefixo):
    if frame is None:
        return None
    os.makedirs(config.PASTA_CAPTURAS, exist_ok=True)
    nome = f"{prefixo}_{datetime.now():%Y%m%d_%H%M%S}_{uuid.uuid4().hex[:6]}.jpg"
    caminho = os.path.join(config.PASTA_CAPTURAS, nome)
    cv2.imwrite(caminho, frame)
    return caminho


def _enviar_imagem_painel(frame, camera):
    if frame is None:
        return
    altura, largura = frame.shape[:2]
    if largura > 480:
        frame = cv2.resize(frame, (480, int(altura * 480 / largura)))
    ok, buffer = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
    if ok:
        notificar_painel("IMAGEM_CAPTURADA", camera=camera, base64=base64.b64encode(buffer).decode("ascii"))


def _coletar(db, direcao):
    """Foto da placa (em paralelo) + reconhecimento facial."""
    camera_placa = config.PE_PLATE_CAM if direcao == "ENTRADA" else config.PS_PLATE_CAM
    futuro_placa = _executor.submit(_ler_placa, camera_placa)
    morador, frame_rosto = _capturar_rosto_webcam(db)
    try:
        frame_placa, placa = futuro_placa.result(timeout=45)
    except Exception as e:
        print(f"⚠️  Falha na leitura da placa: {e}")
        frame_placa, placa = None, None

    _enviar_imagem_painel(frame_placa, "PLACA")
    _enviar_imagem_painel(frame_rosto, "ROSTO")

    sufixo = "in" if direcao == "ENTRADA" else "out"
    path_placa = _salvar_imagem_disco(frame_placa, f"placa_{sufixo}")
    path_rosto = _salvar_imagem_disco(frame_rosto, f"rosto_{sufixo}")
    print(f"   👤 Morador: {morador.nome if morador else 'não reconhecido'} | 🔤 Placa: {placa or 'não lida'}")
    return morador, placa, path_rosto, path_placa


# ==========================================
# CONSULTAS
# ==========================================
def _agendamento_ativo(db, placa):
    agora = datetime.now()
    return db.query(AgendamentoVisita).filter(
        AgendamentoVisita.placa_veiculo == placa,
        AgendamentoVisita.cancelado == False,  # noqa: E712
        AgendamentoVisita.inicio <= agora,
        AgendamentoVisita.fim >= agora,
    ).order_by(AgendamentoVisita.fim.desc()).first()


def _agendamento_para_saida(db, placa):
    """Último agendamento dessa placa que já começou (pode ter vencido: o visitante precisa sair)."""
    return db.query(AgendamentoVisita).filter(
        AgendamentoVisita.placa_veiculo == placa,
        AgendamentoVisita.inicio <= datetime.now(),
    ).order_by(AgendamentoVisita.fim.desc()).first()


def _temporario_dentro(db, fk_morador, placa=None):
    consulta = db.query(VeiculoTemporario).filter(
        VeiculoTemporario.fk_morador == fk_morador,
        VeiculoTemporario.status == StatusTemporarioEnum.DENTRO,
    )
    if placa:
        consulta = consulta.filter(VeiculoTemporario.placa == placa)
    return consulta.first()


# ==========================================
# REGISTRO, ALERTA E CANCELA
# ==========================================
def _registrar_log(db, direcao, tipo, placa, path_rosto, path_placa, sucesso, motivo,
                   fk_morador=None, fk_agendamento=None):
    """Cria o log e devolve com id (flush), sem commit: quem chama decide o commit."""
    log = LogAcesso(
        direcao=direcao, tipo=tipo, placa_lida=placa,
        fk_morador=fk_morador, fk_agendamento=fk_agendamento,
        path_foto_rosto=path_rosto, path_foto_placa=path_placa,
        sucesso=sucesso, motivo=motivo,
    )
    db.add(log)
    db.flush()
    return log


def _gerar_alerta(db, tipo, texto, fk_log=None, fk_morador=None, fk_vaga=None):
    db.add(AlertaPainel(tipo=tipo, texto=texto[:255], fk_log=fk_log, fk_morador=fk_morador, fk_vaga=fk_vaga))


def _abrir_cancela(lado):
    print(f"   🟢 Abrindo cancela de {lado.upper()}")
    return broker.enviar_mensagem(TOPICO_CANCELA.format(lado=lado), "ABRIR")


def _concluir(db, log, lado, alerta=None):
    """Grava tudo, abre a cancela (se liberado) e avisa o painel."""
    if alerta:
        _gerar_alerta(db, fk_log=log.id, **alerta)
    db.commit()
    if log.sucesso:
        _abrir_cancela(lado)
    else:
        print(f"   🔴 Acesso negado: {log.motivo}")
    notificar_painel("NOVO_ACESSO")
    if alerta:
        notificar_painel("NOVO_ALERTA")


def _negar(db, direcao, motivo, placa, path_rosto, path_placa, tipo_alerta, texto_alerta,
           fk_morador=None, fk_morador_alerta=None):
    lado = "entrada" if direcao == DirecaoEnum.ENTRADA else "saida"
    log = _registrar_log(db, direcao, TipoAcessoEnum.NEGADO, placa, path_rosto, path_placa, False, motivo,
                         fk_morador=fk_morador)
    _concluir(db, log, lado, alerta={"tipo": tipo_alerta, "texto": texto_alerta, "fk_morador": fk_morador_alerta})


def abrir_cancela_manual(lado: str, motivo: str = "Liberação manual pelo porteiro"):
    """Usado pela rota da portaria: registra log MANUAL e abre a cancela."""
    direcao = DirecaoEnum.ENTRADA if lado == "entrada" else DirecaoEnum.SAIDA
    with SessionLocal() as db:
        log = _registrar_log(db, direcao, TipoAcessoEnum.MANUAL, None, None, None, True, motivo)
        db.commit()
        enviado = _abrir_cancela(lado)
        notificar_painel("NOVO_ACESSO")
        return log.id, enviado


# ==========================================
# ENTRADA
# ==========================================
def _processar_entrada(db):
    print("\n[ORQUESTRADOR] 🚗 Fluxo de ENTRADA")
    E = DirecaoEnum.ENTRADA
    morador, placa, path_rosto, path_placa = _coletar(db, "ENTRADA")
    veiculo = db.query(Veiculo).filter_by(placa=placa).first() if placa else None
    agendamento = _agendamento_ativo(db, placa) if placa else None

    # 1) Visitante agendado: a placa basta
    if agendamento and not (veiculo and morador and veiculo.fk_morador == morador.id):
        log = _registrar_log(db, E, TipoAcessoEnum.VISITANTE, placa, path_rosto, path_placa, True,
                             f"Visitante agendado: {agendamento.visitante.nome}",
                             fk_agendamento=agendamento.id)
        _concluir(db, log, "entrada", alerta={
            "tipo": "VISITANTE_CHEGOU",
            "texto": f"Visitante {agendamento.visitante.nome} entrou (placa {placa}).",
            "fk_morador": agendamento.fk_morador,
        })
        return

    if morador:
        # 2) Morador com carro próprio
        if veiculo and veiculo.fk_morador == morador.id:
            log = _registrar_log(db, E, TipoAcessoEnum.MORADOR, placa, path_rosto, path_placa, True,
                                 "Morador e placa conferem", fk_morador=morador.id)
            _concluir(db, log, "entrada")
            return

        # 3) Placa não lida: não dá para conferir o carro
        if not placa:
            _negar(db, E, "Morador reconhecido, mas a placa não foi lida", placa, path_rosto, path_placa,
                   "PLACA_ILEGIVEL", f"{morador.nome} na entrada, placa não lida. Confira e libere manualmente.",
                   fk_morador=morador.id)
            return

        # 4) Carro de outro morador
        if veiculo:
            _negar(db, E, "Placa pertence a outro morador", placa, path_rosto, path_placa,
                   "VEICULO_DE_OUTRO_MORADOR",
                   f"{morador.nome} tentou entrar com o carro {placa}, que é de outro morador.",
                   fk_morador=morador.id, fk_morador_alerta=veiculo.fk_morador)
            return

        # 5) Carro desconhecido -> veículo temporário (regra configurável)
        if not config.PERMITIR_VEICULO_TEMPORARIO:
            _negar(db, E, "Veículo não cadastrado (temporário desativado)", placa, path_rosto, path_placa,
                   "VEICULO_NAO_CADASTRADO", f"{morador.nome} chegou com o carro {placa}, que não é cadastrado.",
                   fk_morador=morador.id)
            return

        mesmo_temp = _temporario_dentro(db, morador.id, placa)
        outro_temp = _temporario_dentro(db, morador.id)
        if outro_temp and not mesmo_temp:
            _negar(db, E, "Morador já tem um veículo temporário dentro", placa, path_rosto, path_placa,
                   "LIMITE_TEMPORARIO",
                   f"{morador.nome} já tem o temporário {outro_temp.placa} dentro e chegou com {placa}.",
                   fk_morador=morador.id)
            return

        log = _registrar_log(db, E, TipoAcessoEnum.TEMPORARIO, placa, path_rosto, path_placa, True,
                             "Morador reconhecido com veículo temporário", fk_morador=morador.id)
        if mesmo_temp is None:
            db.add(VeiculoTemporario(placa=placa, fk_morador=morador.id, fk_log_entrada=log.id,
                                     status=StatusTemporarioEnum.DENTRO))
        _concluir(db, log, "entrada", alerta={
            "tipo": "VEICULO_TEMPORARIO",
            "texto": f"{morador.nome} entrou com veículo temporário {placa}.",
            "fk_morador": morador.id,
        })
        return

    # Sem rosto reconhecido
    if veiculo:
        _negar(db, E, "Placa de morador, mas o rosto não foi reconhecido", placa, path_rosto, path_placa,
               "ROSTO_NAO_CONFERE", f"Carro {placa} tentou entrar sem o rosto do morador ser reconhecido.",
               fk_morador_alerta=veiculo.fk_morador)
        return

    _negar(db, E, "Sem permissão", placa, path_rosto, path_placa,
           "ACESSO_NEGADO", f"Tentativa de entrada negada. Placa: {placa or 'não identificada'}.")


# ==========================================
# SAÍDA
# ==========================================
def _processar_saida(db):
    print("\n[ORQUESTRADOR] 🚗 Fluxo de SAÍDA")
    S = DirecaoEnum.SAIDA
    morador, placa, path_rosto, path_placa = _coletar(db, "SAIDA")
    veiculo = db.query(Veiculo).filter_by(placa=placa).first() if placa else None

    if morador:
        if veiculo and veiculo.fk_morador != morador.id:
            _negar(db, S, "Placa pertence a outro morador", placa, path_rosto, path_placa,
                   "SAIDA_SUSPEITA", f"{morador.nome} tentou sair com o carro {placa}, que é de outro morador.",
                   fk_morador=morador.id, fk_morador_alerta=veiculo.fk_morador)
            return

        temp = _temporario_dentro(db, morador.id, placa) if placa else None
        tipo = TipoAcessoEnum.TEMPORARIO if temp else TipoAcessoEnum.MORADOR
        log = _registrar_log(db, S, tipo, placa, path_rosto, path_placa, True,
                             "Saída de morador", fk_morador=morador.id)
        if temp:
            temp.status = StatusTemporarioEnum.SAIU
            temp.fk_log_saida = log.id
        _concluir(db, log, "saida")
        return

    if placa:
        agendamento = _agendamento_para_saida(db, placa)
        if agendamento:
            log = _registrar_log(db, S, TipoAcessoEnum.VISITANTE, placa, path_rosto, path_placa, True,
                                 "Saída de visitante", fk_agendamento=agendamento.id)
            alerta = None
            if agendamento.fim < datetime.now():
                alerta = {"tipo": "VISITA_EXCEDIDA",
                          "texto": f"Visitante {agendamento.visitante.nome} saiu depois do horário ({placa}).",
                          "fk_morador": agendamento.fk_morador}
            _concluir(db, log, "saida", alerta=alerta)
            return

    _negar(db, S, "Saída não autorizada", placa, path_rosto, path_placa,
           "SAIDA_SUSPEITA", f"Saída bloqueada: pessoa não reconhecida. Placa: {placa or 'não identificada'}.",
           fk_morador_alerta=veiculo.fk_morador if veiculo else None)
