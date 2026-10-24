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

const char* TOPICO_ACORDAR = "parksync/camera/saida/acordar";
const char* MQTT_CLIENT_ID = "ESP32_CAM_SAIDA"; // ID ÚNICO PARA SAÍDA

// Pinos do modelo AI-Thinker (Compatível com OV3660 nesta placa)
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
httpd_handle_t camera_httpd = NULL;

// ================= ENDPOINT DE FOTO ÚNICA (/capture) =================
static esp_err_t capture_handler(httpd_req_t *req) {
  camera_fb_t * fb = NULL;
  esp_err_t res = ESP_OK;

  Serial.println("📸 Requisição de foto recebida via HTTP!");

  fb = esp_camera_fb_get();
  if (!fb) {
    Serial.println("❌ Falha na captura da câmera");
    httpd_resp_send_500(req);
    return ESP_FAIL;
  }

  httpd_resp_set_type(req, "image/jpeg");
  httpd_resp_set_hdr(req, "Content-Disposition", "inline; filename=capture.jpg");

  res = httpd_resp_send(req, (const char *)fb->buf, fb->len);
  
  esp_camera_fb_return(fb);
  return res;
}

void startCameraServer() {
  httpd_config_t config = HTTPD_DEFAULT_CONFIG();
  config.server_port = 81;

  httpd_uri_t capture_uri = {
    .uri       = "/capture",
    .method    = HTTP_GET,
    .handler   = capture_handler,
    .user_ctx  = NULL
  };

  if (httpd_start(&camera_httpd, &config) == ESP_OK) {
    httpd_register_uri_handler(camera_httpd, &capture_uri);
    Serial.println("🌐 Servidor HTTP iniciado.");
  }
}

// ================= LÓGICA MQTT =================
void callbackMqtt(char* topic, byte* payload, unsigned int length) {
  if (String(topic) == TOPICO_ACORDAR) {
    Serial.println("⏰ GATILHO RECEBIDO! Backend vai pedir a foto em milissegundos.");
  }
}

void reconectarMqtt() {
  while (!client.connected()) {
    Serial.print("Tentando MQTT... ");
    if (client.connect(MQTT_CLIENT_ID)) {
      Serial.println("Conectado!");
      client.subscribe(TOPICO_ACORDAR);
    } else {
      Serial.print("Falha, rc=");
      Serial.print(client.state());
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
  
  config.frame_size = FRAMESIZE_VGA;
  config.jpeg_quality = 12; 
  config.fb_count = 1;

  esp_err_t err = esp_camera_init(&config);
  if (err != ESP_OK) {
    Serial.printf("❌ Falha na camera: 0x%x", err);
    return;
  }

  sensor_t * s = esp_camera_sensor_get();
  s->set_contrast(s, 1);
  s->set_saturation(s, 1);

  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  
  Serial.println("");
  Serial.print("✅ IP da Câmera (SAIDA): http://");
  Serial.print(WiFi.localIP());
  Serial.println(":81/capture");

  client.setServer(mqtt_server, 1883);
  client.setCallback(callbackMqtt);

  startCameraServer();
}

void loop() {
  if (!client.connected()) reconectarMqtt();
  client.loop();
}