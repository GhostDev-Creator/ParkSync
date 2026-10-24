import os
import cv2
import time
import requests
from dotenv import load_dotenv
from database.setup_db import SessionLocal
from database.models import VagaModel, VeiculoModel, AlertaPainel
from services.plate_service import extrair_placa_de_recorte

load_dotenv()
camera_estacionamento = os.getenv("PM_PARK_CAM")
laplaciano_vaga = float(os.getenv("LAPLACIAN_THRESHOLD", 5.0))


def start_monitoring():
    db = SessionLocal()
    cap = None

    try:
        todas_vagas = db.query(VagaModel).all()
        vagas_ativas = {}

        # Fator de escala: Canvas do Frontend (800x600) -> Frame de Vídeo (1920x1080)
        scale_x = 1920 / 800.0
        scale_y = 1080 / 600.0

        for vaga in todas_vagas:
            coords = vaga.coordenadas
            if not coords or sum(coords) == 0: continue

            if len(coords) >= 8:
                x_coords = coords[0::2]
                y_coords = coords[1::2]
                x = int(min(x_coords) * scale_x)
                y = int(min(y_coords) * scale_y)
                w = int((max(x_coords) - min(x_coords)) * scale_x)
                h = int((max(y_coords) - min(y_coords)) * scale_y)
            else:
                raw_x, raw_y, raw_w, raw_h = coords[:4]
                x, y = int(raw_x * scale_x), int(raw_y * scale_y)
                w, h = int(raw_w * scale_x), int(raw_h * scale_y)

            vagas_ativas[vaga.id] = {
                "vaga_obj": vaga, "numero": vaga.numero, "box": (x, y, w, h),
                "ocupada": vaga.ocupado, "tempo_inicio": None, "ultimo_ocr": 0,
                "fundo_vazio": None, "ocr_timeout_msg": False
            }

        if not vagas_ativas:
            print("Nenhuma vaga mapeada ainda. Encerrando monitoramento.")
            return

        cap = cv2.VideoCapture(camera_estacionamento)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)

        tempo_necessario = 5.0
        tempo_limite_ocr = 15.0

        while True:
            ret, frame = cap.read()
            if not ret: break
            frame = cv2.resize(frame, (1920, 1080))

            for id_vaga, dados in vagas_ativas.items():
                x, y, w, h = dados["box"]
                vaga_obj = dados["vaga_obj"]
                if w <= 0 or h <= 0: continue

                recorte_vaga = frame[y:y + h, x:x + w]
                if recorte_vaga.size == 0: continue

                cinza = cv2.cvtColor(recorte_vaga, cv2.COLOR_BGR2GRAY)
                cinza = cv2.GaussianBlur(cinza, (21, 21), 0)

                if dados["fundo_vazio"] is None:
                    dados["fundo_vazio"] = cinza
                    continue

                diferenca = cv2.absdiff(dados["fundo_vazio"], cinza)
                _, thresh = cv2.threshold(diferenca, 25, 255, cv2.THRESH_BINARY)
                porcentagem = (cv2.countNonZero(thresh) / (w * h)) * 100

                if porcentagem > laplaciano_vaga:
                    if dados["tempo_inicio"] is None:
                        dados["tempo_inicio"] = time.time()
                    else:
                        tempo_decorrido = time.time() - dados["tempo_inicio"]
                        if tempo_decorrido >= tempo_necessario:
                            if not dados["ocupada"]:
                                dados["ocupada"] = True
                                vaga_obj.ocupado = True
                                db.commit()
                                print(f"\n[VAGA {dados['numero']}] CARRO DETECTADO!")
                                try:
                                    requests.post("http://127.0.0.1:8000/api/internal/trigger",
                                                  json={"evento": "ATUALIZACAO_VAGAS"})
                                except:
                                    pass

                            if tempo_decorrido <= tempo_limite_ocr:
                                if (time.time() - dados["ultimo_ocr"]) >= 3.0:
                                    dados["ultimo_ocr"] = time.time()
                                    placa_lida = extrair_placa_de_recorte(recorte_vaga)

                                    if placa_lida and placa_lida != vaga_obj.current_plate:
                                        vaga_obj.current_plate = placa_lida
                                        veiculos_dono = db.query(VeiculoModel).filter_by(
                                            fk_morador_dono=vaga_obj.fk_morador_dono).all()
                                        placas_do_dono = [v.placa for v in veiculos_dono]

                                        if placa_lida in placas_do_dono:
                                            vaga_obj.status_conflito = False
                                        else:
                                            vaga_obj.status_conflito = True
                                            if not db.query(AlertaPainel).filter_by(tipo_alerta="CONFLITO_VAGA",
                                                                                    resolvido=False).filter(
                                                    AlertaPainel.texto.like(f"%vaga {vaga_obj.numero}%")).first():
                                                db.add(AlertaPainel(tipo_alerta="CONFLITO_VAGA",
                                                                    texto=f"Invasão vaga {vaga_obj.numero}. Placa {placa_lida}."))
                                                db.commit()
                                                try:
                                                    requests.post("http://127.0.0.1:8000/api/internal/trigger",
                                                                  json={"evento": "NOVO_ALERTA"})
                                                except:
                                                    pass
                                    db.commit()
                        else:
                            if not dados["ocr_timeout_msg"]:
                                dados["ocr_timeout_msg"] = True
                else:
                    if dados["ocupada"]:
                        if vaga_obj.status_conflito:
                            alerta_aberto = db.query(AlertaPainel).filter_by(tipo_alerta="CONFLITO_VAGA",
                                                                             resolvido=False).first()
                            if alerta_aberto: alerta_aberto.resolvido = True

                        dados["ocupada"] = False
                        vaga_obj.ocupado = False
                        vaga_obj.current_plate = None
                        vaga_obj.status_conflito = False
                        db.commit()
                        print(f"\n[VAGA {dados['numero']}] Vaga livre.")
                        try:
                            requests.post("http://127.0.0.1:8000/api/internal/trigger",
                                          json={"evento": "ATUALIZACAO_VAGAS"})
                        except:
                            pass

                    dados["tempo_inicio"] = None
                    dados["ultimo_ocr"] = 0
                    dados["ocr_timeout_msg"] = False
    finally:
        db.close()
        if cap: cap.release()
        cv2.destroyAllWindows()