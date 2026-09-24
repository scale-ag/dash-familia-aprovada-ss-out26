#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Gera a dashboard estatica (index.html) do funil "Venda de Ingressos" (lancamento
pago) de Nubia Oliveira a partir de 2 planilhas do Google Sheets (somente leitura):

  - Planilha Meta Ads, aba "Pagina1" (gid 0): investimento/impressoes/cliques/
    landing page views por dia x anuncio, exportados do gerenciador.
  - Planilha Leads, aba "Leads" (gid 193755064): FONTE PRINCIPAL de leads — cada
    linha e uma inscricao, com utm_campaign/utm_medium/utm_content (= Campaign
    Name / Ad Set Name / Ad Name do Meta Ads) e utm_term (posicionamento).
  - Planilha Leads, aba "Pesquisa" (gid 0): respostas da pesquisa (chave = email).
    AINDA NAO E LIDA — sera usada quando o criterio de MQL for definido.

Criterio de Lead Qualificado (MQL): AINDA NAO DEFINIDO pelo estrategista —
is_mql() devolve sempre False (MQLs = 0, CPMQL = "-"). Quando o criterio vier,
ler a aba Pesquisa (GID_PESQUISA), cruzar por email e ajustar is_mql().

FUNIL DE VENDAS: cada linha da aba "Leads" e um INGRESSO VENDIDO; a coluna
"oferta" e o valor pago (lote R$ 47/67). sales[] = 1 venda por comprador
(e-mail unico), faturamento = oferta.

Este script apenas LE as planilhas (export CSV publico) e emite os REGISTROS
BRUTOS (leads[] e meta[]) dentro do HTML. Todos os filtros, agregacoes, KPIs,
tabelas e graficos sao calculados no navegador (client-side). Nunca escreve
nada de volta.

Teste local: --leads-file / --meta-file apontando para CSVs baixados.
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import os
import re
import sys
import time
import unicodedata
import urllib.error
import urllib.request
from datetime import datetime, timezone, timedelta

# Planilha do Meta Ads (aba "Pagina1") e planilha de Leads (abas "Leads" e "Pesquisa").
META_SPREADSHEET_ID = "1pzA2w8n4W06uUA8_DqzwUTgWc9_CK-GCcx-UsNIQrKU"
GID_META = "0"                # aba "Pagina1"
LEADS_SPREADSHEET_ID = "1mniLIjov9tc4jlPpXKN3l_aOYfeOFCmC73apABI7nZY"
GID_LEADS = "193755064"       # aba "Leads" — fonte principal de leads (inscricoes + UTMs)
GID_PESQUISA = "0"            # aba "Pesquisa" — respostas (chave = email) → Lead Scoring
EXPORT_URL = "https://docs.google.com/spreadsheets/d/{sid}/export?format=csv&gid={gid}"

# Identificação do cliente/conta (usada só em textos/relatórios — não afeta o cruzamento de dados).
CLIENT_NAME = "Nubia Oliveira"
MAIN_PRODUCT = "Venda de Ingressos"
# Sigla do funil = prefixo comum a TODAS as campanhas da conta
# (ex. "SS-OUT26 | E2-CAP | P1-QUENTE | LEAD | ABO | ...").
MAIN_PRODUCT_PREFIX = "SS-OUT26"

BRT = timezone(timedelta(hours=-3))   # horario de Brasilia (exibicao)
TAX_FACTOR = 1.1381    # imposto da Meta sobre o gasto de mídia paga — valor EXATO da especificação
                       # "Lead Scoring MFA" (gasto_real = gasto × 1,1381). Não trocar por 1.13806:
                       # os números do ROAS projetado precisam bater com a outra implementação.

# Fuso: a conta de anúncios roda em America/Noronha (UTC-2) — o dia da Meta vira
# às 23h de Brasília. A data_inscricao dos leads está em horário de Brasília
# (UTC-3), então somamos 1h antes de tirar a data, para que "gasto do dia" e
# "leads do dia" usem o MESMO fuso (spec Lead Scoring MFA, regras de borda).
LEAD_TZ_SHIFT_HOURS = 1

# --------------------------------------------------------------------------- #
# Regras da aba Relatório (Top/Piores anúncios)
# --------------------------------------------------------------------------- #
# Amostra mínima para julgar um anúncio como "vencedor" ou "ruim". Abaixo disso
# ele entra como "Em observação" (dado insuficiente) — nunca é classificado só
# porque teve 1 resultado com pouco investimento. Ajuste conforme o ticket/CAC.
SAMPLE_MIN_SPEND = 100.0   # gasto mínimo (R$) para amostra relevante
SAMPLE_MIN_MQLS = 3        # MQLs mínimos para julgar qualidade profunda
TOP_ADS_N = 10             # nº de linhas em Top / Piores anúncios

# Metas & parâmetros da conta (DEFAULTS do painel editável da aba Relatório).
# São só o valor inicial: o usuário edita no navegador (persistido em
# localStorage) e as tabelas de anúncios recoram CPMQL/CAC e reavaliam a
# amostra ao vivo. None = "meta não definida" (métrica aparece sem cor até o
# gestor preencher).
META_CPMQL = None          # meta de CPMQL (R$/MQL); None = não definida
META_CAC = None            # meta de CAC (R$/venda); None = não definida
VOLUME_MIN_AMOSTRAL = SAMPLE_MIN_MQLS  # conversões (MQLs) mínimas p/ amostra confiável
N_DIAS_CORTE = 5           # dias consecutivos acima do teto p/ considerar corte


# --------------------------------------------------------------------------- #
# Leitura
# --------------------------------------------------------------------------- #
FETCH_RETRIES = 3       # tentativas totais em caso de timeout/erro de rede no export CSV
FETCH_RETRY_DELAY = 15  # segundos entre tentativas (o Google Sheets às vezes trava a resposta)


def fetch_csv(url: str) -> list[list[str]]:
    req = urllib.request.Request(url, headers={"User-Agent": "dash-template-bot/1.0"})
    last_err: Exception | None = None
    for attempt in range(1, FETCH_RETRIES + 1):
        try:
            with urllib.request.urlopen(req, timeout=180) as resp:
                raw = resp.read().decode("utf-8", errors="replace")
            return list(csv.reader(io.StringIO(raw)))
        except (TimeoutError, urllib.error.URLError) as exc:
            last_err = exc
            if attempt < FETCH_RETRIES:
                print(f"[fetch_csv] tentativa {attempt}/{FETCH_RETRIES} falhou ({exc!r}); "
                      f"tentando de novo em {FETCH_RETRY_DELAY}s...", file=sys.stderr)
                time.sleep(FETCH_RETRY_DELAY)
    raise last_err


def read_csv_file(path: str) -> list[list[str]]:
    with open(path, "r", encoding="utf-8", errors="replace", newline="") as f:
        return list(csv.reader(f))


def load_rows(url: str, local: str | None) -> list[list[str]]:
    return read_csv_file(local) if local else fetch_csv(url)


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def strip_accents(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))


def norm(s: str | None) -> str:
    return strip_accents((s or "").strip().lower())


def to_float(v) -> float:
    if v is None:
        return 0.0
    if isinstance(v, (int, float)):
        return float(v)
    s = re.sub(r"[^\d,.\-]", "", str(v).strip())
    if not s:
        return 0.0
    if "," in s and "." in s:
        s = s.replace(".", "").replace(",", ".")
    elif "," in s:
        s = s.replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return 0.0


def parse_datetime(v: str) -> tuple[datetime, bool] | None:
    """Data (+ hora, quando houver) de uma célula. Devolve (datetime, tem_hora)."""
    if not v:
        return None
    s = str(v).strip()
    if not s:
        return None
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})(?:[ T](\d{1,2}):(\d{2}))?", s)
    if m:
        dt = datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)),
                      int(m.group(4) or 0), int(m.group(5) or 0))
        return dt, m.group(4) is not None
    # Serial de data do Google Sheets/Excel (ex. "46288,68125" = 23/09/2026 16:21):
    # aparece quando a célula de data não está formatada como texto/data.
    if re.fullmatch(r"\d{5}([.,]\d+)?", s):
        serial = float(s.replace(",", "."))
        return datetime(1899, 12, 30) + timedelta(days=serial), "," in s or "." in s
    parts = s.split()
    for fmt in ("%d/%m/%Y", "%m/%d/%Y", "%d/%m/%y", "%b %d, %Y", "%Y/%m/%d"):
        try:
            dt = datetime.strptime(parts[0] if fmt != "%b %d, %Y" else s, fmt)
        except ValueError:
            continue
        tm = re.match(r"(\d{1,2}):(\d{2})", parts[1]) if len(parts) > 1 and fmt != "%b %d, %Y" else None
        if tm:
            return dt.replace(hour=int(tm.group(1)), minute=int(tm.group(2))), True
        return dt, False
    return None


def parse_date(v: str) -> str | None:
    r = parse_datetime(v)
    return r[0].strftime("%Y-%m-%d") if r else None


def lead_day(v: str) -> str | None:
    """Dia do lead no fuso da conta de anúncios (Brasília + LEAD_TZ_SHIFT_HOURS).
    Sem hora na célula, não há como deslocar: usa a data como está."""
    r = parse_datetime(v)
    if not r:
        return None
    dt, has_time = r
    if has_time:
        dt = dt + timedelta(hours=LEAD_TZ_SHIFT_HOURS)
    return dt.strftime("%Y-%m-%d")


def is_test_lead(rowtext: str) -> bool:
    return "<test lead" in rowtext.lower()


# --------------------------------------------------------------------------- #
# Lead Scoring MFA (spec "Lead_Scoring_MFA.pdf")
# --------------------------------------------------------------------------- #
# Pontos por resposta — tabela da especificação, SEM recalcular/normalizar.
# Chave "" = não respondeu / em branco / lead sem linha na aba Pesquisa.
LEAD_SCORING = {
    "concursos_sonhos": {
        "Receita Federal (AFRFB / ATRFB)": 13, "ISS Municipal": 6, "TCU": 4, "CGU": 3,
        "SEFAZ (SP, RS, DF, CE ou outro estado)": 2, "TCE (Tribunal de Contas Estadual)": 2,
        "Ainda não decidi": 0, "": 2,
    },
    "momento_atual_estudos": {
        "Estudo há 1 a 2 anos": 5, "Estudo há 6 meses a 1 ano": 4, "Estudo há mais de 2 anos": 4,
        "Comecei há menos de 6 meses": 3, "Ainda não comecei": 0, "": 0,
    },
    "situacao_hoje": {
        "Sou servidor público e quero avançar na carreira": 6,
        "Trabalho em tempo integral e tenho filhos": 3,
        "Trabalho em tempo integral e não tenho filhos": 2, "Outra situação": 2,
        "Estou em transição de carreira ou sem emprego fixo": 1, "": 0,
    },
    "horas_de_estudos": {
        "Entre 20 e 30 horas": 13, "Mais de 30 horas": 9, "Entre 10 e 20 horas": 6,
        "Ainda não sei, vou organizar minha rotina": 1, "Menos de 10 horas": 0, "": 3,
    },
    "dificuldade_nos_estudos": {
        "Começo mas não consigo manter a constância": 5,
        "Estudo mas sinto que não estou evoluindo ou retendo o conteúdo": 4,
        "Tenho dificuldade de conciliar estudos com trabalho e família": 4,
        "Não sei o que priorizar para o meu concurso alvo": 1,
        "Não sei por onde começar ou como montar um plano de estudos": 1, "": 0,
    },
    "espera_mentoria": {
        "Acompanhamento próximo e suporte ao longo da preparação": 7,
        "Disciplina e cobrança para manter a constância": 7,
        "Um método que funcione dentro da minha rotina real": 2,
        "Direcionamento e um plano claro de onde e como começar": 0,
        "Motivação e apoio emocional para não desistir": 0, "": 0,
    },
}
SCORING_QUESTIONS = list(LEAD_SCORING)
# faixa = A se score >= 29 · B se 18..28 · C se 9..17 · D se <= 8
FAIXAS = [("A", 29), ("B", 18), ("C", 9), ("D", -10**9)]
VALOR_POR_LEAD = {"A": 962, "B": 309, "C": 117, "D": 80}          # R$ (receita projetada por lead)
CUSTO_MAXIMO_POR_LEAD = {"A": 321, "B": 103, "C": 39, "D": 27}     # R$ (valor ÷ ROAS mínimo)
MIX_REFERENCIA = {"A": 0.25, "B": 0.30, "C": 0.27, "D": 0.18}      # distribuição esperada (sinaliza desvio)
ROAS_MINIMO = 3
# Faixas que contam como MQL nos cards/tabelas legados do template (MQLs, CPMQL,
# Tx-MQL, Top/Piores anúncios). PROVISÓRIO: A+B, a confirmar com o estrategista.
MQL_FAIXAS = ("A", "B")
# E-mails internos da equipe a descartar antes de qualquer contagem (além dos que
# contêm "test"). Minúsculas; entradas começando com "@" descartam o domínio todo.
INTERNAL_EMAILS: set[str] = set()

# índice normalizado (sem acento/caixa/espaços extras) → pontos, por pergunta
_SCORING_IDX = {q: {re.sub(r"\s+", " ", norm(k)): v for k, v in t.items()} for q, t in LEAD_SCORING.items()}


def norm_email(e: str | None) -> str:
    """Chave do join Leads × Pesquisa: minúscula e sem espaço nas pontas."""
    return (e or "").strip().lower()


def is_excluded_email(email: str) -> bool:
    """Linha de teste (e-mail com "test") ou e-mail interno da equipe."""
    if not email:
        return False
    if "test" in email:
        return True
    return email in INTERNAL_EMAILS or ("@" + email.split("@")[-1]) in INTERNAL_EMAILS


def score_respostas(respostas: dict | None, unknown: dict | None = None) -> int:
    """Soma simples dos pontos das 6 respostas. Sem linha na Pesquisa (None) ou
    resposta em branco = "(não respondeu)". Resposta fora da tabela vale 0 e é
    registrada em `unknown` ((pergunta, resposta) -> ocorrências) para log."""
    total = 0
    for q in SCORING_QUESTIONS:
        raw = ((respostas or {}).get(q) or "").strip()
        key = re.sub(r"\s+", " ", norm(raw))
        pts = _SCORING_IDX[q].get(key)
        if pts is None:
            pts = 0
            if unknown is not None:
                unknown[(q, raw)] = unknown.get((q, raw), 0) + 1
        total += pts
    return total


def faixa_of(score: int) -> str:
    for fx, minimo in FAIXAS:
        if score >= minimo:
            return fx
    return "D"


def build_pesquisa_index(pesquisa_rows) -> tuple[dict, dict]:
    """email normalizado -> (score, respostas). E-mail repetido na Pesquisa:
    fica a linha de MAIOR pontuação. Devolve também o log de respostas fora da tabela."""
    header = pesquisa_rows[0] if pesquisa_rows else []
    idx = header_index(header, {"email": ["email"], **{q: [q] for q in SCORING_QUESTIONS}},
                       {"email": 0, **{q: i + 1 for i, q in enumerate(SCORING_QUESTIONS)}})
    unknown: dict = {}
    out: dict[str, tuple[int, dict]] = {}
    for row in pesquisa_rows[1:]:
        if not any((c or "").strip() for c in row):
            continue
        email = norm_email(cell(row, idx["email"]))
        if not email:
            continue
        resp = {q: cell(row, idx[q]) for q in SCORING_QUESTIONS}
        sc = score_respostas(resp, unknown)
        if email not in out or sc > out[email][0]:
            out[email] = (sc, resp)
    return out, unknown


def is_mql(faixa: str) -> bool:
    """MQL (provisório) = lead nas faixas MQL_FAIXAS do Lead Scoring."""
    return faixa in MQL_FAIXAS


def pretty_specialty(v: str) -> str:
    s = (v or "").strip()
    return s if s else "Sem resposta"


def mask_email(e: str) -> str:
    e = (e or "").strip()
    if "@" not in e:
        return "—"
    user, dom = e.split("@", 1)
    keep = user[:2] if len(user) > 2 else user[:1]
    return f"{keep}****@{dom}"


def mask_phone(p: str) -> str:
    digits = re.sub(r"\D", "", p or "")
    return f"…{digits[-4:]}" if len(digits) >= 4 else "—"


def first_last_initial(name: str) -> str:
    parts = (name or "").strip().split()
    if not parts:
        return "—"
    return parts[0] if len(parts) == 1 else f"{parts[0]} {parts[-1][:1]}."


def valid_utm(campaign: str) -> bool:
    c = norm(campaign)
    return bool(c) and c not in ("-", "—", "nao encontrado")


# --------------------------------------------------------------------------- #
# Indexacao das colunas
# --------------------------------------------------------------------------- #
def header_index(header, wanted, fallback):
    idx = {}
    hn = [norm(h) for h in header]
    for key, aliases in wanted.items():
        found = None
        for a in aliases:
            a = norm(a)
            for i, h in enumerate(hn):
                if h == a or (a and a in h):
                    found = i
                    break
            if found is not None:
                break
        idx[key] = found if found is not None else fallback.get(key)
    return idx


def cell(row, i):
    if i is None or i < 0 or i >= len(row):
        return ""
    return (row[i] or "").strip()


# --------------------------------------------------------------------------- #
# Processamento -> registros brutos
# --------------------------------------------------------------------------- #
def platform_of(term: str, source: str) -> str:
    """Plataforma a partir de utm_term (posicionamento, ex. "Instagram_Reels") /
    utm_source. 'ig'/'fb' viram Instagram/Facebook no front."""
    t = norm(term) + " " + norm(source)
    if "insta" in t or t.startswith("ig"):
        return "ig"
    if "face" in t or "fb" in t:
        return "fb"
    if "messenger" in t:
        return "Messenger"
    if "audience" in t or "an_" in t:
        return "Audience Network"
    if "threads" in t:
        return "Threads"
    return "—"


def process(leads_rows, meta_rows, pesquisa_rows=None):
    pesquisa, unknown = build_pesquisa_index(pesquisa_rows or [])

    lheader = leads_rows[0] if leads_rows else []
    lidx = header_index(
        lheader,
        {"created": ["data_inscricao", "data"], "name": ["nome"], "email": ["email"], "phone": ["telefone"],
         "source": ["utm_source"], "campaign": ["utm_campaign"], "adset": ["utm_medium"],
         "ad": ["utm_content"], "term": ["utm_term"], "offer": ["oferta"]},
        {"created": 0, "name": 1, "email": 2, "phone": 3, "source": 4, "campaign": 5, "adset": 6, "ad": 7, "term": 8,
         "offer": 10},
    )

    leads = []
    by_email: dict[str, int] = {}   # email -> índice em leads[] (dedupe)
    n_excluded = n_dups = 0
    for row in leads_rows[1:]:
        if not any((c or "").strip() for c in row):
            continue
        if is_test_lead(" ".join(str(c) for c in row)):
            continue
        email = norm_email(cell(row, lidx["email"]))
        if is_excluded_email(email):
            n_excluded += 1
            continue
        campaign_raw = cell(row, lidx["campaign"])
        campaign_valid = valid_utm(campaign_raw)
        src = "meta" if campaign_valid else "org"
        term = cell(row, lidx["term"])
        ad = cell(row, lidx["ad"]) if campaign_valid else "(sem anúncio)"
        # Lead Scoring: sem linha na Pesquisa = as 6 respostas "(não respondeu)" (5 pts, faixa D)
        sc, _ = pesquisa.get(email) or (score_respostas(None), None)
        fx = faixa_of(sc)
        lead = {
            "d": lead_day(cell(row, lidx["created"])),
            "src": src,
            "plat": platform_of(term, cell(row, lidx["source"])) if campaign_valid else "—",
            # lead sem UTM = orgânico (não distribui entre campanhas, não descarta)
            "camp": campaign_raw if campaign_valid else "(orgânico)",
            "adset": (cell(row, lidx["adset"]) or "(sem conjunto)") if campaign_valid else "(orgânico)",
            "ad": (ad or "(sem anúncio)") if campaign_valid else "(orgânico)",
            # dimensões dos gráficos da Visão Geral: "prof" = anúncio (utm_content),
            # "bucket" = faixa do Lead Scoring.
            "prof": (ad or "(sem anúncio)") if campaign_valid else "(orgânico)",
            "bucket": "Faixa " + fx,
            "sc": sc,
            "of": round(to_float(cell(row, lidx["offer"])), 2),   # valor do ingresso (faturamento)
            "fx": fx,
            "ps": 1 if email in pesquisa else 0,   # respondeu a pesquisa?
            "q": 1 if is_mql(fx) else 0,
            "utm": 1 if campaign_valid else 0,
            "nm": first_last_initial(cell(row, lidx["name"])),
            "em": mask_email(email),
            "ph": mask_phone(cell(row, lidx["phone"])),
        }
        # E-mail repetido: conta o lead UMA vez, mantendo a linha de maior pontuação
        # (empate: a primeira inscrição).
        if email and email in by_email:
            n_dups += 1
            i = by_email[email]
            if sc > leads[i]["sc"]:
                leads[i] = lead
            continue
        if email:
            by_email[email] = len(leads)
        leads.append(lead)

    n_ps = sum(l["ps"] for l in leads)
    print(f"  lead scoring: {n_ps}/{len(leads)} leads com resposta na Pesquisa "
          f"({len(pesquisa)} e-mails na aba Pesquisa) · {n_dups} e-mail(s) repetido(s) · "
          f"{n_excluded} teste/interno(s) descartado(s)", file=sys.stderr)
    if leads and n_ps == 0:
        print("  ⚠️  NENHUM lead casou com a aba Pesquisa — todos caem na faixa D. "
              "Conferir se a Pesquisa está sendo alimentada.", file=sys.stderr)
    for (q, raw), n in sorted(unknown.items(), key=lambda x: -x[1]):
        print(f"  ⚠️  resposta fora da tabela (vale 0): {q} = {raw!r} ({n}x)", file=sys.stderr)

    # Funil de VENDAS: cada comprador (e-mail único, já deduplicado acima) é 1
    # venda de ingresso; faturamento = coluna "oferta" (valor do lote pago).
    # Atribuição/data = as da própria linha (utm_* e data_inscricao no fuso da conta).
    sales = [{"d": l["d"], "src": l["src"], "camp": l["camp"], "adset": l["adset"], "ad": l["ad"],
              "vendas": 1, "fat": l["of"], "receita": l["of"]} for l in leads]

    mheader = meta_rows[0] if meta_rows else []
    midx = header_index(
        mheader,
        {"day": ["day", "data"], "campaign": ["campaign name", "campaign"], "adset": ["ad set name", "adset"],
         "ad": ["ad name"], "spent": ["amount spent", "valor gasto", "gasto"], "impr": ["impressions", "impress"],
         "clicks": ["link clicks", "clicks", "cliques"], "leads": ["leads"],
         "pv": ["landing page views", "page views", "pageviews"],
         # Cliente não tem evento "Initiate Checkout" configurado no pixel — usa
         # "Adds to Cart" como proxy de Checkout (decisão do cliente).
         "chk": ["adds to cart", "add to cart", "initiate checkout", "checkouts iniciados", "checkouts"],
         # Link do criativo (ex. Instagram) — coluna opcional adicionada pelo cliente
         # na aba de mídia. Usada na aba Relatório (Top/Piores anúncios) para linkar
         # o anúncio. Aliases cobrem variações do cabeçalho.
         "link": ["creative instagram permalink", "instagram permalink", "permalink",
                  "creative link", "link do anuncio", "link do criativo"]},
        {"day": 0, "campaign": 2, "adset": 3, "ad": 4, "spent": 5, "impr": 6, "clicks": 7, "leads": None, "pv": 8},
    )

    meta = []
    # Anúncio (nome) -> 1 permalink do criativo. "Qualquer um correlato" ao
    # anúncio serve (o mesmo criativo pode rodar em vários dias/conjuntos);
    # guardamos o primeiro link não-vazio encontrado para cada anúncio.
    ad_links = {}
    for row in meta_rows[1:]:
        if not any((c or "").strip() for c in row):
            continue
        ad = cell(row, midx["ad"]) or "(sem anúncio)"
        link = cell(row, midx["link"])
        if link and ad not in ad_links:
            ad_links[ad] = link
        meta.append({
            "d": parse_date(cell(row, midx["day"])),
            "camp": cell(row, midx["campaign"]) or "(sem campanha)",
            "adset": cell(row, midx["adset"]) or "(sem conjunto)",
            "ad": ad,
            "sp": round(to_float(cell(row, midx["spent"])), 4),
            "im": to_float(cell(row, midx["impr"])),
            "cl": to_float(cell(row, midx["clicks"])),
            "pv": to_float(cell(row, midx["pv"])),
            "ck": to_float(cell(row, midx["chk"])),
            "ml": to_float(cell(row, midx["leads"])),
        })

    dates = sorted({d for d in (
        [l["d"] for l in leads if l["d"]] + [m["d"] for m in meta if m["d"]] + [s["d"] for s in sales if s["d"]]
    )})
    now_brt = datetime.now(BRT)
    return {
        "build": {
            "generated_at_brt": now_brt.strftime("%d/%m/%Y %H:%M"),
            "build_id": datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S"),
            # "hoje" no fuso da conta de anúncios (Noronha) — mesmo fuso de leads e gasto
            "today": (now_brt + timedelta(hours=LEAD_TZ_SHIFT_HOURS)).strftime("%Y-%m-%d"),
            "date_min": dates[0] if dates else None,
            "date_max": dates[-1] if dates else None,
            "tax_factor": TAX_FACTOR,
            # Lead Scoring MFA (lido pela página "Lead Scoring")
            "scoring": {
                "valor_por_lead": VALOR_POR_LEAD,
                "custo_maximo_por_lead": CUSTO_MAXIMO_POR_LEAD,
                "mix_referencia": MIX_REFERENCIA,
                "roas_minimo": ROAS_MINIMO,
                "faixas": {fx: m for fx, m in FAIXAS},
                "mql_faixas": list(MQL_FAIXAS),
            },
            # config da aba Relatório (lida pelo front)
            "sample_min_spend": SAMPLE_MIN_SPEND,
            "sample_min_mqls": SAMPLE_MIN_MQLS,
            "top_ads_n": TOP_ADS_N,
            # metas & parâmetros (defaults do painel editável; None = não definida)
            "meta_cpmql": META_CPMQL,
            "meta_cac": META_CAC,
            "volume_min_amostral": VOLUME_MIN_AMOSTRAL,
            "n_dias_corte": N_DIAS_CORTE,
        },
        "leads": leads,
        "meta": meta,
        "sales": sales,
        # Anúncio -> permalink do criativo (aba Relatório).
        "ad_links": ad_links,
        # Insights de Tráfego (texto pré-escrito, lido de relatorios.json). Preenchido
        # em main() via load_briefings(); fica {} se relatorios.json não existir.
        "briefings": {},
    }


# --------------------------------------------------------------------------- #
# Insights de Tráfego (aba Relatório)
# --------------------------------------------------------------------------- #
def load_briefings(path: str) -> dict:
    """Lê build/relatorios.json. Estrutura:
        {"generated_at": "...", "periodos": {"<preset>": {"html": "..."}, ...}}
    Retorna o dict inteiro (ou {} se o arquivo não existir/for inválido).
    A geração NÃO acontece aqui — este build só lê o texto já pronto, sem
    chamar nenhuma API (custo zero no build/no navegador)."""
    if not path or not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            obj = json.load(f)
        return obj if isinstance(obj, dict) else {}
    except (ValueError, OSError):
        return {}


# --------------------------------------------------------------------------- #
# Render
# --------------------------------------------------------------------------- #
def render(data, template_path):
    # A dashboard e montada a partir de arquivos separados (visual x logica):
    #   template.html          -> esqueleto HTML (placeholders __STYLES__/__APP_JS__)
    #   identidade-visual.css  -> TODAS as cores (edite aqui p/ mexer so em cor)
    #   estilos.css            -> layout/componentes
    #   app.js                 -> logica + renderizacao
    # Esta funcao so COSTURA os arquivos e injeta os dados; nao altera nada deles.
    base = os.path.dirname(os.path.abspath(template_path))

    def readf(name):
        with open(os.path.join(base, name), "r", encoding="utf-8") as f:
            return f.read()

    with open(template_path, "r", encoding="utf-8") as f:
        tpl = f.read()
    styles = readf("identidade-visual.css") + "\n" + readf("estilos.css")
    tpl = tpl.replace("__STYLES__", styles)
    tpl = tpl.replace("__APP_JS__", readf("app.js"))
    tpl = tpl.replace("__DATA_JSON__", json.dumps(data, ensure_ascii=False))
    tpl = tpl.replace("__BUILD_ID__", data["build"]["build_id"])
    tpl = tpl.replace("__GENERATED_BRT__", data["build"]["generated_at_brt"])
    return tpl


def load_data(leads_file: str | None = None, meta_file: str | None = None,
              pesquisa_file: str | None = None) -> dict:
    """Lê as 2 planilhas (ou CSVs locais) e devolve os registros brutos.
    Compartilhado com coletar_dados_relatorio.py / gerar_relatorios.py."""
    leads_rows = load_rows(EXPORT_URL.format(sid=LEADS_SPREADSHEET_ID, gid=GID_LEADS), leads_file)
    pesquisa_rows = load_rows(EXPORT_URL.format(sid=LEADS_SPREADSHEET_ID, gid=GID_PESQUISA), pesquisa_file)
    meta_rows = load_rows(EXPORT_URL.format(sid=META_SPREADSHEET_ID, gid=GID_META), meta_file)
    return process(leads_rows, meta_rows, pesquisa_rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--leads-file", help="CSV local da aba Leads (fonte principal de leads)")
    ap.add_argument("--meta-file", help="CSV local da aba Pagina1 (Meta Ads)")
    ap.add_argument("--pesquisa-file", help="CSV local da aba Pesquisa (Lead Scoring)")
    ap.add_argument("--template", default="build/template.html")
    ap.add_argument("--out", default="dist/index.html")
    args = ap.parse_args()

    data = load_data(args.leads_file, args.meta_file, args.pesquisa_file)

    # Insights de Tráfego (texto pré-escrito) — lidos do arquivo versionado ao
    # lado do template. Sem chamada de API no build.
    briefings_path = os.path.join(os.path.dirname(os.path.abspath(args.template)), "relatorios.json")
    data["briefings"] = load_briefings(briefings_path)

    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        f.write(render(data, args.template))

    b = data["build"]
    q = sum(l["q"] for l in data["leads"])
    print("== build ok ==", file=sys.stderr)
    print(f"  periodo   : {b['date_min']} -> {b['date_max']}", file=sys.stderr)
    print(f"  vendas    : {len(data['sales'])} ingressos  faturamento: R$ {sum(x['fat'] for x in data['sales']):,.2f}",
          file=sys.stderr)
    fx = {f: sum(1 for l in data["leads"] if l["fx"] == f) for f in "ABCD"}
    print(f"  leads     : {len(data['leads'])}  faixas A/B/C/D: {fx['A']}/{fx['B']}/{fx['C']}/{fx['D']}  "
          f"MQLs ({'+'.join(MQL_FAIXAS)}): {q}", file=sys.stderr)
    print(f"  meta      : {len(data['meta'])} linhas", file=sys.stderr)
    print(f"  out       : {args.out}", file=sys.stderr)


if __name__ == "__main__":
    main()
