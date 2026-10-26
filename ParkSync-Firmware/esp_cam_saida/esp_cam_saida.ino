// =====================================================================
//  ParkSync - ESP32-CAM (AI-Thinker) da SAÍDA: foto da placa por HTTP
//
//  O código das duas câmeras é IGUAL; só muda a linha CAMERA_DA_ENTRADA abaixo.
//  Placa na IDE: "AI Thinker ESP32-CAM" (PSRAM ligada). Biblioteca: PubSubClient.
//  Compila com core esp32 3.0.7 e 2.0.17, PubSubClient 2.8.
//
//  Fluxo com o backend:
//    backend publica "ACORDA" em parksync/camera/<lado>/acordar (só aviso; a câmera já está pronta)
//    ~0,4 s depois faz GET http://IP:81/capture (timeout 3 s, 3 tentativas) e roda YOLO + OCR
//
//  Endpoints:  http://IP:81/capture  (JPEG)   http://IP:81/status  (JSON de diagnóstico)
// =====================================================================
#define CAMERA_DA_ENTRADA 0   // 1 = entrada, 0 = saída
#define FIRMWARE_VERSAO "v3 (25/10)"   // aparece no boot e no /status: confira depois de gravar

#include <WiFi.h>
#include <PubSubClient.h>
#include <esp_task_wdt.h>
#include "esp_camera.h"
#include "esp_http_server.h"
#include "soc/soc.h"
#include "soc/rtc_cntl_reg.h"
#include "config.h"

#if CAMERA_DA_ENTRADA
  #define LADO          "entrada"
  #define TOPICO_ACORDAR TOPICO_ACORDAR_ENTRADA
  #define IP_DESTA_CAM  IP_CAM_ENTRADA
#else
  #define LADO          "saida"
  #define TOPICO_ACORDAR TOPICO_ACORDAR_SAIDA
  #define IP_DESTA_CAM  IP_CAM_SAIDA
#endif

// ================= AJUSTES DA FOTO =================
// SVGA (800x600) + qualidade 12 = placa nítida para o OCR e ~20-50 KB por foto (rápido no Wi-Fi).
// Se a placa ficar pequena na foto, teste FRAMESIZE_XGA (1024x768).
#define CAM_RESOLUCAO        FRAMESIZE_SVGA
#define CAM_QUALIDADE_JPEG   14    // 0-63, menor = melhor (menor demais gera "FB-OVF")
// 10 MHz evita o "cam_hal: FB-OVF" (quadros corrompidos) do OV3660 com Wi-Fi ligado.
// Se continuar aparecendo, tente 8. O OV2640 também funciona bem em 10.
#define CAM_XCLK_MHZ         10
#define CAM_BUFFERS          2     // quadros guardados na PSRAM
#define AQUECER_A_CADA_MS    3000  // sem pedidos, tira e descarta 1 quadro nesse intervalo
#define CAM_VIRAR_VERTICAL   0     // 1 se a imagem sair de cabeça para baixo (comum no OV3660)
#define CAM_ESPELHAR         0     // 1 se a placa sair espelhada
#define CAM_NIVEL_EXPOSICAO  0     // -2 (mais escuro) a 2 (mais claro)

// Flash (LED branco do GPIO 4). Na maquete costuma refletir na placa: comece com 0.
#define USAR_FLASH           0
#define PINO_FLASH           4
#define FLASH_ANTES_MS       120   // tempo para a exposição se ajustar com o flash aceso

// ================= PINOS AI-THINKER =================
#define PWDN_GPIO_NUM     32
#define RESET_GPIO_NUM    -1
#define XCLK_GPIO_NUM      0
#define SIOD_GPIO_NUM     26
#define SIOC_GPIO_NUM     27
#define Y9_GPIO_NUM       35
#define Y8_GPIO_NUM       34
#define Y7_GPIO_NUM       39
#define Y6_GPIO_NUM       36
#define Y5_GPIO_NUM       21
#define Y4_GPIO_NUM       19
#define Y3_GPIO_NUM       18
#define Y2_GPIO_NUM        5
#define VSYNC_GPIO_NUM    25
#define HREF_GPIO_NUM     23
#define PCLK_GPIO_NUM     22
#define LED_VERMELHO      33   // LED da placa (lógica invertida): aceso = sem rede

WiFiClient wifiClient;
PubSubClient mqtt(wifiClient);
httpd_handle_t servidor = nullptr;
char mqttClientId[40];
char topicoStatus[48];
char urlCaptura[48];

uint32_t totalFotos = 0, falhasSeguidas = 0, totalAcordar = 0;
volatile bool pedirReinicio = false;
volatile uint32_t flashDesligarEm = 0;
volatile uint32_t ultimoUsoCamera = 0;
SemaphoreHandle_t mutexCamera;    // pedido HTTP e aquecimento não usam a câmera ao mesmo tempo
int buffersCamera = 1;
bool brokerValido = false;

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

// ================= CÂMERA =================
bool iniciarCamera() {
  camera_config_t config = {};
  config.ledc_channel = LEDC_CHANNEL_0;
  config.ledc_timer = LEDC_TIMER_0;
  config.pin_d0 = Y2_GPIO_NUM;
  config.pin_d1 = Y3_GPIO_NUM;
  config.pin_d2 = Y4_GPIO_NUM;
  config.pin_d3 = Y5_GPIO_NUM;
  config.pin_d4 = Y6_GPIO_NUM;
  config.pin_d5 = Y7_GPIO_NUM;
  config.pin_d6 = Y8_GPIO_NUM;
  config.pin_d7 = Y9_GPIO_NUM;
  config.pin_xclk = XCLK_GPIO_NUM;
  config.pin_pclk = PCLK_GPIO_NUM;
  config.pin_vsync = VSYNC_GPIO_NUM;
  config.pin_href = HREF_GPIO_NUM;
  config.pin_sccb_sda = SIOD_GPIO_NUM;
  config.pin_sccb_scl = SIOC_GPIO_NUM;
  config.pin_pwdn = PWDN_GPIO_NUM;
  config.pin_reset = RESET_GPIO_NUM;
  config.xclk_freq_hz = CAM_XCLK_MHZ * 1000000;
  config.pixel_format = PIXFORMAT_JPEG;

  if (psramFound()) {
    // GRAB_WHEN_EMPTY: a captura para quando os buffers enchem (sem DMA contínuo disputando a
    // PSRAM com o Wi-Fi). No pedido, os quadros parados são descartados e vai um quadro novo.
    config.frame_size = CAM_RESOLUCAO;
    config.jpeg_quality = CAM_QUALIDADE_JPEG;
    config.fb_count = CAM_BUFFERS;
    config.fb_location = CAMERA_FB_IN_PSRAM;
    config.grab_mode = CAMERA_GRAB_WHEN_EMPTY;
  } else {
    Serial.println("⚠️  PSRAM não encontrada: usando VGA com 1 buffer (confira a placa escolhida na IDE)");
    config.frame_size = FRAMESIZE_VGA;
    config.jpeg_quality = 12;
    config.fb_count = 1;
    config.fb_location = CAMERA_FB_IN_DRAM;
    config.grab_mode = CAMERA_GRAB_WHEN_EMPTY;
  }

  buffersCamera = config.fb_count;
  esp_err_t err = esp_camera_init(&config);
  if (err != ESP_OK) {
    Serial.printf("❌ Falha ao iniciar a câmera: 0x%x (cabo flat solto? fonte fraca?)\n", err);
    return false;
  }

  sensor_t* s = esp_camera_sensor_get();
  Serial.printf("📷 Sensor: %s\n", s->id.PID == OV3660_PID ? "OV3660" : s->id.PID == OV2640_PID ? "OV2640" : "outro");
  s->set_framesize(s, config.frame_size);
  s->set_whitebal(s, 1);
  s->set_awb_gain(s, 1);
  s->set_exposure_ctrl(s, 1);
  s->set_aec2(s, 1);                       // exposição automática melhor com pouca luz
  s->set_ae_level(s, CAM_NIVEL_EXPOSICAO);
  s->set_gain_ctrl(s, 1);
  s->set_gainceiling(s, GAINCEILING_8X);   // limita o ganho: menos ruído nas letras
  s->set_bpc(s, 1);
  s->set_wpc(s, 1);
  s->set_lenc(s, 1);
  s->set_dcw(s, 1);
  s->set_contrast(s, 1);                   // letras pretas mais destacadas
  s->set_saturation(s, 0);
  s->set_sharpness(s, 1);                  // o OV2640 ignora
  s->set_vflip(s, CAM_VIRAR_VERTICAL);
  s->set_hmirror(s, CAM_ESPELHAR);

  // Descarta os primeiros quadros (exposição e balanço de branco ainda ajustando)
  for (int i = 0; i < 5; i++) {
    camera_fb_t* fb = esp_camera_fb_get();
    if (fb) esp_camera_fb_return(fb);
  }
  return true;
}

void flash(bool ligado) {
#if USAR_FLASH
  digitalWrite(PINO_FLASH, ligado ? HIGH : LOW);
#endif
}

// JPEG inteiro começa com FF D8 e termina com FF D9. Quadro cortado (imagem com a parte de
// baixo branca/cinza) não tem o FF D9 no fim e é jogado fora.
bool jpegCompleto(const camera_fb_t* fb) {
  if (!fb || fb->len < 1024 || fb->buf[0] != 0xFF || fb->buf[1] != 0xD8) return false;
  size_t fim = fb->len;
  while (fim > 2 && fb->buf[fim - 1] == 0x00) fim--;   // alguns sensores completam com zeros
  return fb->buf[fim - 2] == 0xFF && fb->buf[fim - 1] == 0xD9;
}

uint32_t quadrosRuins = 0;

// Descarta os quadros parados nos buffers e devolve um quadro inteiro começado depois do pedido.
// Cada esp_camera_fb_get espera no máximo 4 s; se um descarte falhar, pula direto para a foto.
camera_fb_t* capturarQuadroNovo() {
  for (int i = 0; i < buffersCamera; i++) {
    camera_fb_t* velho = esp_camera_fb_get();
    if (!velho) break;
    esp_camera_fb_return(velho);
  }
  for (int tentativa = 0; tentativa < 4; tentativa++) {
    camera_fb_t* fb = esp_camera_fb_get();
    if (!fb) continue;
    if (jpegCompleto(fb)) return fb;
    quadrosRuins++;
    Serial.printf("⚠️  Quadro cortado descartado (%u bytes)\n", (unsigned)fb->len);
    esp_camera_fb_return(fb);
  }
  return nullptr;
}

// Tarefa que mantém a câmera "aquecida": sem pedidos, tira e descarta um quadro a cada
// AQUECER_A_CADA_MS. Assim a exposição está ajustada e uma câmera travada é detectada antes.
void tarefaAquecer(void*) {
  uint32_t falhas = 0;
  for (;;) {
    vTaskDelay(pdMS_TO_TICKS(500));
    if (millis() - ultimoUsoCamera < AQUECER_A_CADA_MS) continue;
    if (xSemaphoreTake(mutexCamera, 0) != pdTRUE) continue;
    uint32_t t0 = millis();
    camera_fb_t* fb = esp_camera_fb_get();
    if (fb) esp_camera_fb_return(fb);
    ultimoUsoCamera = millis();
    xSemaphoreGive(mutexCamera);
    if (!fb) {
      Serial.printf("⚠️  Aquecimento: câmera não entregou quadro (%u)\n", (unsigned)++falhas);
      if (falhas >= 3) pedirReinicio = true;
    } else {
      falhas = 0;
      if (millis() - t0 > 1000) Serial.printf("⚠️  Aquecimento lento: %lu ms\n", (unsigned long)(millis() - t0));
    }
  }
}

// ================= HTTP =================
static esp_err_t handlerCaptura(httpd_req_t* req) {
  uint32_t t0 = millis();
  if (xSemaphoreTake(mutexCamera, pdMS_TO_TICKS(6000)) != pdTRUE) {
    httpd_resp_send_500(req);
    return ESP_FAIL;
  }
#if USAR_FLASH
  flash(true);
  delay(FLASH_ANTES_MS);
#endif

  camera_fb_t* fb = capturarQuadroNovo();
  uint32_t msCaptura = millis() - t0;

#if USAR_FLASH
  flash(false);
  flashDesligarEm = 0;
#endif

  if (!fb) {
    ultimoUsoCamera = millis();
    xSemaphoreGive(mutexCamera);
    falhasSeguidas++;
    Serial.printf("❌ Falha na captura (%u seguidas)\n", (unsigned)falhasSeguidas);
    if (falhasSeguidas >= 3) pedirReinicio = true;
    httpd_resp_send_500(req);
    return ESP_FAIL;
  }
  falhasSeguidas = 0;

  httpd_resp_set_type(req, "image/jpeg");
  httpd_resp_set_hdr(req, "Content-Disposition", "inline; filename=capture.jpg");
  httpd_resp_set_hdr(req, "Cache-Control", "no-store");
  httpd_resp_set_hdr(req, "Access-Control-Allow-Origin", "*");
  esp_err_t res = httpd_resp_send(req, (const char*)fb->buf, fb->len);
  size_t tamanho = fb->len;
  uint16_t largura = fb->width, altura = fb->height;
  esp_camera_fb_return(fb);
  ultimoUsoCamera = millis();
  xSemaphoreGive(mutexCamera);

  totalFotos++;
  // "captura" alto = câmera; "envio" alto = Wi-Fi fraco ou fonte instável
  Serial.printf("📸 Foto %u enviada: %ux%u, %u KB (captura %lu ms, envio %lu ms)%s\n", (unsigned)totalFotos,
                largura, altura, (unsigned)(tamanho / 1024), (unsigned long)msCaptura,
                (unsigned long)(millis() - t0 - msCaptura), res == ESP_OK ? "" : " ERRO NO ENVIO");
  return res;
}

static esp_err_t handlerStatus(httpd_req_t* req) {
  char json[400];
  snprintf(json, sizeof(json),
           "{\"versao\":\"" FIRMWARE_VERSAO "\",\"quadros_ruins\":%u,\"lado\":\"%s\",\"ip\":\"%s\",\"rssi\":%d,\"mqtt\":%s,\"fotos\":%u,\"acordar\":%u,"
           "\"heap_livre\":%u,\"psram_livre\":%u,\"uptime_s\":%lu}",
           (unsigned)quadrosRuins, LADO, WiFi.localIP().toString().c_str(), WiFi.RSSI(), mqtt.connected() ? "true" : "false",
           (unsigned)totalFotos, (unsigned)totalAcordar, (unsigned)ESP.getFreeHeap(), (unsigned)ESP.getFreePsram(),
           (unsigned long)(millis() / 1000));
  httpd_resp_set_type(req, "application/json");
  httpd_resp_set_hdr(req, "Access-Control-Allow-Origin", "*");
  return httpd_resp_sendstr(req, json);
}

void iniciarServidor() {
  httpd_config_t config = HTTPD_DEFAULT_CONFIG();
  config.server_port = 81;               // igual ao PE_PLATE_CAM / PS_PLATE_CAM do .env
  config.ctrl_port = 32781;
  config.stack_size = 8192;
  config.max_open_sockets = 3;
  config.lru_purge_enable = true;        // conexão velha é fechada se chegar uma nova
  config.recv_wait_timeout = 5;
  config.send_wait_timeout = 5;

  httpd_uri_t captura = {};
  captura.uri = "/capture";
  captura.method = HTTP_GET;
  captura.handler = handlerCaptura;
  httpd_uri_t status = {};
  status.uri = "/status";
  status.method = HTTP_GET;
  status.handler = handlerStatus;

  if (httpd_start(&servidor, &config) == ESP_OK) {
    httpd_register_uri_handler(servidor, &captura);
    httpd_register_uri_handler(servidor, &status);
    Serial.println("🌐 Servidor HTTP na porta 81 (/capture e /status)");
  } else {
    Serial.println("❌ Não consegui iniciar o servidor HTTP, reiniciando...");
    delay(2000);
    ESP.restart();
  }
}

// ================= MQTT =================
void callbackMqtt(char* topico, byte* payload, unsigned int len) {
  if (strcmp(topico, TOPICO_ACORDAR) != 0) return;
  totalAcordar++;
  Serial.printf("⏰ %.*s recebido: o backend vai pedir a foto em instantes\n", (int)len, (const char*)payload);
#if USAR_FLASH
  flash(true);                           // acende já para a exposição se ajustar
  flashDesligarEm = millis() + 3000;     // apaga sozinho se a foto não vier
#endif
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
  mqtt.subscribe(TOPICO_ACORDAR, 1);
  mqtt.publish(topicoStatus, "online", true);
  char topicoUrl[64];
  snprintf(topicoUrl, sizeof(topicoUrl), "%s/url", topicoStatus);
  mqtt.publish(topicoUrl, urlCaptura, true);
  return true;
}

// ================= SETUP / LOOP =================
void setup() {
  WRITE_PERI_REG(RTC_CNTL_BROWN_OUT_REG, 0);  // evita reset por queda de tensão no pico do Wi-Fi
  Serial.begin(115200);
  delay(200);
  Serial.println("\n=== ParkSync ESP32-CAM (" LADO ") firmware " FIRMWARE_VERSAO " ===");
  pinMode(LED_VERMELHO, OUTPUT);
  digitalWrite(LED_VERMELHO, LOW);            // aceso até conectar
#if USAR_FLASH
  pinMode(PINO_FLASH, OUTPUT);
  flash(false);
#endif

  if (!iniciarCamera()) {
    delay(3000);
    ESP.restart();                            // não adianta seguir sem câmera
  }
  mutexCamera = xSemaphoreCreateMutex();
  ultimoUsoCamera = millis();
  xTaskCreatePinnedToCore(tarefaAquecer, "aquecer", 4096, nullptr, 1, nullptr, 1);
  configurarWatchdog();
  esp_task_wdt_add(NULL);

  // MAC lido do eFuse: WiFi.macAddress() antes do Wi-Fi ligar devolve 00:00:00 no core 3
  uint64_t mac = ESP.getEfuseMac();
  WiFi.mode(WIFI_STA);
  snprintf(mqttClientId, sizeof(mqttClientId), "parksync-cam-" LADO "-%02X%02X%02X",
           (unsigned)((mac >> 24) & 0xFF), (unsigned)((mac >> 32) & 0xFF), (unsigned)((mac >> 40) & 0xFF));
  snprintf(topicoStatus, sizeof(topicoStatus), "%scam_" LADO, TOPICO_STATUS_BASE);

  WiFi.setHostname("parksync-cam-" LADO);
  WiFi.setSleep(false);                       // sem economia de energia: HTTP responde bem mais rápido
  WiFi.setAutoReconnect(true);
#if USAR_IP_FIXO
  WiFi.config(IPAddress(IP_DESTA_CAM), IPAddress(IP_GATEWAY), IPAddress(IP_MASCARA), IPAddress(IP_DNS));
#endif
  WiFi.begin(WIFI_SSID, WIFI_SENHA);
  Serial.printf("📶 Conectando ao Wi-Fi \"%s\"", WIFI_SSID);
  uint32_t inicio = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - inicio < 20000) {
    esp_task_wdt_reset();
    delay(250);
    Serial.print(".");
  }
  Serial.println();
  if (WiFi.status() == WL_CONNECTED) {
    snprintf(urlCaptura, sizeof(urlCaptura), "http://%s:81/capture", WiFi.localIP().toString().c_str());
    Serial.printf("✅ Câmera (%s) pronta: %s  (RSSI %d dBm)\n", LADO, urlCaptura, WiFi.RSSI());
    Serial.printf("   No .env do backend: %s=http://%s:81\n",
                  CAMERA_DA_ENTRADA ? "PE_PLATE_CAM" : "PS_PLATE_CAM", WiFi.localIP().toString().c_str());
  } else {
    Serial.println("⚠️  Wi-Fi ainda não conectou; continuo tentando no loop");
  }

  // Confere se o IP do broker no config.h está completo (ex.: "192.168.15.20", 4 números)
  IPAddress ipBroker;
  brokerValido = ipBroker.fromString(MQTT_BROKER_IP);
  if (!brokerValido) {
    Serial.printf("❌ MQTT_BROKER_IP \"%s\" no config.h não é um IP válido. Sem MQTT; o /capture funciona.\n", MQTT_BROKER_IP);
  }
  mqtt.setServer(ipBroker, MQTT_PORTA);
  mqtt.setCallback(callbackMqtt);
  mqtt.setKeepAlive(MQTT_KEEPALIVE_S);
  mqtt.setSocketTimeout(3);
  // Conexão TCP ao broker desiste em 1,5 s (padrão é 3 s) se o PC não responder
#if defined(ESP_ARDUINO_VERSION_MAJOR) && ESP_ARDUINO_VERSION_MAJOR >= 3
  wifiClient.setConnectionTimeout(1500);
#else
  wifiClient.setTimeout(2);
#endif

  iniciarServidor();
}

void loop() {
  static uint32_t ultimaTentativaMqtt = 0, ultimaTentativaWifi = 0, semWifiDesde = millis();
  static uint32_t esperaMqtt = 5000;   // backoff: 5 s, 10 s, 20 s... até 60 s
  static bool estavaConectado = false;
  esp_task_wdt_reset();
  uint32_t agora = millis();

  if (pedirReinicio) {
    Serial.println("♻️  Câmera falhando várias vezes seguidas, reiniciando...");
    delay(200);
    ESP.restart();
  }
#if USAR_FLASH
  if (flashDesligarEm && (int32_t)(agora - flashDesligarEm) >= 0) { flash(false); flashDesligarEm = 0; }
#endif

  if (WiFi.status() != WL_CONNECTED) {
    if (estavaConectado) Serial.println("📶 Wi-Fi caiu, reconectando...");
    estavaConectado = false;
    digitalWrite(LED_VERMELHO, LOW);
    if (agora - semWifiDesde > REINICIAR_SEM_WIFI_MS) {
      Serial.println("♻️  Sem Wi-Fi há muito tempo, reiniciando...");
      delay(100);
      ESP.restart();
    }
    if (agora - ultimaTentativaWifi > 15000) {
      ultimaTentativaWifi = agora;
      WiFi.disconnect();
      WiFi.begin(WIFI_SSID, WIFI_SENHA);
    }
    delay(50);
    return;
  }
  semWifiDesde = agora;
  if (!estavaConectado) {
    estavaConectado = true;
    snprintf(urlCaptura, sizeof(urlCaptura), "http://%s:81/capture", WiFi.localIP().toString().c_str());
    Serial.printf("✅ Wi-Fi OK: %s\n", urlCaptura);
  }

  if (!brokerValido) {
    // sem MQTT configurado: só o servidor HTTP
  } else if (!mqtt.connected()) {
    digitalWrite(LED_VERMELHO, LOW);
    // O MQTT só serve para o aviso "ACORDA": mesmo sem ele o /capture continua funcionando
    if (ultimaTentativaMqtt == 0 || agora - ultimaTentativaMqtt >= esperaMqtt) {
      ultimaTentativaMqtt = millis();
      if (conectarMqtt()) {
        esperaMqtt = 5000;
      } else {
        esperaMqtt = min<uint32_t>(esperaMqtt * 2, 60000);
        Serial.printf("   próxima tentativa em %lu s (o /capture funciona sem MQTT)\n", (unsigned long)(esperaMqtt / 1000));
      }
    }
  } else {
    digitalWrite(LED_VERMELHO, HIGH);         // apagado = tudo conectado
    mqtt.loop();
  }
  delay(10);
}
