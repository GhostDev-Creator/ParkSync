import re
from typing import Optional

PADRAO_MERCOSUL = re.compile(r'^[A-Z]{3}[0-9][A-Z][0-9]{2}$')

_TIPOS_POSICAO = ['L', 'L', 'L', 'N', 'L', 'N', 'N']
_LETRA_PARA_NUMERO = {'O': '0', 'Q': '0', 'I': '1', 'L': '1', 'B': '8', 'S': '5', 'Z': '2', 'G': '6'}
_NUMERO_PARA_LETRA = {'0': 'O', '1': 'I', '8': 'B', '5': 'S', '2': 'Z', '6': 'G'}

def _limpar(texto: str) -> str:
    """Remove palavras de OCR sujo da tarja Mercosul, hífen e símbolos."""
    texto = (texto or '').upper()
    texto = re.sub(r'(BRASIL|MERCOSUL|BR)', '', texto)
    return re.sub(r'[^A-Z0-9]', '', texto)

def validar_placa_mercosul(texto: str) -> Optional[str]:
    limpo = _limpar(texto)
    return limpo if PADRAO_MERCOSUL.match(limpo) else None

def _corrigir_posicoes(sete_caracteres: str) -> Optional[str]:
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
    limpo = _limpar(texto)
    if len(limpo) < 7: return None
    for inicio in range(len(limpo) - 6):
        candidato = _corrigir_posicoes(limpo[inicio:inicio + 7])
        if candidato: return candidato
    return None