# 📖 O Projeto: Redefinindo a Automação Condominial

A gestão de acessos em condomínios residenciais parou no tempo. Enquanto a tecnologia avança, a segurança patrimonial ainda confia em processos analógicos ou sistemas digitais engessados que geram atrito, lentidão e brechas de segurança. O **ParkSync** nasceu para resolver essa defasagem, entregando um ecossistema inteligente, autônomo e altamente reativo.

### 🛑 Os Problemas do Modelo Atual

Condomínios modernos enfrentam três grandes gargalos diários:

1. **Vulnerabilidade de Tags e Controles:** O uso de tags RFID ou controles de portão tradicionais não autentica o motorista, apenas o objeto. Controles clonados ou roubados dão acesso livre a invasores sem levantar suspeitas.
2. **Fricção e Erro Humano na Portaria:** O cadastro manual de visitantes e a verificação visual de quem entra e sai dependem inteiramente da atenção do porteiro. Isso gera filas em horários de pico e falhas graves de auditoria em caso de incidentes.
3. **Caos no Pátio de Estacionamento:** O uso indevido de vagas (moradores estacionando em vagas de terceiros) é uma das maiores causas de atritos em assembleias. A verificação hoje é feita no "boca a boca" ou por rondas ineficientes.

### 💡 A Solução ParkSync

O ParkSync substitui a confiança cega em objetos físicos pela **autenticação biométrica infalível** e pela **visão computacional avançada**, criando uma barreira invisível, porém intransponível, para não autorizados, e fluida para os moradores.

* **Fim da Clonagem (Biometria Soberana):** Seu rosto é a sua chave. Com processamento de 128 pontos faciais em frações de segundo, o sistema sabe exatamente quem está ao volante. Se o morador trocar de carro ou usar um veículo de aluguel, o sistema reconhece o rosto, autoriza a entrada e cadastra o veículo temporariamente, evitando travamentos e burocracia.
* **Auditoria Imutável de Visitantes:** Acabou a prancheta de papel. Visitantes pré-aprovados pelo App do morador são reconhecidos pela placa (LPR) via IA. No momento do acesso, o sistema exige e captura um *snapshot* fotográfico do rosto do condutor, gerando um registro imutável no banco de dados.
* **Gestão Autônoma de Vagas (Smart Parking):** Câmeras aéreas monitoram as vagas mapeadas do pátio. Utilizando redes neurais (YOLOv8) e OCR de alta precisão, o sistema sabe não apenas se a vaga está ocupada, mas *quem* está nela. Ocupou a vaga do vizinho? O painel da guarita acusa conflito imediatamente, antes mesmo de gerar uma reclamação.

### 🚀 Por que o ParkSync?

Não construímos apenas uma "catraca eletrônica", mas um **orquestrador de segurança**. Integrando Edge Computing via dispositivos IoT (ESP32) com um Backend robusto e assíncrono em Python, o ParkSync garante que o processamento pesado de IA ocorra localmente, sem depender de internet para abrir a cancela, garantindo latência zero. 

É a transformação da portaria passiva em uma central de inteligência ativa, onde a segurança é máxima e a intervenção humana é necessária apenas quando há anomalias reais.