"""
Utilitários de placa Mercosul (formato LLLNLNN, ex: ABC1D23).

Por que este módulo existe:
- O projeto padronizou TODAS as placas (moradores, visitantes e leitura das
  câmeras) no formato Mercosul. Antes, cada ponto de entrada tratava a placa de
  um jeito (ou não tratava), então a mesma placa podia aparecer como "ABC-1D23"
  no cadastro e "ABC1D23" no OCR, e a comparação no orchestrator nunca batia.
- Centralizar aqui garante que schemas.py (cadastros) e plate_service.py (OCR)
  usem exatamente a mesma regra.

Duas funções, com propósitos diferentes:
- validar_placa_mercosul(): ESTRITA. Usada nos cadastros manuais. Não "conserta"
  nada: se o usuário digitou errado, deve corrigir em vez de o sistema adivinhar.
- normalizar_placa_ocr(): TOLERANTE. Usada na leitura das câmeras. O OCR confunde
  letras e números parecidos (O/0, I/1, B/8...), e como a placa Mercosul tem
  posições fixas de letra e número, dá para corrigir essas confusões.
"""
import re
from typing import Optional

PADRAO_MERCOSUL = re.compile(r'^[A-Z]{3}[0-9][A-Z][0-9]{2}$')

# Tipo esperado em cada uma das 7 posições: L = letra, N = número
_TIPOS_POSICAO = ['L', 'L', 'L', 'N', 'L', 'N', 'N']

# Confusões visuais mais comuns do OCR
_LETRA_PARA_NUMERO = {'O': '0', 'Q': '0', 'I': '1', 'L': '1', 'B': '8', 'S': '5', 'Z': '2', 'G': '6'}
_NUMERO_PARA_LETRA = {'0': 'O', '1': 'I', '8': 'B', '5': 'S', '2': 'Z', '6': 'G'}


def _limpar(texto: str) -> str:
    """Remove hífen, espaços e símbolos; deixa maiúsculo."""
    return re.sub(r'[^A-Z0-9]', '', (texto or '').upper())


def validar_placa_mercosul(texto: str) -> Optional[str]:
    """
    Versão ESTRITA (cadastros). Retorna a placa limpa se já estiver no padrão
    Mercosul; caso contrário retorna None. Não corrige caracteres.
    """
    limpo = _limpar(texto)
    return limpo if PADRAO_MERCOSUL.match(limpo) else None


def _corrigir_posicoes(sete_caracteres: str) -> Optional[str]:
    """Aplica a correção posicional em exatamente 7 caracteres."""
    corrigido = []
    for caractere, tipo in zip(sete_caracteres, _TIPOS_POSICAO):
        if tipo == 'L' and caractere.isdigit():
            caractere = _NUMERO_PARA_LETRA.get(caractere, caractere)
        elif tipo == 'N' and caractere.isalpha():
            caractere = _LETRA_PARA_NUMERO.get(caractere, caractere)
        corrigido.append(caractere)

    resultado = ''.join(corrigido)
    return resultado if PADRAO_MERCOSUL.match(resultado) else None


def normalizar_placa_ocr(texto: str) -> Optional[str]:
    """
    Versão TOLERANTE (OCR). Recebe o texto bruto lido pela câmera, que pode ter
    ruído antes/depois da placa, e devolve a placa Mercosul ou None.

    Por que testar janelas de 7 caracteres: o código antigo pegava sempre os
    "últimos 7" caracteres, o que corta a placa certa se o ruído vier no final.
    Aqui testamos todas as janelas e devolvemos a primeira que forma uma placa
    válida.
    """
    limpo = _limpar(texto)
    if len(limpo) < 7:
        return None

    for inicio in range(len(limpo) - 6):
        candidato = _corrigir_posicoes(limpo[inicio:inicio + 7])
        if candidato:
            return candidato
    return None