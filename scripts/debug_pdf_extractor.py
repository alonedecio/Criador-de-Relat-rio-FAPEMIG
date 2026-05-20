# scripts/debug_pdf_extractor.py
"""
Debug isolado do pdf_extractor.
Uso: python -m scripts.debug_pdf_extractor
"""
import re
import unicodedata
from pathlib import Path

from app.domain.projects.pdf_reader import ler_pdf_projeto

PDF_PATH = Path("data/input/termo_projeto.pdf")

# ── carrega PDF ───────────────────────────────────────────────────────────────
pdf = ler_pdf_projeto(PDF_PATH)
texto_orig = pdf.texto_completo
print(f"[OK] PDF carregado — {pdf.total_paginas} páginas, {len(texto_orig)} chars\n")

if not texto_orig.strip():
    print("[ERRO FATAL] texto_completo está vazio.")
    exit(1)

# ── normalização ──────────────────────────────────────────────────────────────
def norm(t: str) -> str:
    return (
        unicodedata.normalize("NFD", t)
        .encode("ascii", "ignore")
        .decode("ascii")
        .lower()
    )

texto_norm  = norm(texto_orig)
linhas_norm = texto_norm.splitlines()
print(f"[OK] {len(linhas_norm)} linhas após normalização\n")

# ── regex ─────────────────────────────────────────────────────────────────────
RE_DATA       = re.compile(r"(?:inicio|vigencia|data\s+de\s+inicio)[^\d]*(\d{1,2})[\/\-\.](\d{1,2})[\/\-\.](\d{4})")
RE_MES_INICIO = re.compile(r"m[eê]?s\s+(?:de\s+)?ini[cç][íi]?o[^\d]*(\d{1,2})")
RE_MES_FIM    = re.compile(r"m[eê]?s\s+(?:de\s+)?(?:fim|termino|final)[^\d]*(\d{1,2})")
RE_DURACAO    = re.compile(r"dura[cç]?[aã]?o[^\d]*(\d{1,2})")
RE_ATIVIDADE  = re.compile(r"(?:atividade|descri[çc]?[aã]?o)?\s*(\d+)\.(\d+)")

sep = "=" * 60

# ── 1. data de início ─────────────────────────────────────────────────────────
print(sep)
print("1. DATA DE INÍCIO")
print(sep)
m = RE_DATA.search(texto_norm)
if m:
    print(f"  [OK] {m.group(1)}/{m.group(2)}/{m.group(3)}")
    print(f"  Trecho: {repr(texto_norm[max(0,m.start()-20):m.end()+20])}")
else:
    print("  [FAIL] Padrão principal não encontrou data.")
    todas = re.findall(r"\d{2}[\/\-\.]\d{2}[\/\-\.]\d{4}", texto_orig)
    print(f"  Todas as datas DD/MM/YYYY: {todas[:10]}")

# ── 2. como "mês" aparece ────────────────────────────────────────────────────
print(f"\n{sep}")
print("2. COMO 'MÊS' APARECE NO TEXTO (primeiras 10 ocorrências)")
print(sep)
for m in list(re.finditer(r"\bm.{0,2}s\b", texto_norm))[:10]:
    print(f"  pos {m.start():5d}: {repr(texto_norm[max(0,m.start()-5):m.end()+35])}")

# ── 3. contagem de matches ───────────────────────────────────────────────────
print(f"\n{sep}")
print("3. TOTAL DE MATCHES POR REGEX")
print(sep)
for label, rx in [
    ("MES_INICIO", RE_MES_INICIO),
    ("MES_FIM",    RE_MES_FIM),
    ("DURACAO",    RE_DURACAO),
    ("ATIVIDADE",  RE_ATIVIDADE),
]:
    matches = list(rx.finditer(texto_norm))
    valores = [m.group(1) for m in matches[:5]]
    print(f"  {label:12s}: {len(matches):3d} matches  → primeiros: {valores}")

# ── 4. janela real após "1.1" ────────────────────────────────────────────────
print(f"\n{sep}")
print("4. JANELA DE 15 LINHAS APÓS PRIMEIRA OCORRÊNCIA DE '1.1'")
print(sep)
encontrou = False
for i, linha in enumerate(linhas_norm):
    if re.search(r"\b1\.1\b", linha):
        janela = "\n".join(linhas_norm[i: i + 15])
        print(f"  Linha {i}: {repr(linha)}")
        print(f"\n--- janela ---\n{janela}\n--- fim ---")
        print(f"\n  MES_INICIO: {RE_MES_INICIO.findall(janela)}")
        print(f"  MES_FIM:    {RE_MES_FIM.findall(janela)}")
        print(f"  DURACAO:    {RE_DURACAO.findall(janela)}")
        encontrou = True
        break
if not encontrou:
    print("  [FAIL] '1.1' não encontrado.")
    print("  Primeiras 10 linhas não-vazias:")
    count = 0
    for l in linhas_norm:
        if l.strip():
            print(f"    {repr(l)}")
            count += 1
            if count >= 10:
                break

# ── 5. trechos ao redor de padrão de mês ────────────────────────────────────
print(f"\n{sep}")
print("5. TRECHOS COM PADRÃO DE MÊS INÍCIO (primeiros 3 blocos)")
print(sep)
count = 0
for i, linha in enumerate(linhas_norm):
    if re.search(r"m.{0,3}s.{0,10}in", linha):
        bloco = linhas_norm[max(0, i-1): i+6]
        print(f"\n  --- linha {i} ---")
        for j, l in enumerate(bloco, start=max(0, i-1)):
            print(f"  {j:4d}: {repr(l)}")
        count += 1
        if count >= 3:
            break
if count == 0:
    print("  [NENHUM] Dump das primeiras 40 linhas não-vazias:")
    c = 0
    for i, l in enumerate(linhas_norm):
        if l.strip():
            print(f"  {i:3d}: {repr(l)}")
            c += 1
            if c >= 40:
                break

print("\n[DEBUG CONCLUÍDO]")