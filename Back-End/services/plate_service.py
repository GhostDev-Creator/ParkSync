import os
import cv2
import easyocr
from ultralytics import YOLO
from utils.placa import normalizar_placa_ocr

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODEL_PATH = os.path.join(BASE_DIR, "models", "brazilian_license_plate_and_mercosul_plate.pt")

# Validação do arquivo
if not os.path.exists(MODEL_PATH):
    raise FileNotFoundError(f"❌ O arquivo do modelo não foi encontrado em: {MODEL_PATH}")

modelo_yolo = YOLO(MODEL_PATH)
leitor_ocr = easyocr.Reader(['en'], gpu=False)

def extrair_placa_de_recorte(recorte_vaga):
    """
    Recebe um recorte (numpy array/frame do OpenCV) de uma vaga.
    Retorna a string da placa detectada ou None se não encontrar nada.
    """
    if recorte_vaga is None or recorte_vaga.size == 0:
        return None

    resultados = modelo_yolo(recorte_vaga, verbose=False)

    for resultado in resultados:
        caixas = resultado.boxes

        if len(caixas) == 0:
            continue  # Nenhuma placa detectada pelo YOLO neste frame

        melhor_caixa = max(caixas, key=lambda c: c.conf[0])
        x1, y1, x2, y2 = map(int, melhor_caixa.xyxy[0].tolist())

        recorte_placa = recorte_vaga[y1:y2, x1:x2]

        if recorte_placa.size == 0:
            continue

        cinza = cv2.cvtColor(recorte_placa, cv2.COLOR_BGR2GRAY)

        textos_lidos = leitor_ocr.readtext(cinza, detail=0)

        texto_unido = "".join(textos_lidos)

        placa_mercosul = normalizar_placa_ocr(texto_unido)

        if placa_mercosul:
            return placa_mercosul

    return None