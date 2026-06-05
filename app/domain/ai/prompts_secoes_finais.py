"""
Prompts para os writers das seções finais do relatório (tópicos 5 a 10).

Estrutura alinhada ao modelo oficial do RAT FAPEMIG/FINEP:
  5. Avaliação da gestão do projeto
  6. Impactos internos e externos do projeto
  7. Produção tecnológica
  8. Parceria institucional
  9. Comentário final
  10. Resumo + palavras-chave

Arquitetura:
    - 1 chamada LLM por relatório (não por atividade)
    - Contexto: ContextoProjeto + resumo de metas/atividades com textos gerados
    - Saída: JSON com todos os campos das seções 5-10
"""
from __future__ import annotations

from app.domain.projects.termo_outorga import ContextoProjeto


def _meta_numero(m) -> str:
    if isinstance(m, dict):
        return str(m.get("numero", ""))
    return str(getattr(m, "numero", ""))


def _meta_descricao(m) -> str:
    if isinstance(m, dict):
        return str(m.get("descricao", "") or m.get("titulo", ""))
    return str(getattr(m, "descricao", "") or getattr(m, "titulo", ""))


def system_prompt_secoes_finais(ctx_projeto: ContextoProjeto) -> str:
    metas_txt = ""
    for m in ctx_projeto.metas_pactuadas:
        metas_txt += f"  - Meta {_meta_numero(m)}: {_meta_descricao(m)}\n"

    periodo = getattr(ctx_projeto, "periodo_relatorio", None) or "não informado"
    instituicao = getattr(ctx_projeto, "instituicao", None) or "não informada"
    objetivo = getattr(ctx_projeto, "objetivo_geral", None) or "não informado"

    return f"""Você é um especialista em redação de relatórios técnicos institucionais para projetos financiados por agências de fomento (FAPEMIG, FINEP, CNPq).

PROJETO: {ctx_projeto.titulo_projeto}
INSTITUIÇÃO: {instituicao}
OBJETIVO GERAL: {objetivo}
PERÍODO DO RELATÓRIO: {periodo}

METAS PACTUADAS:
{metas_txt if metas_txt else '  (não extraídas do termo de outorga)'}

Sua tarefa é redigir os tópicos 5 a 10 de um Relatório de Acompanhamento Técnico (RAT) da FAPEMIG.

ESTRUTURA OBRIGATÓRIA:
  5. Avaliação da gestão do projeto
     - Capacitações realizadas pela equipe no período
     - Melhorias em instalações físicas realizadas
     - Dificuldades não técnicas encontradas na execução
  6. Impactos internos e externos do projeto
     - Desdobramentos internos: mudanças organizacionais, faturamento, processos internos
     - Posicionamento de mercado: mudanças no posicionamento da instituição
     - Benefícios sociais trazidos pelo projeto
  7. Produção tecnológica
     - Produtos, protótipos, patentes, processos ou metodologias não previstos como indicadores
  8. Parceria institucional
     - Articulações institucionais mantidas, resultados transferidos, contribuição de cada parceiro
  9. Comentário final
     - Observações relevantes que não se aplicam aos outros campos
  10. Resumo
     - Até 200 palavras para divulgação externa
     - Até 6 palavras-chave que caracterizem os resultados

REGRAS OBRIGATÓRIAS:
- Baseie-se SOMENTE nos dados fornecidos. Não invente fatos, percentuais ou realizações não descritas.
- Tom: técnico, institucional, objetivo — sem elogios genéricos ou afirmações vagas.
- Use o estilo do modelo de RAT: parágrafos densos, linguagem formal, foco em fatos e evidências.
- Se não houver dados suficientes para um sub-campo, escreva: "Não houve registro de [campo] no período."
- Não use markdown, bullets nem formatação especial — apenas texto corrido por campo.
- No campo 'resumo', limite a 200 palavras.
- No campo 'palavras_chave', retorne uma lista JSON de até 6 strings.
- Retorne APENAS JSON válido, sem texto fora do JSON, sem blocos ```."""


def user_prompt_secoes_finais(
    resumo_metas: list[dict],
    textos_atividades: list[dict] | None = None,
) -> str:
    """
    Monta o prompt de usuário com o resumo consolidado de todas as metas
    e os textos já gerados das atividades.
    """
    linhas = ["=== RESUMO DE EXECUÇÃO POR META ===\n"]
    for m in resumo_metas:
        linhas.append(
            f"Meta {m.get('numero', '?')}: {m.get('titulo', '')}\n"
            f"  Previsto acumulado: {m.get('previsto_pct', '?')}% | "
            f"Realizado acumulado: {m.get('realizado_pct', '?')}%"
        )
        for atv in m.get("atividades", []):
            dev  = atv.get("desenvolvimento", "")
            res  = atv.get("resultados", "")
            just = atv.get("justificativa", "")
            linhas.append(
                f"  [{atv.get('codigo')}] {atv.get('titulo', '')} "
                f"| Status: {atv.get('status', '?')} "
                f"| Realizado: {atv.get('realizado', '?')}%"
            )
            if dev:  linhas.append(f"    Desenvolvimento: {dev[:400]}")
            if res:  linhas.append(f"    Resultados: {res[:400]}")
            if just: linhas.append(f"    Justificativa: {just[:300]}")
        linhas.append("")

    prompt = "\n".join(linhas)
    prompt += """

Com base no contexto acima, redija os tópicos 5 a 10 do RAT.
Retorne APENAS o seguinte JSON (sem markdown, sem texto fora do JSON):

{
  "avaliacao_gestao": "<tópico 5 — texto consolidado sobre avaliação da gestão: capacitações da equipe realizadas no período, melhorias físicas executadas e dificuldades não técnicas enfrentadas>",

  "desdobramentos_internos": "<tópico 6a — desdobramentos internos: perspectivas e mudanças proporcionadas pelo projeto às atividades internas da instituição executora e parceiros, incluindo mudanças organizacionais, faturamento, etc.>",

  "posicionamento_mercado": "<tópico 6b — mudanças no posicionamento da instituição perante o mercado ou sociedade, proporcionadas pelo projeto>",

  "beneficios_sociais": "<tópico 6c — benefícios sociais trazidos pelo projeto à comunidade>",

  "producao_tecnologica": "<tópico 7 — produtos, protótipos, patentes, processos ou metodologias que surgiram e não haviam sido previstos como indicadores físicos>",

  "parcerias_institucionais": "<tópico 8 — articulações institucionais mantidas, resultados transferidos para cada parceiro e contribuição específica de cada instituição partícipe>",

  "comentario_final": "<tópico 9 — observações relevantes que não se aplicariam aos outros campos do relatório, incluindo contexto de atrasos, fatores externos, encaminhamentos necessários>",

  "resumo": "<tópico 10 — resumo com até 200 palavras para divulgação externa, destacando principais resultados e perspectivas>",

  "palavras_chave": ["<palavra 1>", "<palavra 2>", "<palavra 3>", "<palavra 4>", "<palavra 5>", "<palavra 6>"]
}"""
    return prompt
