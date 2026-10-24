import threading
import queue
import time
import cv2
import os
import requests
import numpy as np
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
from dotenv import load_dotenv
from database.setup_db import SessionLocal
from database.models import (
    MoradorModel, VeiculoModel, AcessoEnum, StatusEnum, LogAcessoExterno,
    AlertaPainel, AgendamentoVisita, LogVisitante, VeiculoTemporario, VisitanteModel
)

from services.plate_service import extrair_placa_de_recorte
from services.face_service import identificar_morador
from services.parking_service import start_monitoring
from mqtt.broker import ParkBroker

load_dotenv()


# Tratamento para IPs de câmeras (ESP32) e IDs locais (Webcam)
def parse_cam(env_val):
    if not env_val: return 0
    return int(env_val) if env_val.isdigit() else env_val


PE_FACE_CAM = parse_cam(os.getenv("PE_FACE_CAM", "0"))
PE_PLATE_CAM = parse_cam(os.getenv("PE_PLATE_CAM", "0"))
PS_FACE_CAM = parse_cam(os.getenv("PS_FACE_CAM", "0"))
PS_PLATE_CAM = parse_cam(os.getenv("PS_PLATE_CAM", "0"))


def extrair_placa_unica_foto(foto):
    return extrair_placa_de_recorte(foto)


class ParkSyncOrchestrator:
    def __init__(self):
        self.event_queue = queue.Queue()
        self.broker = ParkBroker()

        self.broker.cadastrar_assunto("parksync/sensor/entrada", self._mqtt_gatilho_entrada)
        self.broker.cadastrar_assunto("parksync/sensor/saida", self._mqtt_gatilho_saida)
        self.broker.iniciar()

        self.worker_thread = threading.Thread(target=self._processar_fila, daemon=True)
        self.worker_thread.start()

        print("🎼 Maestro Iniciado! Aguardando eventos reais de MQTT (Sensores)...")
        self._iniciar_monitoramento_vagas()

    def _mqtt_gatilho_entrada(self, mensagem):
        self.broker.enviar_mensagem("parksync/camera/entrada/acordar", "ACORDA")
        self.adicionar_evento("GATILHO_ENTRADA")

    def _mqtt_gatilho_saida(self, mensagem):
        self.broker.enviar_mensagem("parksync/camera/saida/acordar", "ACORDA")
        self.adicionar_evento("GATILHO_SAIDA")

    def _iniciar_monitoramento_vagas(self):
        print("🎭 [Ato 0] Câmera de Teto (Vagas) em Background... Ativada.")
        threading.Thread(target=start_monitoring, daemon=True).start()

    def adicionar_evento(self, gatilho_mqtt: str):
        print(f"📥 Novo Evento Recebido: {gatilho_mqtt}")
        self.event_queue.put(gatilho_mqtt)

    def _processar_fila(self):
        """Thread worker que processa um carro por vez, com banco de dados seguro por sessão"""
        while True:
            evento = self.event_queue.get()
            with SessionLocal() as db:
                try:
                    if evento == "GATILHO_ENTRADA":
                        self._ato_1_fluxo_entrada(db)
                    elif evento == "GATILHO_SAIDA":
                        self._ato_2_fluxo_saida(db)
                except Exception as e:
                    print(f"❌ [ERRO CRÍTICO] Falha ao processar {evento}: {e}")
                    db.rollback()
            self.event_queue.task_done()

    def _salvar_imagem_disco(self, frame, prefixo="evidencia") -> str:
        if frame is None: return ""
        os.makedirs("armazenamento/capturas", exist_ok=True)
        nome_arquivo = f"armazenamento/capturas/{prefixo}_{int(time.time() * 1000)}.jpg"
        cv2.imwrite(nome_arquivo, frame)
        return nome_arquivo

    def _capturar_foto_placa(self, camera_input):
        """Captura via HTTP (ESP32-CAM) ou Webcam se for Int"""
        if isinstance(camera_input, str) and camera_input.startswith("http"):
            url = f"{camera_input}/capture" if not camera_input.endswith("/capture") else camera_input
            for _ in range(3):
                try:
                    time.sleep(0.4)  # Tempo para ajustar exposição da ESP
                    response = requests.get(url, timeout=3.0)
                    if response.status_code == 200:
                        img_array = np.frombuffer(response.content, np.uint8)
                        frame = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
                        if frame is not None:
                            return cv2.resize(frame, (1920, 1080))
                except Exception as e:
                    print(f"⚠️ Erro ao puxar foto da ESP32: {e}")
            return None
        else:
            return self._capturar_foto_real(camera_input)

    def _capturar_rosto_continuo(self, camera_id, db, timeout=4.0):
        """Mantém a câmera aberta por 4 segundos caçando um rosto conhecido"""
        cap = cv2.VideoCapture(camera_id)
        if not cap.isOpened(): return None, None
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)

        start_time = time.time()
        best_frame = None
        morador_encontrado = None

        while (time.time() - start_time) < timeout:
            ret, frame = cap.read()
            if not ret: continue

            frame = cv2.resize(frame, (1920, 1080))
            best_frame = frame.copy()

            morador = identificar_morador(frame, db)
            if morador:
                morador_encontrado = morador
                break

        cap.release()
        return best_frame, morador_encontrado

    def _capturar_foto_real(self, camera_id):
        cap = cv2.VideoCapture(camera_id)
        if not cap.isOpened(): return None
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)
        for _ in range(5): cap.read()
        ret, frame = cap.read()
        cap.release()
        return cv2.resize(frame, (1920, 1080)) if ret else None

    def _abrir_cancela_hardware(self, direcao):
        print(f"   ⚙️ [HARDWARE] Enviando sinal (MQTT) para abrir cancela de {direcao}...")
        self.broker.enviar_mensagem(f"parksync/cancela/{direcao.lower()}/comando", "ABRIR")

    def _registrar_log(self, db, direcao, tipo_acesso: AcessoEnum, placa, path_foto):
        novo_log = LogAcessoExterno(
            placa_detectada=placa if placa else "DESCONHECIDO",
            tipo_acesso=tipo_acesso,
            path_foto_capturada=path_foto
        )
        db.add(novo_log)

        if tipo_acesso == AcessoEnum.NEGADO and direcao == "ENTRADA":
            novo_alerta = AlertaPainel(
                tipo_alerta="INVASAO_PORTARIA",
                texto=f"Tentativa de {direcao} bloqueada! Placa lida: {placa}. Evidência salva."
            )
            db.add(novo_alerta)
            print("   🚨 [ALERTA] Acesso Negado notificado no painel!")
            self._disparar_gatilho("NOVO_ALERTA")

        db.commit()
        self._disparar_gatilho("NOVO_ACESSO")

    def _disparar_gatilho(self, evento):
        try:
            requests.post("http://127.0.0.1:8000/api/internal/trigger", json={"evento": evento})
        except:
            pass

    # ==========================================
    # 🎭 ATO 1: A ENTRADA
    # ==========================================
    def _ato_1_fluxo_entrada(self, db):
        print("\n" + "=" * 60)
        print("🎬 [Ato 1] SENSOR DE ENTRADA ATIVADO!")

        with ThreadPoolExecutor(max_workers=2) as executor:
            future_placa = executor.submit(self._capturar_foto_placa, PE_PLATE_CAM)
            future_rosto = executor.submit(self._capturar_rosto_continuo, PE_FACE_CAM, db, 4.0)

            foto_placa = future_placa.result()
            foto_rosto, morador_encontrado = future_rosto.result()

        if foto_rosto is None or foto_placa is None:
            print("❌ Falha crítica nas câmeras de ENTRADA.")
            return

        placa_lida = extrair_placa_unica_foto(foto_placa)
        path_rosto = self._salvar_imagem_disco(foto_rosto, prefixo="entrada_rosto")
        path_placa = self._salvar_imagem_disco(foto_placa, prefixo="entrada_placa")

        agora = datetime.now()

        if morador_encontrado:
            veiculo_cadastrado = db.query(VeiculoModel).filter_by(fk_morador_dono=morador_encontrado.id,
                                                                  placa=placa_lida).first()

            if veiculo_cadastrado:
                print(f"\n   🟢 [CENÁRIO 1] Match Duplo! Morador: {morador_encontrado.nome} | Placa: {placa_lida}")
                self._abrir_cancela_hardware("ENTRADA")
                self._registrar_log(db, "ENTRADA", AcessoEnum.MORADOR, placa_lida, path_rosto)
            else:
                print(f"\n   🟡 [CENÁRIO 2] Prioridade Biométrica! Morador validado, carro diferente ({placa_lida}).")
                novo_temp = VeiculoTemporario(
                    fk_morador_dono=morador_encontrado.id,
                    placa_veiculo_temporario=placa_lida if placa_lida else "SEM_PLACA",
                    status=StatusEnum.DENTRO
                )
                db.add(novo_temp)
                db.commit()
                self._abrir_cancela_hardware("ENTRADA")
                self._registrar_log(db, "ENTRADA", AcessoEnum.MORADOR, placa_lida, path_rosto)
        else:
            if not placa_lida:
                print("\n   🔴 [CENÁRIO 3] Invasor Total! Sem rosto e sem placa.")
                self._gerar_log_invasor(db, placa_lida, path_rosto, "INVASOR SEM PLACA")
                self._registrar_log(db, "ENTRADA", AcessoEnum.NEGADO, "ILEGIVEL", path_rosto)
            else:
                agendamento = db.query(AgendamentoVisita).join(
                    VisitanteModel, AgendamentoVisita.fk_id_visitante == VisitanteModel.id
                ).filter(
                    VisitanteModel.placa_veiculo == placa_lida, AgendamentoVisita.ativo == True
                ).order_by(AgendamentoVisita.id_agendamento.desc()).first()

                if agendamento:
                    visitante = agendamento.visitante
                    morador_anf = db.query(MoradorModel).filter_by(id=agendamento.fk_id_morador).first()

                    if agendamento.data_entrada_prevista <= agora <= agendamento.data_saida_prevista:
                        print(f"\n   🔵 [CENÁRIO 4] Visitante Autorizado no prazo!")
                        log_visitante = LogVisitante(
                            path_foto_capturada=path_rosto,
                            visitante_nome=visitante.nome, visitante_cpf=visitante.cpf,
                            visitante_cnh=visitante.cnh if visitante.cnh else "N/A", visitante_placa=placa_lida,
                            morador_anfitriao_nome=morador_anf.nome if morador_anf else "N/A",
                            apartamento_visitado=morador_anf.apartamento if morador_anf else "N/A",
                            bloco_visitado=morador_anf.bloco if morador_anf else "N/A"
                        )
                        db.add(log_visitante)
                        db.commit()
                        self._abrir_cancela_hardware("ENTRADA")
                        self._registrar_log(db, "ENTRADA", AcessoEnum.VISITANTE, placa_lida, path_rosto)
                    else:
                        print(f"\n   🟠 [CENÁRIO 5] Convite Expirado para a placa {placa_lida}.")
                        self._gerar_log_invasor(db, placa_lida, path_rosto, f"EXPIRADO: {visitante.nome}", morador_anf)
                        self._registrar_log(db, "ENTRADA", AcessoEnum.NEGADO, placa_lida, path_rosto)
                else:
                    print(f"\n   🔴 [CENÁRIO 3] Invasor! Placa desconhecida.")
                    self._gerar_log_invasor(db, placa_lida, path_rosto, "INVASOR DESCONHECIDO")
                    self._registrar_log(db, "ENTRADA", AcessoEnum.NEGADO, placa_lida, path_rosto)
        print("=" * 60 + "\n")

    # ==========================================
    # 🎭 ATO 2: A SAÍDA
    # ==========================================
    def _ato_2_fluxo_saida(self, db):
        print("\n" + "=" * 60)
        print("🎬 [Ato 2] SENSOR DE SAÍDA ATIVADO!")

        with ThreadPoolExecutor(max_workers=2) as executor:
            future_placa = executor.submit(self._capturar_foto_placa, PS_PLATE_CAM)
            future_rosto = executor.submit(self._capturar_rosto_continuo, PS_FACE_CAM, db, 4.0)

            foto_placa = future_placa.result()
            foto_rosto, morador_encontrado = future_rosto.result()

        if foto_rosto is None or foto_placa is None:
            print("❌ Falha crítica nas câmeras de SAÍDA.")
            return

        placa_lida = extrair_placa_unica_foto(foto_placa)
        path_rosto = self._salvar_imagem_disco(foto_rosto, prefixo="saida_rosto")
        path_placa = self._salvar_imagem_disco(foto_placa, prefixo="saida_placa")

        if morador_encontrado:
            veiculo_cadastrado = db.query(VeiculoModel).filter_by(fk_morador_dono=morador_encontrado.id,
                                                                  placa=placa_lida).first()

            # Verifica se ele está saindo com um carro temporário (Cenário 2 da Entrada sendo resolvido)
            veiculo_temp = db.query(VeiculoTemporario).filter_by(fk_morador_dono=morador_encontrado.id,
                                                                 placa_veiculo_temporario=placa_lida,
                                                                 status=StatusEnum.DENTRO).first()

            if veiculo_cadastrado or veiculo_temp:
                if veiculo_temp:
                    veiculo_temp.status = StatusEnum.SAIU  # Finaliza a visita do carro temporário
                    db.commit()
                print(
                    f"\n   🟢 [SAÍDA: CENÁRIO 1] Tudo certo! Morador ({morador_encontrado.nome}) saindo com veículo ({placa_lida}).")
                self._abrir_cancela_hardware("SAIDA")
                self._registrar_log(db, "SAIDA", AcessoEnum.MORADOR, placa_lida, path_rosto)
            else:
                print(
                    f"\n   🟡 [SAÍDA: CENÁRIO 2] Atenção! Morador ({morador_encontrado.nome}) saindo com veículo roubado/desconhecido ({placa_lida}).")
                veiculo_terceiro = db.query(VeiculoModel).filter_by(placa=placa_lida).first()
                if veiculo_terceiro:
                    dono = db.query(MoradorModel).filter_by(id=veiculo_terceiro.fk_morador_dono).first()
                    texto_alerta = f"SAÍDA SUSPEITA: {morador_encontrado.nome} saiu com o veículo placa {placa_lida}, do vizinho {dono.nome if dono else 'Outro'}."
                else:
                    texto_alerta = f"SAÍDA SUSPEITA: {morador_encontrado.nome} saiu com veículo desconhecido ({placa_lida})."

                novo_alerta = AlertaPainel(tipo_alerta="USO_INDEVIDO", texto=texto_alerta)
                db.add(novo_alerta)
                db.commit()
                print(f"   🚨 [ALERTA] {texto_alerta}")
                self._disparar_gatilho("NOVO_ALERTA")

                self._abrir_cancela_hardware("SAIDA")
                self._registrar_log(db, "SAIDA", AcessoEnum.MORADOR, placa_lida, path_rosto)
        else:
            print(f"\n   ⚪ [SAÍDA: VISITANTE] Veículo {placa_lida} saindo.")
            self._abrir_cancela_hardware("SAIDA")
            self._registrar_log(db, "SAIDA", AcessoEnum.VISITANTE, placa_lida, path_placa)
        print("=" * 60 + "\n")

    def _gerar_log_invasor(self, db, placa, path_foto, motivo_nome, morador_anf=None):
        log_invasor = LogVisitante(
            path_foto_capturada=path_foto,
            visitante_nome=motivo_nome, visitante_cpf="N/A", visitante_cnh="N/A",
            visitante_placa=placa if placa else "ILEGIVEL",
            morador_anfitriao_nome=morador_anf.nome if morador_anf else "N/A",
            apartamento_visitado=morador_anf.apartamento if morador_anf else "N/A",
            bloco_visitado=morador_anf.bloco if morador_anf else "N/A"
        )
        db.add(log_invasor)
        db.commit()