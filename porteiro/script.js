// ==========================================
// 🕒 CONTROLE DE DATA E HORA
// ==========================================
function atualizarRelogio() {
    const elementoRelogio = document.getElementById('current-time'); // Garanta que no HTML tem um id="current-time"
    if (elementoRelogio) {
        const agora = new Date();
        const opcoesData = { day: '2-digit', month: '2-digit', year: 'numeric' };
        const opcoesHora = { hour: '2-digit', minute: '2-digit', second: '2-digit' };
        
        const dataFormatada = agora.toLocaleDateString('pt-BR', opcoesData);
        const horaFormatada = agora.toLocaleTimeString('pt-BR', opcoesHora);
        
        elementoRelogio.textContent = `${dataFormatada} - ${horaFormatada}`;
    }
}
setInterval(atualizarRelogio, 1000);
atualizarRelogio();

// ==========================================
// 📡 CONEXÃO WEBSOCKET E STATUS
// ==========================================
let ws;
const wsStatusText = document.getElementById('ws-status-text'); 
const wsStatusBadge = document.getElementById("websocket-status"); // A div ou span principal que envolve o texto

function conectarWebSocket() {
    // Altere para o IP do seu servidor de produção quando for a hora
    ws = new WebSocket(`ws://127.0.0.1:8000/ws/portaria`);

    ws.onopen = () => {
        if(wsStatusText && wsStatusBadge) {
            wsStatusText.textContent = "Servidor Online";
            
            // Remove a classe de erro e adiciona a classe de sucesso
            wsStatusBadge.classList.remove("ws-disconnected");
            wsStatusBadge.classList.add("ws-connected");
        }
        carregarDadosIniciais(); // Busca o histórico ao reconectar
    };

    ws.onclose = () => {
        if(wsStatusText && wsStatusBadge) {
            wsStatusText.textContent = "Servidor Offline - Reconectando...";
            
            // Remove a classe de sucesso e adiciona a classe de erro
            wsStatusBadge.classList.remove("ws-connected");
            wsStatusBadge.classList.add("ws-disconnected");
        }
        setTimeout(conectarWebSocket, 3000); // Tenta reconectar a cada 3s
    };

    ws.onmessage = (event) => {
        const dados = JSON.parse(event.data);
        processarMensagemTempoReal(dados);
    };
}
conectarWebSocket();

// ==========================================
// 🔄 CARREGAMENTO INICIAL (REST API)
// ==========================================
async function carregarDadosIniciais() {
    try {
        const response = await fetch('http://127.0.0.1:8000/api/portaria/iniciar-dados');
        const dados = await response.json();

        renderizarHistorico(dados.historico);
        renderizarAlertas(dados.alertas);
        renderizarVagas(dados.vagas);
    } catch (error) {
        console.error("Erro ao buscar dados iniciais:", error);
    }
}

// ==========================================
// 🛠️ RENDERIZAÇÃO DOS CARDS
// ==========================================

function renderizarHistorico(historicoList) {
    const container = document.getElementById('acess-history');
    if (!container) return;
    
    container.innerHTML = ''; // Limpa a div

    historicoList.forEach(log => {
        // Define a cor da borda baseada no tipo (Entrada/Saída/Negado)
        let borderCor = log.tipo.includes("NEGADO") ? "border-left: 4px solid red;" : "border-left: 4px solid green;";
        
        const card = `
            <div style="padding: 10px; margin-bottom: 10px; background: #0f172a; border-radius: 5px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); ${borderCor}">
                <strong>${log.tipo.replace('_', ' ')}</strong><br>
                <small style="color: #666;">${log.data_hora}</small><br>
                <span>Placa: <b>${log.placa}</b></span>
            </div>
        `;
        container.innerHTML += card;
    });
}

function renderizarAlertas(alertasList) {
    const container = document.getElementById('alerts-list');
    if (!container) return;
    
    if (alertasList.length === 0) {
        container.innerHTML = `<div class="empty-state"><i class="ri-notification-3-line"></i><p>Nenhum alerta ativo</p></div>`;
        return;
    }

    container.innerHTML = '';
    alertasList.forEach(alerta => {
        // Alertas de Invasão (Vermelho), Alertas de Intervenção/Vagas (Laranja)
        let bgCor = alerta.tipo.includes("INVASAO") ? "#0f172a" : "#0f172a";
        let iconCor = alerta.tipo.includes("INVASAO") ? "#d32f2f" : "#e65100";
        
        const card = `
            <div style="background: ${bgCor}; border: 1px solid ${iconCor}; padding: 12px; margin-bottom: 10px; border-radius: 5px;">
                <div style="color: ${iconCor}; font-weight: bold; margin-bottom: 5px;">
                    <i class="ri-alert-fill"></i> ${alerta.tipo.replace('_', ' ')}
                </div>
                <p style="margin: 0; font-size: 14px;">${alerta.descricao}</p>
                <small style="color: #666; margin-top: 5px; display: block;">${alerta.data_hora}</small>
            </div>
        `;
        container.innerHTML += card;
    });
}

function renderizarVagas(vagasList) {
    const container = document.getElementById('parking-spots');
    const summary = document.getElementById('parking-summary');
    if (!container) return;

    container.innerHTML = '';
    let ocupadas = 0;
    let conflitos = 0;

    vagasList.forEach(vaga => {
        let corStatus = "var(--color-success, #28a745)"; // Verde (Livre)
        let textoStatus = "LIVRE";
        
        if (vaga.conflito) {
            corStatus = "var(--color-danger, #dc3545)"; // Vermelho (Invasão)
            textoStatus = "CONFLITO!";
            conflitos++;
        } else if (vaga.ocupada) {
            corStatus = "var(--color-warning, #ffc107)"; // Amarelo (Ocupada corretamente)
            textoStatus = "OCUPADA";
            ocupadas++;
        }

        const infoVeiculo = vaga.ocupada ? `<br><small>Placa Atual: <b>${vaga.placa_atual || 'Lendo...'}</b></small>` : '';

        const card = `
            <div style="border-left: 5px solid ${corStatus}; padding: 10px; margin-bottom: 10px; background: #0f172a; border-radius: 4px;">
                <div style="display: flex; justify-content: space-between;">
                    <strong>Vaga ${vaga.numero}</strong>
                    <span style="color: ${corStatus}; font-size: 12px; font-weight: bold;">${textoStatus}</span>
                </div>
                <div style="font-size: 13px; color: #0f172a; margin-top: 5px;">
                    Proprietário: ${vaga.dono_nome} (${vaga.dono_apt})
                    ${infoVeiculo}
                </div>
            </div>
        `;
        container.innerHTML += card;
    });

    if(summary) {
        summary.innerHTML = `Vagas Cadastradas: <b>${vagasList.length}</b> | Ocupadas: <b>${ocupadas}</b> | Conflitos: <b>${conflitos}</b>`;
    }
}

// ==========================================
// 🚀 PROCESSAR EVENTOS EM TEMPO REAL (WEBSOCKET)
// ==========================================
function processarMensagemTempoReal(dados) {
    // Essa função será chamada automaticamente quando o backend enviar um JSON
    
    if (dados.evento === "ATUALIZACAO_VAGAS") {
        carregarDadosIniciais(); // Recarrega os dados para simplificar (Poderia atualizar só 1 card)
    } 
    else if (dados.evento === "NOVO_ALERTA") {
        carregarDadosIniciais(); // Toca som e atualiza tela
        tocarSomAlerta();
    }
    else if (dados.evento === "NOVO_ACESSO") {
        carregarDadosIniciais();
    }
    else if (dados.evento === "IMAGEM_CANCELA") {
        // Exemplo: Substituir a imagem da div box-content
        const boxPlaca = document.getElementById('box-content-placa');
        if(boxPlaca && dados.tipo === "PLACA") {
            // O backend manda a URL da foto salva no base64
            boxPlaca.style.backgroundImage = `url('data:image/jpeg;base64,${dados.imagemBase64}')`;
            boxPlaca.style.backgroundSize = "cover";
            boxPlaca.style.backgroundPosition = "center";
        }
    }
}

function tocarSomAlerta() {
    // Se quiser, adicione um arquivo de audio no html e toque ele aqui
    // const audio = new Audio('alerta.mp3'); audio.play();
    console.log("🚨 BEEP BEEP BEEP!");
}