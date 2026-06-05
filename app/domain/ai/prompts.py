"""
Montagem de prompts para writer e validator.

Design:
- system_prompt_writer:    injetado UMA VEZ com o ContextoProjeto (estático)
- user_prompt_writer:      injetado por atividade com o ContextoAtividade (dinâmico)
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
7. SOBRE ANEXOS: quando a atividade possui anexos registrados, você pode mencionar a existência do anexo como evidência de execução e, pelo título, inferir o tipo de evidência (ex: se o título contém "planilha", "lista", "ata", "relatório", "fotos", "certificado", infira o que representa). Não invente o conteúdo do anexo — apenas reconheça sua existência como indicador de execução.
8. SOBRE ITENS DE AÇÃO: quando campos customizados (customfields) da task estão disponíveis, use-os como evidência adicional sobre o estado e resultado da atividade. Não invente valores não listados.
9. SOBRE PROGRESSO ZERO COM STATUS ATIVO: quando o status da atividade é 'em progresso' (ou equivalente) mas o percentual realizado é 0.0%, isso indica que a atividade foi iniciada formalmente mas ainda não gerou entregas mensuráveis no sistema. Nesse caso, adote a seguinte narrativa coerente:
   - No campo 'desenvolvimento': descreva as ações previstas para esta atividade e registre que ela se encontra em fase inicial de execução, sem entregas consolidadas até o momento.
   - No campo 'resultados': escreva "A atividade encontra-se em fase inicial de execução. Não há entregas consolidadas registradas para este período."
   - No campo 'justificativa': foque exclusivamente no atraso em relação à data prevista, sem mencionar dúvida sobre o início da atividade.
   PROIBIDO: afirmar simultaneamente que 'a atividade está em progresso' E que 'o início efetivo ainda não ocorreu'. Escolha uma narrativa única e mantenha-a nos três campos.


CONTEXTO DO PROJETO (use para dar coerência institucional aos textos):
{ctx_projeto.resumo_para_prompt()}
"""


def _fmt_customfields(customfields: list[dict]) -> str:
    """
    Formata customfields da task para exibição no prompt.
    Filtra campos sem valor e limita a 10 itens.
    """
    linhas = []
    for cf in customfields:
        nome = cf.get("name") or cf.get("field_name") or ""
        valor = (
            cf.get("value")
            or cf.get("value_richtext")
            or cf.get("type_config", {}).get("default", "")
            or ""
        )
        if nome and valor and str(valor).strip():
            linhas.append(f"  {nome}: {str(valor).strip()[:200]}")
        if len(linhas) >= 10:
            break
    return "\n".join(linhas) if linhas else "  Nenhum campo customizado com valor registrado."


def user_prompt_writer(ctx: ContextoAtividade) -> str:
    """
    User prompt dinâmico por atividade.
    Monta o bloco de contexto factual disponível.
    """
    # Indica explicitamente a origem do título para o writer
    origem_titulo = "ClickUp (título original da task)" if ctx.task_id else "Relatório canônico (task não encontrada no snapshot)"

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

    # Anexos — título como evidência inferível
    def _fmt_anexo(a) -> str:
        if isinstance(a, dict):
            titulo = a.get("title") or a.get("name") or a.get("filename") or str(a)
        else:
            titulo = str(a)
        return f"  - {titulo}"

    if ctx.anexos:
        anexos_txt = "\n".join(_fmt_anexo(a) for a in ctx.anexos[:10])
    else:
        anexos_txt = "  Nenhum anexo registrado."

    # Customfields (itens de ação e campos extras da task)
    customfields = getattr(ctx, "customfields", None) or []
    customfields_txt = _fmt_customfields(customfields)

    return f"""Preencha os três campos textuais da atividade abaixo com base EXCLUSIVAMENTE nas informações fornecidas.


━━ IDENTIFICAÇÃO ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Meta: {ctx.meta_codigo}
Atividade: {ctx.codigo} — {ctx.titulo}
Origem do título: {origem_titulo}
Status no ClickUp: {ctx.status}
Responsáveis: {', '.join(ctx.responsaveis) or 'Não informado'}
Data início prevista: {ctx.data_inicio or 'Não informada'}
Data fim prevista: {ctx.data_fim or 'Não informada'}


━━ PROGRESSO ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{progresso_bloco}


━━ DESCRIÇÃO DA ATIVIDADE (ClickUp) ━━━━━━━━━━━━━━━━━
{ctx.descricao or 'Sem descrição registrada.'}


━━ ITENS DE AÇÃO / CAMPOS CUSTOMIZADOS (ClickUp) ━━━━━━━
{customfields_txt}


━━ COMENTÁRIOS (ClickUp) ━━━━━━━━━━━━━━━━━━━━━
{comentarios_txt}


━━ CHECKLISTS (ClickUp) ━━━━━━━━━━━━━━━━━━━━━━━
{checklists_txt}


━━ ANEXOS REGISTRADOS (ClickUp) ━━━━━━━━━━━━━━━
{anexos_txt}
(Você não tem acesso ao conteúdo dos anexos. Use o título como indicador
 do tipo de evidência produzida. Não invente o conteúdo.)


━━ CAMPOS A PREENCHER ━━━━━━━━━━━━━━━━━━━━━━━━━━━
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
7. Sobre anexos: verificar se o writer mencionou anexos de forma coerente — se há anexos registrados e a atividade está concluída, o texto de resultados deve reconhecer a existência de evidência
8. Sobre itens de ação: verificar se o writer fez uso coerente dos customfields quando disponíveis
9. SOBRE PROGRESSO ZERO COM STATUS ATIVO: quando status é 'em progresso' e realizado é 0.0%, o texto correto é afirmar que a atividade está em fase inicial de execução sem entregas consolidadas. NÃO reprove esse caso como contradição — é um estado válido. Reprove apenas se o writer afirmar simultaneamente que 'está em progresso' E que 'o início efetivo ainda não ocorreu'.


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

    # Passa os primeiros comentários reais para o validator verificar aderência factual
    if ctx.comentarios:
        comentarios_resumo = "\n".join(
            f"  [{i+1}] {c[:200]}" for i, c in enumerate(ctx.comentarios[:5])
        )
    else:
        comentarios_resumo = "  Nenhum comentário registrado."

    # Informa títulos de anexos ao validator
    def _titulo_anexo(a) -> str:
        if isinstance(a, dict):
            return a.get("title") or a.get("name") or a.get("filename") or str(a)
        return str(a)

    if ctx.anexos:
        anexos_resumo = "; ".join(_titulo_anexo(a) for a in ctx.anexos[:5])
    else:
        anexos_resumo = "Nenhum"

    # Customfields para o validator verificar aderência
    customfields = getattr(ctx, "customfields", None) or []
    if customfields:
        cf_resumo = "; ".join(
            f"{cf.get('name','')}: {cf.get('value','')}"
            for cf in customfields[:5]
            if cf.get('name') and cf.get('value')
        ) or "Nenhum com valor"
    else:
        cf_resumo = "Nenhum"

    return f"""Valide os textos abaixo gerados para a atividade.


ATIVIDADE: {ctx.codigo} — {ctx.titulo}
STATUS CLICKUP: {ctx.status}
SITUAÇÃO NO PRAZO: {situacao}
REALIZADO %: {realizado}
TÍTULO ORIGEM: {'ClickUp' if ctx.task_id else 'Relatório canônico (sem task)'}
DESCRIÇÃO ORIGINAL: {(ctx.descricao or '')[:400]}
ANEXOS REGISTRADOS: {anexos_resumo}
CAMPOS CUSTOMIZADOS: {cf_resumo}

COMENTÁRIOS DISPONÍVEIS ({len(ctx.comentarios)}):
{comentarios_resumo}


TEXTOS GERADOS:
{textos_json}


Responda apenas com o JSON de validação.
"""
