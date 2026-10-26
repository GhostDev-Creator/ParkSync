# Arquivo: Back-End/services/plate_service.py
#
# YOLO acha a placa na imagem e o EasyOCR lê o texto.
# Os modelos são carregados só no primeiro uso (a API sobe rápido) e, se faltar
# o arquivo .pt ou alguma biblioteca, a API NÃO cai: a leitura só devolve None.

import os
import threading
import cv2
from utils.placa import normalizar_placa_ocr

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODEL_PATH = os.path.join(BASE_DIR, "models", "brazilian_license_plate_and_mercosul_plate.pt")

_modelo_yolo = None
_leitor_ocr = None
_erro_carregamento = None
_lock = threading.Lock()


def carregar_modelos() -> bool:
    """Carrega YOLO + EasyOCR uma única vez. Devolve True se está tudo pronto."""
    global _modelo_yolo, _leitor_ocr, _erro_carregamento
    with _lock:
        if _modelo_yolo is not None and _leitor_ocr is not None:
            return True
        if _erro_carregamento:
            return False
        try:
            if not os.path.exists(MODEL_PATH):
                raise FileNotFoundError(f"modelo YOLO não encontrado em {MODEL_PATH}")
            from ultralytics import YOLO
            import easyocr

            _modelo_yolo = YOLO(MODEL_PATH)
            _leitor_ocr = easyocr.Reader(["en"], gpu=False)
            print("🔤 Leitor de placas (YOLO + EasyOCR) carregado.")
            return True
        except Exception as e:
            _erro_carregamento = str(e)
            print(f"❌ Leitura de placas desativada: {e}")
            return False


def _ler_texto(recorte_placa):
    cinza = cv2.cvtColor(recorte_placa, cv2.COLOR_BGR2GRAY)
    # Aumenta placas pequenas (maquete) para o OCR enxergar melhor
    altura = cinza.shape[0]
    if altura < 60:
        escala = 60.0 / max(altura, 1)
        cinza = cv2.resize(cinza, None, fx=escala, fy=escala, interpolation=cv2.INTER_CUBIC)
    textos = _leitor_ocr.readtext(
        cinza, detail=0, allowlist="ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 -"
    )
    # Junta com espaço para a limpeza conseguir remover a palavra "BRASIL" inteira
    return " ".join(textos)


def extrair_placa_de_recorte(imagem):
    """
    Recebe uma imagem BGR (numpy/OpenCV): foto da ESP32-CAM ou recorte de uma vaga.
    Retorna a placa (ex.: 'BRA2E19') ou None.
    """
    if imagem is None or getattr(imagem, "size", 0) == 0:
        return None
    if not carregar_modelos():
        return None

    resultados = _modelo_yolo(imagem, verbose=False)
    for resultado in resultados:
        caixas = resultado.boxes
        if caixas is None or len(caixas) == 0:
            continue

        # Tenta da caixa mais confiável para a menos confiável
        for caixa in sorted(caixas, key=lambda c: float(c.conf[0]), reverse=True):
            x1, y1, x2, y2 = map(int, caixa.xyxy[0].tolist())
            x1, y1 = max(x1, 0), max(y1, 0)
            recorte_placa = imagem[y1:y2, x1:x2]
            if recorte_placa.size == 0:
                continue
            placa = normalizar_placa_ocr(_ler_texto(recorte_placa))
            if placa:
                return placa
    return None
