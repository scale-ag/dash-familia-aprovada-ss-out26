# Descoberta TEMPORARIA (somente leitura): lista abas/gids, cabecalhos, contagem
# e valores NAO pessoais (campanhas, formato de data). Nao imprime PII.
import csv, io, re, urllib.request, urllib.parse, collections
SHEETS = {"META": "1pzA2w8n4W06uUA8_DqzwUTgWc9_CK-GCcx-UsNIQrKU",
          "LEADS": "1mniLIjov9tc4jlPpXKN3l_aOYfeOFCmC73apABI7nZY"}
def get(u):
    r = urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0"})
    return urllib.request.urlopen(r, timeout=120).read().decode("utf-8", "replace")
SAFE = re.compile(r"(utm|campa|campaign|ad set|adset|conjunto|ad name|anuncio|anúncio|day|data|date|hora|source|medium|content|term|origem|fonte|reporting)", re.I)
for tag, sid in SHEETS.items():
    print("#"*20, tag, sid)
    try:
        html = get(f"https://docs.google.com/spreadsheets/d/{sid}/htmlview")
    except Exception as e:
        print("htmlview ERRO", e); html = ""
    tabs = re.findall(r'name:\s*"([^"]+)"[^}]*?gid:\s*"(\d+)"', html)
    print("ABAS (nome, gid):", tabs)
    for name, gid in tabs or [("?", "0")]:
        print("="*10, "aba", repr(name), "gid", gid)
        try:
            rows = list(csv.reader(io.StringIO(get(f"https://docs.google.com/spreadsheets/d/{sid}/export?format=csv&gid={gid}"))))
        except Exception as e:
            print("export ERRO", e); continue
        if not rows: print("vazia"); continue
        h = rows[0]; body = [r for r in rows[1:] if any(c.strip() for c in r)]
        print("linhas:", len(body))
        for i, c in enumerate(h):
            filled = sum(1 for r in body if i < len(r) and r[i].strip())
            line = f"  [{i}] {c!r}  preenchidas={filled}"
            if SAFE.search(c):
                vals = collections.Counter(r[i].strip() for r in body if i < len(r) and r[i].strip())
                if re.search(r"(day|data|date|hora)", c, re.I):
                    line += f"  ex={[r[i] for r in body[:2] if i < len(r)]} ult={[r[i] for r in body[-2:] if i < len(r)]}"
                else:
                    line += f"  distintos={len(vals)} top={vals.most_common(25)}"
            elif body and re.fullmatch(r"[\d.,R$ %\-]*", (body[0][i] if i < len(body[0]) else "")):
                line += f"  ex_num={body[0][i] if i < len(body[0]) else ''}"
            print(line)
