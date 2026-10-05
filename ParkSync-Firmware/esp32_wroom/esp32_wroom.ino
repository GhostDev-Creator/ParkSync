#include <WiFi.h>
#include <PubSubClient.h>
#include <ESP32Servo.h>

// ================= CONFIGURAÇÕES =================
const char* ssid = "SEU_WIFI";
const char* password = "SUA_SENHA_WIFI";
const char* mqtt_server = "192.168.1.100"; // IP do computador rodando o Mosquitto

// Pinos Entrada
#define TRIG_ENTRADA 5
#define ECHO_ENTRADA 18
#define PINO_SERVO_ENTRADA 19

// Pinos Saída
#define TRIG_SAIDA 21
#define ECHO_SAIDA 22
#define PINO_SERVO_SAIDA 23

// Constantes de Lógica
const int DISTANCIA_GATILHO = 20; // cm para detectar o carro
const long COOLDOWN_SENSOR = 5000; // 5 segundos de trava anti-spam
const long TEMPO_CANCELA_ABERTA = 5000; // 5 segundos para o carro passar

// Instâncias
WiFiClient espClient;
PubSubClient client(espClient);
Servo servoEntrada;
Servo servoSaida;

// Variáveis de Controle (Modo não-bloqueante)
long ultimoAvisoEntrada = 0;
long ultimoAvisoSaida = 0;

bool cancelaEntradaAberta = false;
long tempoAberturaEntrada = 0;

bool cancelaSaidaAberta = false;
long tempoAberturaSaida = 0;

// ================= FUNÇÕES AUXILIARES =================
long lerDistancia(int trigPin, int echoPin) {
  digitalWrite(trigPin, LOW);
  delayMicroseconds(2);
  digitalWrite(trigPin, HIGH);
  delayMicroseconds(10);
  digitalWrite(trigPin, LOW);
  long duracao = pulseIn(echoPin, HIGH, 30000); // Timeout para não travar
  if (duracao == 0) return 999;
  return duracao * 0.034 / 2;
}

void callbackMqtt(char* topic, byte* payload, unsigned int length) {
  String mensagem = "";
  for (int i = 0; i < length; i++) {
    mensagem += (char)payload[i];
  }
  
  // Escuta os comandos do Python
  if (String(topic) == "parksync/cancela/entrada/comando" && mensagem == "ABRIR") {
    servoEntrada.write(90); // Levanta cancela
    cancelaEntradaAberta = true;
    tempoAberturaEntrada = millis();
    Serial.println("Abrindo cancela de ENTRADA");
  } 
  else if (String(topic) == "parksync/cancela/saida/comando" && mensagem == "ABRIR") {
    servoSaida.write(90); // Levanta cancela
    cancelaSaidaAberta = true;
    tempoAberturaSaida = millis();
    Serial.println("Abrindo cancela de SAÍDA");
  }
}

void reconectarMqtt() {
  while (!client.connected()) {
    Serial.print("Conectando ao MQTT...");
    if (client.connect("ESP32_WROOM_Sensores")) {
      Serial.println("Conectado!");
      client.subscribe("parksync/cancela/entrada/comando"); //[cite: 1]
      client.subscribe("parksync/cancela/saida/comando");   //[cite: 1]
    } else {
      delay(2000);
    }
  }
}

// ================= SETUP E LOOP =================
void setup() {
  Serial.begin(115200);
  
  pinMode(TRIG_ENTRADA, OUTPUT);
  pinMode(ECHO_ENTRADA, INPUT);
  pinMode(TRIG_SAIDA, OUTPUT);
  pinMode(ECHO_SAIDA, INPUT);
  
  servoEntrada.attach(PINO_SERVO_ENTRADA);
  servoSaida.attach(PINO_SERVO_SAIDA);
  servoEntrada.write(0); // Posição inicial (fechada)
  servoSaida.write(0);
  
  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED) delay(500);
  
  client.setServer(mqtt_server, 1883);
  client.setCallback(callbackMqtt);
}

void loop() {
  if (!client.connected()) reconectarMqtt();
  client.loop(); // Mantém MQTT vivo

  long agora = millis();

  // 1. LEITURA SENSOR DE ENTRADA E ANTI-SPAM
  if (agora - ultimoAvisoEntrada > COOLDOWN_SENSOR) {
    if (lerDistancia(TRIG_ENTRADA, ECHO_ENTRADA) < DISTANCIA_GATILHO) {
      client.publish("parksync/sensor/entrada", "DETECTADO"); //[cite: 1]
      Serial.println("Carro na entrada! Avisando Python...");
      ultimoAvisoEntrada = agora;
    }
  }

  // 2. LEITURA SENSOR DE SAÍDA E ANTI-SPAM
  if (agora - ultimoAvisoSaida > COOLDOWN_SENSOR) {
    if (lerDistancia(TRIG_SAIDA, ECHO_SAIDA) < DISTANCIA_GATILHO) {
      client.publish("parksync/sensor/saida", "DETECTADO"); //[cite: 1]
      Serial.println("Carro na saída! Avisando Python...");
      ultimoAvisoSaida = agora;
    }
  }

  // 3. FECHAMENTO AUTOMÁTICO DAS CANCELAS
  if (cancelaEntradaAberta && (agora - tempoAberturaEntrada > TEMPO_CANCELA_ABERTA)) {
    servoEntrada.write(0);
    cancelaEntradaAberta = false;
    Serial.println("Fechando cancela de ENTRADA");
  }

  if (cancelaSaidaAberta && (agora - tempoAberturaSaida > TEMPO_CANCELA_ABERTA)) {
    servoSaida.write(0);
    cancelaSaidaAberta = false;
    Serial.println("Fechando cancela de SAÍDA");
  }
}