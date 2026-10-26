# Arquivo: Back-End/utils/eventos.py
#
# Envia eventos em tempo real para o painel do porteiro (WebSocket /ws/portaria).
# Pode ser chamado de qualquer thread (orquestrador, monitor de vagas) sem
# precisar fazer requests.post para a própria API.

import asyncio
from typing import Optional
from fastapi import WebSocket


class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []
        self.loop: Optional[asyncio.AbstractEventLoop] = None

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        for connection in list(self.active_connections):
            try:
                await connection.send_json(message)
            except Exception:
                self.disconnect(connection)


manager = ConnectionManager()


def registrar_loop(loop: asyncio.AbstractEventLoop):
    """Chamado no startup da API para as threads saberem onde mandar os eventos."""
    manager.loop = loop


def notificar_painel(evento: str, **dados):
    """
    Eventos que o porteiro.html entende:
      ATUALIZACAO_VAGAS, NOVO_ACESSO, NOVO_ALERTA,
      IMAGEM_CAPTURADA (camera="PLACA"|"ROSTO", base64="...")
    """
    if manager.loop is None or not manager.active_connections:
        return
    mensagem = {"evento": evento, **dados}
    try:
        asyncio.run_coroutine_threadsafe(manager.broadcast(mensagem), manager.loop)
    except RuntimeError:
        pass  # loop encerrado (API desligando)
