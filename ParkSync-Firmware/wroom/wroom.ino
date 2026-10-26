// =====================================================================
//  ParkSync - ESP32 WROOM (controle): 2 sensores ultrassônicos + 2 cancelas (servos)
//
//  Placa na IDE: "ESP32 Dev Module".  Bibliotecas: PubSubClient (Nick O'Leary) e ESP32Servo.
//  Compila com core esp32 3.0.7 e 2.0.17, PubSubClient 2.8, ESP32Servo 3.2.1.
//
//  Fluxo com o backend:
//    sensor detecta carro  -> publica "DETECTADO" em parksync/sensor/<lado> (só na chegada)
//    backend manda "ABRIR" em parksync/cancela/<lado>/comando -> cancela abre
//    cancela fecha sozinha depois de TEMPO_CANCELA_ABERTA_MS, mas só com o sensor livre
//
//  Arquitetura: Wi-Fi + MQTT rodam numa tarefa própria (núcleo 0). O loop() (núcleo 1)
//  só cuida de sensores e servos, então uma queda de rede nunca trava as cancelas.
//
//  Teste pelo Serial Monitor (115200, "Nova linha"):
//    e / s   -> simula carro na entrada / saída (publica DETECTADO)
//    E / S   -> abre a cancela de entrada / saída localmente
//    d       -> mostra as distâncias atuais
// =====================================================================
#include <WiFi.h>
#include <PubSubClient.h>
#include <ESP32Servo.h>
#include <esp_task_wdt.h>
#include "soc/gpio_struct.h"
#include "config.h"

// ================= PINOS =================
// ATENÇÃO: o ECHO da entrada saiu do GPIO 12. O 12 é pino de "strapping": se estiver em
// nível alto no boot, a ESP32 tenta ligar a flash em 1,8 V e não inicia. O 34 é só entrada,
// perfeito para ECHO.  O ECHO do HC-SR04 sai em 5 V: use divisor (1 kΩ + 2 kΩ) nos dois ECHO.
#define TRIG_ENTRADA        13
#define ECHO_ENTRADA        34   // era 12
#define TRIG_SAIDA          14
#define ECHO_SAIDA          27
#define PINO_SERVO_ENTRADA  26
#define PINO_SERVO_SAIDA    25

// ================= AJUSTES DA MAQUETE =================
const float    DISTANCIA_GATILHO_CM   = 10.0;  // carro mais perto que isso = presente
const float    HISTERESE_CM           = 2.0;   // precisa passar de 12 cm para contar como "saiu"
const uint8_t  AMOSTRAS_CONFIRMA      = 2;     // medianas seguidas "perto" para confirmar chegada
const uint32_t TEMPO_LIVRE_MS         = 1000;  // sensor livre por 1 s = carro saiu
const uint32_t COOLDOWN_DETECCAO_MS   = 3000;  // mesmo valor do DEBOUNCE do backend
const uint32_t INTERVALO_PING_MS      = 30;    // um sensor a cada 30 ms, alternando (sem eco cruzado)
const uint32_t TIMEOUT_ECO_US         = 25000; // ~4 m; acima disso conta como "nada na frente"

const int      ANGULO_FECHADO         = 0;
const int      ANGULO_ABERTO          = 90;
const uint32_t TEMPO_CANCELA_ABERTA_MS = 5000; // mínimo aberta (um novo ABRIR reinicia)
const uint32_t PASSO_SERVO_MS         = 8;     // 1 grau a cada 8 ms (~0,7 s para 90°). 0 = instantâneo

// ================= TIPOS =================
struct Sensor {
  const char* nome;
  uint8_t trig, echo;
  const char* topico;
  volatile uint32_t inicioEco = 0;
  volatile uint32_t duracaoEco = 0;
  volatile bool pronto = false;
  float leituras[3] = {999, 999, 999};
  uint8_t qtdLeituras = 0, posLeitura = 0;
  float distancia = 999;   // mediana das 3 últimas
  bool presente = false;
  uint8_t contaPerto = 0;
  uint32_t livreDesde = 0; // 0 = não está livre
  uint32_t ultimoEnvio = 0;
  Sensor(const char* n, uint8_t t, uint8_t e, const char* top) : nome(n), trig(t), echo(e), topico(top) {}
};

struct Cancela {
  const char* nome;
  uint8_t pino;
  Servo servo{};
  Sensor* sensor = nullptr;
  const char* topicoEstado = nullptr;
  bool aberta = false;
  uint32_t abertaEm = 0;
  int anguloAtual = ANGULO_FECHADO, anguloAlvo = ANGULO_FECHADO;
  uint32_t ultimoPasso = 0;
  Cancela(const char* n, uint8_t p) : nome(n), pino(p) {}
};

struct MensagemSaida {
  char topico[48];
  char payload[24];
  bool retido;
};

enum Comando : uint8_t { CMD_ABRIR_ENTRADA, CMD_ABRIR_SAIDA, CMD_FECHAR_ENTRADA, CMD_FECHAR_SAIDA };

// ================= ESTADO =================
Sensor sensorEntrada("ENTRADA", TRIG_ENTRADA, ECHO_ENTRADA, TOPICO_SENSOR_ENTRADA);
Sensor sensorSaida  ("SAIDA",   TRIG_SAIDA,   ECHO_SAIDA,   TOPICO_SENSOR_SAIDA);
Sensor* sensores[2]  = { &sensorEntrada, &sensorSaida };
uint8_t sensorAtual = 0;
uint32_t ultimoPing = 0;
bool pingEmAndamento = false;

Cancela cancelaEntrada("ENTRADA", PINO_SERVO_ENTRADA);
Cancela cancelaSaida  ("SAIDA",   PINO_SERVO_SAIDA);

QueueHandle_t filaSaida;     // loop -> tarefa de rede (publicações)
QueueHandle_t filaComandos;  // callback MQTT -> loop (abrir/fechar)

WiFiClient wifiClient;
PubSubClient mqtt(wifiClient);
char mqttClientId[40];
char topicoStatus[48];
volatile bool mqttOnline = false;

// ================= WATCHDOG (API muda entre core 2.x e 3.x) =================
void configurarWatchdog() {
#if defined(ESP_ARDUINO_VERSION_MAJOR) && ESP_ARDUINO_VERSION_MAJOR >= 3
  esp_task_wdt_config_t cfg = {};
  cfg.timeout_ms = WATCHDOG_SEGUNDOS * 1000;
  cfg.idle_core_mask = 0;
  cfg.trigger_panic = true;
  if (esp_task_wdt_reconfigure(&cfg) != ESP_OK) esp_task_wdt_init(&cfg);
#else
  esp_task_wdt_init(WATCHDOG_SEGUNDOS, true);
#endif
}

// ================= ULTRASSÔNICO POR INTERRUPÇÃO (sem pulseIn) =================
static inline bool IRAM_ATTR nivelPino(uint8_t pino) {
  return pino < 32 ? ((GPIO.in >> pino) & 1) : ((GPIO.in1.val >> (pino - 32)) & 1);
}

void IRAM_ATTR isrEco(void* arg) {
  Sensor* s = (Sensor*)arg;
  uint32_t agora = micros();
  if (nivelPino(s->echo)) {
    s->inicioEco = agora;
  } else if (s->inicioEco) {
    s->duracaoEco = agora - s->inicioEco;
    s->pronto = true;
  }
}

void dispararPing(Sensor* s) {
  noInterrupts();
  s->pronto = false;
  s->inicioEco = 0;
  s->duracaoEco = 0;
  interrupts();
  digitalWrite(s->trig, LOW);
  delayMicroseconds(2);
  digitalWrite(s->trig, HIGH);
  delayMicroseconds(10);
  digitalWrite(s->trig, LOW);
}

float mediana3(float a, float b, float c) {
  if (a > b) { float t = a; a = b; b = t; }
  if (b > c) { float t = b; b = c; c = t; }
  if (a > b) { float t = a; a = b; b = t; }
  return b;
}

void publicar(const char* topico, const char* payload, bool retido = false) {
  MensagemSaida m;
  strlcpy(m.topico, topico, sizeof(m.topico));
  strlcpy(m.payload, payload, sizeof(m.payload));
  m.retido = retido;
  if (xQueueSend(filaSaida, &m, 0) != pdTRUE) Serial.println("⚠️  Fila MQTT cheia, mensagem descartada");
}

void processarLeitura(Sensor* s) {
  float cm = 999.0;
  if (s->pronto && s->duracaoEco > 0 && s->duracaoEco < TIMEOUT_ECO_US) cm = s->duracaoEco / 58.0f;

  s->leituras[s->posLeitura] = cm;
  s->posLeitura = (s->posLeitura + 1) % 3;
  if (s->qtdLeituras < 3) { s->qtdLeituras++; return; }
  s->distancia = mediana3(s->leituras[0], s->leituras[1], s->leituras[2]);

  uint32_t agora = millis();
  if (!s->presente) {
    if (s->distancia <= DISTANCIA_GATILHO_CM) {
      if (++s->contaPerto >= AMOSTRAS_CONFIRMA) {
        s->presente = true;
        s->livreDesde = 0;
        if (s->ultimoEnvio == 0 || agora - s->ultimoEnvio >= COOLDOWN_DETECCAO_MS) {
          s->ultimoEnvio = agora;
          Serial.printf("🚗 Carro na %s (%.1f cm) -> %s\n", s->nome, s->distancia, PAYLOAD_DETECTADO);
          publicar(s->topico, PAYLOAD_DETECTADO);
        } else {
          Serial.printf("⏭️  Carro na %s ignorado (cooldown)\n", s->nome);
        }
      }
    } else {
      s->contaPerto = 0;
    }
  } else {
    if (s->distancia > DISTANCIA_GATILHO_CM + HISTERESE_CM) {
      if (s->livreDesde == 0) s->livreDesde = agora;
      else if (agora - s->livreDesde >= TEMPO_LIVRE_MS) {
        s->presente = false;
        s->contaPerto = 0;
        Serial.printf("💨 Carro saiu da %s\n", s->nome);
      }
    } else {
      s->livreDesde = 0;
    }
  }
}

void atualizarSensores() {
  uint32_t agora = millis();
  if (agora - ultimoPing < INTERVALO_PING_MS) return;
  ultimoPing = agora;
  if (pingEmAndamento) processarLeitura(sensores[sensorAtual]);
  sensorAtual = (sensorAtual + 1) % 2;
  dispararPing(sensores[sensorAtual]);
  pingEmAndamento = true;
}

// ================= CANCELAS =================
void iniciarCancela(Cancela& c, Sensor* s, const char* topicoEstado) {
  c.sensor = s;
  c.topicoEstado = topicoEstado;
  c.servo.setPeriodHertz(50);
  c.servo.attach(c.pino, 500, 2400);
  c.anguloAtual = c.anguloAlvo = ANGULO_FECHADO;
  c.servo.write(ANGULO_FECHADO);
  c.aberta = false;
}

void abrirCancela(Cancela& c) {
  c.abertaEm = millis();  // novo ABRIR com ela aberta só reinicia o tempo
  if (!c.aberta) {
    c.aberta = true;
    c.anguloAlvo = ANGULO_ABERTO;
    Serial.printf("🟢 Abrindo cancela de %s\n", c.nome);
    publicar(c.topicoEstado, "ABERTA", true);
  } else {
    Serial.printf("🔁 Cancela de %s já aberta: tempo reiniciado\n", c.nome);
  }
}

void fecharCancela(Cancela& c) {
  if (!c.aberta) return;
  c.aberta = false;
  c.anguloAlvo = ANGULO_FECHADO;
  Serial.printf("🔴 Fechando cancela de %s\n", c.nome);
  publicar(c.topicoEstado, "FECHADA", true);
}

void atualizarCancela(Cancela& c) {
  uint32_t agora = millis();
  // Fecha só depois do tempo mínimo E com o sensor daquele lado livre
  if (c.aberta && agora - c.abertaEm >= TEMPO_CANCELA_ABERTA_MS && !c.sensor->presente) fecharCancela(c);

  if (c.anguloAtual == c.anguloAlvo) return;
  if (PASSO_SERVO_MS == 0) {
    c.anguloAtual = c.anguloAlvo;
    c.servo.write(c.anguloAtual);
  } else if (agora - c.ultimoPasso >= PASSO_SERVO_MS) {
    c.ultimoPasso = agora;
    c.anguloAtual += (c.anguloAlvo > c.anguloAtual) ? 1 : -1;
    c.servo.write(c.anguloAtual);
  }
}

void tratarComandos() {
  Comando cmd;
  while (xQueueReceive(filaComandos, &cmd, 0) == pdTRUE) {
    switch (cmd) {
      case CMD_ABRIR_ENTRADA:  abrirCancela(cancelaEntrada); break;
      case CMD_ABRIR_SAIDA:    abrirCancela(cancelaSaida);   break;
      case CMD_FECHAR_ENTRADA: fecharCancela(cancelaEntrada); break;
      case CMD_FECHAR_SAIDA:   fecharCancela(cancelaSaida);   break;
    }
  }
}

void tratarSerial() {
  while (Serial.available()) {
    char c = Serial.read();
    switch (c) {
      case 'e': Serial.println("🧪 Simulando carro na ENTRADA"); publicar(TOPICO_SENSOR_ENTRADA, PAYLOAD_DETECTADO); break;
      case 's': Serial.println("🧪 Simulando carro na SAIDA");   publicar(TOPICO_SENSOR_SAIDA, PAYLOAD_DETECTADO);   break;
      case 'E': abrirCancela(cancelaEntrada); break;
      case 'S': abrirCancela(cancelaSaida);   break;
      case 'd':
        Serial.printf("📏 Entrada %.1f cm (%s) | Saída %.1f cm (%s) | MQTT %s\n",
                      sensorEntrada.distancia, sensorEntrada.presente ? "carro" : "livre",
                      sensorSaida.distancia, sensorSaida.presente ? "carro" : "livre",
                      mqttOnline ? "online" : "offline");
        break;
    }
  }
}

// ================= REDE (tarefa no núcleo 0) =================
static bool payloadIgual(const byte* p, unsigned int len, const char* esperado) {
  // ignora espaços/quebras de linha nas pontas e maiúsc./minúsc.
  while (len && isspace(p[len - 1])) len--;
  while (len && isspace(*p)) { p++; len--; }
  if (len != strlen(esperado)) return false;
  for (unsigned int i = 0; i < len; i++) if (toupper(p[i]) != esperado[i]) return false;
  return true;
}

void callbackMqtt(char* topico, byte* payload, unsigned int len) {
  Serial.printf("📨 %s -> %.*s\n", topico, (int)len, (const char*)payload);
  bool entrada = strcmp(topico, TOPICO_CANCELA_ENTRADA) == 0;
  bool saida   = strcmp(topico, TOPICO_CANCELA_SAIDA) == 0;
  if (!entrada && !saida) return;
  Comando cmd;
  if (payloadIgual(payload, len, PAYLOAD_ABRIR))       cmd = entrada ? CMD_ABRIR_ENTRADA : CMD_ABRIR_SAIDA;
  else if (payloadIgual(payload, len, PAYLOAD_FECHAR)) cmd = entrada ? CMD_FECHAR_ENTRADA : CMD_FECHAR_SAIDA;
  else { Serial.println("⚠️  Comando desconhecido, ignorado"); return; }
  xQueueSend(filaComandos, &cmd, 0);
}

bool conectarMqtt() {
  Serial.printf("🔌 MQTT %s:%d como %s... ", MQTT_BROKER_IP, MQTT_PORTA, mqttClientId);
  const char* usuario = strlen(MQTT_USUARIO) ? MQTT_USUARIO : nullptr;
  const char* senha   = strlen(MQTT_USUARIO) ? MQTT_SENHA : nullptr;
  if (!mqtt.connect(mqttClientId, usuario, senha, topicoStatus, 1, true, "offline")) {
    Serial.printf("falhou (rc=%d)\n", mqtt.state());
    return false;
  }
  Serial.println("conectado!");
  mqtt.subscribe(TOPICO_CANCELA_ENTRADA, 1);
  mqtt.subscribe(TOPICO_CANCELA_SAIDA, 1);
  mqtt.publish(topicoStatus, "online", true);
  mqtt.publish(cancelaEntrada.topicoEstado, cancelaEntrada.aberta ? "ABERTA" : "FECHADA", true);
  mqtt.publish(cancelaSaida.topicoEstado, cancelaSaida.aberta ? "ABERTA" : "FECHADA", true);
  return true;
}

void tarefaRede(void*) {
  esp_task_wdt_add(NULL);
  uint32_t ultimaTentativaWifi = millis(), ultimaTentativaMqtt = 0, semWifiDesde = millis();
  bool wifiAvisado = false;

  for (;;) {
    esp_task_wdt_reset();
    uint32_t agora = millis();

    if (WiFi.status() != WL_CONNECTED) {
      mqttOnline = false;
      wifiAvisado = false;
      if (agora - semWifiDesde > REINICIAR_SEM_WIFI_MS) {
        Serial.println("♻️  Sem Wi-Fi há muito tempo, reiniciando...");
        delay(100);
        ESP.restart();
      }
      if (agora - ultimaTentativaWifi > 15000) {
        ultimaTentativaWifi = agora;
        Serial.println("📶 Wi-Fi caiu, tentando de novo...");
        WiFi.disconnect();
        WiFi.begin(WIFI_SSID, WIFI_SENHA);
      }
      vTaskDelay(pdMS_TO_TICKS(100));
      continue;
    }
    semWifiDesde = agora;
    if (!wifiAvisado) {
      wifiAvisado = true;
      Serial.printf("✅ Wi-Fi OK. IP do WROOM: %s (RSSI %d dBm)\n", WiFi.localIP().toString().c_str(), WiFi.RSSI());
    }

    if (!mqtt.connected()) {
      mqttOnline = false;
      if (ultimaTentativaMqtt == 0 || agora - ultimaTentativaMqtt >= 3000) {
        ultimaTentativaMqtt = agora;
        mqttOnline = conectarMqtt();
      }
    } else {
      mqtt.loop();
      MensagemSaida m;
      while (xQueuePeek(filaSaida, &m, 0) == pdTRUE) {
        if (!mqtt.publish(m.topico, m.payload, m.retido)) break;  // tenta de novo depois
        xQueueReceive(filaSaida, &m, 0);
        Serial.printf("📤 %s -> %s\n", m.topico, m.payload);
      }
    }
    vTaskDelay(pdMS_TO_TICKS(5));
  }
}

// ================= SETUP / LOOP =================
void setup() {
  Serial.begin(115200);
  delay(200);
  Serial.println("\n=== ParkSync WROOM (sensores + cancelas) ===");
  configurarWatchdog();

  filaSaida = xQueueCreate(16, sizeof(MensagemSaida));
  filaComandos = xQueueCreate(8, sizeof(Comando));

  for (Sensor* s : sensores) {
    pinMode(s->trig, OUTPUT);
    digitalWrite(s->trig, LOW);
    pinMode(s->echo, INPUT);
    attachInterruptArg(digitalPinToInterrupt(s->echo), isrEco, s, CHANGE);
  }

  ESP32PWM::allocateTimer(0);
  ESP32PWM::allocateTimer(1);
  iniciarCancela(cancelaEntrada, &sensorEntrada, "parksync/cancela/entrada/estado");
  iniciarCancela(cancelaSaida,   &sensorSaida,   "parksync/cancela/saida/estado");

  // MAC lido do eFuse: WiFi.macAddress() antes do Wi-Fi ligar devolve 00:00:00 no core 3
  uint64_t mac = ESP.getEfuseMac();
  WiFi.mode(WIFI_STA);
  snprintf(mqttClientId, sizeof(mqttClientId), "parksync-wroom-%02X%02X%02X",
           (unsigned)((mac >> 24) & 0xFF), (unsigned)((mac >> 32) & 0xFF), (unsigned)((mac >> 40) & 0xFF));
  snprintf(topicoStatus, sizeof(topicoStatus), "%swroom", TOPICO_STATUS_BASE);

  WiFi.setHostname("parksync-wroom");
  WiFi.setSleep(false);  // resposta mais rápida ao "ABRIR"
  WiFi.setAutoReconnect(true);
#if USAR_IP_FIXO
  WiFi.config(IPAddress(IP_WROOM), IPAddress(IP_GATEWAY), IPAddress(IP_MASCARA), IPAddress(IP_DNS));
#endif
  WiFi.begin(WIFI_SSID, WIFI_SENHA);
  Serial.printf("📶 Conectando ao Wi-Fi \"%s\" (sem travar as cancelas)...\n", WIFI_SSID);

  IPAddress ipBroker;
  if (!ipBroker.fromString(MQTT_BROKER_IP)) {
    Serial.printf("❌ MQTT_BROKER_IP \"%s\" no config.h não é um IP válido (precisa de 4 números)\n", MQTT_BROKER_IP);
  }
  mqtt.setServer(ipBroker, MQTT_PORTA);
  mqtt.setCallback(callbackMqtt);
  mqtt.setKeepAlive(MQTT_KEEPALIVE_S);
  mqtt.setSocketTimeout(3);
#if defined(ESP_ARDUINO_VERSION_MAJOR) && ESP_ARDUINO_VERSION_MAJOR >= 3
  wifiClient.setConnectionTimeout(1500);
#else
  wifiClient.setTimeout(2);
#endif

  xTaskCreatePinnedToCore(tarefaRede, "rede", 6144, nullptr, 1, nullptr, 0);
  esp_task_wdt_add(NULL);  // loopTask
}

void loop() {
  esp_task_wdt_reset();
  atualizarSensores();
  tratarComandos();
  atualizarCancela(cancelaEntrada);
  atualizarCancela(cancelaSaida);
  tratarSerial();
  delay(1);
}
