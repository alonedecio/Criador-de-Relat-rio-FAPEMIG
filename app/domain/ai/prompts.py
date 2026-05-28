"""
Montagem de prompts para writer e validator.

Design:
- system_prompt_writer: injetado UMA VEZ com o ContextoProjeto (estático)
- user_prompt_writer:   injetado por atividade com o ContextoAtividade (dinâmico)
- system_prompt_validator: instruções fixas do validator
- user_prompt_validator:   textos gerados + contexto para validação

Separar system/user permite reaproveitar o contexto do projeto
como mensagem de sistema cacheada, reduzindo tokens por chamada.
"""
from __future__ import annotations

from app.domain.context.builders import ContextoAtividade
from app.domain.projects.termo_outorga import ContextoProjeto


def system_prompt_writer(ctx_projeto: ContextoProjeto) -> str:
    """
    System prompt do writer. Carregado uma vez por sessão.
    Contém o contexto institucional completo do projeto.
    """
    return f"""Você é um redator técnico especializado em relatórios institucionais de projetos financiados por agências de fomento. Seu objetivo é preencher três campos textuais de cada atividade de um relatório de prestação de contas.

ATENÇÃO — REGRAS INEGOCIÁVEIS:
1. Use SOMENTE as informações fornecidas no contexto da atividade. Nunca invente dados, datas, resultados ou entregas não registrados.
2. Escreva em linguagem técnica, formal, em terceira pessoa, compatível com relatórios de prestação de contas para agências de fomento.
3. Use o vocabulário institucional do projeto listado abaixo.
4. Se não houver informação suficiente para um campo, escreva "Não há registros disponíveis para este período." — nunca deixe o campo vazio com conteúdo inventado.
5. Os três campos são independentes. Não repita a mesma frase nos três.
6. O campo 'justificativa' só deve ser preenchido com conteúdo substantivo quando houver atraso ou adiantamento real. Se a atividade está no prazo, escreva "A atividade encontra-se dentro do cronograma previsto."

CONTEXTO DO PROJETO (use para dar coerência institucional aos textos):
{ctx_projeto.resumo_para_prompt()}
"""


def user_prompt_writer(ctx: ContextoAtividade) -> str:
    """
    User prompt dinâmico por atividade.
    Monta o bloco de contexto factual disponível.
    """
    # Progresso
    prog = ctx.progresso
    if prog:
        progresso_bloco = (
            f"  Previsto: {prog.previsto_percentual}%\n"
            f"  Realizado: {prog.realizado_percentual}%\n"
            f"  Situação no prazo: {prog.situacao_prazo}\n"
            f"  Atrasada: {prog.atrasada}\n"
            f"  Mês/Ano fim previsto: {prog.mes_ano_fim_previsto}\n"
            f"  Mês/Ano fim real: {prog.mes_ano_fim_real or 'ainda em execução'}"
        )
    else:
        progresso_bloco = "  Informações de progresso não disponíveis."

    # Comentários
    comentarios_txt = (
        "\n".join(f"  [{i+1}] {c}" for i, c in enumerate(ctx.comentarios[:10]))
        if ctx.comentarios
        else "  Nenhum comentário registrado."
    )

    # Checklists
    def _fmt_checklist(cl: dict) -> str:
        nome = cl.get("name", "Checklist")
        itens = cl.get("items", [])
        linhas = [f"  [{nome}]"]
        for it in itens[:15]:
            status = "✓" if it.get("resolved") else "○"
            linhas.append(f"    {status} {it.get('name', '')}")
        return "\n".join(linhas)

    checklists_txt = (
        "\n".join(_fmt_checklist(cl) for cl in ctx.checklists[:5])
        if ctx.checklists
        else "  Nenhum checklist registrado."
    )

    return f"""Preencha os três campos textuais da atividade abaixo com base EXCLUSIVAMENTE nas informações fornecidas.

━━ IDENTIFICAÇÃO ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Meta: {ctx.meta_codigo}
Atividade: {ctx.codigo} — {ctx.titulo}
Status no ClickUp: {ctx.status}
Responsáveis: {', '.join(ctx.responsaveis) or 'Não informado'}
Data início prevista: {ctx.data_inicio or 'Não informada'}
Data fim prevista: {ctx.data_fim or 'Não informada'}

━━ PROGRESSO ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{progresso_bloco}

━━ DESCRIÇÃO DA ATIVIDADE (ClickUp) ━━━━━━━━━━━━
{ctx.descricao or 'Sem descrição registrada.'}

━━ COMENTÁRIOS (ClickUp) ━━━━━━━━━━━━━━━━━━━━━━━
{comentarios_txt}

━━ CHECKLISTS (ClickUp) ━━━━━━━━━━━━━━━━━━━━━━━━
{checklists_txt}

━━ CAMPOS A PREENCHER ━━━━━━━━━━━━━━━━━━━━━━━━━━
Responda em JSON com exatamente estas três chaves:

{{
  "desenvolvimento": "<Descreva o desenvolvimento da atividade>",
  "resultados": "<Comente sobre o(s) resultado(s). Em caso de tarefa concluída, o indicador físico deverá constar como anexo ao relatório.>",
  "justificativa": "<Justifique o eventual atraso ou adiantamento da execução da tarefa em relação à previsão inicial.>"
}}

Não adicione nenhuma chave além das três acima. Não inclua markdown. Responda apenas com o JSON.
"""


def system_prompt_validator() -> str:
    return """Você é um validador de textos para relatórios institucionais de projetos financiados por agências de fomento.

Sua função é verificar se os textos gerados pelo writer estão:
1. Factualmente aderentes ao contexto fornecido — sem inventar dados ou entregas
2. Coerentes com o status da atividade (ex: não afirmar conclusão se status é 'pendente')
3. Coerentes com o progresso (ex: não afirmar 100% realizado se realizado_percentual < 100)
4. Em tom técnico-institucional adequado (3ª pessoa, formal, sem coloquialismo)
5. Sem contradição com as metas pactuadas no termo de outorga
6. Com justificativa consistente: presente quando há atraso/adiantamento real, neutra quando no prazo

Responda em JSON com exatamente este formato:
{{
  "status": "aprovado" | "reprovado" | "aprovado_com_ressalva",
  "erros": ["lista de erros graves que impedem aprovação"],
  "ressalvas": ["lista de pontos a melhorar mas que não impedem aprovação"],
  "sugestoes_correcao": ["sugestões objetivas para o writer corrigir"]
}}
"""


def user_prompt_validator(
    ctx: ContextoAtividade,
    textos_json: str,
) -> str:
    prog = ctx.progresso
    situacao = prog.situacao_prazo if prog else "desconhecida"
    realizado = prog.realizado_percentual if prog else None

    return f"""Valide os textos abaixo gerados para a atividade.

ATIVIDADE: {ctx.codigo} — {ctx.titulo}
STATUS CLICKUP: {ctx.status}
SITUAÇÃO NO PRAZO: {situacao}
REALIZADO %: {realizado}
DESCRIÇÃO ORIGINAL: {(ctx.descricao or '')[:300]}
COMENTÁRIOS DISPONÍVEIS: {len(ctx.comentarios)} comentário(s)

TEXTOS GERADOS:
{textos_json}

Responda apenas com o JSON de validação.
"""
