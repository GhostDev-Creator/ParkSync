# Arquivo: Back-End/services/parking_service.py
#
# Monitor das vagas (webcam de cima). Para cada vaga desenhada no vagas.html:
#   1. guarda uma foto da vaga vazia (fundo);
#   2. compara cada frame com o fundo: se muita coisa mudou por 5 s, a vaga está ocupada;
#   3. lê a placa do carro parado e confere se ele pode usar aquela vaga;
#   4. se não puder, marca conflito e gera alerta para o porteiro e para o morador dono.
#
# A mesma câmera alimenta o /api/video_feed (o vagas.html usa de fundo para desenhar),
# assim a webcam só é aberta UMA vez.

import threading
import time
from datetime import datetime

import cv2
import numpy as np

from utils import config
from utils.eventos import notificar_painel
from database.setup_db import SessionLocal
from database.models import (
    Vaga, Veiculo, VeiculoTemporario, AgendamentoVisita, AlertaPainel, StatusTemporarioEnum
)
from services.plate_service import extrair_placa_de_recorte
from schemas import normalizar_coordenadas

LARGURA, ALTURA = 1920, 1080
INTERVALO_PROCESSAMENTO = 0.5  # segundos entre análises das vagas
INTERVALO_RELOAD = 10.0        # segundos entre recargas das coordenadas do banco
INTERVALO_OCR = 3.0            # segundos entre leituras de placa na mesma vaga

_parar = threading.Event()
_lock_frame = threading.Lock()
_ultimo_jpeg = None
_vagas_ativas = {}
_lock_vagas = threading.Lock()
_rodando = False


# ======================================================================
# COORDENADAS
# ======================================================================
def _poligono_em_pixels(coords):
    plano = normalizar_coordenadas(coords)
    if not plano:
        return None
    escala_x = LARGURA / float(config.FRONT_LARGURA)
    escala_y = ALTURA / float(config.FRONT_ALTURA)
    pontos = [[int(plano[i] * escala_x), int(plano[i + 1] * escala_y)] for i in range(0, 8, 2)]
    return np.array(pontos, np.int32).reshape((-1, 1, 2))


def recalibrar():
    """Esquece o fundo de todas as vagas. Chame com o estacionamento VAZIO."""
    with _lock_vagas:
        for dados in _vagas_ativas.values():
            dados["fundo_vazio"] = None
    print("🎯 Fundo das vagas será recapturado no próximo frame.")


def _recarregar_vagas():
    with SessionLocal() as db:
        vagas = db.query(Vaga).all()
        ids_no_banco = set()
        with _lock_vagas:
            for vaga in vagas:
                poligono = _poligono_em_pixels(vaga.coordenadas)
                if poligono is None:
                    continue
                ids_no_banco.add(vaga.id)
                atual = _vagas_ativas.get(vaga.id)
                if atual is None:
                    _vagas_ativas[vaga.id] = {
                        "numero": vaga.numero,
                        "poligono": poligono,
                        "ocupada": bool(vaga.ocupada),
                        "tempo_inicio": None,
                        "tempo_livre": None,
                        "ultimo_ocr": 0.0,
                        "fundo_vazio": None,
                    }
                elif not np.array_equal(atual["poligono"], poligono):
                    # Desenho mudou: o fundo antigo tem outro tamanho, precisa recapturar
                    atual["poligono"] = poligono
                    atual["fundo_vazio"] = None
            for vaga_id in list(_vagas_ativas.keys()):
                if vaga_id not in ids_no_banco:
                    del _vagas_ativas[vaga_id]


# ======================================================================
# REGRAS DA VAGA
# ======================================================================
def _placa_autorizada_na_vaga(db, vaga, placa):
    """A placa pode ocupar essa vaga? (carro do morador, carro temporário dele ou visitante dele)"""
    if vaga.unidade is None:
        return True  # vaga comum / sem dono: não gera conflito
    ids_moradores = [m.id for m in vaga.unidade.moradores]
    if not ids_moradores:
        return True

    if db.query(Veiculo).filter(Veiculo.placa == placa, Veiculo.fk_morador.in_(ids_moradores)).first():
        return True
    if db.query(VeiculoTemporario).filter(
        VeiculoTemporario.placa == placa,
        VeiculoTemporario.fk_morador.in_(ids_moradores),
        VeiculoTemporario.status == StatusTemporarioEnum.DENTRO,
    ).first():
        return True
    agora = datetime.now()
    if db.query(AgendamentoVisita).filter(
        AgendamentoVisita.placa_veiculo == placa,
        AgendamentoVisita.fk_morador.in_(ids_moradores),
        AgendamentoVisita.cancelado == False,  # noqa: E712
        AgendamentoVisita.inicio <= agora,
        AgendamentoVisita.fim >= agora,
    ).first():
        return True
    return False


def _marcar_ocupada(vaga_id):
    with SessionLocal() as db:
        vaga = db.get(Vaga, vaga_id)
        if vaga and not vaga.ocupada:
            vaga.ocupada = True
            db.commit()
            notificar_painel("ATUALIZACAO_VAGAS")


def _registrar_placa(vaga_id, placa):
    with SessionLocal() as db:
        vaga = db.get(Vaga, vaga_id)
        if vaga is None or placa == vaga.current_plate:
            return
        vaga.current_plate = placa

        if not _placa_autorizada_na_vaga(db, vaga, placa):
            if not vaga.status_conflito:
                vaga.status_conflito = True
                dono = vaga.unidade.moradores[0] if vaga.unidade and vaga.unidade.moradores else None
                db.add(AlertaPainel(
                    tipo="INVASAO_VAGA",
                    texto=f"Vaga {vaga.numero} ocupada por veículo não autorizado (placa {placa}).",
                    fk_vaga=vaga.id,
                    fk_morador=dono.id if dono else None,
                ))
                db.commit()
                notificar_painel("NOVO_ALERTA")
                return
        else:
            vaga.status_conflito = False
        db.commit()
        notificar_painel("ATUALIZACAO_VAGAS")


def _marcar_livre(vaga_id):
    with SessionLocal() as db:
        vaga = db.get(Vaga, vaga_id)
        if vaga is None:
            return
        # Resolve só os alertas DESTA vaga
        for alerta in db.query(AlertaPainel).filter_by(fk_vaga=vaga.id, resolvido=False).all():
            alerta.resolvido = True
        vaga.ocupada = False
        vaga.current_plate = None
        vaga.status_conflito = False
        db.commit()
        notificar_painel("ATUALIZACAO_VAGAS")


# ======================================================================
# PROCESSAMENTO DE IMAGEM
# ======================================================================
def _analisar_vaga(frame, dados, vaga_id):
    pts = dados["poligono"]
    x, y, w, h = cv2.boundingRect(pts)
    x, y = max(x, 0), max(y, 0)
    if w <= 0 or h <= 0:
        return

    mask = np.zeros(frame.shape[:2], dtype=np.uint8)
    cv2.fillPoly(mask, [pts], 255)
    recorte = cv2.bitwise_and(frame, frame, mask=mask)[y:y + h, x:x + w]
    mascara_recorte = mask[y:y + h, x:x + w]
    area_poligono = cv2.countNonZero(mascara_recorte)
    if recorte.size == 0 or area_poligono == 0:
        return

    cinza = cv2.GaussianBlur(cv2.cvtColor(recorte, cv2.COLOR_BGR2GRAY), (21, 21), 0)

    if dados["fundo_vazio"] is None or dados["fundo_vazio"].shape != cinza.shape:
        dados["fundo_vazio"] = cinza.astype(np.float32)
        return

    diferenca = cv2.absdiff(cv2.convertScaleAbs(dados["fundo_vazio"]), cinza)
    _, thresh = cv2.threshold(diferenca, 25, 255, cv2.THRESH_BINARY)
    porcentagem = (cv2.countNonZero(cv2.bitwise_and(thresh, mascara_recorte)) / area_poligono) * 100
    agora = time.time()

    if porcentagem > config.OCUPACAO_PERCENTUAL:
        dados["tempo_livre"] = None
        if dados["tempo_inicio"] is None:
            dados["tempo_inicio"] = agora
        elif agora - dados["tempo_inicio"] >= config.TEMPO_CONFIRMA_VAGA:
            if not dados["ocupada"]:
                dados["ocupada"] = True
                _marcar_ocupada(vaga_id)
            if agora - dados["ultimo_ocr"] >= INTERVALO_OCR:
                dados["ultimo_ocr"] = agora
                placa = extrair_placa_de_recorte(recorte)
                if placa:
                    _registrar_placa(vaga_id, placa)
    else:
        dados["tempo_inicio"] = None
        if dados["ocupada"]:
            # Espera 3 s vazia para não "piscar" por causa de sombra/reflexo
            if dados["tempo_livre"] is None:
                dados["tempo_livre"] = agora
            elif agora - dados["tempo_livre"] >= 3.0:
                dados["ocupada"] = False
                dados["tempo_livre"] = None
                _marcar_livre(vaga_id)
        elif porcentagem < config.OCUPACAO_PERCENTUAL / 2:
            # Vaga vazia: adapta o fundo devagar às mudanças de luz do ambiente
            cv2.accumulateWeighted(cinza, dados["fundo_vazio"], 0.02)


def _abrir_camera():
    from services.face_service import abrir_camera
    cap = abrir_camera(config.PM_PARK_CAM)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, LARGURA)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, ALTURA)
    return cap


def start_monitoring():
    """Loop principal (roda numa thread). Se a câmera cair, tenta abrir de novo a cada 5 s."""
    global _ultimo_jpeg, _rodando
    _rodando = True
    _parar.clear()
    print(f"🅿️  Monitor de vagas iniciado (câmera PM_PARK_CAM={config.PM_PARK_CAM}).")
    ultimo_reload = 0.0
    ultimo_processamento = 0.0
    cap = None
    avisou_falha = False

    try:
        while not _parar.is_set():
            if cap is None or not cap.isOpened():
                cap = _abrir_camera()
                if not cap.isOpened():
                    if not avisou_falha:
                        print(f"⚠️  Não abri a câmera das vagas (PM_PARK_CAM={config.PM_PARK_CAM}). "
                              "Vou continuar tentando a cada 5 s em silêncio.")
                        avisou_falha = True
                    cap.release()
                    cap = None
                    _parar.wait(5)
                    continue
                if avisou_falha:
                    print("✅ Câmera das vagas conectada.")
                    avisou_falha = False

            ret, frame = cap.read()
            if not ret or frame is None:
                cap.release()
                cap = None
                _parar.wait(1)
                continue

            frame = cv2.resize(frame, (LARGURA, ALTURA))
            ok, buffer = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
            if ok:
                with _lock_frame:
                    _ultimo_jpeg = buffer.tobytes()

            agora = time.time()
            if agora - ultimo_reload > INTERVALO_RELOAD:
                try:
                    _recarregar_vagas()
                except Exception as e:
                    print(f"⚠️  Erro ao recarregar vagas: {e}")
                ultimo_reload = agora

            if agora - ultimo_processamento < INTERVALO_PROCESSAMENTO:
                continue
            ultimo_processamento = agora

            with _lock_vagas:
                itens = list(_vagas_ativas.items())
            for vaga_id, dados in itens:
                try:
                    _analisar_vaga(frame, dados, vaga_id)
                except Exception as e:
                    print(f"⚠️  Erro analisando vaga {dados.get('numero')}: {e}")
    finally:
        if cap is not None:
            cap.release()
        _rodando = False
        print("🅿️  Monitor de vagas encerrado.")


def iniciar_monitoramento():
    if _rodando:
        return
    threading.Thread(target=start_monitoring, daemon=True, name="monitor-vagas").start()


def parar_monitoramento():
    _parar.set()


def forcar_recarga():
    """Depois de salvar coordenadas: aplica o novo desenho sem esperar 10 s."""
    try:
        _recarregar_vagas()
    except Exception as e:
        print(f"⚠️  Erro ao recarregar vagas: {e}")


# ======================================================================
# VÍDEO PARA O vagas.html
# ======================================================================
def _frame_sem_sinal():
    img = np.zeros((ALTURA // 2, LARGURA // 2, 3), dtype=np.uint8)
    cv2.putText(img, "Sem imagem da camera das vagas", (60, ALTURA // 4), cv2.FONT_HERSHEY_SIMPLEX, 1.2,
                (255, 255, 255), 2)
    return cv2.imencode(".jpg", img)[1].tobytes()


def gerar_frames_mjpeg():
    """Stream MJPEG com o último frame do monitor (não abre a câmera de novo)."""
    sem_sinal = _frame_sem_sinal()
    cap_proprio = None
    try:
        while True:
            with _lock_frame:
                jpeg = _ultimo_jpeg
            if jpeg is None and not _rodando:
                # Monitor desligado (MONITORAR_VAGAS=false): abre a câmera só para o vídeo
                if cap_proprio is None:
                    cap_proprio = _abrir_camera()
                ret, frame = cap_proprio.read() if cap_proprio.isOpened() else (False, None)
                if ret:
                    jpeg = cv2.imencode(".jpg", cv2.resize(frame, (LARGURA, ALTURA)))[1].tobytes()
            yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + (jpeg or sem_sinal) + b"\r\n"
            time.sleep(0.07)
    finally:
        if cap_proprio is not None:
            cap_proprio.release()
