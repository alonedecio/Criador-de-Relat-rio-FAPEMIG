"""
Prompts para os writers das seções finais do relatório (seções 5 a 10).

Cada função recebe o contexto consolidado do projeto + resumo de progresso
de todas as metas e devolve o prompt pronto para a LLM.

Arquitetura:
    - 1 chamada LLM por relatório (não por atividade)
    - Contexto de entrada: ContextoProjeto + lista de metas com progresso
      + textos já gerados das atividades (opcional, para coerência)
    - Saída: JSON com todos os campos das seções finais de uma vez
"""
from __future__ import annotations

from app.domain.projects.termo_outorga import ContextoProjeto


def system_prompt_secoes_finais(ctx_projeto: ContextoProjeto) -> str:
    metas_txt = ""
    for m in ctx_projeto.metas_pactuadas:
        metas_txt += f"  - Meta {m.get('numero', '')}: {m.get('descricao', '')}\n"

    return f"""Você é um especialista em redação de relatórios técnicos institucionais para projetos financiados por agências de fomento (FAPEMIG, FINEP, CNPq).

PROJETO: {ctx_projeto.titulo_projeto}
OBJETIVO GERAL: {ctx_projeto.objetivo_geral}

METAS DO PROJETO:
{metas_txt if metas_txt else '  (não extraídas do termo)'}

Sua tarefa é redigir as seções finais de um Relatório de Acompanhamento Técnico (RAT).
As seções são:
  5. Avaliação da gestão do projeto
  6. Impactos internos e externos
  7. Produção tecnológica
  8. Parceria institucional
  9. Comentário final
  10. Resumo

REGRAS OBRIGATÓRIAS:
- Baseie-se SOMENTE nos dados fornecidos. Não invente fatos, percentuais ou realizações não descritas.
- Tom: técnico, institucional, objetivo, sem elogios genéricos.
- Se não houver dados suficientes para um campo, escreva "Não houve registro de [campo] no período."
- Não use markdown, bullets nem formatação especial — apenas texto corrido por campo.
- Retorne APENAS JSON válido, sem texto fora do JSON, sem blocos ```."""


def user_prompt_secoes_finais(
    resumo_metas: list[dict],
    textos_atividades: list[dict] | None = None,
) -> str:
    """
    Monta o prompt de usuário com o resumo consolidado de todas as metas
    e os textos já gerados das atividades (opcional).

    Args:
        resumo_metas: lista de dicts com {meta, previsto_pct, realizado_pct,
                      atividades: [{codigo, titulo, status, previsto, realizado,
                      desenvolvimento, resultados, justificativa}]}
        textos_atividades: textos já gerados, para coerência narrativa
    """
    linhas = ["=== RESUMO DE EXECUÇÃO POR META ===\n"]
    for m in resumo_metas:
        linhas.append(
            f"Meta {m.get('numero', '?')}: {m.get('titulo', '')}\n"
            f"  Previsto: {m.get('previsto_pct', '?')}% | Realizado: {m.get('realizado_pct', '?')}%"
        )
        for atv in m.get("atividades", []):
            dev  = atv.get("desenvolvimento", "")
            res  = atv.get("resultados", "")
            just = atv.get("justificativa", "")
            linhas.append(
                f"  [{atv.get('codigo')}] {atv.get('titulo', '')} "
                f"| Status: {atv.get('status','?')} "
                f"| Realizado: {atv.get('realizado','?')}%"
            )
            if dev:  linhas.append(f"    Desenvolvimento: {dev[:300]}")
            if res:  linhas.append(f"    Resultados: {res[:300]}")
            if just: linhas.append(f"    Justificativa: {just[:200]}")
        linhas.append("")

    prompt = "\n".join(linhas)
    prompt += """

Com base no contexto acima, redija as seções finais do RAT.
Retorne APENAS o seguinte JSON (sem markdown, sem texto fora do JSON):

{
  "capacitacoes_equipe": "<texto para seção 5 — capacitações da equipe no período>",
  "melhorias_instalacoes": "<texto para seção 5 — melhorias nas instalações físicas>",
  "dificuldades_nao_tecnicas": "<texto para seção 5 — dificuldades não técnicas enfrentadas>",
  "impactos_internos": "<texto para seção 6 — impactos internos gerados pelo projeto>",
  "impactos_externos": "<texto para seção 6 — impactos externos e sociais do projeto>",
  "producao_tecnologica": "<texto para seção 7 — produção tecnológica gerada>",
  "parcerias_institucionais": "<texto para seção 8 — parcerias e articulações institucionais>",
  "comentario_final": "<texto para seção 9 — comentário final sobre o período>",
  "resumo": "<texto para seção 10 — resumo executivo do período>"
}"""
    return prompt
