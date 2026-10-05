import os
import paho.mqtt.client as mqtt
import json
import logging

from dotenv import load_dotenv

load_dotenv()
MQTT_BROKER_IP = os.getenv("MQTT_IP")
MQTT_BROKER_PORT = int(os.getenv("MQTT_PORT"))
MQTT_TIMEOUT = int(os.getenv("MQTT_TIMEOUT"))

logger = logging.getLogger(__name__)

class ParkBroker:
    def __init__(self):
        self.client = mqtt.Client(callback_api_version=mqtt.CallbackAPIVersion.VERSION2)

        # Dicionário que mapeia tópicos para funções
        self.funcoes_topicos = {}

        # Registra os callbacks (funções que MQTT chama automaticamente)
        self.client.on_connect = self._quando_conectar
        self.client.on_message = self._quando_mensagem_chegar
        self.client.on_disconnect = self._quando_desconectar

        # Flag para rastrear se está conectado
        self.conectado = False

    def _quando_conectar(self, client, userdata, flags, rc, properties=None):
        """
        Callback: chamado quando o cliente se conecta ao broker.

        rc = código de retorno:
            0 = Conexão bem-sucedida
            1 = Protocolo incorreto
            2 = Identificador rejeitado
            3 = Servidor indisponível
            4 = Credenciais incorretas
            5 = Não autorizado
        """

        if rc == 0:
            self.conectado = True
            print("✅ Broker MQTT conectado com sucesso!")
            logger.info(f"[MQTT] Conectado ao broker {MQTT_BROKER_IP}:{MQTT_BROKER_PORT}")

            # Reinscreve em todos os tópicos cadastrados
            for topico in list(self.funcoes_topicos.keys()):
                self.client.subscribe(topico)
                print(f"   📢 Inscrito em: {topico}")
        else:
            self.conectado = False
            erros = {
                1: "Protocolo MQTT incorreto",
                2: "Identificador de cliente rejeitado",
                3: "Broker indisponível (verifique IP e porta)",
                4: "Credenciais incorretas",
                5: "Não autorizado",
            }
            mensagem_erro = erros.get(rc, f"Erro desconhecido (código {rc})")
            print(f"❌ Erro na conexão MQTT: {mensagem_erro}")
            logger.error(f"[MQTT] Falha na conexão. Código: {rc} - {mensagem_erro}")

    def _quando_mensagem_chegar(self, client, userdata, msg):
        topico = msg.topic
        try:
            # Decodifica a mensagem (de bytes para string)
            conteudo = msg.payload.decode("utf-8")

            # Se tem função registrada para este tópico, chama
            if topico in self.funcoes_topicos:
                print(f"📨 Mensagem recebida em '{topico}': {conteudo}")

                # Chama a função registrada, passando o conteúdo
                self.funcoes_topicos[topico](conteudo)
            else:
                print(f"⚠️  Mensagem em tópico desconhecido: {topico}")

        except Exception as e:
            print(f"❌ Erro ao processar mensagem do tópico '{topico}': {e}")
            logger.error(f"[MQTT] Erro ao processar mensagem: {e}")

    def _quando_desconectar(self, client, userdata, rc):
        if rc != 0:
            print(f"⚠️  Desconectado do broker. Código: {rc}")
            self.conectado = False
        else:
            print("✅ Desconectado do broker (normal)")
            self.conectado = False

    def cadastrar_assunto(self, topico: str, funcao):
        if topico in self.funcoes_topicos:
            print(f"⚠️  Tópico '{topico}' já tem uma função registrada. Substituindo...")

        self.funcoes_topicos[topico] = funcao
        print(f"✓ Tópico '{topico}' registrado para escuta.")

        # Se já está conectado, inscreve imediatamente
        if self.conectado:
            self.client.subscribe(topico)

    def iniciar(self):
        try:
            print(f"🔌 Conectando ao broker MQTT em {MQTT_BROKER_IP}:{MQTT_BROKER_PORT}...")

            self.client.connect(MQTT_BROKER_IP, MQTT_BROKER_PORT, MQTT_TIMEOUT)

            # loop_start() inicia uma thread que processa mensagens
            # Isso permite que o FastAPI continue rodando normalmente
            self.client.loop_start()

            print("✓ Loop MQTT iniciado em background")

        except Exception as e:
            print(f"❌ Erro ao conectar ao broker: {e}")
            logger.error(f"[MQTT] Erro ao conectar: {e}")
            raise

    def enviar_mensagem(self, topico: str, mensagem):
        if not self.conectado:
            print(f"⚠️  Não está conectado ao broker. Mensagem não enviada.")
            return False

        try:
            # Se mensagem é dict, converte para JSON
            if isinstance(mensagem, dict):
                conteudo = json.dumps(mensagem)
            else:
                conteudo = str(mensagem)

            self.client.publish(topico, conteudo)
            print(f"📤 Mensagem publicada em '{topico}': {conteudo}")
            return True

        except Exception as e:
            print(f"❌ Erro ao publicar mensagem: {e}")
            logger.error(f"[MQTT] Erro ao publicar: {e}")
            return False

    def parar(self):
        try:
            self.client.loop_stop()
            self.client.disconnect()
            print("✓ Broker MQTT parado.")

        except Exception as e:
            print(f"❌ Erro ao parar o broker: {e}")
            logger.error(f"[MQTT] Erro ao parar: {e}")