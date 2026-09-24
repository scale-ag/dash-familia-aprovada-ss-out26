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

Sem aba de Compradores: nao ha Vendas/Faturamento neste funil (sales[] vazio ->
metricas de venda aparecem "-").

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
GID_PESQUISA = "0"            # aba "Pesquisa" — respostas (chave = email); reservada p/ o MQL
EXPORT_URL = "https://docs.google.com/spreadsheets/d/{sid}/export?format=csv&gid={gid}"

# Identificação do cliente/conta (usada só em textos/relatórios — não afeta o cruzamento de dados).
CLIENT_NAME = "Nubia Oliveira"
MAIN_PRODUCT = "Venda de Ingressos"
# Sigla do funil = prefixo comum a TODAS as campanhas da conta
# (ex. "SS-OUT26 | E2-CAP | P1-QUENTE | LEAD | ABO | ...").
MAIN_PRODUCT_PREFIX = "SS-OUT26"

BRT = timezone(timedelta(hours=-3))   # horario de Brasilia (exibicao)
TAX_FACTOR = 1.13806   # fator padrão de imposto/taxa sobre o gasto de mídia paga (Meta Ads) = 13,806%.
                       # Default do template para toda nova dash criada a partir dele; ajuste apenas
                       # se o cliente tiver um fator diferente, ou use 1.0 se não houver imposto.

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


def parse_date(v: str) -> str | None:
    if not v:
        return None
    s = str(v).strip()
    if not s:
        return None
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", s)
    if m:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
    # Serial de data do Google Sheets/Excel (ex. "46288,68125" = 23/09/2026 16:21):
    # aparece quando a célula de data não está formatada como texto/data.
    if re.fullmatch(r"\d{5}([.,]\d+)?", s):
        return (datetime(1899, 12, 30) + timedelta(days=int(s.split(",")[0].split(".")[0]))).strftime("%Y-%m-%d")
    s = s.split()[0]   # descarta a hora ("23/09/2026 17:05" -> "23/09/2026")
    for fmt in ("%d/%m/%Y", "%m/%d/%Y", "%d/%m/%y", "%b %d, %Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(s, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None


def is_test_lead(rowtext: str) -> bool:
    return "<test lead" in rowtext.lower()


# Critério de MQL: AINDA NÃO DEFINIDO pelo estrategista. Enquanto não vier,
# nenhum lead é qualificado (MQLs = 0, CPMQL/Tx-MQL = "-"). Quando o critério
# chegar: ler a aba "Pesquisa" (GID_PESQUISA; colunas email, concursos_sonhos,
# momento_atual_estudos, situacao_hoje, horas_de_estudos, dificuldade_nos_estudos,
# espera_mentoria), cruzar com a aba Leads por email e implementar a regra aqui.
def is_mql(respostas: dict | None) -> bool:
    """Critério de MQL — não definido ainda: sempre False."""
    return False


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


def process(leads_rows, meta_rows):
    lheader = leads_rows[0] if leads_rows else []
    lidx = header_index(
        lheader,
        {"created": ["data_inscricao", "data"], "name": ["nome"], "email": ["email"], "phone": ["telefone"],
         "source": ["utm_source"], "campaign": ["utm_campaign"], "adset": ["utm_medium"],
         "ad": ["utm_content"], "term": ["utm_term"]},
        {"created": 0, "name": 1, "email": 2, "phone": 3, "source": 4, "campaign": 5, "adset": 6, "ad": 7, "term": 8},
    )

    leads = []
    for row in leads_rows[1:]:
        if not any((c or "").strip() for c in row):
            continue
        if is_test_lead(" ".join(str(c) for c in row)):
            continue
        campaign_raw = cell(row, lidx["campaign"])
        campaign_valid = valid_utm(campaign_raw)
        src = "meta" if campaign_valid else "org"
        term = cell(row, lidx["term"])
        placement = term.replace("_", " ").strip() if term else "Não informado"
        ad = cell(row, lidx["ad"]) if campaign_valid else "(sem anúncio)"
        leads.append({
            "d": parse_date(cell(row, lidx["created"])),
            "src": src,
            "plat": platform_of(term, cell(row, lidx["source"])) if campaign_valid else "—",
            "camp": campaign_raw if campaign_valid else "(sem campanha)",
            "adset": (cell(row, lidx["adset"]) or "(sem conjunto)") if campaign_valid else "(sem conjunto)",
            "ad": ad or "(sem anúncio)",
            # dimensões dos gráficos da Visão Geral: "prof" = anúncio (utm_content),
            # "bucket" = posicionamento (utm_term). Sem pesquisa/MQL por enquanto.
            "prof": ad or "(sem anúncio)",
            "bucket": placement,
            "q": 1 if is_mql(None) else 0,
            "utm": 1 if campaign_valid else 0,
            "nm": first_last_initial(cell(row, lidx["name"])),
            "em": mask_email(cell(row, lidx["email"])),
            "ph": mask_phone(cell(row, lidx["phone"])),
        })

    # Sem aba de Compradores neste funil: nenhuma venda/faturamento.
    sales = []

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
            "today": now_brt.strftime("%Y-%m-%d"),
            "date_min": dates[0] if dates else None,
            "date_max": dates[-1] if dates else None,
            "tax_factor": TAX_FACTOR,
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


def load_data(leads_file: str | None = None, meta_file: str | None = None) -> dict:
    """Lê as 2 planilhas (ou CSVs locais) e devolve os registros brutos.
    Compartilhado com coletar_dados_relatorio.py / gerar_relatorios.py."""
    leads_rows = load_rows(EXPORT_URL.format(sid=LEADS_SPREADSHEET_ID, gid=GID_LEADS), leads_file)
    meta_rows = load_rows(EXPORT_URL.format(sid=META_SPREADSHEET_ID, gid=GID_META), meta_file)
    return process(leads_rows, meta_rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--leads-file", help="CSV local da aba Leads (fonte principal de leads)")
    ap.add_argument("--meta-file", help="CSV local da aba Pagina1 (Meta Ads)")
    ap.add_argument("--template", default="build/template.html")
    ap.add_argument("--out", default="dist/index.html")
    args = ap.parse_args()

    data = load_data(args.leads_file, args.meta_file)

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
    print(f"  leads     : {len(data['leads'])}  MQLs: {q} (critério ainda não definido)", file=sys.stderr)
    print(f"  meta      : {len(data['meta'])} linhas", file=sys.stderr)
    print(f"  out       : {args.out}", file=sys.stderr)


if __name__ == "__main__":
    main()
