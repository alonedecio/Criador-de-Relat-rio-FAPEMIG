"""Renderizador HTML a partir do relatório canônico JSON.

Gera HTML navigável para as seções do Relatório de Acompanhamento Técnico (RAT):
  - Seção 3: Tabela resumo da execução do cronograma físico
  - Seção 4: Execução detalhada por meta física (desenvolvimento, resultados, justificativa)
  - Seção 5: Avaliação da gestão (capacitações, melhorias, dificuldades consolidadas)
  - Seção 6: Desdobramentos e impactos (3 sub-campos)
  - Seção 7: Produção tecnológica
  - Seção 8: Parcerias institucionais
  - Seção 9: Comentário final
  - Seção 10: Resumo executivo e palavras-chave

O HTML é autocontido (CSS inline) para facilitar cópia para Word/sistema de relatórios.

Mapeamento real do JSON canônico (relatorio_final_completo.json):
  meta.item                           → número da meta (ex: "1", "2")
  meta.meta_nome                      → título da meta
  meta.percentual_meta                → % realizado da meta (float direto)
  meta.progresso                      → dict com campos de progresso da meta
  atividade.numero_atividade_original → código ex: "1.1"
  atividade.titulo / titulo_original  → título da atividade
  atividade.indicador_fisico          → indicador físico
  atividade.percentual_realizado      → % realizado (float direto)
  atividade.progresso                 → dict com previsto_percentual, realizado_percentual,
                                        situacao_prazo, atrasada,
                                        mes_ano_inicio_previsto, mes_ano_fim_previsto,
                                        mes_ano_inicio_real, mes_ano_fim_real
  atividade.datas                     → dict com data_inicio, data_fim (fallback ISO)
  atividade.desenvolvimento           → texto gerado pela IA (só no JSON com textos)
  atividade.resultados                → texto gerado pela IA
  atividade.justificativa             → texto gerado pela IA
  atividade.texto                     → dict alternativo com as mesmas chaves (fallback)
  secoes_finais.*                     → textos gerados para as seções 5-10 do RAT

Campos de secoes_finais (alinhados a TextosSecaoFinal v2):
  avaliacao_gestao        → Tópico 5
  desdobramentos_internos → Tópico 6a
  posicionamento_mercado  → Tópico 6b
  beneficios_sociais      → Tópico 6c
  producao_tecnologica    → Tópico 7
  parcerias_institucionais→ Tópico 8
  comentario_final        → Tópico 9
  resumo                  → Tópico 10a
  palavras_chave          → Tópico 10b (lista)

Estrutura de colunas da Seção 3 (11 colunas):
  1  Item
  2  Meta / Atividade
  3  Indicador Físico
  4  Duração prevista — Mês/Ano início
  5  Duração prevista — Mês/Ano fim
  6  Duração efetiva  — Mês/Ano início
  7  Duração efetiva  — Mês/Ano fim
  8  Executado no período — Prev. (%)
  9  Executado no período — Real. (%)
  10 Acumulado — Prev. (%)
  11 Acumulado — Real. (%)
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any


# ───────────────────────────────────────────────────────────────────────────────────
# helpers internos
# ───────────────────────────────────────────────────────────────────────────────────

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


def _mes_ano(valor: Any) -> str:
    """
    Converte data para formato MM/AAAA.

    Aceita:
      - string já no formato 'MM/AAAA'  → retorna direto
      - string ISO 'YYYY-MM-DD'         → converte para MM/AAAA
      - string 'YYYY-MM'                → converte para MM/AAAA
      - None / vazio                    → retorna '—'
    """
    if not valor:
        return "—"
    s = str(valor).strip()
    if not s:
        return "—"
    # Já no formato MM/AAAA
    if len(s) == 7 and s[2] == "/":
        return s
    # ISO YYYY-MM-DD ou YYYY-MM
    try:
        parts = s[:10].split("-")
        if len(parts) >= 2:
            return f"{parts[1]}/{parts[0]}"
    except Exception:
        pass
    return s


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


def _get_datas_atv(atv: dict) -> tuple[str, str, str, str]:
    """
    Retorna (prev_ini, prev_fim, real_ini, real_fim) em formato MM/AAAA.

    Prioridade:
      1. atividade.progresso.mes_ano_inicio_previsto / mes_ano_fim_previsto /
                             mes_ano_inicio_real     / mes_ano_fim_real
      2. atividade.datas.data_inicio / data_fim  (ISO → MM/AAAA)
    """
    p = atv.get("progresso") or {}
    datas = atv.get("datas") or {}

    prev_ini = _mes_ano(p.get("mes_ano_inicio_previsto") or datas.get("data_inicio"))
    prev_fim = _mes_ano(p.get("mes_ano_fim_previsto")    or datas.get("data_fim"))
    real_ini = _mes_ano(p.get("mes_ano_inicio_real"))
    real_fim = _mes_ano(p.get("mes_ano_fim_real"))

    return prev_ini, prev_fim, real_ini, real_fim


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


# ───────────────────────────────────────────────────────────────────────────────────
# CSS base (autocontido, sem dependências externas)
# ───────────────────────────────────────────────────────────────────────────────────

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
.page-wrap { max-width: 1120px; margin: 0 auto; }

/* ── Cabeçalho ─────────────────────────────────────────── */
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

/* ── Navegação âncoras ────────────────────────────────── */
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

/* ── Seção ─────────────────────────────────────────────── */
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

/* ── Aviso campos manuais ──────────────────────────────── */
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

/* ── Tabela resumo ─────────────────────────────────────── */
table.resumo {
  width: 100%;
  border-collapse: collapse;
  font-size: .75rem;
}
table.resumo th {
  background: var(--primary);
  color: #fff;
  padding: 7px 8px;
  text-align: center;
  font-weight: 600;
  white-space: nowrap;
  border-right: 1px solid rgba(255,255,255,.15);
}
table.resumo th.left { text-align: left; }
table.resumo td {
  padding: 6px 8px;
  border-bottom: 1px solid #eeece9;
  vertical-align: middle;
  border-right: 1px solid #f0ede9;
}
table.resumo tr:last-child td { border-bottom: none; }
table.resumo tr:hover td { background: #f2f8f7; }
table.resumo tr.meta-row td {
  background: var(--primary-light);
  font-weight: 700;
  font-size: .78rem;
  color: var(--primary-dark);
  border-top: 2px solid #b8d4d2;
}
table.resumo .num { text-align: center; font-variant-numeric: tabular-nums; white-space: nowrap; }
table.resumo .date-cell { text-align: center; font-size: .72rem; white-space: nowrap; color: var(--muted); }

/* ── Meta block ───────────────────────────────────────────── */
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

/* ── Atividade block ─────────────────────────────────────── */
.atividade-block {
  border-top: 1px solid #eeece9;
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

/* ── Campos de texto ───────────────────────────────────────── */
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

/* ── Seções finais (5-10) ────────────────────────────────── */
.secao-final-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 14px;
}
.secao-final-card {
  background: #fafaf8;
  border: 1px solid #e6e4e0;
  border-radius: 5px;
  padding: 14px 16px;
}
.secao-final-card.full-width { grid-column: 1 / -1; }
.secao-final-card .card-label {
  font-size: .68rem;
  font-weight: 700;
  letter-spacing: .07em;
  text-transform: uppercase;
  color: var(--primary-dark);
  margin-bottom: 8px;
  display: flex;
  align-items: center;
  gap: 5px;
}
.secao-final-card .card-text {
  font-size: .83rem;
  color: var(--text);
  line-height: 1.7;
  white-space: pre-wrap;
}
.secao-final-card .card-text.pending {
  color: var(--faint);
  font-style: italic;
}
.resumo-destaque {
  background: var(--primary-light);
  border: 1px solid #b8d4d2;
  border-radius: 5px;
  padding: 16px 20px;
  margin-bottom: 16px;
}
.resumo-destaque .card-label {
  font-size: .72rem;
  font-weight: 700;
  letter-spacing: .06em;
  text-transform: uppercase;
  color: var(--primary-dark);
  margin-bottom: 8px;
}
.resumo-destaque .card-text {
  font-size: .85rem;
  color: var(--text);
  line-height: 1.7;
  white-space: pre-wrap;
}
.palavras-chave-box {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-top: 8px;
}
.palavra-chave-tag {
  background: var(--primary-light);
  border: 1px solid #b8d4d2;
  border-radius: 3px;
  padding: 3px 8px;
  font-size: .74rem;
  color: var(--primary-dark);
  font-weight: 600;
}
.comentario-final-box {
  background: #f0f7f6;
  border: 1px solid #b8d4d2;
  border-left: 4px solid var(--primary);
  border-radius: 5px;
  padding: 14px 16px;
  margin-top: 14px;
}
.comentario-final-box .card-label {
  font-size: .68rem;
  font-weight: 700;
  letter-spacing: .07em;
  text-transform: uppercase;
  color: var(--primary-dark);
  margin-bottom: 8px;
}
.comentario-final-box .card-text {
  font-size: .83rem;
  color: var(--text);
  line-height: 1.7;
  white-space: pre-wrap;
}

/* ── Responsivo ───────────────────────────────────────────── */
@media (max-width: 700px) {
  .atv-fields { grid-template-columns: 1fr; }
  .field-box.full-width { grid-column: 1; }
  table.resumo { display: block; overflow-x: auto; }
  .meta-title-bar { flex-direction: column; align-items: flex-start; }
  .meta-progress-wrap { margin-left: 0; }
  .secao-final-grid { grid-template-columns: 1fr; }
  .secao-final-card.full-width { grid-column: 1; }
}
"""


# ───────────────────────────────────────────────────────────────────────────────────
# Seção 3 — Tabela resumo do cronograma físico
#
# Estrutura de colunas (11 ao total):
#   Col 1  : Item          (rowspan=2)
#   Col 2  : Meta/Ativ.    (rowspan=2)
#   Col 3  : Indicador     (rowspan=2)
#   Col 4-5: Duração prevista (colspan=2) → Mês/Ano início | Mês/Ano fim
#   Col 6-7: Duração efetiva  (colspan=2) → Mês/Ano início | Mês/Ano fim
#   Col 8-9: Executado no período (colspan=2) → Prev.(%) | Real.(%)
#   Col 10-11: Acumulado   (colspan=2) → Prev.(%) | Real.(%)
# ───────────────────────────────────────────────────────────────────────────────────

def _render_secao3(metas: list[dict]) -> str:
    rows = []
    for idx, meta in enumerate(metas, start=1):
        num_meta = _get_num_meta(meta, idx)
        titulo_meta = _get_titulo_meta(meta)
        realizado_meta, previsto_meta = _get_progresso_meta(meta)

        # Linha de meta: cols 1-3 fundidas (Item + Meta/Ativ + Indicador),
        # datas com "—" e percentuais da meta repetidos em período e acumulado.
        rows.append(
            f'<tr class="meta-row">'
            f'<td colspan="3"><strong>Meta {num_meta}</strong> — {titulo_meta}</td>'
            f'<td class="date-cell">—</td>'  # prev_ini
            f'<td class="date-cell">—</td>'  # prev_fim
            f'<td class="date-cell">—</td>'  # real_ini
            f'<td class="date-cell">—</td>'  # real_fim
            f'<td class="num">{_pct(previsto_meta)}</td>'   # executado período prev
            f'<td class="num">{_pct(realizado_meta)}</td>'  # executado período real
            f'<td class="num">{_pct(previsto_meta)}</td>'   # acumulado prev
            f'<td class="num">{_pct(realizado_meta)}</td>'  # acumulado real
            f'</tr>'
        )
        for atv in meta.get("atividades", []):
            codigo = _safe(atv.get("numero_atividade_original") or atv.get("numero_atividade"))
            titulo_atv = _safe(atv.get("titulo") or atv.get("titulo_original"), "—")
            indicador = _safe(atv.get("indicador_fisico"), "—")
            p = _get_progresso_atv(atv)
            prev_ini, prev_fim, real_ini, real_fim = _get_datas_atv(atv)
            prev_atv = _pct(p.get("previsto_percentual"))
            real_atv = _pct(p.get("realizado_percentual") or atv.get("percentual_realizado"))
            rows.append(
                f'<tr>'
                f'<td class="num" style="color:var(--muted)">{codigo}</td>'
                f'<td>{titulo_atv}</td>'
                f'<td style="color:var(--muted);font-size:.72rem;line-height:1.4">{indicador}</td>'
                f'<td class="date-cell">{prev_ini}</td>'
                f'<td class="date-cell">{prev_fim}</td>'
                f'<td class="date-cell">{real_ini}</td>'
                f'<td class="date-cell">{real_fim}</td>'
                f'<td class="num">{prev_atv}</td>'   # executado período prev
                f'<td class="num">{real_atv}</td>'   # executado período real
                f'<td class="num">{prev_atv}</td>'   # acumulado prev
                f'<td class="num">{real_atv}</td>'   # acumulado real
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
          <th class="left" rowspan="2" style="width:42px">Item</th>
          <th class="left" rowspan="2">Meta / Atividade</th>
          <th class="left" rowspan="2">Indicador Físico</th>
          <th colspan="2" style="background:#015f65">Duração prevista</th>
          <th colspan="2" style="background:#024a50">Duração efetiva</th>
          <th colspan="2" style="background:#015f65">Executado no período</th>
          <th colspan="2" style="background:#024a50">Acumulado</th>
        </tr>
        <tr style="background:#013e44;font-size:.70rem">
          <th>Mês/Ano<br>início</th>
          <th>Mês/Ano<br>fim</th>
          <th>Mês/Ano<br>início</th>
          <th>Mês/Ano<br>fim</th>
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


# ───────────────────────────────────────────────────────────────────────────────────
# Seção 4 — Execução detalhada por meta
# ───────────────────────────────────────────────────────────────────────────────────

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


# ───────────────────────────────────────────────────────────────────────────────────
# Seções 5-10 — Seções finais do RAT (alinhadas ao formulário FAPEMIG)
# ───────────────────────────────────────────────────────────────────────────────────

def _card(emoji: str, label: str, texto: str, full_width: bool = False) -> str:
    """Renderiza um card de seção final."""
    pending = not texto or texto.strip() == ""
    cls = "secao-final-card full-width" if full_width else "secao-final-card"
    texto_display = texto if not pending else "Texto não gerado para esta seção."
    texto_cls = "card-text pending" if pending else "card-text"
    return (
        f'<div class="{cls}">'
        f'<div class="card-label">{emoji} {label}</div>'
        f'<div class="{texto_cls}">{texto_display}</div>'
        f'</div>'
    )


def _render_secao5(sf: dict) -> str:
    """Seção 5 — Avaliação da gestão (capacitações, melhorias, dificuldades consolidadas)."""
    texto = _safe(sf.get("avaliacao_gestao"), "")
    return f"""
<div class="section" id="secao5">
  <div class="section-header">
    <span class="sec-num">5.</span>
    <span class="sec-title">Avaliação da gestão: capacitações, melhorias e dificuldades não técnicas</span>
  </div>
  <div class="section-body">
    {_card("📋", "Avaliação da gestão do projeto", texto, full_width=True)}
  </div>
</div>
"""


def _render_secao6(sf: dict) -> str:
    """Seção 6 — Desdobramentos e impactos (3 sub-campos)."""
    desdobramentos = _safe(sf.get("desdobramentos_internos"), "")
    posicionamento = _safe(sf.get("posicionamento_mercado"), "")
    beneficios = _safe(sf.get("beneficios_sociais"), "")
    return f"""
<div class="section" id="secao6">
  <div class="section-header">
    <span class="sec-num">6.</span>
    <span class="sec-title">Desdobramentos internos, posicionamento de mercado e benefícios sociais</span>
  </div>
  <div class="section-body">
    <div class="secao-final-grid">
      {_card("🏢", "Desdobramentos internos", desdobramentos)}
      {_card("📈", "Posicionamento de mercado", posicionamento)}
    </div>
    <div style="margin-top:14px">
      {_card("🌍", "Benefícios sociais", beneficios, full_width=True)}
    </div>
  </div>
</div>
"""


def _render_secao7(sf: dict) -> str:
    """Seção 7 — Produção tecnológica."""
    texto = _safe(sf.get("producao_tecnologica"), "")
    return f"""
<div class="section" id="secao7">
  <div class="section-header">
    <span class="sec-num">7.</span>
    <span class="sec-title">Produção tecnológica gerada no período</span>
  </div>
  <div class="section-body">
    {_card("🔬", "Produção tecnológica", texto, full_width=True)}
  </div>
</div>
"""


def _render_secao8(sf: dict) -> str:
    """Seção 8 — Parcerias institucionais."""
    texto = _safe(sf.get("parcerias_institucionais"), "")
    return f"""
<div class="section" id="secao8">
  <div class="section-header">
    <span class="sec-num">8.</span>
    <span class="sec-title">Parcerias e articulações institucionais</span>
  </div>
  <div class="section-body">
    {_card("🤝", "Parcerias institucionais", texto, full_width=True)}
  </div>
</div>
"""


def _render_secao9(sf: dict) -> str:
    """Seção 9 — Comentário final do período."""
    texto = _safe(sf.get("comentario_final"), "")
    return f"""
<div class="section" id="secao9">
  <div class="section-header">
    <span class="sec-num">9.</span>
    <span class="sec-title">Comentário final do gestor</span>
  </div>
  <div class="section-body">
    <div class="comentario-final-box">
      <div class="card-label">💬 Comentário final</div>
      <div class="card-text{'' if texto else ' pending'}">{texto or 'Texto não gerado para esta seção.'}</div>
    </div>
  </div>
</div>
"""


def _render_secao10(sf: dict) -> str:
    """Seção 10 — Resumo executivo e palavras-chave."""
    resumo = _safe(sf.get("resumo"), "")
    palavras_raw = sf.get("palavras_chave") or []
    if isinstance(palavras_raw, str):
        palavras = [p.strip() for p in palavras_raw.split(",") if p.strip()]
    elif isinstance(palavras_raw, list):
        palavras = [str(p).strip() for p in palavras_raw if str(p).strip()]
    else:
        palavras = []

    tags_html = ""
    if palavras:
        tags = "".join(
            f'<span class="palavra-chave-tag">{p}</span>' for p in palavras
        )
        tags_html = f'<div class="palavras-chave-box">{tags}</div>'

    resumo_html = f"""
<div class="resumo-destaque">
  <div class="card-label">📋 Resumo executivo do período</div>
  <div class="card-text{'' if resumo else ' pending'}">{resumo or 'Texto não gerado para esta seção.'}</div>
  {f'<div style="margin-top:14px"><div class="card-label" style="margin-bottom:6px">🏷️ Palavras-chave</div>{tags_html}</div>' if tags_html else ''}
</div>"""

    return f"""
<div class="section" id="secao10">
  <div class="section-header">
    <span class="sec-num">10.</span>
    <span class="sec-title">Resumo executivo e palavras-chave</span>
  </div>
  <div class="section-body">
    {resumo_html}
  </div>
</div>
"""


# ───────────────────────────────────────────────────────────────────────────────────
# Cabeçalho e TOC
# ───────────────────────────────────────────────────────────────────────────────────

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


def _render_toc(metas: list[dict], tem_secoes_finais: bool = False) -> str:
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
    if tem_secoes_finais:
        itens += [
            '<li><a href="#secao5">5. Avaliação da gestão</a></li>',
            '<li><a href="#secao6">6. Desdobramentos e impactos</a></li>',
            '<li><a href="#secao7">7. Produção tecnológica</a></li>',
            '<li><a href="#secao8">8. Parcerias</a></li>',
            '<li><a href="#secao9">9. Comentário final</a></li>',
            '<li><a href="#secao10">10. Resumo / Palavras-chave</a></li>',
        ]
    return f"""
<nav class="toc">
  <div class="toc-title">Navegação rápida</div>
  <ul class="toc-links">{''.join(itens)}</ul>
</nav>
"""


# ───────────────────────────────────────────────────────────────────────────────────
# Ponto de entrada principal
# ───────────────────────────────────────────────────────────────────────────────────

def gerar_html(relatorio: dict) -> str:
    """Gera o HTML completo (Seções 3-10) a partir do JSON canônico."""
    metas: list[dict] = relatorio.get("metas", [])
    sf: dict = relatorio.get("secoes_finais") or {}
    tem_secoes_finais = bool(sf)

    header = _render_header(relatorio)
    toc = _render_toc(metas, tem_secoes_finais=tem_secoes_finais)
    sec3 = _render_secao3(metas)
    sec4 = _render_secao4(metas)

    secoes_finais_html = ""
    if tem_secoes_finais:
        secoes_finais_html = (
            _render_secao5(sf)
            + _render_secao6(sf)
            + _render_secao7(sf)
            + _render_secao8(sf)
            + _render_secao9(sf)
            + _render_secao10(sf)
        )

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
  {secoes_finais_html}
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
