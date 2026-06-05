"""Renderizador HTML a partir do relatório canônico JSON.

Gera HTML navegável para as seções do Relatório de Acompanhamento Técnico:
  - Seção 3: Tabela resumo da execução do cronograma físico
  - Seção 4: Execução detalhada por meta física (desenvolvimento, resultados, justificativa)

O HTML é autocontido (CSS inline) para facilitar cópia para Word/sistema de relatórios.

Mapeamento real do JSON canônico (relatorio_final_completo.json):
  meta.item                       → número da meta (ex: "1", "2")
  meta.meta_nome                  → título da meta
  meta.percentual_meta            → % realizado da meta (float direto)
  meta.progresso                  → dict com campos de progresso da meta
  atividade.numero_atividade_original → código ex: "1.1"
  atividade.titulo / titulo_original  → título da atividade
  atividade.indicador_fisico      → indicador físico
  atividade.percentual_realizado  → % realizado (float direto)
  atividade.progresso             → dict com previsto_percentual, realizado_percentual, situacao_prazo, atrasada
  atividade.desenvolvimento       → texto gerado pela IA (só no JSON com textos)
  atividade.resultados            → texto gerado pela IA
  atividade.justificativa         → texto gerado pela IA
  atividade.texto                 → dict alternativo com as mesmas chaves (fallback)
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
        v = float(value)
        return f"{v:.0f}%"
    except (TypeError, ValueError):
        return fallback


def _safe(value: Any, fallback: str = "—") -> str:
    if value is None or str(value).strip() == "":
        return fallback
    return str(value).strip()


def _get_texto(atv: dict, campo: str) -> str:
    """Busca texto da atividade: primeiro na raiz, depois dentro de atv['texto']."""
    valor = atv.get(campo)
    if valor and str(valor).strip():
        return str(valor).strip()
    # fallback: bloco aninhado 'texto' gerado pelo pipeline de IA
    texto_dict = atv.get("texto") or {}
    if isinstance(texto_dict, dict):
        valor2 = texto_dict.get(campo)
        if valor2 and str(valor2).strip():
            return str(valor2).strip()
    return ""


def _get_num_meta(meta: dict, idx: int) -> str:
    """Resolve o número da meta a partir de meta.item ou fallback numérico."""
    return _safe(meta.get("item"), str(idx))


def _get_titulo_meta(meta: dict) -> str:
    """Resolve o título da meta tentando múltiplas chaves."""
    return _safe(
        meta.get("meta_nome") or meta.get("titulo_meta") or meta.get("titulo"),
        "Meta sem título",
    )


def _get_progresso_meta(meta: dict) -> tuple[float | None, float | None]:
    """Retorna (realizado, previsto) da meta."""
    p = meta.get("progresso") or {}
    realizado = p.get("realizado_percentual") if p else None
    previsto = p.get("previsto_percentual") if p else None
    # fallback: percentual_meta é o realizado direto, sem previsto
    if realizado is None:
        try:
            realizado = float(meta.get("percentual_meta") or 0)
        except (TypeError, ValueError):
            realizado = None
    return realizado, previsto


def _get_progresso_atv(atv: dict) -> dict:
    """Retorna o dict de progresso da atividade com fallbacks."""
    p = atv.get("progresso") or {}
    # Se não tiver previsto/realizado no dict, tenta percentual_realizado direto
    if not p.get("realizado_percentual") and atv.get("percentual_realizado") is not None:
        p = dict(p)
        p["realizado_percentual"] = atv["percentual_realizado"]
    return p


def _status_badge(situacao: str | None, atrasada: bool | None, status_clickup: str | None = None) -> str:
    """Retorna um badge HTML colorido baseado no status da atividade."""
    s = (situacao or status_clickup or "").lower().replace(" ", "_")
    if "conclu" in s:
        cor, texto = "#2d7a2d", "Concluída"
    elif "atraso" in s or atrasada:
        cor, texto = "#b84c00", "Em Atraso"
    elif "progresso" in s or "andamento" in s or "open" in s:
        cor, texto = "#1a6a9a", "Em Progresso"
    elif "nao_inic" in s or "não inic" in s or "nao inic" in s:
        cor, texto = "#888", "Não Iniciada"
    elif s:
        cor, texto = "#555", _safe(situacao or status_clickup, "—")
    else:
        return ""
    return (
        f'<span style="background:{cor};color:#fff;padding:2px 8px;'
        f'border-radius:3px;font-size:11px;font-weight:600;'
        f'white-space:nowrap">{texto}</span>'
    )


def _barra_progresso(realizado: Any, previsto: Any) -> str:
    """Retorna uma barra de progresso dupla (previsto cinza vs realizado colorido)."""
    try:
        r = min(float(realizado or 0), 100)
    except (TypeError, ValueError):
        r = 0
    try:
        p = min(float(previsto or 0), 100)
    except (TypeError, ValueError):
        p = 0

    # Se não tem previsto, barra simples só com realizado
    cor_r = "#1a6a9a" if (p == 0 or r >= p * 0.8) else "#b84c00"
    barra_prev = (
        f'<div title="Previsto: {p:.0f}%" style="position:absolute;height:100%;'
        f'width:{p:.1f}%;background:#c5d8d6;border-radius:3px"></div>'
    ) if p > 0 else ""

    return (
        f'<div style="position:relative;height:12px;background:#e8e8e8;'
        f'border-radius:3px;overflow:hidden;min-width:120px">'
        f'{barra_prev}'
        f'<div title="Realizado: {r:.0f}%" style="position:absolute;height:100%;'
        f'width:{r:.1f}%;background:{cor_r};border-radius:3px;opacity:.9"></div>'
        f'</div>'
        f'<div style="font-size:10px;color:#666;margin-top:2px">'
        f'{r:.0f}% realizado{(" / " + str(int(p)) + "% previsto") if p > 0 else ""}'
        f'</div>'
    )


# ─────────────────────────────────────────────────────────────────────────────
# CSS base (autocontido, sem dependências externas)
# ─────────────────────────────────────────────────────────────────────────────

_CSS = """
:root {
  --bg: #f4f4f2;
  --surface: #ffffff;
  --border: #d6d3ce;
  --primary: #01696f;
  --primary-dark: #0c4e54;
  --primary-light: #e6f0ef;
  --text: #28251d;
  --muted: #6b6a65;
  --faint: #b0aea9;
  --warn: #b84c00;
  --ok: #2d7a2d;
  --radius: 6px;
  --shadow: 0 1px 3px rgba(0,0,0,.07), 0 1px 2px rgba(0,0,0,.04);
}
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
html { font-size: 14px; scroll-behavior: smooth; }
body {
  font-family: 'Segoe UI', system-ui, Arial, sans-serif;
  background: var(--bg);
  color: var(--text);
  line-height: 1.55;
  padding: 28px 16px 60px;
}
.page-wrap { max-width: 1080px; margin: 0 auto; }

/* ── Cabeçalho ─────────────────────────────────── */
.report-header {
  background: var(--primary);
  color: #fff;
  padding: 22px 28px 18px;
  border-radius: var(--radius);
  margin-bottom: 24px;
  box-shadow: 0 2px 8px rgba(1,105,111,.25);
}
.report-header h1 { font-size: 1.2rem; font-weight: 700; letter-spacing: -.01em; }
.report-header .subtitle {
  font-size: .82rem;
  opacity: .88;
  margin-top: 5px;
  max-width: 75ch;
  line-height: 1.4;
}
.report-header .meta-info {
  font-size: .75rem;
  opacity: .65;
  margin-top: 10px;
  display: flex;
  flex-wrap: wrap;
  gap: 4px 16px;
}

/* ── Navegação âncoras ─────────────────────────── */
.toc {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 14px 18px;
  margin-bottom: 24px;
  box-shadow: var(--shadow);
}
.toc-title {
  font-size: .8rem;
  font-weight: 700;
  letter-spacing: .06em;
  text-transform: uppercase;
  color: var(--muted);
  margin-bottom: 10px;
}
.toc-links {
  display: flex;
  flex-wrap: wrap;
  gap: 4px 8px;
  list-style: none;
}
.toc-links li a {
  display: inline-block;
  color: var(--primary);
  text-decoration: none;
  font-size: .8rem;
  padding: 3px 8px;
  border-radius: 3px;
  border: 1px solid var(--primary-light);
  background: var(--primary-light);
  transition: background .12s, border-color .12s;
}
.toc-links li a:hover {
  background: #cfe0de;
  border-color: #b0cccb;
}

/* ── Seção ─────────────────────────────────────── */
.section {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  box-shadow: var(--shadow);
  margin-bottom: 28px;
  overflow: hidden;
}
.section-header {
  background: var(--primary);
  color: #fff;
  padding: 11px 20px;
  display: flex;
  align-items: baseline;
  gap: 8px;
}
.sec-num { font-size: 1rem; font-weight: 800; opacity: .55; min-width: 24px; }
.sec-title { font-size: .95rem; font-weight: 600; }
.section-body { padding: 20px; }

/* ── Aviso campos manuais ──────────────────────── */
.manual-hint {
  background: #fffbeb;
  border: 1px solid #f0c040;
  border-left: 4px solid #f0c040;
  border-radius: 4px;
  padding: 10px 14px;
  font-size: .78rem;
  color: #7a5c00;
  margin-bottom: 18px;
  line-height: 1.5;
}
.manual-hint strong { display: block; margin-bottom: 2px; font-size: .8rem; }

/* ── Tabela resumo ─────────────────────────────── */
table.resumo {
  width: 100%;
  border-collapse: collapse;
  font-size: .78rem;
}
table.resumo th {
  background: var(--primary);
  color: #fff;
  padding: 8px 10px;
  text-align: left;
  font-weight: 600;
  white-space: nowrap;
  border-right: 1px solid rgba(255,255,255,.15);
}
table.resumo td {
  padding: 7px 10px;
  border-bottom: 1px solid #eeecе9;
  vertical-align: middle;
  border-right: 1px solid #f0ede9;
}
table.resumo tr:last-child td { border-bottom: none; }
table.resumo tr:hover td { background: #f2f8f7; }
table.resumo tr.meta-row td {
  background: var(--primary-light);
  font-weight: 700;
  font-size: .82rem;
  color: var(--primary-dark);
  border-top: 2px solid #b8d4d2;
}
table.resumo .num { text-align: center; font-variant-numeric: tabular-nums; }

/* ── Meta block ────────────────────────────────── */
.meta-block {
  border: 1px solid var(--border);
  border-radius: var(--radius);
  margin-bottom: 20px;
  overflow: hidden;
}
.meta-block:last-child { margin-bottom: 0; }
.meta-title-bar {
  background: var(--primary-light);
  border-bottom: 1px solid var(--border);
  padding: 10px 16px;
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}
.meta-num {
  font-weight: 800;
  color: var(--primary);
  font-size: .95rem;
  white-space: nowrap;
}
.meta-title-text {
  font-weight: 600;
  color: var(--text);
  flex: 1;
  font-size: .875rem;
  line-height: 1.4;
}
.meta-progress-wrap { margin-left: auto; min-width: 150px; }

/* ── Atividade block ───────────────────────────── */
.atividade-block {
  border-top: 1px solid #eeecе9;
  padding: 14px 16px 16px;
}
.atv-header {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  flex-wrap: wrap;
  margin-bottom: 10px;
}
.atv-num {
  font-weight: 700;
  color: var(--primary-dark);
  font-size: .875rem;
  min-width: 34px;
  padding-top: 1px;
  white-space: nowrap;
}
.atv-title {
  font-weight: 600;
  color: var(--text);
  font-size: .85rem;
  flex: 1;
  line-height: 1.45;
}
.atv-badges { display: flex; gap: 6px; align-items: center; flex-wrap: wrap; margin-left: auto; }
.atv-pct { font-size: .75rem; color: var(--muted); white-space: nowrap; }
.indicador {
  font-size: .75rem;
  color: var(--muted);
  margin-bottom: 8px;
  line-height: 1.4;
}
.indicador strong { color: var(--primary-dark); }

/* ── Campos de texto ───────────────────────────── */
.atv-fields {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
  margin-top: 12px;
}
.field-box {
  background: #fafaf8;
  border: 1px solid #e6e4e0;
  border-radius: 4px;
  padding: 10px 12px;
}
.field-box.full-width { grid-column: 1 / -1; }
.field-label {
  font-size: .68rem;
  font-weight: 700;
  letter-spacing: .07em;
  text-transform: uppercase;
  color: var(--muted);
  margin-bottom: 6px;
}
.field-text {
  font-size: .82rem;
  color: var(--text);
  line-height: 1.65;
  white-space: pre-wrap;
}
.field-text.pending {
  color: var(--faint);
  font-style: italic;
  font-size: .78rem;
}

/* ── Responsivo ────────────────────────────────── */
@media (max-width: 700px) {
  .atv-fields { grid-template-columns: 1fr; }
  .field-box.full-width { grid-column: 1; }
  table.resumo { display: block; overflow-x: auto; }
  .meta-title-bar { flex-direction: column; align-items: flex-start; }
  .meta-progress-wrap { margin-left: 0; }
}
"""


# ─────────────────────────────────────────────────────────────────────────────
# Seção 3 — Tabela resumo do cronograma físico
# ─────────────────────────────────────────────────────────────────────────────

def _render_secao3(metas: list[dict]) -> str:
    rows = []
    for idx, meta in enumerate(metas, start=1):
        num_meta = _get_num_meta(meta, idx)
        titulo_meta = _get_titulo_meta(meta)
        realizado_meta, previsto_meta = _get_progresso_meta(meta)

        rows.append(
            f'<tr class="meta-row">'
            f'<td colspan="3"><strong>Meta {num_meta}</strong> — {titulo_meta}</td>'
            f'<td class="num">{_pct(previsto_meta)}</td>'
            f'<td class="num">{_pct(realizado_meta)}</td>'
            f'<td class="num">{_pct(previsto_meta)}</td>'
            f'<td class="num">{_pct(realizado_meta)}</td>'
            f'</tr>'
        )
        for atv in meta.get("atividades", []):
            codigo = _safe(atv.get("numero_atividade_original") or atv.get("numero_atividade"))
            titulo_atv = _safe(atv.get("titulo") or atv.get("titulo_original"), "—")
            indicador = _safe(atv.get("indicador_fisico"), "—")
            p = _get_progresso_atv(atv)
            prev_atv = _pct(p.get("previsto_percentual"))
            real_atv = _pct(p.get("realizado_percentual") or atv.get("percentual_realizado"))
            rows.append(
                f'<tr>'
                f'<td class="num" style="color:var(--muted)">{codigo}</td>'
                f'<td>{titulo_atv}</td>'
                f'<td style="color:var(--muted);font-size:.73rem;line-height:1.4">{indicador}</td>'
                f'<td class="num">{prev_atv}</td>'
                f'<td class="num">{real_atv}</td>'
                f'<td class="num">{prev_atv}</td>'
                f'<td class="num">{real_atv}</td>'
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
      <strong>⚠ Campos para preenchimento manual no sistema</strong>
      Duração prevista/efetiva do projeto, Mês/Ano início e fim, e percentuais globais do projeto
      devem ser inseridos diretamente no sistema do órgão financiador.
    </div>
    <div style="overflow-x:auto">
    <table class="resumo">
      <thead>
        <tr>
          <th style="width:48px">Item</th>
          <th>Meta / Atividade</th>
          <th>Indicador Físico</th>
          <th colspan="2" style="text-align:center;background:#015f65">Executado no período</th>
          <th colspan="2" style="text-align:center;background:#024a50">Acumulado</th>
        </tr>
        <tr style="background:#024a50;font-size:.72rem">
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
</div>
"""


# ─────────────────────────────────────────────────────────────────────────────
# Seção 4 — Execução detalhada por meta
# ─────────────────────────────────────────────────────────────────────────────

def _render_atividade(atv: dict) -> str:
    codigo = _safe(atv.get("numero_atividade_original") or atv.get("numero_atividade"))
    titulo = _safe(atv.get("titulo") or atv.get("titulo_original"), "Atividade sem título")
    indicador = _safe(atv.get("indicador_fisico"), "")
    p = _get_progresso_atv(atv)

    situacao = p.get("situacao_prazo") or ""
    atrasada = p.get("atrasada", False)
    status_clickup = _safe(atv.get("status_clickup"), "")

    realizado = p.get("realizado_percentual") or atv.get("percentual_realizado")
    previsto = p.get("previsto_percentual")

    desenvolvimento = _get_texto(atv, "desenvolvimento")
    resultados = _get_texto(atv, "resultados")
    justificativa = _get_texto(atv, "justificativa")

    badge = _status_badge(situacao, atrasada, status_clickup)
    barra = _barra_progresso(realizado, previsto)
    pct_str = _pct(realizado)

    campo_dev = (
        f'<div class="field-box">'
        f'<div class="field-label">📝 Desenvolvimento da atividade</div>'
        f'<div class="field-text{" pending" if not desenvolvimento else ""}">'
        f'{desenvolvimento or "Texto não gerado para esta atividade."}'
        f'</div></div>'
    )
    campo_res = (
        f'<div class="field-box">'
        f'<div class="field-label">📊 Resultados alcançados</div>'
        f'<div class="field-text{" pending" if not resultados else ""}">'
        f'{resultados or "Texto não gerado para esta atividade."}'
        f'</div></div>'
    )
    campo_jus = (
        f'<div class="field-box full-width">'
        f'<div class="field-label">⏰ Justificativa de atraso / adiantamento</div>'
        f'<div class="field-text{" pending" if not justificativa else ""}">'
        f'{justificativa or "Texto não gerado para esta atividade."}'
        f'</div></div>'
    )

    indicador_html = (
        f'<div class="indicador"><strong>Indicador:</strong> {indicador}</div>'
        if indicador else ""
    )

    return f"""
<div class="atividade-block" id="atv-{codigo.replace('.', '-')}">
  <div class="atv-header">
    <span class="atv-num">{codigo}</span>
    <span class="atv-title">{titulo}</span>
    <div class="atv-badges">
      {badge}
      <span class="atv-pct">{pct_str}</span>
    </div>
  </div>
  {indicador_html}
  <div style="margin:4px 0 0">{barra}</div>
  <div class="atv-fields">
    {campo_dev}
    {campo_res}
    {campo_jus}
  </div>
</div>
"""


def _render_secao4(metas: list[dict]) -> str:
    blocos = []
    for idx, meta in enumerate(metas, start=1):
        num_meta = _get_num_meta(meta, idx)
        titulo_meta = _get_titulo_meta(meta)
        realizado_meta, previsto_meta = _get_progresso_meta(meta)
        barra_meta = _barra_progresso(realizado_meta, previsto_meta)
        atividades_html = "".join(_render_atividade(a) for a in meta.get("atividades", []))

        blocos.append(f"""
<div class="meta-block" id="meta-{num_meta.replace('.', '-')}">
  <div class="meta-title-bar">
    <span class="meta-num">Meta {num_meta}</span>
    <span class="meta-title-text">{titulo_meta}</span>
    <div class="meta-progress-wrap">{barra_meta}</div>
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
    periodo = _safe(meta_dados.get("periodo_relatorio") or resumo.get("periodo_relatorio"), "")
    gerado_em = datetime.now().strftime("%d/%m/%Y às %H:%M")
    return f"""
<div class="report-header">
  <h1>Relatório de Acompanhamento Técnico</h1>
  <div class="subtitle">{titulo}</div>
  <div class="meta-info">
    {'<span>📅 Período: ' + periodo + '</span>' if periodo else ''}
    <span>🕐 Gerado em: {gerado_em}</span>
    <span>⚙ Gerador de Relatórios de Agências de Fomento</span>
  </div>
</div>
"""


def _render_toc(metas: list[dict]) -> str:
    itens = [
        '<li><a href="#secao3">3. Tabela resumo</a></li>',
        '<li><a href="#secao4">4. Execução por meta</a></li>',
    ]
    for idx, meta in enumerate(metas, start=1):
        num = _get_num_meta(meta, idx)
        titulo = _get_titulo_meta(meta)[:55]
        itens.append(
            f'<li><a href="#meta-{num.replace(".", "-")}">Meta {num}: {titulo}…</a></li>'
        )
    return f"""
<nav class="toc">
  <div class="toc-title">Navegação rápida</div>
  <ul class="toc-links">{''.join(itens)}</ul>
</nav>
"""


# ─────────────────────────────────────────────────────────────────────────────
# Ponto de entrada principal
# ─────────────────────────────────────────────────────────────────────────────

def gerar_html(relatorio: dict) -> str:
    """Gera o HTML completo (Seções 3 e 4) a partir do JSON canônico."""
    metas: list[dict] = relatorio.get("metas", [])

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
