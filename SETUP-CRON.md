# Ativação + configuração do cron-job.org

## Passo 1 — Colocar na branch `main` (uma vez)

O disparo por `workflow_dispatch` (o que o cron-job.org usa) **só existe quando o
workflow está na `main`**. Faça o merge da sua branch de desenvolvimento na `main`
(Pull Request → Merge, ou `git checkout main && git merge <branch> && git push`).

Na **primeira execução** o próprio workflow **habilita o GitHub Pages**
automaticamente (`actions/configure-pages` com `enablement: true`). Depois de rodar
uma vez, a página fica no ar em:

**`https://scale-ag.github.io/dash-familia-aprovada-ss-out26/`**

Se preferir disparar a primeira execução na mão: aba **Actions** → *Build & Deploy
Dashboard* → **Run workflow**.

## Passo 2 — Token do GitHub (fine-grained)

GitHub → *Settings* → *Developer settings* → **Fine-grained tokens** → *Generate*:
- Repository access: **Only select repositories → `scale-ag/dash-familia-aprovada-ss-out26`**
- Permissions → **Actions: Read and write**
- (opcional) validade longa

Guarde o token; ele vai só no cron-job.org (**nunca** no repositório, nunca em texto
puro em chat/documento compartilhado). Se um token for exposto acidentalmente,
revogue-o e gere um novo imediatamente.

## Passo 3 — Criar o cron job em https://cron-job.org

Crie um job e preencha **exatamente** (um valor por vez). Troque `TOKEN_AQUI`
pelo token fine-grained do Passo 2 (nunca comitar o token):

### URL
```
https://api.github.com/repos/scale-ag/dash-familia-aprovada-ss-out26/actions/workflows/deploy.yml/dispatches
```

### Método (Request method)
```
POST
```

### Schedule (execução)
```
A cada 30 minutos  (Every 30 minutes)
```

### Headers — nome e valor em blocos separados (4 headers)

**Header 1 — nome**
```
Accept
```
**Header 1 — valor**
```
application/vnd.github+json
```

**Header 2 — nome**
```
Authorization
```
**Header 2 — valor**
```
Bearer TOKEN_AQUI
```

**Header 3 — nome**
```
X-GitHub-Api-Version
```
**Header 3 — valor**
```
2022-11-28
```

**Header 4 — nome**
```
Content-Type
```
**Header 4 — valor**
```
application/json
```

### Request body
```
{"ref":"main"}
```

> No cron-job.org: em **Advanced**, marque para **enviar o corpo** e defina o
> **Content-Type** como `application/json` (o header acima já cobre isso).

## Como saber se funcionou

- Resposta esperada da API: **HTTP 204 No Content** (sucesso, sem corpo).
- Em **Actions** aparece uma nova execução a cada disparo.
- 401/403 = token errado ou sem permissão **Actions: write**.
- 404 = confira owner/repo/nome do arquivo (`deploy.yml`) e se ele está na `main`.
- 422 = o workflow ainda não está na `main` (faça o Passo 1).

## Observações

- A página lê as planilhas **somente leitura**; nunca escreve nelas.
- O `schedule` nativo (`*/30 * * * *`) fica como **backup**; o GitHub costuma
  atrasar agendamentos, por isso o cron-job.org é a fonte principal de pontualidade.
- Trocar o critério de qualificação, gids ou colunas: edite `build/build.py`.
