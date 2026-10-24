#include <WiFi.h>
#include <PubSubClient.h>
#include <ESP32Servo.h> // OBRIGATÓRIO instalar na IDE do Arduino para ESP32

// ================= CONFIGURAÇÕES DE REDE E MQTT =================
const char* ssid = "SEU_WIFI";
const char* password = "SUA_SENHA_WIFI";
const char* mqtt_server = "192.168.1.100"; // O mesmo IP que configurou nas câmeras
const char* MQTT_CLIENT_ID = "ESP32_WROOM_CONTROL";

WiFiClient espClient;
PubSubClient client(espClient);

// ================= DEFINIÇÃO DE PINOS =================
#define TRIG_ENTRADA 13
#define ECHO_ENTRADA 12
#define TRIG_SAIDA 14
#define ECHO_SAIDA 27
#define PINO_SERVO_ENTRADA 26
#define PINO_SERVO_SAIDA 25

Servo servoEntrada;
Servo servoSaida;

// ================= VARIÁVEIS DE CONTROLE =================
const float DISTANCIA_GATILHO = 10.0; // Distância em cm para detectar o carrinho na maquete

// Estados dos Sensores (Borda de subida para não spammar o backend)
bool carroNaEntrada = false;
bool carroNaSaida = false;

// Controle de tempo para fechar as cancelas automaticamente sem usar delay()
bool cancelaEntradaAberta = false;
bool cancelaSaidaAberta = false;
unsigned long tempoAberturaEntrada = 0;
unsigned long tempoAberturaSaida = 0;
const unsigned long TEMPO_CANCELA_ABERTA = 5000; // Cancela fica aberta por 5 segundos

// Ângulos dos Servos (Ajuste conforme a mecânica da sua maquete)
const int ANGULO_FECHADO = 0;
const int ANGULO_ABERTO = 90;

// ================= FUNÇÕES DE LEITURA =================
float lerDistancia(int pinoTrig, int pinoEcho) {
  digitalWrite(pinoTrig, LOW);
  delayMicroseconds(2);
  digitalWrite(pinoTrig, HIGH);
  delayMicroseconds(10);
  digitalWrite(pinoTrig, LOW);
  
  long duracao = pulseIn(pinoEcho, HIGH, 30000); // Timeout de 30ms para não travar
  if (duracao == 0) return 999.0; // Se não leu nada, retorna muito longe
  
  return (duracao * 0.0343) / 2.0; // Converte para centímetros
}

// ================= CALLBACK MQTT =================
void callbackMqtt(char* topic, byte* payload, unsigned int length) {
  String mensagem = "";
  for (int i = 0; i < length; i++) {
    mensagem += (char)payload[i];
  }
  
  String topico = String(topic);
  Serial.println("Comando recebido: " + topico + " -> " + mensagem);

  // Comando para abrir a cancela de ENTRADA
  if (topico == "parksync/cancela/entrada/comando" && mensagem == "ABRIR") {
    servoEntrada.write(ANGULO_ABERTO);
    cancelaEntradaAberta = true;
    tempoAberturaEntrada = millis(); // Inicia o cronômetro
    Serial.println("🟢 Abrindo Cancela de ENTRADA");
  }
  
  // Comando para abrir a cancela de SAÍDA
  if (topico == "parksync/cancela/saida/comando" && mensagem == "ABRIR") {
    servoSaida.write(ANGULO_ABERTO);
    cancelaSaidaAberta = true;
    tempoAberturaSaida = millis(); // Inicia o cronômetro
    Serial.println("🟢 Abrindo Cancela de SAÍDA");
  }
}

void reconectarMqtt() {
  while (!client.connected()) {
    Serial.print("Tentando conexão MQTT WROOM... ");
    if (client.connect(MQTT_CLIENT_ID)) {
      Serial.println("Conectado!");
      // Inscreve nos tópicos de comando das cancelas
      client.subscribe("parksync/cancela/entrada/comando");
      client.subscribe("parksync/cancela/saida/comando");
    } else {
      Serial.print("Falhou, rc=");
      Serial.print(client.state());
      delay(2000);
    }
  }
}

// ================= SETUP =================
void setup() {
  Serial.begin(115200);

  // Configura Pinos Sensores
  pinMode(TRIG_ENTRADA, OUTPUT);
  pinMode(ECHO_ENTRADA, INPUT);
  pinMode(TRIG_SAIDA, OUTPUT);
  pinMode(ECHO_SAIDA, INPUT);

  // Configura Servos
  servoEntrada.attach(PINO_SERVO_ENTRADA);
  servoSaida.attach(PINO_SERVO_SAIDA);
  servoEntrada.write(ANGULO_FECHADO); // Inicia fechado
  servoSaida.write(ANGULO_FECHADO);   // Inicia fechado

  // Conecta Wi-Fi
  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println("\n✅ WROOM Conectado ao Wi-Fi!");

  // Configura MQTT
  client.setServer(mqtt_server, 1883);
  client.setCallback(callbackMqtt);
}

// ================= LOOP PRINCIPAL =================
void loop() {
  if (!client.connected()) reconectarMqtt();
  client.loop();

  // 1. LEITURA DOS SENSORES (Não-bloqueante)
  float distEntrada = lerDistancia(TRIG_ENTRADA, ECHO_ENTRADA);
  float distSaida = lerDistancia(TRIG_SAIDA, ECHO_SAIDA);

  // 1.1 Lógica de Borda da Entrada
  if (distEntrada <= DISTANCIA_GATILHO && !carroNaEntrada) {
    carroNaEntrada = true; // O carro acabou de chegar
    Serial.println("🚗 Carrinho detectado na ENTRADA!");
    client.publish("parksync/sensor/entrada", "DETECTADO");
  } 
  else if (distEntrada > DISTANCIA_GATILHO + 2.0 && carroNaEntrada) {
    carroNaEntrada = false; // O carro saiu (adicionado Histerese de 2cm para evitar falso positivo)
    Serial.println("💨 Carrinho saiu da ENTRADA.");
  }

  // 1.2 Lógica de Borda da Saída
  if (distSaida <= DISTANCIA_GATILHO && !carroNaSaida) {
    carroNaSaida = true;
    Serial.println("🚗 Carrinho detectado na SAÍDA!");
    client.publish("parksync/sensor/saida", "DETECTADO");
  } 
  else if (distSaida > DISTANCIA_GATILHO + 2.0 && carroNaSaida) {
    carroNaSaida = false;
    Serial.println("💨 Carrinho saiu da SAÍDA.");
  }

  // 2. FECHAMENTO AUTOMÁTICO DAS CANCELAS
  // Se estiver aberta e já passou o tempo, fecha automaticamente
  if (cancelaEntradaAberta && (millis() - tempoAberturaEntrada >= TEMPO_CANCELA_ABERTA)) {
    servoEntrada.write(ANGULO_FECHADO);
    cancelaEntradaAberta = false;
    Serial.println("🔴 Fechando Cancela de ENTRADA");
  }

  if (cancelaSaidaAberta && (millis() - tempoAberturaSaida >= TEMPO_CANCELA_ABERTA)) {
    servoSaida.write(ANGULO_FECHADO);
    cancelaSaidaAberta = false;
    Serial.println("🔴 Fechando Cancela de SAÍDA");
  }

  delay(50); // Pequeno delay apenas para estabilizar as leituras dos sensores
}