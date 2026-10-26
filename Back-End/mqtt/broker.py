# Arquivo: Back-End/mqtt/broker.py
#
# Conexão com o Mosquitto. Tópicos usados pelo firmware:
#   ESP32 WROOM publica:   parksync/sensor/entrada  e  parksync/sensor/saida   ("DETECTADO")
#   ESP32 WROOM assina:    parksync/cancela/entrada/comando  e  .../saida/comando  ("ABRIR")
#   ESP32-CAM assinam:     parksync/camera/entrada/acordar  e  .../saida/acordar  ("ACORDA")

import json
import paho.mqtt.client as mqtt
from utils import config

TOPICO_SENSOR_ENTRADA = "parksync/sensor/entrada"
TOPICO_SENSOR_SAIDA = "parksync/sensor/saida"
TOPICO_CANCELA = "parksync/cancela/{lado}/comando"
TOPICO_ACORDAR_CAMERA = "parksync/camera/{lado}/acordar"


class ParkBroker:
    def __init__(self):
        self.client = mqtt.Client(
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
            client_id="ParkSync_Backend",
        )
        if config.MQTT_USER:
            self.client.username_pw_set(config.MQTT_USER, config.MQTT_PASSWORD)
        self.client.reconnect_delay_set(min_delay=1, max_delay=10)

        self.funcoes_topicos = {}
        self.conectado = False
        self.iniciado = False

        self.client.on_connect = self._quando_conectar
        self.client.on_message = self._quando_mensagem_chegar
        self.client.on_disconnect = self._quando_desconectar

    def _quando_conectar(self, client, userdata, flags, reason_code, properties=None):
        if reason_code == 0:
            self.conectado = True
            print(f"✅ Broker MQTT conectado em {config.MQTT_IP}:{config.MQTT_PORT}")
            # Re-assina tudo a cada (re)conexão
            for topico in list(self.funcoes_topicos.keys()):
                self.client.subscribe(topico, qos=1)
        else:
            self.conectado = False
            print(f"❌ Erro na conexão MQTT: {reason_code}")

    def _quando_mensagem_chegar(self, client, userdata, msg):
        topico = msg.topic
        try:
            conteudo = msg.payload.decode("utf-8").strip()
            funcao = self.funcoes_topicos.get(topico)
            if funcao:
                print(f"📨 MQTT '{topico}': {conteudo}")
                funcao(topico, conteudo)
        except Exception as e:
            print(f"❌ Erro ao processar mensagem de '{topico}': {e}")

    def _quando_desconectar(self, client, userdata, flags, reason_code, properties=None):
        self.conectado = False
        if reason_code != 0:
            print(f"⚠️  MQTT desconectado (código {reason_code}). Tentando reconectar sozinho...")

    def cadastrar_assunto(self, topico: str, funcao):
        """funcao(topico, mensagem) será chamada quando chegar mensagem no tópico."""
        self.funcoes_topicos[topico] = funcao
        if self.conectado:
            self.client.subscribe(topico, qos=1)

    def iniciar(self):
        """Não trava e não derruba a API se o Mosquitto estiver desligado: fica tentando em background."""
        if self.iniciado:
            return
        self.iniciado = True
        print(f"🔌 Conectando ao broker MQTT em {config.MQTT_IP}:{config.MQTT_PORT}...")
        try:
            self.client.connect_async(config.MQTT_IP, config.MQTT_PORT, config.MQTT_TIMEOUT)
            self.client.loop_start()
        except Exception as e:
            print(f"❌ [AVISO] Não foi possível iniciar o MQTT ({e}). A API sobe mesmo assim, sem sensores.")

    def enviar_mensagem(self, topico: str, mensagem, qos: int = 1) -> bool:
        if not self.conectado:
            print(f"⚠️  MQTT offline: não enviei '{mensagem}' para '{topico}'.")
            return False
        try:
            conteudo = json.dumps(mensagem) if isinstance(mensagem, dict) else str(mensagem)
            self.client.publish(topico, conteudo, qos=qos)
            print(f"📤 MQTT '{topico}': {conteudo}")
            return True
        except Exception as e:
            print(f"❌ Erro ao publicar em '{topico}': {e}")
            return False

    def parar(self):
        try:
            self.client.loop_stop()
            self.client.disconnect()
        except Exception:
            pass
        self.iniciado = False


# Instância única usada pelo main.py e pelo orquestrador
broker = ParkBroker()
