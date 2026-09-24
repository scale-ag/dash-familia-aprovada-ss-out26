# Dashboard de Captura de Leads · Nubia Oliveira — Venda de Ingressos

Dashboard **100% na nuvem** do funil **Venda de Ingressos** (lançamento pago) de
**Nubia Oliveira**. Cruza as inscrições da aba **Leads** (com UTMs) com o
investimento de mídia paga (**Meta Ads**), calcula CPL/CTR/CPM/ConvLP por
campanha → conjunto → anúncio e é publicada no **GitHub Pages**. Reconstrói
sozinha a cada ~30 min, disparada pelo **cron-job.org** — sem depender de
nenhum PC ligado.

**URL pública:** `https://scale-ag.github.io/dash-familia-aprovada-ss-out26/`

Sigla do funil nas campanhas: **`SS-OUT26`**.

---

## O que ela mostra

- **KPIs**: Gasto Total, Leads, CPL, Impressões, Cliques, CTR, CPC, CPM, Landing Page Views, ConvLP.
- **Evolução diária**: gasto/dia, leads/dia, CPL/dia.
- **Origem**: leads por origem (Meta Ads vs. orgânico/sem UTM), por plataforma, por posicionamento (`utm_term`) e por anúncio (`utm_content`).
- **Cruzamento por campanha/conjunto/anúncio**: gasto (Meta Ads) × leads (aba Leads).
- **Lead Scoring MFA**: faixas A/B/C/D, receita e ROAS projetados, sinais de cortar/escalar.
- **Toggle de imposto da mídia paga** (13,81%, ativo por padrão) e **modo claro/escuro**.
- **Aba Relatório**: painel de metas editável + Top/Piores Anúncios + Insights de Tráfego.

## Lead Scoring MFA e MQL

Cada lead ganha um **score** (soma dos pontos das 6 respostas da aba **Pesquisa**,
cruzada por e-mail) e uma **faixa A/B/C/D**. A página **Lead Scoring** mostra %
por faixa × mix de referência, custo por lead de cada faixa × teto, **receita e
ROAS projetados** (gasto × 1,1381 de imposto) no total, por dia, campanha,
conjunto e criativo. Regras completas em `CLAUDE.md`; casos de teste em
`build/test_lead_scoring.py`. **MQL (provisório) = faixas A+B.**

Este funil **não tem Vendas/Faturamento** (sem aba de compradores) — essas
métricas aparecem "-".

## Fontes de dados (somente leitura)

| Planilha | Aba | gid | Uso |
|----------|-----|-----|-----|
| Meta Ads (`1pzA2w8n4W06uUA8_DqzwUTgWc9_CK-GCcx-UsNIQrKU`) | `Página1` | `0` | gasto, impressões, cliques, landing page views |
| Leads (`1mniLIjov9tc4jlPpXKN3l_aOYfeOFCmC73apABI7nZY`) | `Leads` | `193755064` | fonte **principal** de leads (inscrições + UTMs) |
| Leads (`1mniLIjov9tc4jlPpXKN3l_aOYfeOFCmC73apABI7nZY`) | `Pesquisa` | `0` | respostas da pesquisa → Lead Scoring (faixas A/B/C/D) |

O build lê essas abas via **export CSV público** (`.../export?format=csv&gid=...`).
**Nada é escrito de volta** nas planilhas.

---

## Arquitetura

```
cron-job.org  ──(POST workflow_dispatch a cada 30 min)──▶  GitHub Actions
                                                              │
                          build/build.py  lê os CSVs ◀────────┘
                                 │  cruza Leads (UTMs) × Meta Ads
                                 ▼
                          dist/index.html  ──▶  deploy  ──▶  GitHub Pages (URL pública)
```

- `build/build.py` — baixa os CSVs, cruza os dados, gera `dist/index.html`.
- `build/template.html` — layout/gráficos/tema (Chart.js via CDN).
- `.github/workflows/deploy.yml` — roda o build e publica no Pages.

**Cache-bust:** a página usa `Cache-Control: no-cache`, mostra o horário do último
build, tem botão **Atualizar** e se recarrega sozinha (`?t=timestamp`) ~30 min após
aberta — sempre pegando a versão mais nova.

## Rodar localmente (opcional)

```bash
python build/build.py --out dist/index.html            # busca os CSVs ao vivo
# ou, com arquivos locais para teste:
python build/build.py --leads-file leads.csv --meta-file meta.csv --out dist/index.html
```

---

## Ativação e cron-job.org

O disparo por `workflow_dispatch` só funciona quando o workflow está na branch
**`main`**. Veja **`SETUP-CRON.md`** para os valores exatos (URL, headers e body)
a colar no cron-job.org.

> ⚠️ **Segurança:** nunca comite tokens no repositório. Gere um token
> *fine-grained*, só com **Actions: read/write** neste repositório, e use-o
> apenas no cron-job.org.
