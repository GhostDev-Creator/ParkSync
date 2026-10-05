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

        for vaga in todas_vagas:
            coords = vaga.coordenadas
            if not coords or sum(coords) == 0:
                continue

            if len(coords) >= 8:
                x_coords = coords[0::2]
                y_coords = coords[1::2]
                x = min(x_coords)
                y = min(y_coords)
                w = max(x_coords) - x
                h = max(y_coords) - y
            else:
                x, y, w, h = coords[:4]

            vagas_ativas[vaga.id] = {
                "vaga_obj": vaga,
                "numero": vaga.numero,
                "box": (x, y, w, h),
                "ocupada": vaga.ocupado,
                "tempo_inicio": None,
                "ultimo_ocr": 0,
                "fundo_vazio": None,
                "ocr_timeout_msg": False
            }

        if not vagas_ativas:
            print("Nenhuma vaga foi mapeada no painel ainda!")
            return

        print(f"Monitorando {len(vagas_ativas)} vagas simultaneamente!")

        cap = cv2.VideoCapture(camera_estacionamento)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)

        tempo_necessario = 5.0
        tempo_limite_ocr = 15.0

        while True:
            ret, frame = cap.read()
            if not ret:
                break

            frame = cv2.resize(frame, (1920, 1080))

            for id_vaga, dados in vagas_ativas.items():
                x, y, w, h = dados["box"]
                vaga_obj = dados["vaga_obj"]

                if w <= 0 or h <= 0:
                    continue

                recorte_vaga = frame[y:y + h, x:x + w]
                if recorte_vaga.size == 0:
                    continue

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
                                print(f"\n" + "-" * 50)
                                print(f"[VAGA {dados['numero']}] CARRO DETECTADO!")
                                print(f"Iniciando varredura de OCR a cada 3s (Limite de 15s)...")
                                dados["ultimo_ocr"] = 0

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
                                            print(f"SUCESSO: Matrícula {placa_lida} validada. Pertence ao morador!")
                                        else:
                                            vaga_obj.status_conflito = True
                                            print(f"ALERTA: Matrícula {placa_lida} desconhecida! Conflito gerado!")

                                            alerta_existente = db.query(AlertaPainel).filter_by(
                                                tipo_alerta="CONFLITO_VAGA",
                                                resolvido=False
                                            ).filter(
                                                AlertaPainel.texto.like(f"%vaga {vaga_obj.numero}%")
                                            ).first()

                                            if not alerta_existente:
                                                novo_alerta = AlertaPainel(
                                                    tipo_alerta="CONFLITO_VAGA",
                                                    texto=f"Invasão detectada na vaga {vaga_obj.numero}. A Placa {placa_lida} não pertence ao dono."
                                                )
                                                db.add(novo_alerta)
                                                db.commit()
                                                print(f"Novo alerta crítico disparado para o porteiro!")

                                                # GATILHO: Piscar alerta na tela
                                                try:
                                                    requests.post("http://127.0.0.1:8000/api/internal/trigger",
                                                                  json={"evento": "NOVO_ALERTA"})
                                                except:
                                                    pass

                                    db.commit()

                                    try:
                                        requests.post("http://127.0.0.1:8000/api/internal/trigger",
                                                      json={"evento": "ATUALIZACAO_VAGAS"})
                                    except:
                                        pass

                                    print("-" * 50)

                                elif not placa_lida and not vaga_obj.current_plate:
                                    print(f"Nenhuma placa encontrada. Tentando novamente...")

                        else:
                            if not dados["ocr_timeout_msg"]:
                                print(f"Mantendo apenas monitoramento de presença contínuo.")
                                print("-" * 50)
                                dados["ocr_timeout_msg"] = True
                else:
                    if dados["ocupada"]:
                        if vaga_obj.status_conflito:
                            alerta_aberto = db.query(AlertaPainel).filter_by(
                                tipo_alerta="CONFLITO_VAGA",
                                resolvido=False
                            ).first()

                            if alerta_aberto:
                                alerta_aberto.resolvido = True
                                print("Conflito resolvido: O invasor saiu da vaga.")

                        dados["ocupada"] = False
                        vaga_obj.ocupado = False
                        vaga_obj.current_plate = None
                        vaga_obj.status_conflito = False
                        db.commit()

                        print(f"\n[VAGA {dados['numero']}] O carro saiu. Vaga livre novamente.")
                        print("-" * 50)

                        # GATILHO: Vaga liberada
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

        if cap is not None:
            cap.release()

        cv2.destroyAllWindows()