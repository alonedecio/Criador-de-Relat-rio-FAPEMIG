"""
Writer — agente responsável por gerar os três campos textuais de cada atividade.

Recebe:
    ContextoProjeto   — contexto estático do projeto (termo de outorga)
    ContextoAtividade — contexto dinâmico da atividade (ClickUp + progresso)

Devolve:
    TextosGerados     — desenvolvimento, resultados, justificativa

A chamada LLM usa dois papéis:
    system: contexto do projeto (cacheável, não muda entre atividades)
    user:   contexto da atividade (muda a cada chamada)

Arquitetura LLM:
    Recebe llm_client já instanciado (openai.OpenAI apontando para Gemini
    via base_url, ou openai.OpenAI padrão). Não instancia nem importa
    nenhuma lib de LLM diretamente — segue o padrão Ed Donner.
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

# Modelos que aceitam response_format={"type": "json_object"} via OpenAI SDK.
# Gemini via base_url do Google NÃO aceita esse parâmetro — retorna erro 400.
_MODELOS_COM_JSON_MODE = ("gpt-", "o1-", "o3-")


class WriterError(Exception):
    """Erro não recuperável do writer (ex: LLM indisponível)."""


class WriterParseError(Exception):
    """Resposta da LLM não pôde ser parseada como JSON válido."""


def _suporta_json_mode(model: str) -> bool:
    """Retorna True apenas para modelos OpenAI que aceitam response_format."""
    return any(model.startswith(p) for p in _MODELOS_COM_JSON_MODE)


def _parse_resposta(resposta_raw: str) -> TextosGerados:
    """
    Extrai JSON da resposta bruta da LLM.
    A LLM pode retornar o JSON envolto em markdown (```json ... ```).
    """
    texto = resposta_raw.strip()

    if texto.startswith("```"):
        texto = "\n".join(
            l for l in texto.splitlines()
            if not l.strip().startswith("```")
        ).strip()

    try:
        data = json.loads(texto)
    except json.JSONDecodeError as e:
        raise WriterParseError(
            f"JSON inválido na resposta do writer: {e}\nResposta: {texto[:300]}"
        )

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
    model: str = "gemini-2.5-flash",
) -> TextosGerados:
    """
    Gera os textos de desenvolvimento, resultados e justificativa
    para uma atividade usando a LLM configurada.

    Args:
        ctx_projeto:   ContextoProjeto extraído do termo de outorga.
        ctx_atividade: ContextoAtividade montado pelo builder.
        llm_client:    Cliente openai.OpenAI (Gemini via base_url ou OpenAI nativo).
        model:         Identificador do modelo — sem prefixo de provider.

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

    # Gemini via base_url não aceita response_format — instrução está no prompt
    kwargs: dict = dict(
        model=model,
        temperature=0.3,
        messages=[
            {"role": "system", "content": sys_prompt},
            {"role": "user",   "content": usr_prompt},
        ],
    )
    if _suporta_json_mode(model):
        kwargs["response_format"] = {"type": "json_object"}

    try:
        response = llm_client.chat.completions.create(**kwargs)
        resposta_raw = response.choices[0].message.content or ""
    except Exception as e:
        raise WriterError(
            f"Falha ao chamar LLM para atividade {ctx_atividade.codigo}: {e}"
        ) from e

    return _parse_resposta(resposta_raw)
