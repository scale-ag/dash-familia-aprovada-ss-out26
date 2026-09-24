#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Casos de teste da especificação "Lead Scoring MFA" (seção 8) + regras de borda.
A implementação está certa quando bate nos quatro casos. Rodar:
    python build/test_lead_scoring.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import build as bp  # noqa: E402

Q = bp.SCORING_QUESTIONS
CASOS = [
    (["Receita Federal (AFRFB / ATRFB)", "Estudo há 1 a 2 anos", "Sou servidor público e quero avançar na carreira",
      "Entre 20 e 30 horas", "Começo mas não consigo manter a constância",
      "Acompanhamento próximo e suporte ao longo da preparação"], 49, "A"),
    (["ISS Municipal", "Estudo há 6 meses a 1 ano", "Trabalho em tempo integral e tenho filhos", "Entre 10 e 20 horas",
      "Tenho dificuldade de conciliar estudos com trabalho e família",
      "Um método que funcione dentro da minha rotina real"], 25, "B"),
    (["TCU", "Comecei há menos de 6 meses", "Outra situação", "Ainda não sei, vou organizar minha rotina",
      "Estudo mas sinto que não estou evoluindo ou retendo o conteúdo",
      "Um método que funcione dentro da minha rotina real"], 16, "C"),
    (None, 5, "D"),   # lead que não respondeu a pesquisa: 2+0+0+3+0+0
]


def main():
    ok = True
    for resp, score, faixa in CASOS:
        r = dict(zip(Q, resp)) if resp else None
        sc = bp.score_respostas(r)
        fx = bp.faixa_of(sc)
        good = sc == score and fx == faixa
        ok &= good
        print(f"{'OK ' if good else 'ERRO'} score={sc} (esperado {score}) faixa={fx} (esperada {faixa})")

    # bordas
    unk = {}
    blank = bp.score_respostas({q: "" for q in Q})
    fora = bp.score_respostas({**{q: "" for q in Q}, "concursos_sonhos": "Polícia Federal"}, unk)
    checks = [
        ("respostas em branco = não respondeu (5, D)", blank == 5 and bp.faixa_of(blank) == "D"),
        ("resposta fora da tabela vale 0 e é logada", fora == 3 and ("concursos_sonhos", "Polícia Federal") in unk),
        ("limites das faixas 29/28/18/17/9/8", [bp.faixa_of(x) for x in (29, 28, 18, 17, 9, 8)] == list("ABBCCD")),
        ("e-mail normalizado", bp.norm_email("  Fulano@Mail.COM ") == "fulano@mail.com"),
        ("e-mail com test é descartado", bp.is_excluded_email("teste@x.com")),
        ("lead às 23h30 BRT cai no dia seguinte (Noronha)", bp.lead_day("24/09/2026 23:30") == "2026-09-25"),
        ("lead às 22h59 BRT fica no mesmo dia", bp.lead_day("24/09/2026 22:59") == "2026-09-24"),
    ]
    for name, good in checks:
        ok &= good
        print(f"{'OK ' if good else 'ERRO'} {name}")

    # dedupe + join por e-mail + sem UTM = orgânico
    leads = [["data_inscricao", "nome", "email", "telefone", "utm_source", "utm_campaign", "utm_medium",
              "utm_content", "utm_term", "url_pagina", "oferta"],
             ["24/09/2026 10:00", "A B", "Dup@x.com", "1", "Meta-Ads", "C1", "S1", "VID01", "Instagram_Feed", "", "47"],
             ["24/09/2026 11:00", "A B", "dup@x.com ", "1", "Meta-Ads", "C1", "S1", "VID01", "Instagram_Feed", "", "47"],
             ["24/09/2026 12:00", "C D", "org@x.com", "2", "", "", "", "", "", "", "47"]]
    pesq = [["email"] + Q, ["DUP@x.com"] + CASOS[0][0], ["dup@x.com"] + CASOS[2][0]]
    data = bp.process(leads, [["Day"]], pesq)
    L = data["leads"]
    for name, good in [
        ("e-mail repetido conta 1 vez", len(L) == 2),
        ("pesquisa repetida: fica a maior pontuação (49/A)", L[0]["sc"] == 49 and L[0]["fx"] == "A"),
        ("lead sem pesquisa = 5/D", L[1]["sc"] == 5 and L[1]["fx"] == "D"),
        ("lead sem UTM = orgânico", L[1]["camp"] == "(orgânico)" and L[1]["src"] == "org"),
    ]:
        ok &= good
        print(f"{'OK ' if good else 'ERRO'} {name}")

    print("TODOS OS TESTES OK" if ok else "HÁ TESTES FALHANDO")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
