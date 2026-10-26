"""Teste de contrato: firmware (simulado) <-> backend real (mqtt/broker.py + orchestractor.py).

Os tópicos/payloads do lado do firmware são lidos do config.h entregue, não digitados aqui.
O banco, rosto e OCR são substituídos por stubs; o resto (MQTT, debounce, ACORDA, GET /capture,
decodificação do JPEG, ABRIR) é o código real do backend.
"""
import os, re, sys, time, types, threading, http.server
import cv2, numpy as np
import paho.mqtt.client as mqtt

BACKEND, FIRMWARE = sys.argv[1], sys.argv[2]
cfg = open(os.path.join(FIRMWARE, "wroom", "config.h"), encoding="utf-8").read()
H = dict(re.findall(r'#define\s+(\w+)\s+"([^"]*)"', cfg))

# ---------- câmeras falsas (HTTP /capture como a ESP32-CAM) ----------
pedidos = {"entrada": [], "saida": []}
def servidor(lado, porta):
    img = np.full((600, 800, 3), 255, np.uint8)
    cv2.putText(img, "ABC1D23", (150, 330), cv2.FONT_HERSHEY_SIMPLEX, 3, (0, 0, 0), 8)
    jpg = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 90])[1].tobytes()
    class H_(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            pedidos[lado].append((self.path, time.time()))
            if self.path != "/capture":
                self.send_response(404); self.end_headers(); return
            self.send_response(200); self.send_header("Content-Type", "image/jpeg")
            self.send_header("Content-Length", str(len(jpg))); self.end_headers(); self.wfile.write(jpg)
        def log_message(self, *a): pass
    s = http.server.ThreadingHTTPServer(("127.0.0.1", porta), H_)
    threading.Thread(target=s.serve_forever, daemon=True).start()
servidor("entrada", 18081); servidor("saida", 18082)

os.environ.update(MQTT_IP="127.0.0.1", MQTT_PORT="1883",
                  PE_PLATE_CAM="http://127.0.0.1:18081", PS_PLATE_CAM="http://127.0.0.1:18082",
                  FACE_CAM="0", PM_PARK_CAM="1")

# ---------- stubs das partes pesadas do backend ----------
sys.path.insert(0, BACKEND)
def stub(nome, **attrs):
    m = types.ModuleType(nome); m.__dict__.update(attrs); sys.modules[nome] = m
class _Qualquer:
    def __getattr__(self, k): return _Qualquer()
    def __call__(self, *a, **k): return _Qualquer()
    def __enter__(self): return self
    def __exit__(self, *a): return False
stub("database.setup_db", SessionLocal=_Qualquer())
stub("database.models", **{n: _Qualquer() for n in "LogAcesso VeiculoTemporario AgendamentoVisita AlertaPainel Veiculo DirecaoEnum TipoAcessoEnum StatusTemporarioEnum".split()})
stub("services.face_service", identificar_morador=lambda *a: None, abrir_camera=lambda *a: None)
tamanhos = []
def ocr_falso(frame):
    tamanhos.append(frame.shape); return "ABC1D23"
stub("services.plate_service", extrair_placa_de_recorte=ocr_falso)
stub("utils.eventos", notificar_painel=lambda *a, **k: None)

from utils import config
import services.orchestractor as orq

def fluxo(lado):
    def f(db):
        cam = config.PE_PLATE_CAM if lado == "entrada" else config.PS_PLATE_CAM
        frame, placa = orq._ler_placa(cam)            # código real: sleep 0.4, GET /capture, imdecode
        assert placa == "ABC1D23", "OCR stub não recebeu a imagem"
        orq._abrir_cancela(lado)                       # código real: publica ABRIR
    return f
orq._processar_entrada = fluxo("entrada")
orq._processar_saida = fluxo("saida")

# ---------- firmware falso via MQTT (tópicos do config.h) ----------
recebido = []
def on_msg(c, u, m): recebido.append((m.topic, m.payload.decode(), time.time()))

wroom = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="parksync-wroom-TESTE")
wroom.will_set(H["TOPICO_STATUS_BASE"] + "wroom", "offline", qos=1, retain=True)
wroom.on_message = on_msg
wroom.connect("127.0.0.1", 1883, keepalive=15)
wroom.subscribe([(H["TOPICO_CANCELA_ENTRADA"], 1), (H["TOPICO_CANCELA_SAIDA"], 1)])
wroom.loop_start()

cams = []
for lado, top in (("entrada", H["TOPICO_ACORDAR_ENTRADA"]), ("saida", H["TOPICO_ACORDAR_SAIDA"])):
    c = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=f"parksync-cam-{lado}-TESTE")
    c.on_message = on_msg; c.connect("127.0.0.1", 1883, keepalive=15); c.subscribe(top, 1); c.loop_start()
    cams.append(c)

orq.iniciar_orquestrador()
for _ in range(50):
    if orq.broker.conectado: break
    time.sleep(0.1)
time.sleep(0.5)

ok = True
def checar(cond, texto):
    global ok
    print(("✅ " if cond else "❌ ") + texto); ok &= bool(cond)

for lado in ("entrada", "saida"):
    recebido.clear(); n0 = len(pedidos[lado])
    t0 = time.time()
    wroom.publish(H["TOPICO_SENSOR_" + lado.upper()], H["PAYLOAD_DETECTADO"])
    # repetição dentro do debounce de 3 s (o firmware também tem cooldown, isto prova o backend)
    time.sleep(0.2); wroom.publish(H["TOPICO_SENSOR_" + lado.upper()], H["PAYLOAD_DETECTADO"])
    time.sleep(3)
    acordar = [r for r in recebido if r[0] == H["TOPICO_ACORDAR_" + lado.upper()]]
    abrir = [r for r in recebido if r[0] == H["TOPICO_CANCELA_" + lado.upper()]]
    outros = [r for r in recebido if r not in acordar and r not in abrir]
    checar(len(acordar) == 1 and acordar[0][1] == H["PAYLOAD_ACORDA"],
           f"[{lado}] câmera recebeu 1x '{H['PAYLOAD_ACORDA']}' em {H['TOPICO_ACORDAR_' + lado.upper()]} ({len(acordar)} recebidas)")
    novos = pedidos[lado][n0:]
    checar(len(novos) == 1 and novos[0][0] == "/capture",
           f"[{lado}] backend fez GET /capture na porta da câmera certa {[p for p, _ in novos]}")
    if acordar and novos:
        checar(novos[0][1] > acordar[0][2], f"[{lado}] GET chegou {1000*(novos[0][1]-acordar[0][2]):.0f} ms depois do ACORDA")
    checar(len(abrir) == 1 and abrir[0][1].strip().upper() == H["PAYLOAD_ABRIR"],
           f"[{lado}] WROOM recebeu '{abrir[0][1] if abrir else None}' em {H['TOPICO_CANCELA_' + lado.upper()]} "
           f"({(abrir[0][2]-t0):.2f} s após o DETECTADO)" if abrir else f"[{lado}] WROOM não recebeu ABRIR")
    checar(not outros, f"[{lado}] nenhuma mensagem em tópico inesperado {outros}")

checar(tamanhos and tamanhos[0] == (600, 800, 3), f"JPEG SVGA decodificado pelo backend: {tamanhos[:1]}")
print("RESULTADO:", "PASSOU" if ok else "FALHOU")
sys.exit(0 if ok else 1)
