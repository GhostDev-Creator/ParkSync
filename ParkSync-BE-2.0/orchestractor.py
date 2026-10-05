import threading
import queue
import time
import cv2
import os
import requests
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
PE_FACE_CAM = int(os.getenv("PE_FACE_CAM", 0))
PE_PLATE_CAM = int(os.getenv("PE_PLATE_CAM", 0))
PS_FACE_CAM = int(os.getenv("PS_FACE_CAM", 0))
PS_PLATE_CAM = int(os.getenv("PS_PLATE_CAM", 0))

def verificar_rosto_unica_foto(foto, db):
    # Antes retornava sempre None: nenhum morador era reconhecido e todos caíam
    # no ramo de visitante/invasor. Agora delega para o face_service.
    return identificar_morador(foto, db)

def extrair_placa_unica_foto(foto):
    return extrair_placa_de_recorte(foto)

class ParkSyncOrchestrator:
    def __init__(self):
        self.event_queue = queue.Queue()
        self.db = SessionLocal()
        self.broker = ParkBroker()

        # 1º PRIMEIRO CADASTRA OS TÓPICOS
        self.broker.cadastrar_assunto("parksync/sensor/entrada", self._mqtt_gatilho_entrada)
        self.broker.cadastrar_assunto("parksync/sensor/saida", self._mqtt_gatilho_saida)

        # 2º SÓ ENTÃO INICIA A CONEXÃO
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
        while True:
            evento = self.event_queue.get()
            if evento == "GATILHO_ENTRADA":
                self._ato_1_fluxo_entrada()
            elif evento == "GATILHO_SAIDA":
                self._ato_2_fluxo_saida()
            self.event_queue.task_done()

    def _salvar_imagem_disco(self, frame, prefixo="evidencia") -> str:
        if frame is None:
            return ""
        os.makedirs("armazenamento/capturas", exist_ok=True)
        nome_arquivo = f"armazenamento/capturas/{prefixo}_{int(time.time())}.jpg"
        cv2.imwrite(nome_arquivo, frame)
        return nome_arquivo

    def _capturar_foto_real(self, camera_id):
        cap = cv2.VideoCapture(camera_id)
        if not cap.isOpened(): return None
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)
        for _ in range(5): cap.read()
        ret, frame = cap.read()
        cap.release()
        if ret:
            frame = cv2.resize(frame, (1920, 1080))
            return frame
        return None

    def _abrir_cancela_hardware(self, direcao):
        print(f"   ⚙️ [HARDWARE] Enviando sinal (MQTT) para abrir cancela de {direcao}...")
        topico_cancela = f"parksync/cancela/{direcao.lower()}/comando"
        self.broker.enviar_mensagem(topico_cancela, "ABRIR")

    def _registrar_log(self, direcao, tipo_acesso: AcessoEnum, placa, path_foto):
        print(f"   💾 [MYSQL] Gerando registro de {direcao} com evidência fotográfica...")

        novo_log = LogAcessoExterno(
            placa_detectada=placa if placa else "DESCONHECIDO",
            tipo_acesso=tipo_acesso,
            path_foto_capturada=path_foto
        )
        self.db.add(novo_log)

        if tipo_acesso == AcessoEnum.NEGADO and direcao == "ENTRADA":
            novo_alerta = AlertaPainel(
                tipo_alerta="INVASAO_PORTARIA",
                texto=f"Tentativa de {direcao} bloqueada! Placa lida: {placa}. Evidência salva."
            )
            self.db.add(novo_alerta)
            print("   🚨 [ALERTA] Acesso Negado! O painel da portaria foi notificado!")
            try:
                requests.post("http://127.0.0.1:8000/api/internal/trigger", json={"evento": "NOVO_ALERTA"})
            except:
                pass

        self.db.commit()

        # Atualiza o painel web
        try:
            requests.post("http://127.0.0.1:8000/api/internal/trigger", json={"evento": "NOVO_ACESSO"})
        except:
            pass

    # ==========================================
    # 🎭 ATO 1: A ENTRADA (Matriz de 5 Cenários)
    # ==========================================
    def _ato_1_fluxo_entrada(self):
        print("\n" + "=" * 60)
        print("🎬 [Ato 1] SENSOR DE ENTRADA ATIVADO!")

        # Alterado de `camera_facial` para `PE_FACE_CAM` que é a variável correta carregada no topo
        foto_rosto = self._capturar_foto_real(PE_FACE_CAM)
        foto_placa = self._capturar_foto_real(PE_PLATE_CAM)

        if foto_rosto is None or foto_placa is None:
            print("❌ Falha crítica nas câmeras de ENTRADA.")
            return

        with ThreadPoolExecutor(max_workers=2) as executor:
            future_rosto = executor.submit(verificar_rosto_unica_foto, foto_rosto, self.db)
            future_placa = executor.submit(extrair_placa_unica_foto, foto_placa)
            morador_encontrado = future_rosto.result()
            placa_lida = future_placa.result()

        path_rosto = self._salvar_imagem_disco(foto_rosto, prefixo="entrada_rosto")
        path_placa = self._salvar_imagem_disco(foto_placa, prefixo="entrada_placa")

        agora_2026 = datetime.now().replace(year=2026)

        if morador_encontrado:
            veiculo_cadastrado = self.db.query(VeiculoModel).filter_by(
                fk_morador_dono=morador_encontrado.id, placa=placa_lida
            ).first()

            if veiculo_cadastrado:
                print(f"\n   🟢 [CENÁRIO 1] Match Duplo! Morador: {morador_encontrado.nome} | Placa: {placa_lida}")
                self._abrir_cancela_hardware("ENTRADA")
                self._registrar_log("ENTRADA", AcessoEnum.MORADOR, placa_lida, path_rosto)
            else:
                print(f"\n   🟡 [CENÁRIO 2] Prioridade Biométrica! Morador validado, placa diferente ({placa_lida}).")
                novo_temp = VeiculoTemporario(
                    fk_morador_dono=morador_encontrado.id,
                    placa_veiculo_temporario=placa_lida if placa_lida else "SEM_PLACA",
                    status=StatusEnum.DENTRO
                )
                self.db.add(novo_temp)
                self.db.commit()
                self._abrir_cancela_hardware("ENTRADA")
                self._registrar_log("ENTRADA", AcessoEnum.MORADOR, placa_lida, path_rosto)
        else:
            if not placa_lida:
                print("\n   🔴 [CENÁRIO 3] Invasor Total! Sem rosto e sem placa legível.")
                self._gerar_log_invasor(placa_lida, path_rosto, "INVASOR SEM PLACA")
                self._registrar_log("ENTRADA", AcessoEnum.NEGADO, "ILEGIVEL", path_rosto)
            else:
                agendamento = self.db.query(AgendamentoVisita).join(
                    VisitanteModel, AgendamentoVisita.fk_id_visitante == VisitanteModel.id
                ).filter(
                    VisitanteModel.placa_veiculo == placa_lida, AgendamentoVisita.ativo == True
                ).order_by(AgendamentoVisita.id_agendamento.desc()).first()

                if agendamento:
                    visitante = agendamento.visitante
                    morador_anf = self.db.query(MoradorModel).filter_by(id=agendamento.fk_id_morador).first()

                    if agendamento.data_entrada_prevista <= agora_2026 <= agendamento.data_saida_prevista:
                        print(f"\n   🔵 [CENÁRIO 4] Visitante Autorizado no prazo! (2026)")
                        log_visitante = LogVisitante(
                            path_foto_capturada=path_rosto,
                            visitante_nome=visitante.nome, visitante_cpf=visitante.cpf,
                            visitante_cnh=visitante.cnh if visitante.cnh else "N/A", visitante_placa=placa_lida,
                            morador_anfitriao_nome=morador_anf.nome if morador_anf else "N/A",
                            apartamento_visitado=morador_anf.apartamento if morador_anf else "N/A",
                            bloco_visitado=morador_anf.bloco if morador_anf else "N/A"
                        )
                        self.db.add(log_visitante)
                        self.db.commit()
                        self._abrir_cancela_hardware("ENTRADA")
                        self._registrar_log("ENTRADA", AcessoEnum.VISITANTE, placa_lida, path_rosto)
                    else:
                        print(f"\n   🟠 [CENÁRIO 5] Convite Expirado para a placa {placa_lida}.")
                        self._gerar_log_invasor(placa_lida, path_rosto, f"EXPIRADO: {visitante.nome}", morador_anf)
                        self._registrar_log("ENTRADA", AcessoEnum.NEGADO, placa_lida, path_rosto)
                else:
                    print(f"\n   🔴 [CENÁRIO 3] Invasor! Rosto desconhecido e placa ({placa_lida}) sem convite.")
                    self._gerar_log_invasor(placa_lida, path_rosto, "INVASOR DESCONHECIDO")
                    self._registrar_log("ENTRADA", AcessoEnum.NEGADO, placa_lida, path_rosto)

        print("=" * 60 + "\n")

    # ==========================================
    # 🎭 ATO 2: A SAÍDA (Prevenção de Roubo)
    # ==========================================
    def _ato_2_fluxo_saida(self):
        print("\n" + "=" * 60)
        print("🎬 [Ato 2] SENSOR DE SAÍDA ATIVADO!")

        foto_rosto = self._capturar_foto_real(PS_FACE_CAM)
        foto_placa = self._capturar_foto_real(PS_PLATE_CAM)

        if foto_rosto is None or foto_placa is None:
            print("❌ Falha crítica nas câmeras de SAÍDA.")
            return

        with ThreadPoolExecutor(max_workers=2) as executor:
            future_rosto = executor.submit(verificar_rosto_unica_foto, foto_rosto, self.db)
            future_placa = executor.submit(extrair_placa_unica_foto, foto_placa)
            morador_encontrado = future_rosto.result()
            placa_lida = future_placa.result()

        path_rosto = self._salvar_imagem_disco(foto_rosto, prefixo="saida_rosto")
        path_placa = self._salvar_imagem_disco(foto_placa, prefixo="saida_placa")

        if morador_encontrado:
            veiculo_cadastrado = self.db.query(VeiculoModel).filter_by(
                fk_morador_dono=morador_encontrado.id, placa=placa_lida
            ).first()

            if veiculo_cadastrado:
                # 🟢 CENÁRIO 1 DA SAÍDA: Saída Normal e Autorizada
                print(f"\n   🟢 [SAÍDA: CENÁRIO 1] Tudo certo! Morador ({morador_encontrado.nome}) saindo com o próprio veículo ({placa_lida}).")
                self._abrir_cancela_hardware("SAIDA")
                self._registrar_log("SAIDA", AcessoEnum.MORADOR, placa_lida, path_rosto)
            else:
                # 🟡 CENÁRIO 2 DA SAÍDA: Alerta de Uso Indevido / Roubo
                print(f"\n   🟡 [SAÍDA: CENÁRIO 2] Atenção! Morador ({morador_encontrado.nome}) saindo com veículo desconhecido ({placa_lida}).")

                # Vamos descobrir se esse carro é de algum vizinho
                veiculo_terceiro = self.db.query(VeiculoModel).filter_by(placa=placa_lida).first()
                if veiculo_terceiro:
                    dono = self.db.query(MoradorModel).filter_by(id=veiculo_terceiro.fk_morador_dono).first()
                    dono_nome = dono.nome if dono else "Outro Morador"
                    texto_alerta = f"SAÍDA SUSPEITA: O morador {morador_encontrado.nome} (Apt: {morador_encontrado.apartamento}) saiu conduzindo o veículo placa {placa_lida}, pertencente ao vizinho {dono_nome}."
                else:
                    texto_alerta = f"SAÍDA SUSPEITA: O morador {morador_encontrado.nome} saiu com o veículo placa {placa_lida} (Sem registro no condomínio)."

                # Salva o Alerta Crítico no banco para auditoria futura
                novo_alerta = AlertaPainel(tipo_alerta="USO_INDEVIDO", texto=texto_alerta)
                self.db.add(novo_alerta)
                self.db.commit()

                print(f"   🚨 [ALERTA] {texto_alerta}")
                try:
                    requests.post("http://127.0.0.1:8000/api/internal/trigger", json={"evento": "NOVO_ALERTA"})
                except:
                    pass

                self._abrir_cancela_hardware("SAIDA")
                self._registrar_log("SAIDA", AcessoEnum.MORADOR, placa_lida, path_rosto)
        else:
            # Fallback para Visitante saindo
            print(f"\n   ⚪ [SAÍDA: VISITANTE] Veículo {placa_lida} saindo sem biometria vinculada.")
            self._abrir_cancela_hardware("SAIDA")
            self._registrar_log("SAIDA", AcessoEnum.VISITANTE, placa_lida, path_placa)

        print("=" * 60 + "\n")

    def _gerar_log_invasor(self, placa, path_foto, motivo_nome, morador_anf=None):
        log_invasor = LogVisitante(
            path_foto_capturada=path_foto,
            visitante_nome=motivo_nome, visitante_cpf="N/A", visitante_cnh="N/A",
            visitante_placa=placa if placa else "ILEGIVEL",
            morador_anfitriao_nome=morador_anf.nome if morador_anf else "N/A",
            apartamento_visitado=morador_anf.apartamento if morador_anf else "N/A",
            bloco_visitado=morador_anf.bloco if morador_anf else "N/A"
        )
        self.db.add(log_invasor)
        self.db.commit()