import os
import paho.mqtt.client as mqtt
import json
import logging
from dotenv import load_dotenv

load_dotenv()
MQTT_BROKER_IP = os.getenv("MQTT_IP")
MQTT_BROKER_PORT = int(os.getenv("MQTT_PORT"))
MQTT_TIMEOUT = int(os.getenv("MQTT_TIMEOUT", 60))

logger = logging.getLogger(__name__)

class ParkBroker:
    def __init__(self):
        self.client = mqtt.Client(callback_api_version=mqtt.CallbackAPIVersion.VERSION2)
        self.funcoes_topicos = {}
        self.conectado = False

        self.client.on_connect = self._quando_conectar
        self.client.on_message = self._quando_mensagem_chegar
        self.client.on_disconnect = self._quando_desconectar

    def _quando_conectar(self, client, userdata, flags, reason_code, properties=None):
        if reason_code == 0:
            self.conectado = True
            print("✅ Broker MQTT conectado com sucesso!")
            for topico in list(self.funcoes_topicos.keys()):
                self.client.subscribe(topico)
        else:
            self.conectado = False
            print(f"❌ Erro na conexão MQTT: Código {reason_code}")

    def _quando_mensagem_chegar(self, client, userdata, msg):
        topico = msg.topic
        try:
            conteudo = msg.payload.decode("utf-8")
            if topico in self.funcoes_topicos:
                print(f"📨 Msg em '{topico}': {conteudo}")
                self.funcoes_topicos[topico](conteudo)
        except Exception as e:
            print(f"❌ Erro ao processar msg do '{topico}': {e}")

    def _quando_desconectar(self, client, userdata, flags, reason_code, properties=None):
        self.conectado = False
        if reason_code != 0:
            print(f"⚠️  Desconectado do broker inexperadamente (código {reason_code}).")
        else:
            print("✅ Desconectado do broker normalmente.")

    def cadastrar_assunto(self, topico: str, funcao):
        self.funcoes_topicos[topico] = funcao
        if self.conectado:
            self.client.subscribe(topico)

    def iniciar(self):
        try:
            print(f"🔌 Conectando ao broker MQTT em {MQTT_BROKER_IP}:{MQTT_BROKER_PORT}...")
            self.client.connect(MQTT_BROKER_IP, MQTT_BROKER_PORT, MQTT_TIMEOUT)
            self.client.loop_start()
            print("✓ Loop MQTT iniciado em background")
        except Exception as e:
            print(f"❌ [AVISO] O Mosquitto não está rodando ({e}). O Backend vai iniciar mesmo assim, mas sem sensores.")
            self.conectado = False

    def enviar_mensagem(self, topico: str, mensagem):
        if not self.conectado: return False
        try:
            conteudo = json.dumps(mensagem) if isinstance(mensagem, dict) else str(mensagem)
            self.client.publish(topico, conteudo)
            print(f"📤 Publicado em '{topico}': {conteudo}")
            return True
        except Exception:
            return False

    def parar(self):
        try:
            self.client.loop_stop()
            self.client.disconnect()
        except: pass