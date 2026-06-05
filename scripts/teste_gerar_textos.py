"""
Script de teste do pipeline de geração de textos das atividades.

Uso:
    # Testar atividades específicas (recomendado para validação inicial)
    python scripts/teste_gerar_textos.py --atividades 1.1 2.1

    # Testar todas as atividades de uma meta
    python scripts/teste_gerar_textos.py --atividades 3.1 3.2 3.3 3.4

    # Rodar tudo (sem filtro)
    python scripts/teste_gerar_textos.py

    # Usar modelo diferente
    python scripts/teste_gerar_textos.py --atividades 1.1 --modelo gemini-2.5-flash

Pré-requisitos:
    - GEMINI_API_KEY no ambiente (ou .env na raiz do projeto)
    - Arquivos esperados (defaults):
        data/input/termo_projeto.pdf
        data/output/relatorio_final_com_progresso.json
        data/input/clickup_enriched_snapshot.json

O script exibe:
    1. Resumo do contexto montado por atividade (título, status, progresso, fontes)
    2. Textos gerados (desenvolvimento, resultados, justificativa)
    3. Status da validação e auditoria
    4. Salva resultado parcial em data/output/teste_textos_parcial.json
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from pathlib import Path

# ── garante que o pacote 'app' é encontrado independente de onde o script é chamado
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# ── tenta carregar .env se python-dotenv estiver instalado
try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except ImportError:
    pass

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("teste_gerar_textos")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# CONFIGURAÇÃO DE CAMINHOS — estrutura real do projeto
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

DATA_INPUT  = ROOT / "data" / "input"
DATA_OUTPUT = ROOT / "data" / "output"

TERMO_PDF           = DATA_INPUT  / "termo_projeto.pdf"
RELATORIO_PROGRESSO = DATA_OUTPUT / "relatorio_final_com_progresso.json"
CLICKUP_SNAPSHOT    = DATA_INPUT  / "clickup_enriched_snapshot.json"
OUTPUT_TESTE        = DATA_OUTPUT / "teste_textos_parcial.json"

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


def _separador(titulo: str = "", char: str = "━", largura: int = 70) -> str:
    if titulo:
        return f"\n{char * 3} {titulo} {char * (largura - len(titulo) - 5)}"
    return char * largura


def _exibir_contexto(ctx) -> None:
    """Imprime um resumo do contexto montado para a atividade."""
    print(_separador(f"CONTEXTO: {ctx.codigo} — {ctx.titulo[:55]}"))
    print(f"  Task ID ClickUp : {ctx.task_id or '⚠️  não encontrada no snapshot'} ")
    print(f"  Status          : {ctx.status}")
    print(f"  Origem datas    : {ctx.origem_datas}")
    print(f"  Data início     : {ctx.data_inicio or 'não informada'}")
    print(f"  Data fim        : {ctx.data_fim    or 'não informada'}")

    if ctx.progresso:
        p = ctx.progresso
        print(f"  Progresso       : {p.realizado_percentual}% realizado / {p.previsto_percentual}% previsto")
        print(f"  Situação prazo  : {p.situacao_prazo}  |  Atrasada: {p.atrasada}")
    else:
        print("  Progresso       : ⚠️  não disponível")

    print(f"  Descrição       : {(ctx.descricao or 'sem descrição')[:120]}")
    print(f"  Comentários     : {len(ctx.comentarios)}")
    print(f"  Checklists      : {len(ctx.checklists)}")
    print(f"  Anexos          : {len(ctx.anexos)}")
    print(f"  Customfields    : {len(ctx.customfields)}")

    if ctx.customfields:
        for cf in ctx.customfields[:3]:
            nome  = cf.get("name", "")
            valor = cf.get("value", "")
            if nome and valor:
                print(f"    └ {nome}: {str(valor)[:80]}")

    if ctx.anexos:
        for a in ctx.anexos[:3]:
            titulo_a = a.get("title") or a.get("filename") or str(a) if isinstance(a, dict) else str(a)
            print(f"    📎 {titulo_a[:80]}")


def _exibir_resultado(resultado) -> None:
    """Imprime os textos gerados e a auditoria de uma atividade."""
    print(_separador(f"TEXTOS: {resultado.atividade_id} — {resultado.titulo[:45]}"))

    if resultado.textos:
        t = resultado.textos
        print("\n  📝 DESENVOLVIMENTO:")
        print(f"  {t.desenvolvimento}")
        print("\n  📊 RESULTADOS:")
        print(f"  {t.resultados}")
        print("\n  ⏰ JUSTIFICATIVA:")
        print(f"  {t.justificativa}")
    else:
        print("  ❌ Textos não gerados.")

    aud = resultado.auditoria
    status_emoji = {
        "aprovado":              "✅",
        "aprovado_com_ressalva": "⚠️",
        "reprovado":             "❌",
        "incompleto":            "❓",
    }.get(str(aud.status_final), "❓")

    print(f"\n  Validação: {status_emoji} {aud.status_final}  |  Tentativas: {aud.tentativas}")
    if aud.erros_encontrados:
        print(f"  Erros    : {aud.erros_encontrados}")
    if aud.fontes_contexto:
        print(f"  Fontes   : {aud.fontes_contexto}")


def _verificar_arquivos(*paths: Path) -> bool:
    ok = True
    for p in paths:
        if not p.exists():
            logger.error("Arquivo não encontrado: %s", p)
            ok = False
    return ok


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Testa o pipeline de geração de textos para atividades selecionadas."
    )
    parser.add_argument(
        "--atividades", "-a",
        nargs="+",
        metavar="CODIGO",
        help="Códigos das atividades a processar (ex: 1.1 2.1 4.3). Sem este argumento, processa todas.",
    )
    parser.add_argument(
        "--modelo", "-m",
        default="gemini-2.5-flash-lite",
        help="Modelo LLM a usar (padrão: gemini-2.5-flash-lite)",
    )
    parser.add_argument(
        "--tentativas", "-t",
        type=int,
        default=3,
        help="Número máximo de tentativas por atividade (padrão: 3)",
    )
    parser.add_argument(
        "--relatorio",
        default=str(RELATORIO_PROGRESSO),
        help=f"Caminho para o JSON de progresso (padrão: {RELATORIO_PROGRESSO.relative_to(ROOT)})",
    )
    parser.add_argument(
        "--snapshot",
        default=str(CLICKUP_SNAPSHOT),
        help=f"Caminho para o snapshot enriquecido do ClickUp (padrão: {CLICKUP_SNAPSHOT.relative_to(ROOT)})",
    )
    parser.add_argument(
        "--termo",
        default=str(TERMO_PDF),
        help=f"Caminho para o PDF do Termo de Outorga (padrão: {TERMO_PDF.relative_to(ROOT)})",
    )
    parser.add_argument(
        "--output",
        default=str(OUTPUT_TESTE),
        help=f"Caminho para salvar o resultado parcial (padrão: {OUTPUT_TESTE.relative_to(ROOT)})",
    )
    args = parser.parse_args()

    relatorio_path = Path(args.relatorio)
    snapshot_path  = Path(args.snapshot)
    termo_path     = Path(args.termo)
    output_path    = Path(args.output)

    # ── Valida existência dos arquivos de entrada
    if not _verificar_arquivos(relatorio_path, snapshot_path, termo_path):
        print("\n❌ Arquivos de entrada ausentes. Verifique os caminhos acima.")
        sys.exit(1)

    # ── Garante que o diretório de output existe
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # ── Configura cliente LLM (Gemini via base_url OpenAI)
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        logger.error(
            "Variável GEMINI_API_KEY não encontrada.\n"
            "  Defina no ambiente ou crie um arquivo .env na raiz do projeto com:\n"
            "  GEMINI_API_KEY=sua_chave_aqui"
        )
        sys.exit(1)

    import openai
    llm_client = openai.OpenAI(
        api_key=api_key,
        base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
    )

    filtro = args.atividades  # None = processa tudo

    print(_separador())
    print(f"  Pipeline de textos — TESTE PARCIAL")
    print(f"  Modelo          : {args.modelo}")
    print(f"  Atividades      : {filtro or 'TODAS'}")
    print(f"  Relatório       : {relatorio_path.name}")
    print(f"  Snapshot ClickUp: {snapshot_path.name}")
    print(f"  Termo de Outorga: {termo_path.name}")
    print(_separador())

    # ── Importa funções do use case (fonte única de verdade)
    from app.application.use_cases.gerar_textos_atividades import (
        _iter_atividades,
        _get_codigo,
        _get_ativ_id,
        _get_titulo_canonical,
        _get_progresso,
        _build_snapshot_indexes,
        _buscar_task,
    )
    from app.domain.context.builders import montar_contexto
    from app.domain.reporting.canonical_schemas import ProgressoAtividadeCanonico

    # ── Pré-visualização dos contextos (antes de chamar a LLM)
    print("\n▶ Montando contextos das atividades...")

    with open(relatorio_path, "r", encoding="utf-8") as f:
        relatorio = json.load(f)
    with open(snapshot_path, "r", encoding="utf-8") as f:
        snapshot_raw = json.load(f)

    idx_by_id, idx_by_codigo = _build_snapshot_indexes(snapshot_raw)
    print(f"  Snapshot: {len(idx_by_id)} tasks indexadas por task_id, {len(idx_by_codigo)} por código.")

    # Diagnóstico: quantas atividades existem no JSON antes do filtro
    todos_codigos = sorted({_get_codigo(a) for a in _iter_atividades(relatorio) if _get_codigo(a)})
    print(f"  Relatório: {len(todos_codigos)} atividades encontradas no JSON (chaves raiz: {list(relatorio.keys())})")

    if filtro:
        ausentes = [c for c in filtro if c not in todos_codigos]
        if ausentes:
            print(f"  ⚠️  Códigos solicitados não encontrados no JSON: {ausentes}")
            print(f"     Códigos disponíveis: {todos_codigos}")

    contextos_preview = []
    for atividade in _iter_atividades(relatorio):
        codigo  = _get_codigo(atividade)
        ativ_id = _get_ativ_id(atividade)
        if filtro and codigo not in filtro:
            continue

        task = _buscar_task(ativ_id, codigo, idx_by_id, idx_by_codigo)
        titulo = task.base.name if task else _get_titulo_canonical(atividade, codigo)

        prog_raw = _get_progresso(atividade)
        progresso = None
        if prog_raw and isinstance(prog_raw, dict):
            try:
                progresso = ProgressoAtividadeCanonico(**prog_raw)
            except Exception:
                pass

        ctx = montar_contexto(
            codigo=codigo,
            titulo=titulo,
            task=task,
            pdf_atv=None,
            progresso=progresso,
        )
        contextos_preview.append(ctx)
        _exibir_contexto(ctx)

    if not contextos_preview:
        print(f"\n⚠️  Nenhuma atividade encontrada com filtro {filtro}.")
        print(f"   Códigos disponíveis no relatório: {todos_codigos}")
        sys.exit(0)

    # ── Executa o pipeline completo diretamente
    print(f"\n▶ Executando pipeline para {len(contextos_preview)} atividade(s)...")
    from app.application.use_cases import gerar_textos_atividades

    resultado_final = gerar_textos_atividades.executar(
        termo_pdf_path=termo_path,
        relatorio_progresso_path=relatorio_path,
        clickup_snapshot_path=snapshot_path,
        output_path=output_path,
        llm_client=llm_client,
        model=args.modelo,
        max_tentativas=args.tentativas,
        atividades_filtro=filtro,
    )

    # ── Exibe resultados
    print("\n" + _separador("RESULTADOS GERADOS"))

    # Suporte a ambas as estruturas de saída do relatorio_final
    def _iter_atividades_resultado(rel: dict):
        for meta in rel.get("metas", []):
            yield from meta.get("atividades", [])
        relatorio_inner = rel.get("relatorio", {})
        secoes = relatorio_inner.get("secoes_fixas", {})
        tabela = secoes.get("3_tabela_resumo_execucao_cronograma_fisico", {})
        for meta in tabela.get("itens_meta_atividade", []):
            yield from meta.get("atividades", [])
        for item in rel.get("itens", []):
            yield from item.get("atividades", [])

    for atv in _iter_atividades_resultado(resultado_final):
        codigo = (
            atv.get("numero_atividade_original")
            or atv.get("numero_atividade")
            or atv.get("codigo", "?")
        )
        if filtro and codigo not in filtro:
            continue
        if not atv.get("desenvolvimento"):
            continue

        from app.domain.ai.schemas import ResultadoAtividade, AuditoriaAtividade, TextosGerados, StatusValidacao
        aud_raw = atv.get("_auditoria", {})
        resultado_mock = ResultadoAtividade(
            atividade_id=codigo,
            meta_codigo=codigo.split(".")[0] if "." in codigo else codigo,
            titulo=atv.get("titulo", ""),
            textos=TextosGerados(
                desenvolvimento=atv.get("desenvolvimento", ""),
                resultados=atv.get("resultados", ""),
                justificativa=atv.get("justificativa", ""),
            ),
            auditoria=AuditoriaAtividade(
                atividade_id=codigo,
                tentativas=aud_raw.get("tentativas", 1),
                status_final=StatusValidacao(aud_raw.get("status_validacao", "aprovado")),
                erros_encontrados=aud_raw.get("erros", []),
                fontes_contexto=aud_raw.get("fontes_contexto", []),
            ),
        )
        _exibir_resultado(resultado_mock)

    print(_separador())
    print(f"\n✅ Resultado parcial salvo em: {output_path}")
    print("   Para inspecionar: code data/output/teste_textos_parcial.json\n")


if __name__ == "__main__":
    main()
