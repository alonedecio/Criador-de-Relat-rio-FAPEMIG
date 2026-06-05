"""Renderizador HTML a partir do relatório canônico JSON.

Gera HTML navegável para as seções do Relatório de Acompanhamento Técnico:
  - Seção 3: Tabela resumo da execução do cronograma físico
  - Seção 4: Execução detalhada por meta física (desenvolvimento, resultados, justificativa)

O HTML é autocontido (CSS inline) para facilitar cópia para Word/sistema de relatórios.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any


# ─────────────────────────────────────────────────────────────────────────────
# helpers internos
# ─────────────────────────────────────────────────────────────────────────────

def _pct(value: Any, fallback: str = "—") -> str:
    """Formata percentual como string com símbolo %. Aceita float, int ou str."""
    try:
        return f"{float(value):.0f}%"
    except (TypeError, ValueError):
        return fallback


def _safe(value: Any, fallback: str = "—") -> str:
    if value is None or str(value).strip() == "":
        return fallback
    return str(value).strip()


def _status_badge(situacao: str | None, atrasada: bool | None) -> str:
    """Retorna um badge HTML colorido baseado no status da atividade."""
    s = (situacao or "").lower().replace(" ", "_")
    if "concluida" in s or "concluído" in s:
        cor, texto = "#2d7a2d", "Concluída"
    elif "atrasada" in s or atrasada:
        cor, texto = "#b84c00", "Em Atraso"
    elif "em_progresso" in s or "em progresso" in s:
        cor, texto = "#1a6a9a", "Em Progresso"
    elif "nao_iniciada" in s or "não iniciada" in s:
        cor, texto = "#888", "Não Iniciada"
    else:
        cor, texto = "#555", _safe(situacao, "—")
    return (
        f'<span style="background:{cor};color:#fff;padding:2px 8px;'
        f'border-radius:3px;font-size:11px;font-weight:600;'
        f'white-space:nowrap">{texto}</span>'
    )


def _barra_progresso(realizado: Any, previsto: Any) -> str:
    """Retorna uma barra de progresso dupla (previsto vs realizado) em HTML."""
    try:
        r = min(float(realizado or 0), 100)
        p = min(float(previsto or 0), 100)
    except (TypeError, ValueError):
        return ""
    cor_r = "#1a6a9a" if r >= p * 0.8 else "#b84c00"
    return (
        f'<div style="position:relative;height:14px;background:#e8e8e8;'
        f'border-radius:3px;overflow:hidden;min-width:120px">'
        f'<div title="Previsto: {p:.0f}%" style="position:absolute;height:100%;'
        f'width:{p:.1f}%;background:#ccc;border-radius:3px"></div>'
        f'<div title="Realizado: {r:.0f}%" style="position:absolute;height:100%;'
        f'width:{r:.1f}%;background:{cor_r};border-radius:3px;opacity:.85"></div>'
        f'</div>'
        f'<div style="font-size:10px;color:#555;margin-top:2px">'
        f'{r:.0f}% real. / {p:.0f}% prev.</div>'
    )


# ─────────────────────────────────────────────────────────────────────────────
# CSS base (inline, compatível com Word ao colar)
# ─────────────────────────────────────────────────────────────────────────────

_CSS = """
:root {
  --bg: #f5f5f3;
  --surface: #ffffff;
  --border: #d4d1ca;
  --primary: #01696f;
  --primary-dark: #0c4e54;
  --text: #28251d;
  --muted: #6b6a65;
  --faint: #b0aea9;
  --warn: #b84c00;
  --ok: #2d7a2d;
  --radius: 6px;
  --shadow: 0 1px 4px rgba(0,0,0,.08);
}
* { box-sizing: border-box; margin: 0; padding: 0; }
html { font-size: 14px; }
body {
  font-family: 'Segoe UI', Arial, sans-serif;
  background: var(--bg);
  color: var(--text);
  line-height: 1.55;
  padding: 24px 16px;
}
.page-wrap { max-width: 1100px; margin: 0 auto; }

/* ── Cabeçalho ───────────────────────────────── */
.report-header {
  background: var(--primary);
  color: #fff;
  padding: 20px 28px;
  border-radius: var(--radius);
  margin-bottom: 28px;
}
.report-header h1 { font-size: 1.25rem; font-weight: 700; }
.report-header .subtitle { font-size: .85rem; opacity: .85; margin-top: 4px; }
.report-header .meta { font-size: .8rem; opacity: .7; margin-top: 8px; }

/* ── Navegação âncoras ───────────────────────── */
.toc {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 16px 20px;
  margin-bottom: 28px;
  box-shadow: var(--shadow);
}
.toc h2 { font-size: .95rem; color: var(--primary); margin-bottom: 10px; }
.toc ul { list-style: none; display: flex; flex-wrap: wrap; gap: 6px 16px; }
.toc ul li a {
  color: var(--primary);
  text-decoration: none;
  font-size: .85rem;
  padding: 3px 0;
  border-bottom: 1px solid transparent;
  transition: border-color .15s;
}
.toc ul li a:hover { border-color: var(--primary); }

/* ── Seção ───────────────────────────────────── */
.section {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  box-shadow: var(--shadow);
  margin-bottom: 32px;
  overflow: hidden;
}
.section-header {
  background: var(--primary);
  color: #fff;
  padding: 12px 20px;
  display: flex;
  align-items: baseline;
  gap: 10px;
}
.section-header .sec-num {
  font-size: 1.1rem;
  font-weight: 800;
  opacity: .6;
  min-width: 28px;
}
.section-header .sec-title { font-size: 1rem; font-weight: 600; }
.section-body { padding: 20px; }

/* ── Meta ────────────────────────────────────── */
.meta-block {
  border: 1px solid var(--border);
  border-radius: var(--radius);
  margin-bottom: 24px;
  overflow: hidden;
}
.meta-title-bar {
  background: #e8f0ef;
  border-bottom: 1px solid var(--border);
  padding: 10px 16px;
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}
.meta-num {
  font-weight: 800;
  color: var(--primary);
  font-size: 1rem;
  min-width: 32px;
}
.meta-title-text {
  font-weight: 600;
  color: var(--text);
  flex: 1;
  font-size: .9rem;
}
.meta-progress { margin-left: auto; min-width: 160px; }

/* ── Atividade ───────────────────────────────── */
.atividade-block {
  border-top: 1px solid var(--border);
  padding: 16px;
}
.atividade-block:first-child { border-top: none; }
.atv-header {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  flex-wrap: wrap;
  margin-bottom: 12px;
}
.atv-num {
  font-weight: 700;
  color: var(--primary-dark);
  font-size: .9rem;
  min-width: 36px;
  padding-top: 2px;
}
.atv-title {
  font-weight: 600;
  color: var(--text);
  font-size: .875rem;
  flex: 1;
}
.atv-badges { display: flex; gap: 6px; align-items: center; flex-wrap: wrap; }

/* ── Campo de texto (desenvolvimento / resultados / justificativa) */
.atv-fields {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 12px;
  margin-top: 8px;
}
.field-box {
  background: #fafafa;
  border: 1px solid #e4e2de;
  border-radius: 4px;
  padding: 10px 12px;
}
.field-label {
  font-size: .7rem;
  font-weight: 700;
  letter-spacing: .05em;
  text-transform: uppercase;
  color: var(--muted);
  margin-bottom: 5px;
}
.field-text {
  font-size: .825rem;
  color: var(--text);
  line-height: 1.6;
}
.field-text.empty { color: var(--faint); font-style: italic; }

/* ── Indicador físico ────────────────────────── */
.indicador {
  font-size: .775rem;
  color: var(--muted);
  margin-top: 4px;
}

/* ── Tabela resumo ───────────────────────────── */
table.resumo {
  width: 100%;
  border-collapse: collapse;
  font-size: .8rem;
}
table.resumo th {
  background: var(--primary);
  color: #fff;
  padding: 8px 10px;
  text-align: left;
  font-weight: 600;
  white-space: nowrap;
}
table.resumo td {
  padding: 7px 10px;
  border-bottom: 1px solid #eee;
  vertical-align: middle;
}
table.resumo tr:hover td { background: #f0f7f7; }
table.resumo tr.meta-row td {
  background: #e8f0ef;
  font-weight: 700;
  font-size: .85rem;
  color: var(--primary-dark);
}
table.resumo .num { text-align: center; }

/* ── Aviso campos manuais ────────────────────── */
.manual-hint {
  background: #fff8e6;
  border: 1px solid #f0c040;
  border-radius: var(--radius);
  padding: 10px 14px;
  font-size: .8rem;
  color: #7a5c00;
  margin-bottom: 20px;
}
.manual-hint strong { display: block; margin-bottom: 2px; }

/* ── Responsivo ──────────────────────────────── */
@media (max-width: 640px) {
  .atv-fields { grid-template-columns: 1fr; }
  table.resumo th, table.resumo td { padding: 5px 6px; }
}
"""


# ─────────────────────────────────────────────────────────────────────────────
# Seção 3 — Tabela resumo
# ─────────────────────────────────────────────────────────────────────────────

def _render_secao3(metas: list[dict]) -> str:
    """Gera o HTML da Seção 3 (tabela resumo do cronograma físico)."""
    rows = []
    for meta in metas:
        num_meta = _safe(meta.get("numero_meta") or meta.get("numero"))
        titulo_meta = _safe(meta.get("titulo_meta") or meta.get("titulo"), "Meta sem título")
        p_meta = meta.get("progresso") or {}
        rows.append(
            f'<tr class="meta-row">'
            f'<td colspan="3"><strong>Meta {num_meta}</strong> — {titulo_meta}</td>'
            f'<td class="num">{_pct(p_meta.get("previsto_percentual"))}</td>'
            f'<td class="num">{_pct(p_meta.get("realizado_percentual"))}</td>'
            f'<td class="num">{_pct(p_meta.get("previsto_percentual"))}</td>'
            f'<td class="num">{_pct(p_meta.get("realizado_percentual"))}</td>'
            f'</tr>'
        )
        for atv in meta.get("atividades", []):
            codigo = _safe(atv.get("numero_atividade_original") or atv.get("numero_atividade") or atv.get("codigo"))
            titulo_atv = _safe(atv.get("titulo"), "—")
            indicador = _safe(atv.get("indicador_fisico"), "—")
            p = atv.get("progresso") or {}
            rows.append(
                f'<tr>'
                f'<td class="num" style="color:#888">{codigo}</td>'
                f'<td>{titulo_atv}</td>'
                f'<td style="color:var(--muted);font-size:.75rem">{indicador}</td>'
                f'<td class="num">{_pct(p.get("previsto_percentual"))}</td>'
                f'<td class="num">{_pct(p.get("realizado_percentual"))}</td>'
                f'<td class="num">{_pct(p.get("previsto_percentual"))}</td>'
                f'<td class="num">{_pct(p.get("realizado_percentual"))}</td>'
                f'</tr>'
            )

    return f"""
<div class="section" id="secao3">
  <div class="section-header">
    <span class="sec-num">3.</span>
    <span class="sec-title">Tabela resumo da execução do cronograma físico do projeto</span>
  </div>
  <div class="section-body">
    <div class="manual-hint">
      <strong>⚠ Campos de preenchimento manual</strong>
      Duração prevista/efetiva do projeto e percentuais globais do projeto devem ser inseridos manualmente no sistema do órgão financiador.
    </div>
    <table class="resumo">
      <thead>
        <tr>
          <th style="width:50px">Item</th>
          <th>Meta / Atividade</th>
          <th>Indicador Físico</th>
          <th colspan="2" style="text-align:center;background:#015f65">Executado no período</th>
          <th colspan="2" style="text-align:center;background:#024a50">Acumulado</th>
        </tr>
        <tr style="background:#024a50">
          <th></th><th></th><th></th>
          <th class="num">Prev. (%)</th>
          <th class="num">Real. (%)</th>
          <th class="num">Prev. (%)</th>
          <th class="num">Real. (%)</th>
        </tr>
      </thead>
      <tbody>{''.join(rows)}</tbody>
    </table>
  </div>
</div>
"""


# ─────────────────────────────────────────────────────────────────────────────
# Seção 4 — Execução detalhada por meta
# ─────────────────────────────────────────────────────────────────────────────

def _render_atividade(atv: dict) -> str:
    """Gera o HTML de uma atividade com seus textos."""
    codigo = _safe(atv.get("numero_atividade_original") or atv.get("numero_atividade") or atv.get("codigo"))
    titulo = _safe(atv.get("titulo"), "Atividade sem título")
    indicador = _safe(atv.get("indicador_fisico"), "")
    p = atv.get("progresso") or {}
    situacao = p.get("situacao_prazo") or ""
    atrasada = p.get("atrasada", False)

    desenvolvimento = _safe(atv.get("desenvolvimento"), "")
    resultados = _safe(atv.get("resultados"), "")
    justificativa = _safe(atv.get("justificativa"), "")
    has_texts = desenvolvimento or resultados or justificativa

    barra = _barra_progresso(p.get("realizado_percentual"), p.get("previsto_percentual"))
    badge = _status_badge(situacao, atrasada)

    # Colunas de progresso
    prev = _pct(p.get("previsto_percentual"))
    real = _pct(p.get("realizado_percentual"))
    prog_inline = (
        f'<span style="font-size:.75rem;color:var(--muted)">'
        f'Prev. {prev} · Real. {real}</span>'
    )

    campo_dev = (
        f'<div class="field-box">'
        f'<div class="field-label">📝 Desenvolvimento da atividade</div>'
        f'<div class="field-text{"" if desenvolvimento else " empty"}">{desenvolvimento or "Não gerado ainda."}</div>'
        f'</div>'
    )
    campo_res = (
        f'<div class="field-box">'
        f'<div class="field-label">📊 Resultados</div>'
        f'<div class="field-text{"" if resultados else " empty"}">{resultados or "Não gerado ainda."}</div>'
        f'</div>'
    )
    campo_jus = (
        f'<div class="field-box" style="grid-column: 1 / -1">'
        f'<div class="field-label">⏰ Justificativa de atraso / adiantamento</div>'
        f'<div class="field-text{"" if justificativa else " empty"}">{justificativa or "Não gerado ainda."}</div>'
        f'</div>'
    )

    return f"""
<div class="atividade-block" id="atv-{codigo.replace('.', '-')}">
  <div class="atv-header">
    <span class="atv-num">{codigo}</span>
    <span class="atv-title">{titulo}</span>
    <div class="atv-badges">
      {badge}
      {prog_inline}
    </div>
  </div>
  {'<div class="indicador">🎯 Indicador: ' + indicador + '</div>' if indicador else ''}
  <div style="margin:8px 0">{barra}</div>
  <div class="atv-fields">
    {campo_dev}
    {campo_res}
    {campo_jus}
  </div>
</div>
"""


def _render_secao4(metas: list[dict]) -> str:
    """Gera o HTML da Seção 4 (execução detalhada por meta física)."""
    blocos = []
    for i, meta in enumerate(metas, start=1):
        num_meta = _safe(meta.get("numero_meta") or meta.get("numero"), str(i))
        titulo_meta = _safe(meta.get("titulo_meta") or meta.get("titulo"), "Meta sem título")
        p_meta = meta.get("progresso") or {}
        barra_meta = _barra_progresso(
            p_meta.get("realizado_percentual"),
            p_meta.get("previsto_percentual"),
        )
        atividades_html = "".join(_render_atividade(a) for a in meta.get("atividades", []))

        blocos.append(f"""
<div class="meta-block" id="meta-{num_meta.replace('.', '-')}">
  <div class="meta-title-bar">
    <span class="meta-num">Meta {num_meta}</span>
    <span class="meta-title-text">{titulo_meta}</span>
    <div class="meta-progress">{barra_meta}</div>
  </div>
  {atividades_html}
</div>
""")

    return f"""
<div class="section" id="secao4">
  <div class="section-header">
    <span class="sec-num">4.</span>
    <span class="sec-title">Execução do cronograma físico do projeto</span>
  </div>
  <div class="section-body">
    {''.join(blocos)}
  </div>
</div>
"""


# ─────────────────────────────────────────────────────────────────────────────
# Cabeçalho e TOC
# ─────────────────────────────────────────────────────────────────────────────

def _render_header(relatorio: dict) -> str:
    meta_dados = relatorio.get("metadata") or {}
    resumo = relatorio.get("resumo_projeto") or {}
    titulo = _safe(
        meta_dados.get("titulo_projeto") or resumo.get("titulo_projeto"),
        "Relatório de Acompanhamento Técnico",
    )
    periodo = _safe(meta_dados.get("periodo_relatorio"), "")
    gerado_em = datetime.now().strftime("%d/%m/%Y às %H:%M")
    return f"""
<div class="report-header">
  <h1>Relatório de Acompanhamento Técnico</h1>
  <div class="subtitle">{titulo}</div>
  <div class="meta">
    {'Período: ' + periodo + ' &nbsp;·&nbsp; ' if periodo else ''}
    Gerado em: {gerado_em} &nbsp;·&nbsp; Gerador de Relatórios de Agências de Fomento
  </div>
</div>
"""


def _render_toc(metas: list[dict]) -> str:
    itens = [
        '<li><a href="#secao3">3. Tabela resumo do cronograma</a></li>',
        '<li><a href="#secao4">4. Execução por meta física</a></li>',
    ]
    for meta in metas:
        num = _safe(meta.get("numero_meta") or meta.get("numero"))
        titulo = _safe(meta.get("titulo_meta") or meta.get("titulo"), "")[:60]
        itens.append(f'<li><a href="#meta-{num.replace(".", "-")}">↳ Meta {num}: {titulo}…</a></li>')
    return f"""
<nav class="toc">
  <h2>Navegação rápida</h2>
  <ul>{''.join(itens)}</ul>
</nav>
"""


# ─────────────────────────────────────────────────────────────────────────────
# Ponto de entrada principal
# ─────────────────────────────────────────────────────────────────────────────

def gerar_html(relatorio: dict) -> str:
    """Gera o HTML completo (Seções 3 e 4) a partir do JSON canônico.

    Args:
        relatorio: dicionário carregado do JSON canônico
                   (relatorio_final_completo.json ou teste_textos_parcial.json)

    Returns:
        String HTML completa e autocontida.
    """
    metas: list[dict] = relatorio.get("metas", [])

    # Suporte à estrutura legado dos notebooks (chave relatorio > metas)
    if not metas:
        inner = relatorio.get("relatorio", {})
        secoes = inner.get("secoes_fixas", {})
        tabela = secoes.get("3_tabela_resumo_execucao_cronograma_fisico", {})
        metas = tabela.get("itens_meta_atividade", [])

    header = _render_header(relatorio)
    toc = _render_toc(metas)
    sec3 = _render_secao3(metas)
    sec4 = _render_secao4(metas)

    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Relatório de Acompanhamento Técnico</title>
  <style>{_CSS}</style>
</head>
<body>
<div class="page-wrap">
  {header}
  {toc}
  {sec3}
  {sec4}
</div>
</body>
</html>"""


def salvar_html(relatorio: dict, output_path: Path) -> Path:
    """Gera e salva o HTML no caminho especificado."""
    html = gerar_html(relatorio)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8")
    return output_path
