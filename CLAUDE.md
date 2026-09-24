# CLAUDE.md — Contexto do projeto (Nubia Oliveira · Venda de Ingressos)

> Este arquivo é lido automaticamente pelo Claude Code ao abrir o repositório.
> Ele carrega TODO o contexto necessário para continuar o trabalho sem depender
> de mensagens anteriores. Mantenha-o atualizado.
>
> **Configurado para Nubia Oliveira — funil "Venda de Ingressos" (lançamento
> pago), sigla de campanha `SS-OUT26`.** Todos os marcadores do template já
> foram preenchidos. O CHECKLIST abaixo fica como referência para replicar o
> modelo em outro cliente. Lead Scoring MFA implementado; **MQL provisório = faixas A+B**.

---

## ✅ CHECKLIST DE NOVO CLIENTE (fazer em ordem)

Ordem sugerida para configurar um cliente novo (todos os marcadores do template):

1. **`build/build.py` — constantes do topo:**
   - `META_SPREADSHEET_ID` + `GID_META` — planilha/aba do Meta Ads.
   - `LEADS_SPREADSHEET_ID` + `GID_LEADS` — planilha/aba de Leads (fonte principal).
   - `GID_PESQUISA` — aba de respostas da pesquisa (base do futuro critério de MQL).
   - `CLIENT_NAME`, `MAIN_PRODUCT` — nome do cliente e da oferta principal.
   - `MAIN_PRODUCT_PREFIX` — prefixo comum às campanhas do cliente.
   - `TAX_FACTOR` — fator de imposto/taxa da mídia paga (Meta Ads). **Default do
     template: `1.13806`** (13,806%) — já vem pronto para todo cliente novo;
     só ajuste se o cliente tiver um fator diferente, ou use `1.0` se não
     houver imposto.
2. **`build/build.py` — critério de MQL:** implemente `is_mql()` e ajuste os
   aliases de coluna em `process()` (`lidx`) ao cabeçalho da aba de Leads do cliente.
3. **`build/app.js`:** revisar os rótulos fixos de UI que citam o critério de MQL
   ("MQLs (...)") e o agrupamento de "faixa"/especialidade — o critério de
   `build.py` não propaga sozinho para esses textos.
4. **`build/template.html`:** preencher `<title>` e o logo (`logo-main`/`logo-sub`)
   com o nome/slogan do cliente. (Opcional: trocar o favicon base64.)
5. **`build/identidade-visual.css`:** ajustar cores se o cliente tiver identidade
   própria (opcional — o default funciona).
6. **`README.md` / `SETUP-CRON.md` / este `CLAUDE.md` / `AGENTS.md`:** owner/repo
   do GitHub, URL do GitHub Pages, nome do cliente, planilha/gids.
7. **`build/GUIA-RELATORIOS.md`:** preencher o "Contexto do funil" (cliente,
   oferta, critério de MQL).
8. **GitHub Pages + Actions:** confirmar que `build/` + `.github/workflows/deploy.yml`
   estão na `main` (ativa `workflow_dispatch`); rodar o workflow uma vez.
9. **cron-job.org:** seguir `SETUP-CRON.md` — token fine-grained novo (Actions:
   read/write, só neste repo), nunca reaproveitar um token exposto em chat.
10. **Insights de Tráfego (opcional):** `build/relatorios.json` e
    `build/relatorios_dados.json` começam vazios (`{}`). Para ativar os Insights:
    - deixar a Routine do Actions `briefing.yml` rodar (gera `relatorios_dados.json`
      com os números), e
    - criar a **Routine do Claude** (`create_trigger` apontando para este repo)
      que lê os números + os 2 guias e escreve `relatorios.json` na `main`
      (ver "Briefing automático" abaixo). **Não vem pronta** — precisa ser
      recriada por cliente.
11. **Testar local** com CSVs de amostra antes de publicar (3 páginas, tema
    claro/escuro, multi-seleção).

> **Fora do escopo deste template:** não há Cloudflare Worker nem chamada paga à
> API da Anthropic no pipeline. A automação de Insights é feita por Routine
> agendada do Claude Code (item 10). Se o cliente precisar de outra camada, é
> desenvolvimento novo.

---

## O que é

Dashboard de **Captura de Leads** — um app de BI estático (HTML/CSS/JS
puro + Chart.js via CDN) publicado no **GitHub Pages**, que cruza a lista de
**Leads** com o gerenciador de mídia paga e se atualiza sozinho a cada ~30 min
(build 100% na nuvem via GitHub Actions, disparado externamente pelo cron-job.org).

- **URL pública:** `https://scale-ag.github.io/dash-familia-aprovada-ss-out26/`
- **Repo:** `scale-ag/dash-familia-aprovada-ss-out26`
- **Somente leitura** das planilhas. Nunca escrever de volta.

## Fontes de dados (Google Sheets)

Duas planilhas (somente leitura):

| Planilha | Aba | gid | Colunas |
|----------|-----|-----|---------|
| **Meta Ads** `1pzA2w8n4W06uUA8_DqzwUTgWc9_CK-GCcx-UsNIQrKU` (`META_SPREADSHEET_ID`) | `Página1` | `0` (`GID_META`) | `Day` · `Campaign Name` · `Ad Set Name` · `Ad Name` · `Impressions` · `Link Clicks` · `Amount Spent` (vírgula decimal) · `Landing Page Views` |
| **Leads** `1mniLIjov9tc4jlPpXKN3l_aOYfeOFCmC73apABI7nZY` (`LEADS_SPREADSHEET_ID`) | `Leads` — **fonte principal de leads** | `193755064` (`GID_LEADS`) | `data_inscricao` · `nome` · `email` · `telefone` · `utm_source` · `utm_campaign` · `utm_medium` · `utm_content` · `utm_term` · `url_pagina` · `oferta` |
| **Leads** (mesma planilha) | `Pesquisa` — respostas (chave = `email`) → **Lead Scoring MFA** | `0` (`GID_PESQUISA`) | `email` · `concursos_sonhos` · `momento_atual_estudos` · `situacao_hoje` · `horas_de_estudos` · `dificuldade_nos_estudos` · `espera_mentoria` |

Mapeamento da aba Leads → registro de lead: `utm_campaign`/`utm_medium`/`utm_content`
= `Campaign Name`/`Ad Set Name`/`Ad Name` do Meta Ads (camp/adset/ad); `utm_term`
= posicionamento (ex. `Instagram_Reels`) → plataforma + gráfico "Leads por
posicionamento". Lead sem `utm_campaign` = orgânico/sem UTM. `data_inscricao` vem
como `dd/mm/aaaa hh:mm` **ou** como serial do Sheets (`46288,68125`) — ambos
tratados em `parse_date`. A coluna `oferta` é **ignorada** (decisão do cliente:
sem ticket/vendas).

URL de export CSV: `https://docs.google.com/spreadsheets/d/<ID>/export?format=csv&gid=<GID>`

### Lead Scoring MFA (spec `Lead_Scoring_MFA.pdf`) e MQL
Cada lead recebe **score = soma simples dos pontos das 6 respostas** da aba
**Pesquisa** (tabela `LEAD_SCORING` em `build.py`, copiada da spec — **não
recalcular nem normalizar**) e uma **faixa**: A ≥ 29 · B 18–28 · C 9–17 · D ≤ 8.
- **Join Leads × Pesquisa por e-mail** normalizado (minúscula, sem espaço nas pontas).
- **Sem linha na Pesquisa / resposta em branco** = "(não respondeu)": concursos_sonhos
  vale 2 e horas_de_estudos vale 3 → lead sem pesquisa = **5 pontos, faixa D** (não descartar).
- **Resposta fora da tabela** vale 0 e é logada no build (`⚠️ resposta fora da tabela`).
- **E-mail repetido**: conta 1 vez, fica a linha de maior pontuação.
- **Lead sem UTM** = `(orgânico)`. **Teste**: descarta e-mails com "test" e os de
  `INTERNAL_EMAILS` (vazio — preencher com os e-mails internos da equipe).
- **Fuso**: a conta roda em America/Noronha (dia vira às 23h de Brasília) →
  `lead_day()` soma `LEAD_TZ_SHIFT_HOURS = 1` à `data_inscricao` (BRT); o "hoje" do build também.
- `valor_por_lead` A 962 · B 309 · C 117 · D 80; `custo_maximo_por_lead` A 321 · B 103 ·
  C 39 · D 27; `mix_referencia` 25/30/27/18%; ROAS mínimo 3.
- `gasto_real = gasto × 1,1381` (**`TAX_FACTOR = 1.1381`**, valor exato da spec);
  `receita_projetada = Σ leads_faixa × valor_por_lead`; `ROAS_projetado = receita ÷ gasto_real`;
  `custo_por_lead_X = gasto_real ÷ leads_faixa_X`. Na página **Lead Scoring** o imposto
  é aplicado **sempre** (independe do toggle).
- Casos de teste da spec: `build/test_lead_scoring.py` (49/A · 25/B · 16/C · 5/D) —
  roda no `deploy.yml` antes do build; se falhar, não publica.

**MQL (provisório) = faixas A+B** (`MQL_FAIXAS` em `build.py`) — alimenta os cards/
tabelas legados do template (MQLs, CPMQL, Tx‑MQL, Top/Piores). A confirmar com o estrategista.

**Página "Lead Scoring"** (`renderScore()` em `app.js`, `#score`): KPIs macro (ROAS
projetado, receita projetada, gasto real, custo por lead A, % A), tabela de faixas
(% × mix de referência, custo/lead × teto), gráfico diário empilhado por faixa + ROAS,
e tabelas Diária / Campanha / Conjunto / Criativo com coluna **Sinal** (regras da seção
10 da spec: ROAS < 3 → cortar; custo/lead A > 321 → cortar; < 10 leads → amostra
pequena; %A < metade da referência → volume C/D; senão ROAS ≥ 3 → escalar).

### Vendas & Faturamento
**Não se aplica a este funil** (decisão do cliente: sem ticket e sem vendas).
Não há aba de compradores; `sales[]` sai vazio e Vendas/Fat./CAC/ROAS aparecem "-".

### Imposto da mídia paga
`TAX_FACTOR` em `build.py`, com **default `1.13806`** (13,806%) já configurado no
template — aplica-se somente ao gasto de **Meta Ads**. O toggle "Imposto Meta"
fica **ativo por padrão** (`STATE.tax=true` em `app.js`) e aplica o fator em
todo o gasto de mídia paga/derivados (CPL, CPMQL, CAC etc.) via `taxf()`, que só
multiplica `a.sp` (gasto do Meta Ads) — nunca outras fontes; desativar o toggle
volta ao gasto sem imposto. Se o cliente tiver um fator diferente, ajuste
`TAX_FACTOR`; se não houver imposto, use `TAX_FACTOR = 1.0`.

### Convenções de campanha (do cliente)
Sigla do funil = prefixo **`SS-OUT26`** (`MAIN_PRODUCT_PREFIX`), única sigla
encontrada no `Campaign Name`. Padrão de nome:
`SS-OUT26 | E2-CAP | P1-QUENTE | LEAD | ABO | 2026-09-24 | Teste de Criativos`
(`E2-CAP` = etapa de captação · `P1-QUENTE` = público quente · objetivo `LEAD` ·
`ABO` · data · descrição). Conjuntos: `AUTO | ALL | 25 a 65 | BR | All in One |
LP-A | <anúncio>`; anúncios: `VID01…`, `EST01…`. Não filtramos por sub-funil —
todas as campanhas entram no dashboard.

## Arquitetura / arquivos

```
build/build.py            # lê os CSVs (read-only), emite REGISTROS BRUTOS (leads[]/meta[]/sales[]/ad_links); render() COSTURA os 4 arquivos abaixo
build/template.html       # esqueleto HTML. Placeholders __STYLES__, __APP_JS__, __DATA_JSON__, __BUILD_ID__, __GENERATED_BRT__
build/identidade-visual.css  # TODAS as cores (tema claro=padrão / escuro). Mexa AQUI p/ trocar só cor
build/estilos.css         # layout/componentes (sidebar, topbar, period-picker, funil, tabelas, gráficos, aba Relatório)
build/app.js              # lógica + renderização (KPIs, funil, tabelas, filtro cruzado, period-picker, heatmap, Relatório)
build/relatorios.json     # Insights de Tráfego por período (aba Relatório) — VERSIONADO; lido no build, sem API. Vazio no template ({}).
build/relatorios_dados.json      # números brutos por período (insumo p/ a Routine escrever relatorios.json) — não lido pelo site. Vazio no template ({}).
build/relatorio_lib.py           # datas/agregação compartilhadas (gerar_relatorios.py + coletar_dados_relatorio.py)
build/coletar_dados_relatorio.py # gera relatorios_dados.json (só números, sem texto) — roda no briefing.yml, 1x/dia
build/gerar_relatorios.py        # gera relatorios.json determinístico (sem IA) — fallback MANUAL, não roda mais sozinho
build/GUIA-RELATORIOS.md            # formato/estrutura dos Insights da aba Relatório (os 7 blocos) — preencher o contexto do funil
build/GUIA-INTERPRETACAO-METRICAS.md # regras de diagnóstico por métrica (High Ticket) — leitura obrigatória p/ redigir
.github/workflows/deploy.yml    # roda build.py e publica no Pages (workflow_dispatch + schedule + push)
.github/workflows/briefing.yml  # roda coletar_dados_relatorio.py e commita relatorios_dados.json na main (cron 1x/dia)
dist/index.html           # saída gerada (gitignored; o Actions reconstrói)
GUIA-REPLICACAO.md        # como replicar este modelo para outros relatórios/clientes
SETUP-CRON.md             # valores exatos do cron-job.org (com marcadores a preencher)
```

### Aba Relatório
Terceira página (sidebar, entre a de mídia paga e o rodapé). **Espelha a Visão
Geral** (mesmo funil/KPIs/gráficos/tabela diária, via `renderGeralCore(REL_IDS)`)
e, abaixo, acrescenta 3 blocos novos + um painel de metas editável:
- **Metas & parâmetros (painel editável)** — no topo da aba: Meta CPMQL, Meta CAC, Volume
  mínimo amostral (MQLs), N dias p/ corte. Persiste em `localStorage['dm_metas']`, default de
  `build.py` (`META_CPMQL`/`META_CAC`=None → "não definida"; `VOLUME_MIN_AMOSTRAL`/`N_DIAS_CORTE`).
  Editar recolore **CPMQL/CAC** nas tabelas de anúncio (verde ≤ meta · amarelo até +30% ·
  vermelho acima) e ajusta o badge Em observação/Avaliável, **tudo ao vivo**
  (`METAS` + `renderRelAds()` em `app.js`).
- **Top Anúncios** e **Piores Anúncios** — 17 colunas + coluna **Status** (Anúncio · Status ·
  Campanha · Conjunto · Gasto · Impr · CPM · CTR · Leads · CPL · MQLs · Tx‑MQL · CPMQL · ConvMQL ·
  Vendas · CAC · Faturamento · ROAS · **Link**). Anúncio, Status e Link ficam **sticky**.
  Ranking pelo **resultado mais profundo disponível** (Venda→MQL), amostra relevante primeiro;
  sem amostra → badge **"Em observação"**. Limiares em `build.py`: `SAMPLE_MIN_SPEND`,
  `SAMPLE_MIN_MQLS`, `TOP_ADS_N`.
- **Insights de Tráfego** — texto por período redigido pelo **Claude** (linguagem de
  gestor de tráfego), lido de `build/relatorios.json` (sem API no build/navegador —
  o site só exibe o texto já pronto). Formato em **4 quadrantes** por período. Cada
  período compara com o período anterior **correto para aquela janela** (regra em
  `relatorio_lib.previous_period`). Chaves de período fixas
  (`hoje/ontem/3d/7d/14d/30d/mes/mespass/todo`), tags `Escalar/Otimizar/Cortar/Observar`.
  Toda a aritmética é pré-calculada em `build/relatorios_dados.json` — a Routine só
  interpreta, nunca recalcula. Regras completas em `build/GUIA-RELATORIOS.md` +
  `build/GUIA-INTERPRETACAO-METRICAS.md`. `app.js` ainda reconhece o formato antigo
  (`{"html": "…"}`) como fallback.

### Briefing automático do gestor (Routine do Claude, sem chamada à API Anthropic)
`build/relatorios.json` pode ser escrito 1×/dia por uma **Routine do Claude**
(Claude Code Remote — mesma infraestrutura de sessão/agente deste repo, agendada;
não é chamada paga à API). Fluxo em 2 etapas, porque o ambiente da Routine não
alcança `docs.google.com` (só o runner do GitHub Actions alcança):
1. `build/coletar_dados_relatorio.py` (GitHub Actions, `.github/workflows/briefing.yml`,
   1×/dia) agrega **só números** em `build/relatorios_dados.json` e commita na `main`.
2. A Routine do Claude lê esse JSON + `build/GUIA-RELATORIOS.md` +
   `build/GUIA-INTERPRETACAO-METRICAS.md`, redige `build/relatorios.json` e faz
   commit/push direto na `main`, disparando o `deploy.yml`. **Precisa ser criada
   por cliente** (`create_trigger` apontando para o repo novo) — não vem pronta.

`build/gerar_relatorios.py` (gerador determinístico, sem IA) continua no repo só
como **fallback manual**. Limitação conhecida: usa os defaults de `build.py`
(`META_CPMQL`/`META_CAC`/`VOLUME_MIN_AMOSTRAL`/`N_DIAS_CORTE`), não o que o gestor
editou no painel (fica em `localStorage`).

Funil completo: `Impressões → Cliques → Leads → MQLs → Agendamentos → Reuniões
Realizadas → Vendas → Faturamento`. Enquanto só houver mídia paga × Leads, o funil
vai até MQL; Agendamentos/Reuniões/Vendas/Fat aparecem "-" até chegar a lista do
comercial.

### Link do criativo (aba de mídia paga)
`build.py` lê uma coluna opcional de permalink do criativo na aba de mídia →
mapa `ad_links` (anúncio → 1 permalink). Usado no "Link" das tabelas Top/Piores.
Sem a coluna, o link vira "—".

> **Layout modular:** o front-end é separado em `identidade-visual.css` + `estilos.css`
> + `app.js`, costurados por `render()` nos placeholders `__STYLES__`/`__APP_JS__`.
> Página 1 usa **funil vertical de leads** + KPIs secundários. Topbar tem
> **seletor de período em calendário** (default "Este mês"). **Heatmap** = cor FIXA
> por métrica (só opacidade varia): **Gasto=vermelho · Leads=azul · MQLs=ciano ·
> Vendas=verde · ROAS=amarelo** (`--heat-gasto/leads/mqls/vendas/roas`).

O `build.py` **não agrega**: exporta as linhas cruas e TODA a lógica (filtros de
data, filtro cruzado, KPIs, tabelas, gráficos, heatmap, imposto) roda no navegador.

## Rodar/testar local

```bash
python build/build.py --leads-file leads.csv --meta-file meta.csv --out dist/index.html
# (o sandbox do agente NÃO alcança docs.google.com; use CSVs locais para testar.
#  O runner do GitHub Actions tem internet e busca os CSVs ao vivo.)
```

## Especificação funcional (resumo)

Três **páginas separadas** (sidebar):
1. **Visão Geral de Leads** — funil vertical (Gasto → Impressões → Cliques → Leads →
   MQLs → Vendas/Faturamento) + KPIs secundários; gráfico combinado diário +
   tabela diária com heatmap (todos os leads); barras por origem/faixa/plataforma/profissão.
2. **Captura mídia paga** — funil em etapas; combinado diário; barras por utm_content;
   tabela diária com heatmap (só mídia paga); 3 tabelas hierárquicas Campanha →
   Conjunto → Anúncio, cada uma com gráfico de linha embaixo.
3. **Relatório** — espelha a Visão Geral + painel de Metas editável + Top/Piores
   Anúncios (17 colunas + Status) + Insights de Tráfego. Ver `build/GUIA-RELATORIOS.md`.

**Ordem das colunas nas tabelas:** `Data · Dia · Gasto · CPM · CTR · ConvForm · Leads ·
CPL · Tx‑MQL · MQLs · CPMQL · ConvMQL · Vendas · CAC · Fat. · Receita · ROAS`. Nas
tabelas diárias entram também **Checkouts** e **VisCHK** (da coluna "Adds to Cart"
do Meta Ads, proxy de Checkout). Sem essas colunas, ficam "-".

**Regras obrigatórias das tabelas** (ver `GUIA-REPLICACAO.md`): cabeçalho sticky;
ordenação tri‑state; colunas redimensionáveis (persist localStorage); linha
"Total Geral" fixa; dimensão nunca truncada; seleção com toggle + Ctrl multi;
filtro cruzado bidirecional; tabela diária com último dia no topo; heatmap de cor
fixa por métrica.

## Lacunas de dados (comuns até o cliente enviar mais fontes)
- **Agendamentos / Reuniões Realizadas** → precisam da lista do comercial; aparecem "-".
- **Page Views, CR, CPV, ConvLP** → precisam de uma fonte de page views.
- Enquanto não vierem, essas métricas aparecem como "-".

## Publicação — problemas conhecidos
1. **Push:** se a integração GitHub da sessão for somente‑leitura (403), o caminho
   é `git push` direto para `github.com` com o **PAT do usuário**. Nunca gravar o
   token no `.git/config` (usar URL efêmera `https://x-access-token:<TOKEN>@github.com/...`).
2. **cron-job.org só funciona na `main`:** `workflow_dispatch` só existe na branch
   padrão. Levar `build/` + `.github/workflows/deploy.yml` para a `main`.
3. **Pages liga sozinho:** `actions/configure-pages@v5` com `enablement: true`
   (precisa `permissions: pages: write, id-token: write`).
4. **Proxy do sandbox:** o ambiente do agente costuma NÃO alcançar `docs.google.com`,
   `*.github.io` nem a API REST de Actions/Pages — mas o runner do Actions alcança tudo.
5. **Token exposto:** se um token foi colado no chat, **revogar e gerar um novo**.

## Branch / git
- Desenvolvimento na branch designada da sessão; manter sincronizada com `main`.
