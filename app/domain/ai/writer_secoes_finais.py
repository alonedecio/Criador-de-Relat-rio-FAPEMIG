"""
Writer das seções finais do RAT (seções 5 a 10).

Diferente do writer de atividades, este writer:
  - Processa TODO o relatório de uma vez (1 chamada LLM por execução)
  - Recebe o contexto consolidado de todas as metas e atividades
  - Devolve TextosSecaoFinal com os 9 campos das seções 5-10
"""
from __future__ import annotations

import json
import logging
from typing import Any

from app.domain.ai.schemas import TextosSecaoFinal
from app.domain.ai.prompts_secoes_finais import (
    system_prompt_secoes_finais,
    user_prompt_secoes_finais,
)
from app.domain.projects.termo_outorga import ContextoProjeto

logger = logging.getLogger(__name__)


class WriterSecoesFinalError(Exception):
    pass


def _parse_resposta(raw: str) -> TextosSecaoFinal:
    texto = raw.strip()
    if texto.startswith("```"):
        texto = "\n".join(
            l for l in texto.splitlines()
            if not l.strip().startswith("```")
        ).strip()
    try:
        data = json.loads(texto)
    except json.JSONDecodeError as e:
        raise WriterSecoesFinalError(
            f"JSON inválido na resposta do writer de seções finais: {e}\n{texto[:400]}"
        )
    return TextosSecaoFinal(
        capacitacoes_equipe       = str(data.get("capacitacoes_equipe", "")).strip(),
        melhorias_instalacoes     = str(data.get("melhorias_instalacoes", "")).strip(),
        dificuldades_nao_tecnicas = str(data.get("dificuldades_nao_tecnicas", "")).strip(),
        impactos_internos         = str(data.get("impactos_internos", "")).strip(),
        impactos_externos         = str(data.get("impactos_externos", "")).strip(),
        producao_tecnologica      = str(data.get("producao_tecnologica", "")).strip(),
        parcerias_institucionais  = str(data.get("parcerias_institucionais", "")).strip(),
        comentario_final          = str(data.get("comentario_final", "")).strip(),
        resumo                    = str(data.get("resumo", "")).strip(),
    )


def _montar_resumo_metas(relatorio: dict[str, Any]) -> list[dict]:
    """
    Monta lista de dicts com resumo de execução por meta,
    incluindo os textos já gerados das atividades (se existirem).
    """
    resumo = []
    for meta in relatorio.get("metas", []) + relatorio.get("itens", []):
        numero = (
            meta.get("numero_meta") or meta.get("numeroMeta")
            or meta.get("numero") or "?"
        )
        titulo = (
            meta.get("titulo_meta") or meta.get("tituloMeta")
            or meta.get("titulo") or ""
        )
        prog_meta = meta.get("progresso") or meta.get("progressoCalculado") or {}
        atividades_resumo = []
        for atv in meta.get("atividades", []):
            prog = atv.get("progresso") or atv.get("progressoCalculado") or {}
            textos = atv.get("textos_gerados") or {}
            codigo = (
                atv.get("numero_atividade_original") or atv.get("numeroAtividadeOriginal")
                or atv.get("numero_atividade") or atv.get("codigo") or "?"
            )
            atividades_resumo.append({
                "codigo":         codigo,
                "titulo":         atv.get("titulo") or atv.get("titulo_original") or "",
                "status":         atv.get("status") or prog.get("situacao_prazo") or "",
                "previsto":       prog.get("previsto_pct") or prog.get("previstoAcumulado") or "",
                "realizado":      prog.get("realizado_pct") or prog.get("realizadoAcumulado") or "",
                "desenvolvimento": textos.get("desenvolvimento", ""),
                "resultados":      textos.get("resultados", ""),
                "justificativa":   textos.get("justificativa", ""),
            })
        resumo.append({
            "numero":        str(numero),
            "titulo":        titulo,
            "previsto_pct":  prog_meta.get("previsto_pct") or prog_meta.get("previstoAcumulado") or "",
            "realizado_pct": prog_meta.get("realizado_pct") or prog_meta.get("realizadoAcumulado") or "",
            "atividades":    atividades_resumo,
        })
    return resumo


def gerar_secoes_finais(
    ctx_projeto: ContextoProjeto,
    relatorio_com_textos: dict[str, Any],
    llm_client,
    model: str = "gemini-2.5-flash-lite",
) -> TextosSecaoFinal:
    """
    Gera os textos das seções finais do RAT em uma única chamada LLM.

    Args:
        ctx_projeto:          ContextoProjeto extraído do termo de outorga.
        relatorio_com_textos: Relatório já com textos de atividades aplicados.
        llm_client:           Cliente openai.OpenAI.
        model:                Modelo LLM.

    Returns:
        TextosSecaoFinal com os 9 campos preenchidos.
    """
    resumo_metas = _montar_resumo_metas(relatorio_com_textos)

    sys_prompt = system_prompt_secoes_finais(ctx_projeto)
    usr_prompt = user_prompt_secoes_finais(resumo_metas)

    logger.info(
        "Writer seções finais: %d metas no contexto, modelo %s",
        len(resumo_metas), model,
    )

    try:
        response = llm_client.chat.completions.create(
            model=model,
            temperature=0.3,
            messages=[
                {"role": "system", "content": sys_prompt},
                {"role": "user",   "content": usr_prompt},
            ],
        )
        raw = response.choices[0].message.content or ""
    except Exception as e:
        raise WriterSecoesFinalError(
            f"Falha ao chamar LLM para seções finais: {e}"
        ) from e

    textos = _parse_resposta(raw)
    logger.info("Writer seções finais: textos gerados com sucesso.")
    return textos
