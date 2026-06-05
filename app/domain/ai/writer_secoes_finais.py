"""
Writer das seções finais do RAT (tópicos 5 a 10).

Diferente do writer de atividades, este writer:
  - Processa TODO o relatório de uma vez (1 chamada LLM por execução)
  - Recebe o contexto consolidado de todas as metas e atividades
  - Devolve TextosSecaoFinal com os campos dos tópicos 5-10
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

    # palavras_chave pode vir como lista ou string separada por vírgula
    palavras_raw = data.get("palavras_chave", [])
    if isinstance(palavras_raw, str):
        palavras_chave = [p.strip() for p in palavras_raw.split(",") if p.strip()][:6]
    elif isinstance(palavras_raw, list):
        palavras_chave = [str(p).strip() for p in palavras_raw if str(p).strip()][:6]
    else:
        palavras_chave = []

    return TextosSecaoFinal(
        avaliacao_gestao         = str(data.get("avaliacao_gestao", "")).strip(),
        desdobramentos_internos  = str(data.get("desdobramentos_internos", "")).strip(),
        posicionamento_mercado   = str(data.get("posicionamento_mercado", "")).strip(),
        beneficios_sociais       = str(data.get("beneficios_sociais", "")).strip(),
        producao_tecnologica     = str(data.get("producao_tecnologica", "")).strip(),
        parcerias_institucionais = str(data.get("parcerias_institucionais", "")).strip(),
        comentario_final         = str(data.get("comentario_final", "")).strip(),
        resumo                   = str(data.get("resumo", "")).strip(),
        palavras_chave           = palavras_chave,
    )


def _montar_resumo_metas(relatorio: dict[str, Any]) -> list[dict]:
    """
    Monta lista de dicts com resumo de execução por meta,
    incluindo os textos já gerados das atividades (se existirem).
    Compatível com estrutura canônica (chave 'metas') e legado ('itens').
    """
    resumo = []
    todas_metas = relatorio.get("metas", []) + relatorio.get("itens", [])
    for meta in todas_metas:
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

            # Textos: campo canônico 'texto' ou legado 'textos_gerados'
            textos = atv.get("texto") or atv.get("textos_gerados") or {}

            codigo = (
                atv.get("numero_atividade_original") or atv.get("numeroAtividadeOriginal")
                or atv.get("numero_atividade") or atv.get("codigo") or "?"
            )

            # Percentuais: tenta campos do schema canônico primeiro
            realizado = (
                prog.get("realizado_percentual")
                or prog.get("realizado_pct")
                or prog.get("realizadoAcumulado")
                or ""
            )
            previsto = (
                prog.get("previsto_percentual")
                or prog.get("previsto_pct")
                or prog.get("previstoAcumulado")
                or ""
            )

            atividades_resumo.append({
                "codigo":          codigo,
                "titulo":          atv.get("titulo") or atv.get("titulo_original") or "",
                "status":          atv.get("status") or prog.get("situacao_prazo") or "",
                "previsto":        previsto,
                "realizado":       realizado,
                "desenvolvimento": textos.get("desenvolvimento", ""),
                "resultados":      textos.get("resultados", ""),
                "justificativa":   textos.get("justificativa", ""),
            })

        resumo.append({
            "numero":        str(numero),
            "titulo":        titulo,
            "previsto_pct":  (
                prog_meta.get("previsto_percentual_medio")
                or prog_meta.get("previsto_pct")
                or prog_meta.get("previstoAcumulado")
                or ""
            ),
            "realizado_pct": (
                prog_meta.get("realizado_percentual_medio")
                or prog_meta.get("realizado_pct")
                or prog_meta.get("realizadoAcumulado")
                or ""
            ),
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
    Gera os textos dos tópicos 5-10 do RAT em uma única chamada LLM.

    Args:
        ctx_projeto:          ContextoProjeto extraído do termo de outorga.
        relatorio_com_textos: Relatório já com textos de atividades aplicados.
        llm_client:           Cliente openai.OpenAI.
        model:                Modelo LLM.

    Returns:
        TextosSecaoFinal com todos os campos dos tópicos 5-10.
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
