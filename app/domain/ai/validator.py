"""
Validator — agente responsável por verificar aderência factual e qualidade
dos textos gerados pelo writer.

Recebe:
    ContextoAtividade  — contexto factual da atividade
    TextosGerados      — saída do writer

Devolve:
    ResultadoValidacao — status (aprovado/reprovado/ressalva) + erros + sugestões

O validator usa regras determinísticas ANTES de chamar a LLM,
para evitar gasto de tokens em erros óbvios.

Arquitetura LLM:
    Recebe llm_client já instanciado (openai.OpenAI apontando para Gemini
    via base_url, ou openai.OpenAI padrão). Não instancia nem importa
    nenhuma lib de LLM diretamente — segue o padrão Ed Donner.
"""
from __future__ import annotations

import json
import logging
from typing import Optional

from app.domain.ai.schemas import (
    TextosGerados,
    ResultadoValidacao,
    StatusValidacao,
)
from app.domain.ai.prompts import system_prompt_validator, user_prompt_validator
from app.domain.context.builders import ContextoAtividade

logger = logging.getLogger(__name__)

# Modelos que aceitam response_format={"type": "json_object"} via OpenAI SDK.
# Gemini via base_url do Google NÃO aceita esse parâmetro — retorna erro 400.
_MODELOS_COM_JSON_MODE = ("gpt-", "o1-", "o3-")


def _suporta_json_mode(model: str) -> bool:
    """Retorna True apenas para modelos OpenAI que aceitam response_format."""
    return any(model.startswith(p) for p in _MODELOS_COM_JSON_MODE)


# ── validação determinística (sem LLM) ───────────────────────────────────────

def _validar_deterministico(
    ctx: ContextoAtividade,
    textos: TextosGerados,
) -> list[str]:
    """
    Regras rápidas que dispensam chamada LLM.
    Retorna lista de erros encontrados (vazia = sem erros graves).
    """
    erros: list[str] = []

    status_lower = ctx.status.lower()
    dev_lower = textos.desenvolvimento.lower()
    res_lower = textos.resultados.lower()

    # 1. Atividade pendente não pode afirmar conclusão
    termos_conclusao = ["concluída", "finalizada", "entregue", "100% realizado"]
    if "pendente" in status_lower or "não iniciada" in status_lower:
        for termo in termos_conclusao:
            if termo in dev_lower or termo in res_lower:
                erros.append(
                    f"Atividade com status '{ctx.status}' não pode afirmar conclusão "
                    f"(termo encontrado: '{termo}')."
                )
                break

    # 2. Progresso 0% não pode afirmar realizações quantitativas
    if ctx.progresso and ctx.progresso.realizado_percentual == 0.0:
        for termo in ["realizou", "foram executadas", "atingiu", "completou"]:
            if termo in dev_lower:
                erros.append(
                    f"Realizado = 0% mas texto afirma execução ('{termo}')."
                )
                break

    # 3. Campos vazios ou placeholder
    campos = {
        "desenvolvimento": textos.desenvolvimento,
        "resultados": textos.resultados,
        "justificativa": textos.justificativa,
    }
    for campo, valor in campos.items():
        if not valor or len(valor.strip()) < 20:
            erros.append(f"Campo '{campo}' vazio ou muito curto (menos de 20 caracteres).")

    return erros


# ── validação por LLM ────────────────────────────────────────────────────────

def _parse_validacao(resposta_raw: str) -> ResultadoValidacao:
    texto = resposta_raw.strip()
    if texto.startswith("```"):
        texto = "\n".join(
            l for l in texto.splitlines()
            if not l.strip().startswith("```")
        ).strip()

    try:
        data = json.loads(texto)
    except json.JSONDecodeError:
        return ResultadoValidacao(
            status=StatusValidacao.APROVADO_COM_RESSALVA,
            ressalvas=["Resposta do validator não pôde ser parseada; revisão manual recomendada."],
        )

    status_map = {
        "aprovado":              StatusValidacao.APROVADO,
        "reprovado":             StatusValidacao.REPROVADO,
        "aprovado_com_ressalva": StatusValidacao.APROVADO_COM_RESSALVA,
    }
    status = status_map.get(data.get("status", ""), StatusValidacao.APROVADO_COM_RESSALVA)

    return ResultadoValidacao(
        status=status,
        erros=data.get("erros", []),
        ressalvas=data.get("ressalvas", []),
        sugestoes_correcao=data.get("sugestoes_correcao", []),
    )


def validar_textos(
    ctx_atividade: ContextoAtividade,
    textos: TextosGerados,
    llm_client,
    model: str = "gemini-2.5-flash",
    usar_llm: bool = True,
) -> ResultadoValidacao:
    """
    Valida os textos gerados pelo writer.

    Estratégia em duas camadas:
    1. Regras determinísticas (rápidas, sem custo de tokens)
    2. Validação por LLM (somente se regras passarem e usar_llm=True)

    Args:
        ctx_atividade: contexto da atividade.
        textos:        textos gerados pelo writer.
        llm_client:    cliente openai.OpenAI (Gemini via base_url ou OpenAI nativo).
        model:         modelo LLM — sem prefixo de provider.
        usar_llm:      se False, executa apenas validação determinística.

    Returns:
        ResultadoValidacao com status e detalhamento.
    """
    # Camada 1: determinística
    erros_det = _validar_deterministico(ctx_atividade, textos)
    if erros_det:
        return ResultadoValidacao(
            status=StatusValidacao.REPROVADO,
            erros=erros_det,
            sugestoes_correcao=[f"Corrigir: {e}" for e in erros_det],
        )

    if not usar_llm:
        return ResultadoValidacao(status=StatusValidacao.APROVADO)

    # Camada 2: LLM
    sys_prompt = system_prompt_validator()
    usr_prompt = user_prompt_validator(
        ctx_atividade,
        textos.model_dump_json(indent=2),
    )

    logger.debug("Validator: validando atividade %s", ctx_atividade.codigo)

    kwargs: dict = dict(
        model=model,
        temperature=0.0,
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
        logger.warning("Validator LLM falhou para %s: %s", ctx_atividade.codigo, e)
        return ResultadoValidacao(
            status=StatusValidacao.APROVADO_COM_RESSALVA,
            ressalvas=["Validação LLM indisponível; aprovado com ressalva."],
        )

    return _parse_validacao(resposta_raw)
