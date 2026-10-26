# Arquivo: Back-End/utils/config.py
#
# Lê TODAS as variáveis de ambiente do projeto num só lugar.
# Nenhuma variável ausente derruba a API: cada uma tem um valor padrão e,
# quando falta algo importante, aparece um aviso claro no terminal.

import os
from dotenv import load_dotenv

load_dotenv()

_avisos = []


def _texto(nome, padrao=None, obrigatoria=False, alternativas=()):
    """Lê uma variável de texto. 'alternativas' são nomes antigos aceitos."""
    for chave in (nome, *alternativas):
        valor = os.getenv(chave)
        if valor is not None and valor.strip() != "":
            return valor.strip().strip('"').strip("'")
    if obrigatoria:
        _avisos.append(f"{nome} não definida no .env (usando padrão: {padrao!r})")
    return padrao


def _inteiro(nome, padrao, alternativas=()):
    valor = _texto(nome, None, alternativas=alternativas)
    if valor is None:
        return padrao
    try:
        return int(valor)
    except ValueError:
        _avisos.append(f"{nome}={valor!r} não é um número inteiro (usando {padrao})")
        return padrao


def _decimal(nome, padrao, alternativas=()):
    valor = _texto(nome, None, alternativas=alternativas)
    if valor is None:
        return padrao
    try:
        return float(valor.replace(",", "."))
    except ValueError:
        _avisos.append(f"{nome}={valor!r} não é um número (usando {padrao})")
        return padrao


def _booleano(nome, padrao):
    valor = _texto(nome, None)
    if valor is None:
        return padrao
    return valor.lower() in ("1", "true", "sim", "yes", "on")


def camera(valor):
    """'0' -> 0 (webcam USB), 'http://...' -> URL (ESP32-CAM)."""
    if valor is None:
        return None
    valor = str(valor).strip()
    return int(valor) if valor.isdigit() else valor


# ================= BANCO DE DADOS =================
DATABASE_URL = _texto("DATABASE_URL")  # opcional: sobrescreve tudo abaixo (ex.: sqlite:///teste.db)
DB_HOST = _texto("DB_HOST", "localhost", obrigatoria=DATABASE_URL is None)
DB_USER = _texto("DB_USER", "root", obrigatoria=DATABASE_URL is None)
DB_PASSWORD = _texto("DB_PASSWORD", "")
DB_PORT = _inteiro("DB_PORT", 3306)
DB_NAME = _texto("DB_NAME", "parksync", obrigatoria=DATABASE_URL is None)

# ================= SEGURANÇA (JWT) =================
JWT_SECRET = _texto("JWT_SECRET")
JWT_EXPIRA_MINUTOS = _inteiro("JWT_EXPIRA_MINUTOS", 60 * 24 * 7)  # 1 semana
# false = o app atual (que ainda não manda o token) continua funcionando.
# true  = rotas do morador só respondem com "Authorization: Bearer <token>".
EXIGIR_TOKEN = _booleano("EXIGIR_TOKEN", False)
# Chave opcional para as rotas da portaria (abrir cancela manual, simular sensor, mapear vagas).
PORTARIA_API_KEY = _texto("PORTARIA_API_KEY")

# ================= CÂMERAS =================
# Uma única webcam faz o reconhecimento facial na entrada E na saída.
FACE_CAM = camera(_texto("FACE_CAM", "0", obrigatoria=True, alternativas=("PE_FACE_CAM", "PS_FACE_CAM")))
# ESP32-CAM de cada lado. Ex.: http://192.168.1.50:81  (o /capture é adicionado sozinho)
PE_PLATE_CAM = camera(_texto("PE_PLATE_CAM", None, obrigatoria=True))
PS_PLATE_CAM = camera(_texto("PS_PLATE_CAM", None, obrigatoria=True))
# Webcam apontada para as vagas
PM_PARK_CAM = camera(_texto("PM_PARK_CAM", "1", obrigatoria=True))

# ================= RECONHECIMENTO / VISÃO =================
FACIAL_THRESHOLD = _decimal("FACIAL_THRESHOLD", 0.5)
TEMPO_BUSCA_ROSTO = _decimal("TEMPO_BUSCA_ROSTO", 4.0)
# % de pixels diferentes do fundo vazio para considerar a vaga ocupada
OCUPACAO_PERCENTUAL = _decimal("OCUPACAO_PERCENTUAL", 15.0, alternativas=("LAPLACIAN_THRESHOLD",))
TEMPO_CONFIRMA_VAGA = _decimal("TEMPO_CONFIRMA_VAGA", 5.0)
# Tamanho da tela de desenho do vagas.html (as coordenadas chegam nessa escala)
FRONT_LARGURA = _inteiro("FRONT_LARGURA", 800)
FRONT_ALTURA = _inteiro("FRONT_ALTURA", 600)
MONITORAR_VAGAS = _booleano("MONITORAR_VAGAS", True)

# ================= REGRAS DE ACESSO =================
# Morador reconhecido chegando com carro que não é dele (ex.: carro emprestado).
PERMITIR_VEICULO_TEMPORARIO = _booleano("PERMITIR_VEICULO_TEMPORARIO", True)

# ================= MQTT =================
MQTT_IP = _texto("MQTT_IP", "127.0.0.1", obrigatoria=True, alternativas=("MQTT_HOST",))
MQTT_PORT = _inteiro("MQTT_PORT", 1883)
MQTT_TIMEOUT = _inteiro("MQTT_TIMEOUT", 60)
MQTT_USER = _texto("MQTT_USER")
MQTT_PASSWORD = _texto("MQTT_PASSWORD")

# ================= PASTAS =================
PASTA_CAPTURAS = _texto("PASTA_CAPTURAS", os.path.join("armazenamento", "capturas"))


def mostrar_avisos():
    """Imprime no terminal tudo que está faltando ou inválido no .env."""
    if not _avisos:
        print("✅ .env carregado sem pendências.")
        return
    print("⚠️  Atenção às configurações do .env:")
    for aviso in _avisos:
        print(f"   - {aviso}")
    if PE_PLATE_CAM is None or PS_PLATE_CAM is None:
        print("   -> Sem PE_PLATE_CAM/PS_PLATE_CAM a leitura de placa fica desativada (a API sobe mesmo assim).")
