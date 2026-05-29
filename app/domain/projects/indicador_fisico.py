"""
Extrator de indicadores físicos do Termo de Outorga.

O indicador físico é definido no plano de trabalho para cada atividade
(ex: 'Equipe contratada formalmente (contratos assinados)').

Estratégia:
  1. Tenta extrair do PDF indexado via regex/busca por código da atividade.
  2. Se não encontrar, retorna None — o campo ficará em branco no relatório.
     (não inventamos indicadores não documentados)
"""
from __future__ import annotations

import re
from typing import Optional


# Padrão para localizar blocos de atividade no texto do PDF
# Ex: "1.1", "2.3", "10.5"
_RE_CODIGO = re.compile(
    r"(?:^|\s)(\d{1,2}\.\d{1,2})\s",
    re.MULTILINE,
)

# Palavras-chave que tipicamente precedem o indicador físico no texto do PDF
_PALAVRAS_INDICADOR = [
    "indicador físico",
    "indicador de execução",
    "indicador físico de execução",
    "comprovação",
    "evidência",
]


def extrair_indicador_fisico(
    pdf_texto: str,
    codigo_atividade: str,
) -> Optional[str]:
    """
    Tenta extrair o indicador físico de uma atividade a partir do
    texto completo do PDF do Termo de Outorga.

    Args:
        pdf_texto:         Texto completo do PDF (string).
        codigo_atividade:  Código no formato '1.1', '2.3', etc.

    Returns:
        String com o indicador físico, ou None se não encontrado.
    """
    if not pdf_texto or not codigo_atividade:
        return None

    # Escapa pontos para uso em regex
    codigo_escaped = re.escape(codigo_atividade.strip())

    # Localiza o bloco de texto que começa com o código da atividade
    # Captura até 600 caracteres após o código
    padrao_bloco = re.compile(
        rf"(?:^|\s){codigo_escaped}[\s\t]+(.{{20,600}}?)(?=\d{{1,2}}\.\d{{1,2}}[\s\t]|$)",
        re.DOTALL | re.MULTILINE,
    )
    match = padrao_bloco.search(pdf_texto)
    if not match:
        return None

    bloco = match.group(1)

    # Dentro do bloco, tenta encontrar o indicador por palavra-chave
    for palavra in _PALAVRAS_INDICADOR:
        idx = bloco.lower().find(palavra)
        if idx != -1:
            # Pega o texto após a palavra-chave, até ponto final ou quebra dupla
            trecho = bloco[idx + len(palavra):].strip().lstrip(":").strip()
            # Limpa até ponto final ou 200 chars
            fim = re.search(r"[\.\n]{1}", trecho)
            if fim:
                trecho = trecho[: fim.start()].strip()
            if trecho and len(trecho) > 10:
                return trecho

    # Fallback: se não achou por palavra-chave, tenta a segunda sentença do bloco
    # (estrutura comum: [título da atividade]. [indicador físico]. [período].)
    sentencas = re.split(r"(?<=[.!?])\s+", bloco.strip())
    if len(sentencas) >= 2:
        candidato = sentencas[1].strip()
        if 15 < len(candidato) < 300:
            return candidato

    return None


def enriquecer_atividades_com_indicador(
    relatorio: dict,
    pdf_texto: str,
) -> dict:
    """
    Percorre todas as atividades do relatório e preenche o campo
    'indicador_fisico' a partir do texto do PDF, quando disponível.

    Se o campo já existir e não estiver vazio, não sobrescreve.

    Args:
        relatorio: dict do relatório canônico.
        pdf_texto: texto completo do PDF do Termo de Outorga.

    Returns:
        Relatório com campo 'indicador_fisico' preenchido onde possível.
    """
    for meta in relatorio.get("metas", []) + relatorio.get("itens", []):
        for atv in meta.get("atividades", []):
            # Não sobrescreve se já preenchido
            if atv.get("indicador_fisico"):
                continue

            codigo = (
                atv.get("numero_atividade_original")
                or atv.get("numero_atividade")
                or atv.get("codigo")
                or ""
            )
            indicador = extrair_indicador_fisico(pdf_texto, codigo)
            atv["indicador_fisico"] = indicador or ""

    return relatorio
