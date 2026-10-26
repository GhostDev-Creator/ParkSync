# ParkSync - Firmware das ESP32

Três sketches, cada um na sua pasta (a IDE do Arduino exige pasta com o mesmo nome do `.ino`):

| Pasta | Placa na IDE | Bibliotecas |
|---|---|---|
| `wroom/` | ESP32 Dev Module | PubSubClient (Nick O'Leary) 2.8, ESP32Servo 3.x |
| `esp_cam_entrada/` | AI Thinker ESP32-CAM | PubSubClient 2.8 |
| `esp_cam_saida/` | AI Thinker ESP32-CAM | PubSubClient 2.8 |

Compilados sem nenhum warning com o core **esp32 3.0.7** e com o **2.0.17** (Espressif).
O `config.h` é o mesmo nas três pastas: edite um e copie para as outras.

## Contrato com o backend (conferido contra `Back-End/mqtt/broker.py` e `services/orchestractor.py`)

| Quem | Tópico | Payload |
|---|---|---|
| WROOM publica | `parksync/sensor/entrada` / `parksync/sensor/saida` | `DETECTADO` |
| Backend publica, câmeras assinam | `parksync/camera/entrada/acordar` / `.../saida/acordar` | `ACORDA` |
| Backend faz GET | `http://IP_DA_CAM:81/capture` (`PE_PLATE_CAM` / `PS_PLATE_CAM`) | JPEG 800x600 |
| Backend publica, WROOM assina | `parksync/cancela/entrada/comando` / `.../saida/comando` | `ABRIR` |
| Extras do firmware (backend ignora) | `parksync/status/wroom`, `parksync/status/cam_entrada`, `parksync/status/cam_saida` | `online` / `offline` (LWT, retido) |
| | `parksync/cancela/<lado>/estado` | `ABERTA` / `FECHADA` (retido) |
| | `parksync/status/cam_<lado>/url` | `http://IP:81/capture` (retido) |

No backend só mudou a espera pela foto (`_capturar_foto_placa` em `services/orchestractor.py`): 1ª tentativa com até 10 s e mais 2 de 5 s.

## Ligações

### ESP32 WROOM

| Componente | Pino do componente | Liga em |
|---|---|---|
| HC-SR04 entrada | VCC / GND | 5V (VIN) / GND |
| | TRIG | GPIO 13 |
| | ECHO | **GPIO 34** pelo divisor de tensão (antes era o 12) |
| HC-SR04 saída | VCC / GND | 5V (VIN) / GND |
| | TRIG | GPIO 14 |
| | ECHO | GPIO 27 pelo divisor de tensão |
| Servo entrada | sinal (laranja) | GPIO 26 |
| Servo saída | sinal (laranja) | GPIO 25 |
| Servos | V+ (vermelho) / GND (marrom) | 5V de fonte externa / GND **comum** com a ESP32 |

- **Por que saiu do GPIO 12:** é pino de strapping. Se estiver em nível alto no boot, a ESP32 configura a flash para 1,8 V e não liga (ou fica reiniciando). O GPIO 34 é só entrada e serve bem para ECHO.
- **Divisor no ECHO:** o HC-SR04 responde em 5 V e a ESP32 aguenta 3,3 V. `ECHO — 1 kΩ — (pino da ESP32) — 2 kΩ — GND` dá ~3,3 V.
- **Servos:** dois servos puxando da USB derrubam a ESP32 (brownout). Use fonte 5 V separada e ligue os GND juntos.

### ESP32-CAM (AI-Thinker)

- Alimente com 5 V / 2 A no pino 5V (não no 3V3). Fonte fraca = foto preta, reinício ou `camera init failed`.
- Para gravar: FTDI em 5 V, `U0R`↔TX, `U0T`↔RX, **IO0 no GND**, aperte RESET, grave, tire o IO0 do GND e aperte RESET de novo.
- LED vermelho da placa (GPIO 33): **aceso = sem Wi-Fi ou sem MQTT**, apagado = tudo conectado.
- Flash branco (GPIO 4) vem desligado (`USAR_FLASH 0`); na maquete ele costuma refletir na placa.

## Correção de 25/10 (teste com a OV3660)

- `cam_hal: FB-OVF` e 1ª foto de 6-10 s: XCLK em 10 MHz (`CAM_XCLK_MHZ`), qualidade 12, captura só sob pedido (`GRAB_WHEN_EMPTY`) com descarte dos quadros parados, e câmera aquecida (1 quadro a cada 3 s sem pedidos).
- MQTT: conexão com limite de 1,5 s e intervalo crescente (5 s até 60 s); o `/capture` funciona sem MQTT. Client ID usava MAC 000000; agora vem do eFuse.
- `waiting for download` no boot = IO0 ainda no GND. `POWERON_RESET` repetido = fonte fraca.

## Versão 3 (25/10, 2º teste)

- O boot mostra `firmware v3 (25/10)` e o `/status` mostra `"versao"`. Se o ID ainda terminar em `000000`, a placa está com o firmware antigo.
- JPEG cortado (só a parte de cima da imagem) agora é descartado e a câmera tira outro. Qualidade padrão 14.
- `MQTT_BROKER_IP` incompleto (ex.: `192.168.15`) gera aviso no Serial; a câmera segue só com HTTP.

## Testar só o /capture (sem MQTT, sem backend)

Ligue só a ESP32-CAM (IO0 solto do GND) e no PC:
```
curl http://IP_DA_CAM:81/status
curl -o foto1.jpg -w "%{time_total} s\n" http://IP_DA_CAM:81/capture
curl -o foto2.jpg -w "%{time_total} s\n" http://IP_DA_CAM:81/capture
```
No Serial: `Foto N enviada: 800x600, ~20 KB (captura ~200 ms, envio ~100 ms)` e nenhum `FB-OVF`.
Captura > 1 s: troque `CAM_XCLK_MHZ` para 8. Envio > 1 s: Wi-Fi fraco ou fonte instável.

## Checklist de teste no hardware

1. **Mosquitto aceitando a rede.** O Mosquitto 2.x, sem configuração, só aceita conexões do próprio PC. No `mosquitto.conf` coloque:
   ```
   listener 1883 0.0.0.0
   allow_anonymous true
   ```
   Reinicie o serviço e libere a porta 1883 TCP no firewall do Windows. As ESP32 só funcionam em Wi-Fi **2,4 GHz**.
2. **config.h:** SSID, senha e `MQTT_BROKER_IP` = IP do PC (veja com `ipconfig`). Copie para as três pastas.
3. Abra um terminal e deixe rodando (mostra tudo que passa no broker):
   ```
   mosquitto_sub -h IP_DO_PC -v -t "parksync/#"
   ```
4. **Câmera da entrada:** grave, abra o Serial Monitor (115200). Esperado:
   `Sensor: OV2640` (ou OV3660) → `Câmera (entrada) pronta: http://192.168.x.x:81/capture` → `MQTT ... conectado!`.
   No terminal do passo 3 aparece `parksync/status/cam_entrada online`.
   Abra `http://IP:81/capture` no navegador: a foto deve ser do instante atual e a placa precisa estar legível. Se sair de cabeça para baixo, `CAM_VIRAR_VERTICAL 1`.
5. **Câmera da saída:** mesma coisa. Coloque os dois IPs no `.env` do backend (`PE_PLATE_CAM=http://IP:81`, `PS_PLATE_CAM=http://IP:81`), ou ligue `USAR_IP_FIXO 1` no config.h.
6. **WROOM:** grave e abra o Serial Monitor (115200, "Nova linha"). Esperado: `Wi-Fi OK`, `MQTT ... conectado!`, e no terminal `parksync/cancela/entrada/estado FECHADA`.
   - Digite `d`: mostra a distância dos dois sensores. Sem nada na frente, algo acima de 12 cm.
   - Coloque a mão a menos de 10 cm do sensor de entrada: `Carro na ENTRADA` e no terminal `parksync/sensor/entrada DETECTADO` (uma vez só, mesmo deixando a mão parada).
7. **Cancelas sem o backend:**
   ```
   mosquitto_pub -h IP_DO_PC -t parksync/cancela/entrada/comando -m ABRIR
   mosquitto_pub -h IP_DO_PC -t parksync/cancela/saida/comando -m ABRIR
   ```
   A cancela abre devagar e fecha 5 s depois. Com a mão na frente do sensor ela **não fecha**; tire a mão e ela fecha ~1 s depois. Mandar ABRIR de novo com ela aberta reinicia os 5 s.
8. **Câmera sem o backend:** `mosquitto_pub -h IP_DO_PC -t parksync/camera/entrada/acordar -m ACORDA` → Serial da câmera mostra `ACORDA recebido`. `curl -o placa.jpg http://IP:81/capture` salva a foto; `http://IP:81/status` mostra RSSI, memória e contadores.
9. **Tudo junto:** suba o backend e coloque o carrinho na entrada. No log do backend: `MQTT 'parksync/sensor/entrada': DETECTADO` → `ACORDA` → morador/placa → `Abrindo cancela de ENTRADA`. No Serial da câmera: `Foto N enviada: 800x600, ~50 KB em ~100 ms`. No WROOM: `Abrindo cancela de ENTRADA`.

## O que ajustar se precisar

| Sintoma | Ajuste |
|---|---|
| Placa pequena ou borrada no OCR | `CAM_RESOLUCAO FRAMESIZE_XGA`, aproxime a câmera |
| Foto escura / clara demais | `CAM_NIVEL_EXPOSICAO` de -2 a 2 |
| Carro detectado longe ou perto demais | `DISTANCIA_GATILHO_CM` no wroom.ino |
| Cancela mexe ao contrário ou pouco | `ANGULO_FECHADO` / `ANGULO_ABERTO` |
| Cancela rápida ou lenta | `PASSO_SERVO_MS` (0 = instantâneo) |
| ESP32-CAM reinicia sozinha | Fonte 5 V / 2 A, cabo curto |

## Teste automático (opcional, no PC)

`ferramentas/teste_contrato.py` simula as três placas e roda o código real do backend (MQTT, debounce,
ACORDA, GET /capture, ABRIR) com banco/rosto/OCR falsos. Com o Mosquitto rodando no PC:
```
pip install paho-mqtt opencv-python-headless numpy requests python-dotenv
python ferramentas/teste_contrato.py CAMINHO/DO/Back-End CAMINHO/DO/ParkSync-Firmware
```
