#include <WiFi.h>
#include <PubSubClient.h>
#include "esp_camera.h"
#include "soc/soc.h"           // Controle de Brownout
#include "soc/rtc_cntl_reg.h"  // Controle de Brownout
#include "esp_http_server.h"

// ================= CONFIGURAÇÕES =================
const char* ssid = "SEU_WIFI";
const char* password = "SUA_SENHA_WIFI";
const char* mqtt_server = "192.168.1.100";

// Defina de qual câmera estamos falando (Mude na segunda placa)
const char* TOPICO_ACORDAR = "parksync/camera/entrada/acordar";

// Pinos do modelo AI-Thinker
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

WiFiClient espClient;
PubSubClient client(espClient);
httpd_handle_t stream_httpd = NULL;

// Controle do Modo Soneca
bool cameraAcordada = false;
long tempoAcordada = 0;
const long TEMPO_ATIVA = 10000; // Fica ativa por 10s após ser acordada

// ================= SERVIDOR DE STREAMING MJPEG =================
// Esta função é o que o cv2.VideoCapture() do Python acessa
static esp_err_t stream_handler(httpd_req_t *req) {
  camera_fb_t * fb = NULL;
  esp_err_t res = ESP_OK;
  size_t _jpg_buf_len = 0;
  uint8_t * _jpg_buf = NULL;
  char * part_buf[64];

  res = httpd_resp_set_type(req, "multipart/x-mixed-replace;boundary=123456789000000000000987654321");
  
  while (true) {
    // SE ESTIVER EM SONECA: Envia frames minúsculos vazios para não desconectar o OpenCV, mas não gasta hardware
    if (!cameraAcordada) {
      delay(500); // Economiza CPU
      continue;
    }

    // Se estiver ACORDADA, captura foto real
    fb = esp_camera_fb_get();
    if (!fb) {
      Serial.println("Camera capture failed");
      res = ESP_FAIL;
    } else {
      _jpg_buf_len = fb->len;
      _jpg_buf = fb->buf;
    }
    
    if (res == ESP_OK) {
      size_t hlen = snprintf((char *)part_buf, 64, "Content-Type: image/jpeg\r\nContent-Length: %u\r\n\r\n", _jpg_buf_len);
      res = httpd_resp_send_chunk(req, (const char *)part_buf, hlen);
    }
    if (res == ESP_OK) {
      res = httpd_resp_send_chunk(req, (const char *)_jpg_buf, _jpg_buf_len);
    }
    if (res == ESP_OK) {
      res = httpd_resp_send_chunk(req, "\r\n--123456789000000000000987654321\r\n", 37);
    }
    
    if (fb) {
      esp_camera_fb_return(fb); // Limpa framebuffer
      fb = NULL;
      _jpg_buf = NULL;
    }
    if (res != ESP_OK) break;
  }
  return res;
}

void startCameraServer() {
  httpd_config_t config = HTTPD_DEFAULT_CONFIG();
  config.server_port = 81;

  httpd_uri_t stream_uri = {
    .uri       = "/stream",
    .method    = HTTP_GET,
    .handler   = stream_handler,
    .user_ctx  = NULL
  };

  if (httpd_start(&stream_httpd, &config) == ESP_OK) {
    httpd_register_uri_handler(stream_httpd, &stream_uri);
  }
}

// ================= LÓGICA MQTT E SONECA =================
void callbackMqtt(char* topic, byte* payload, unsigned int length) {
  if (String(topic) == TOPICO_ACORDAR) {
    cameraAcordada = true;
    tempoAcordada = millis();
    Serial.println("⏰ GATILHO RECEBIDO! Câmera ACORDADA para a IA ler a placa.");
  }
}

void reconectarMqtt() {
  while (!client.connected()) {
    if (client.connect("ESP32_CAM_1")) {
      client.subscribe(TOPICO_ACORDAR);
    } else {
      delay(2000);
    }
  }
}

// ================= SETUP E LOOP =================
void setup() {
  WRITE_PERI_REG(RTC_CNTL_BROWN_OUT_REG, 0); // Desativa Brownout

  Serial.begin(115200);

  camera_config_t config;
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
  config.pin_sscb_sda = SIOD_GPIO_NUM;
  config.pin_sscb_scl = SIOC_GPIO_NUM;
  config.pin_pwdn = PWDN_GPIO_NUM;
  config.pin_reset = RESET_GPIO_NUM;
  config.xclk_freq_hz = 20000000;
  config.pixel_format = PIXFORMAT_JPEG;
  
  // Resolução VGA é a melhor para o EasyOCR (velocidade vs nitidez)
  config.frame_size = FRAMESIZE_VGA;
  config.jpeg_quality = 12; // 10-15 é ótimo
  config.fb_count = 1;

  esp_err_t err = esp_camera_init(&config);
  if (err != ESP_OK) {
    Serial.printf("Falha na camera: 0x%x", err);
    return;
  }

  sensor_t * s = esp_camera_sensor_get();
  // Configurações extras de imagem para ajudar o YOLO/EasyOCR
  s->set_contrast(s, 1);
  s->set_saturation(s, 1);

  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  
  Serial.println("");
  Serial.print("Stream pronto em: http://");
  Serial.print(WiFi.localIP());
  Serial.println(":81/stream");

  client.setServer(mqtt_server, 1883);
  client.setCallback(callbackMqtt);

  startCameraServer();
}

void loop() {
  if (!client.connected()) reconectarMqtt();
  client.loop();

  // Verifica se o tempo acordada já passou
  if (cameraAcordada && (millis() - tempoAcordada > TEMPO_ATIVA)) {
    cameraAcordada = false;
    Serial.println("💤 Tempo expirado. Câmera voltando para a soneca...");
  }
}