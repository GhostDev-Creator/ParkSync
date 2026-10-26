// =====================================================================
//  ParkSync - config.h  (MESMO ARQUIVO nas 3 pastas: wroom, esp_cam_entrada, esp_cam_saida)
//
//  A IDE do Arduino só enxerga arquivos dentro da pasta do sketch, por isso
//  existe uma cópia em cada pasta. Edite UMA e copie para as outras duas.
// =====================================================================
#pragma once

// ================= REDE WI-FI =================
#define WIFI_SSID        "SEU_WIFI"
#define WIFI_SENHA       "SUA_SENHA_WIFI"

// ================= BROKER MQTT (Mosquitto, no PC do backend) =================
// Mesmo IP do PC onde roda o Mosquitto (MQTT_IP do .env do backend aponta para ele).
#define MQTT_BROKER_IP   "192.168.1.100"
#define MQTT_PORTA       1883
// Deixe "" se o Mosquitto não tem usuário/senha (igual a MQTT_USER/MQTT_PASSWORD do .env)
#define MQTT_USUARIO     ""
#define MQTT_SENHA       ""
#define MQTT_KEEPALIVE_S 15

// ================= IP FIXO (opcional) =================
// O .env do backend precisa do IP de cada ESP32-CAM (PE_PLATE_CAM / PS_PLATE_CAM).
// 1 = usa os IPs abaixo. 0 = DHCP (aí reserve o IP no roteador ou copie do Serial Monitor).
#define USAR_IP_FIXO     0
#define IP_GATEWAY       192, 168, 1, 1
#define IP_MASCARA       255, 255, 255, 0
#define IP_DNS           192, 168, 1, 1
#define IP_CAM_ENTRADA   192, 168, 1, 50   // .env: PE_PLATE_CAM=http://192.168.1.50:81
#define IP_CAM_SAIDA     192, 168, 1, 51   // .env: PS_PLATE_CAM=http://192.168.1.51:81
#define IP_WROOM         192, 168, 1, 52

// ================= TÓPICOS (iguais ao Back-End/mqtt/broker.py) =================
#define TOPICO_SENSOR_ENTRADA    "parksync/sensor/entrada"          // WROOM publica "DETECTADO"
#define TOPICO_SENSOR_SAIDA      "parksync/sensor/saida"
#define TOPICO_CANCELA_ENTRADA   "parksync/cancela/entrada/comando" // backend publica "ABRIR"
#define TOPICO_CANCELA_SAIDA     "parksync/cancela/saida/comando"
#define TOPICO_ACORDAR_ENTRADA   "parksync/camera/entrada/acordar"  // backend publica "ACORDA"
#define TOPICO_ACORDAR_SAIDA     "parksync/camera/saida/acordar"

#define PAYLOAD_DETECTADO "DETECTADO"
#define PAYLOAD_ABRIR     "ABRIR"
#define PAYLOAD_FECHAR    "FECHAR"   // extra (o backend não usa hoje; útil no teste manual)
#define PAYLOAD_ACORDA    "ACORDA"

// Extras do firmware (o backend ignora; servem para diagnóstico com mosquitto_sub):
//   parksync/status/<dispositivo>         "online" / "offline" (retido, offline vem do LWT)
//   parksync/cancela/<lado>/estado        "ABERTA" / "FECHADA" (retido)
//   parksync/status/cam_<lado>/url        "http://IP:81/capture" (retido)
#define TOPICO_STATUS_BASE "parksync/status/"

// ================= WATCHDOG =================
// Se o loop travar por mais que isso, a placa reinicia sozinha.
#define WATCHDOG_SEGUNDOS 20
// Sem Wi-Fi por mais que isso -> reinicia (destrava o rádio em casos raros).
#define REINICIAR_SEM_WIFI_MS 120000UL
