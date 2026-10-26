# Arquivo: Back-End/services/face_service.py
#
# Reconhecimento facial por embedding (face_recognition / dlib).
# - extract_embedding(): usado no cadastro (foto base64 -> vetor de 128 números)
# - identificar_morador(): usado pelo orquestrador na entrada e na saída
# - verify_embedding(): janela de teste com a webcam
#   (dentro da pasta Back-End rode: python -m services.face_service)

import base64
import os
import threading
import time

import cv2
import numpy as np

from utils import config
from database.setup_db import SessionLocal
from database.models import Morador

tolerancia = config.FACIAL_THRESHOLD

try:
    import face_recognition
except Exception as e:  # dlib não instalado: a API sobe, mas sem reconhecimento facial
    face_recognition = None
    print(f"❌ face_recognition indisponível ({e}). Cadastro com foto e reconhecimento facial desativados.")


def facial_disponivel() -> bool:
    return face_recognition is not None


def extract_embedding(foto_base64: str):
    """Recebe a foto (data URL ou base64 puro) e devolve a lista com 128 floats, ou None."""
    if face_recognition is None:
        return None
    try:
        encoded_img = foto_base64.split(",", 1)[1] if "," in foto_base64 else foto_base64
        img_buffer = np.frombuffer(base64.b64decode(encoded_img), np.uint8)
        img = cv2.imdecode(img_buffer, cv2.IMREAD_COLOR)
        if img is None:
            return None
        rgb_img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        encodings = face_recognition.face_encodings(rgb_img)
        return encodings[0].tolist() if encodings else None
    except Exception as e:
        print(f"Erro no módulo de reconhecimento facial: {e}")
        return None


# ---------------------------------------------------------------------------
# Cache dos encodings dos moradores (evita consultar o banco a cada frame).
# invalidar_cache_moradores() é chamado depois de cada cadastro.
# ---------------------------------------------------------------------------
_TTL_CACHE_SEGUNDOS = 60
_cache_moradores = {"encodings": [], "ids": [], "carregado_em": 0.0}
_lock_cache = threading.Lock()


def invalidar_cache_moradores():
    with _lock_cache:
        _cache_moradores["carregado_em"] = 0.0


def _carregar_cache_moradores(db):
    with _lock_cache:
        if (time.time() - _cache_moradores["carregado_em"]) < _TTL_CACHE_SEGUNDOS:
            return
        moradores = db.query(Morador).filter(Morador.face_encoding.isnot(None)).all()
        _cache_moradores["encodings"] = [np.array(m.face_encoding) for m in moradores]
        _cache_moradores["ids"] = [m.id for m in moradores]
        _cache_moradores["carregado_em"] = time.time()


def identificar_morador(frame_bgr, db):
    """Recebe UM frame BGR e devolve o Morador do rosto, ou None."""
    if frame_bgr is None or face_recognition is None:
        return None

    _carregar_cache_moradores(db)
    if not _cache_moradores["encodings"]:
        return None

    # Reduz a imagem pela metade: bem mais rápido e ainda preciso para 1 pessoa perto da câmera
    pequeno = cv2.resize(frame_bgr, (0, 0), fx=0.5, fy=0.5)
    rgb = cv2.cvtColor(pequeno, cv2.COLOR_BGR2RGB)
    localizacoes = face_recognition.face_locations(rgb)
    if not localizacoes:
        return None

    codificacoes = face_recognition.face_encodings(rgb, localizacoes)
    if not codificacoes:
        return None

    # Na portaria há uma pessoa por vez diante da webcam: usa o primeiro rosto
    distancias = face_recognition.face_distance(_cache_moradores["encodings"], codificacoes[0])
    melhor = int(np.argmin(distancias))
    if distancias[melhor] <= tolerancia:
        return db.get(Morador, _cache_moradores["ids"][melhor])
    return None


def abrir_camera(indice_ou_url):
    """Abre webcam (índice) ou stream (URL). No Windows usa DirectShow, que abre bem mais rápido."""
    if isinstance(indice_ou_url, int) and os.name == "nt":
        cap = cv2.VideoCapture(indice_ou_url, cv2.CAP_DSHOW)
    else:
        cap = cv2.VideoCapture(indice_ou_url)
    return cap


def verify_embedding():
    """Teste visual: abre a webcam e mostra o nome de quem for reconhecido. Tecla q fecha."""
    if face_recognition is None:
        print("face_recognition não está instalado.")
        return

    db = SessionLocal()
    video_capture = None
    try:
        moradores = db.query(Morador).filter(Morador.face_encoding.isnot(None)).all()
        encodings_conhecidos = [np.array(m.face_encoding) for m in moradores]
        nomes_conhecidos = [f"ID {m.id} - {m.nome}" for m in moradores]
        print(f"{len(moradores)} moradores carregados na memória!")

        video_capture = abrir_camera(config.FACE_CAM)
        if not video_capture.isOpened():
            print(f"Não consegui abrir a câmera FACE_CAM={config.FACE_CAM}")
            return

        cv2.namedWindow("Verificacao Facial - ParkSync", cv2.WINDOW_NORMAL)

        while True:
            ret, frame = video_capture.read()
            if not ret:
                break

            small_frame = cv2.resize(frame, (0, 0), fx=0.25, fy=0.25)
            rgb_small_frame = cv2.cvtColor(small_frame, cv2.COLOR_BGR2RGB)
            face_locations = face_recognition.face_locations(rgb_small_frame)
            face_encodings = face_recognition.face_encodings(rgb_small_frame, face_locations)

            for (top, right, bottom, left), encoding_atual in zip(face_locations, face_encodings):
                nome_exibicao = "Desconhecido"
                cor_caixa = (0, 0, 255)

                if encodings_conhecidos:
                    distancias = face_recognition.face_distance(encodings_conhecidos, encoding_atual)
                    melhor = int(np.argmin(distancias))
                    if distancias[melhor] <= tolerancia:
                        nome_exibicao = nomes_conhecidos[melhor]
                        cor_caixa = (0, 255, 0)

                top, right, bottom, left = top * 4, right * 4, bottom * 4, left * 4
                cv2.rectangle(frame, (left, top), (right, bottom), cor_caixa, 2)
                cv2.rectangle(frame, (left, bottom - 35), (right, bottom), cor_caixa, cv2.FILLED)
                cv2.putText(frame, nome_exibicao, (left + 6, bottom - 6), cv2.FONT_HERSHEY_DUPLEX, 0.6,
                            (255, 255, 255), 1)

            cv2.imshow("Verificacao Facial - ParkSync", frame)
            if cv2.waitKey(1) & 0xFF == ord("q"):
                break
    finally:
        db.close()
        if video_capture is not None:
            video_capture.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    verify_embedding()
