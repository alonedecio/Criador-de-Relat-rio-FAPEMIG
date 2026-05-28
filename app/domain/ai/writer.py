"""
Writer — agente responsável por gerar os três campos textuais de cada atividade.

Recebe:
    ContextoProjeto  — contexto estático do projeto (termo de outorga)
    ContextoAtividade — contexto dinâmico da atividade (ClickUp + progresso)

Devolve:
    TextosGerados    — desenvolvimento, resultados, justificativa

A chamada LLM usa dois papéis:
    system: contexto do projeto (cacheável, não muda entre atividades)
    user:   contexto da atividade (muda a cada chamada)
"""
from __future__ import annotations

import json
import logging
from typing import Optional

from app.domain.ai.schemas import TextosGerados
from app.domain.ai.prompts import system_prompt_writer, user_prompt_writer
from app.domain.context.builders import ContextoAtividade
from app.domain.projects.termo_outorga import ContextoProjeto

logger = logging.getLogger(__name__)


class WriterError(Exception):
    """Erro não recuperável do writer (ex: LLM indisponível)."""


class WriterParseError(Exception):
    """Resposta da LLM não pôde ser parseada como JSON válido."""


def _parse_resposta(resposta_raw: str) -> TextosGerados:
    """
    Extrai JSON da resposta bruta da LLM.
    A LLM pode retornar o JSON envolto em markdown (```json ... ```).
    """
    texto = resposta_raw.strip()

    # Remove bloco markdown se presente
    if texto.startswith("```"):
        linhas = texto.splitlines()
        # remove primeira e última linha de markdown
        texto = "\n".join(
            l for l in linhas
            if not l.strip().startswith("```")
        ).strip()

    try:
        data = json.loads(texto)
    except json.JSONDecodeError as e:
        raise WriterParseError(f"JSON inválido na resposta do writer: {e}\nResposta: {texto[:300]}")

    campos_obrigatorios = {"desenvolvimento", "resultados", "justificativa"}
    faltando = campos_obrigatorios - set(data.keys())
    if faltando:
        raise WriterParseError(f"Campos obrigatórios ausentes: {faltando}")

    return TextosGerados(
        desenvolvimento=str(data.get("desenvolvimento", "")).strip(),
        resultados=str(data.get("resultados", "")).strip(),
        justificativa=str(data.get("justificativa", "")).strip(),
    )


def gerar_textos(
    ctx_projeto: ContextoProjeto,
    ctx_atividade: ContextoAtividade,
    llm_client,
    model: str = "gpt-4o",
) -> TextosGerados:
    """
    Gera os textos de desenvolvimento, resultados e justificativa
    para uma atividade usando a LLM configurada.

    Args:
        ctx_projeto:   ContextoProjeto extraído do termo de outorga.
        ctx_atividade: ContextoAtividade montado pelo builder.
        llm_client:    Cliente LLM compatível com interface OpenAI
                       (openai.OpenAI, litellm, etc.).
        model:         Identificador do modelo a usar.

    Returns:
        TextosGerados com os três campos preenchidos.

    Raises:
        WriterError:      falha de comunicação com a LLM.
        WriterParseError: resposta da LLM em formato inesperado.
    """
    sys_prompt = system_prompt_writer(ctx_projeto)
    usr_prompt = user_prompt_writer(ctx_atividade)

    logger.debug(
        "Writer: gerando textos para atividade %s (%s)",
        ctx_atividade.codigo,
        ctx_atividade.titulo[:60],
    )

    try:
        response = llm_client.chat.completions.create(
            model=model,
            temperature=0.3,
            messages=[
                {"role": "system", "content": sys_prompt},
                {"role": "user",   "content": usr_prompt},
            ],
            response_format={"type": "json_object"},
        )
        resposta_raw = response.choices[0].message.content or ""
    except Exception as e:
        raise WriterError(f"Falha ao chamar LLM para atividade {ctx_atividade.codigo}: {e}") from e

    return _parse_resposta(resposta_raw)
