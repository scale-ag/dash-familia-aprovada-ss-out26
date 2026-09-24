# AGENTS.md — TEMPLATE de dashboard de captura de leads (High Ticket)

> Contexto completo em **`CLAUDE.md`** (mesma pasta) — leia-o antes de mexer no
> projeto. Este arquivo é um resumo para agentes/ferramentas que seguem a
> convenção `AGENTS.md`.
>
> **Configurado para Nubia Oliveira — funil "Venda de Ingressos" (sigla `SS-OUT26`).**
> Os marcadores do template já foram todos preenchidos; o checklist abaixo fica
> como referência para replicar o modelo. MQL ainda não definido (`is_mql`).

## ✅ CHECKLIST DE NOVO CLIENTE (fazer em ordem)

1. **`build/build.py` — constantes do topo:** `META_SPREADSHEET_ID`, `GID_META`,
   `LEADS_SPREADSHEET_ID`, `GID_LEADS` (fonte principal), `GID_PESQUISA`,
   `CLIENT_NAME`, `MAIN_PRODUCT`, `MAIN_PRODUCT_PREFIX`, `TAX_FACTOR`.
2. **`build/build.py` — critério de MQL:** implementar `is_mql()` e ajustar os
   aliases de coluna em `process()` ao cabeçalho da aba de Leads do cliente.
3. **`build/app.js`:** revisar os rótulos fixos `'MQLs (...)'` e o agrupamento de
   "faixa"/especialidade (o critério de `build.py` não propaga sozinho a esses textos).
4. **`build/template.html`:** preencher `<title>` e o logo (`logo-main`/`logo-sub`).
5. **`build/identidade-visual.css`:** cores, se o cliente tiver identidade própria.
6. **`README.md` / `CLAUDE.md` / `SETUP-CRON.md`:** owner/repo do GitHub, URL do
   GitHub Pages, nome do cliente, planilha/gids.
7. **`build/GUIA-RELATORIOS.md`:** preencher o "Contexto do funil".
8. **GitHub Pages + Actions:** confirmar `build/` + `.github/workflows/deploy.yml`
   na `main` (ativa `workflow_dispatch`); rodar o workflow uma vez.
9. **cron-job.org:** seguir `SETUP-CRON.md` — token fine-grained novo (Actions:
   read/write, só neste repo), nunca reaproveitar um token exposto em chat.
10. **Insights de Tráfego (opcional):** `build/relatorios.json` e
    `build/relatorios_dados.json` começam vazios (`{}`). Ativar: deixar `briefing.yml`
    gerar os números + criar a **Routine do Claude** (`create_trigger` apontando para
    este repo) que redige `relatorios.json` na `main`. **Não vem pronta** — recriar por cliente.
11. **Testar local** com CSVs de amostra antes de publicar (3 páginas, tema
    claro/escuro, multi-seleção).

> **Fora do escopo deste template:** não há Cloudflare Worker nem chamada paga à
> API da Anthropic. A automação de Insights é uma Routine agendada do Claude Code
> (item 10). Qualquer outra camada é desenvolvimento novo.

## Engine (não muda entre clientes)
`build/template.html`, `build/app.js`, `build/estilos.css`,
`.github/workflows/deploy.yml`, `.github/workflows/briefing.yml`,
`build/relatorio_lib.py`, `build/coletar_dados_relatorio.py`,
`build/gerar_relatorios.py`, `build/GUIA-INTERPRETACAO-METRICAS.md`,
`GUIA-REPLICACAO.md` — tabelas, filtros, gráficos, heatmap, tema claro/escuro,
coleta/redação dos Insights. Ver `GUIA-REPLICACAO.md` para os detalhes de
implementação (filtro cruzado, engine de tabela, gráficos Chart.js).

> `template.html` e `app.js` são engine, mas carregam o nome do cliente em pontos
> pontuais (título/logo, rótulos de MQL e dos gráficos de origem/posicionamento).

## Específico do cliente (troca a cada replicação)
`build/build.py`, `build/identidade-visual.css` (cores, se aplicável),
`build/relatorios.json` + `build/relatorios_dados.json` (conteúdo — começam vazios),
`build/GUIA-RELATORIOS.md` (contexto do funil), `README.md`, `CLAUDE.md`,
`SETUP-CRON.md`.
