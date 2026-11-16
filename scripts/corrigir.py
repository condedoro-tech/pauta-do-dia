#!/usr/bin/env python3
"""Aplica as correções escritas na página (correcoes.json) aos textos da pauta, via Claude.

Uso:
  python scripts/corrigir.py correcoes.json [textos.json] [--teste] [--forcar]

  --teste   mostra o pedido que iria para o Claude e não grava nada (não gasta).
  --forcar  grava mesmo se a conferência apontar nome novo que não estava na pauta nem na correção.

Antes de gravar: copia o JSON original para textos...json.bak-AAAAMMDD-HHMM.
Depois: rode scripts/build.py de novo para atualizar a página.
Requer: pip install anthropic  e  ANTHROPIC_API_KEY no ambiente.
"""
import difflib
import glob
import json
import os
import re
import shutil
import sys
import unicodedata
from datetime import datetime

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODELO = "claude-haiku-5-5"

SISTEMA = """Você corrige a pauta diária do UOL Esporte a pedido do editor.
Regras:
- Aplique SOMENTE as correções pedidas. Todo o resto do texto fica idêntico, caractere por caractere.
- Mantenha o formato: seções em CAIXA ALTA separadas por linhas de traços (________), uma linha por função no padrão "Função: Nome", itens com "• ".
- Não invente pessoas, horários, funções nem disponibilidade. Só use nomes que já estão na pauta ou que o editor escreveu na correção.
- Se a correção deixar uma função sem responsável, escreva RESPONSÁVEL A DEFINIR. Se depender de confirmação, A CONFIRMAR, e registre em PENDÊNCIAS PARA O EDITOR.
- Se a correção resolver um alerta ou uma pendência, remova-o; se criar um problema, acrescente-o em ALERTAS.
- Devolva apenas o texto completo da pauta corrigida, sem comentários, sem cercas de código."""


def sem_acento(s):
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


def ler_pessoas():
    caminho = os.path.join(RAIZ, "pessoas.txt")
    pessoas = []
    if os.path.exists(caminho):
        for linha in open(caminho, encoding="utf-8"):
            linha = linha.strip()
            if linha and not linha.startswith("#"):
                pessoas.append([n.strip() for n in linha.split("|") if n.strip()])
    return pessoas


def nomes_em(texto, pessoas):
    achados = set()
    for nomes in pessoas:
        for n in nomes:
            if re.search(rf"(?<![\w]){re.escape(n)}(?![\w])", texto):
                achados.add(nomes[0])
                break
    return achados


def cabecalhos(texto):
    return {sem_acento(l.strip()).upper()[:20] for l in texto.splitlines()
            if l.strip() and l.strip() == l.strip().upper() and re.match(r"^[A-ZÀ-Ú]{3}", l.strip())}


def chamar(client, data, texto, correcao):
    import anthropic
    pedido = f"Data da pauta: {data}\n\nCORREÇÕES DO EDITOR:\n{correcao}\n\nPAUTA ATUAL:\n{texto}"
    try:
        r = client.messages.create(
            model=MODELO,
            max_tokens=16000,
            system=SISTEMA,
            output_config={"effort": "medium"},
            messages=[{"role": "user", "content": pedido}],
        )
    except anthropic.AuthenticationError:
        sys.exit("ERRO: ANTHROPIC_API_KEY inválida ou ausente.")
    except anthropic.RateLimitError:
        raise RuntimeError("limite de uso da API; tente de novo em alguns minutos")
    except anthropic.APIStatusError as e:
        raise RuntimeError(f"API respondeu {e.status_code}: {e.message}")
    except anthropic.APIConnectionError:
        raise RuntimeError("sem conexão com a API")
    if r.stop_reason == "refusal":
        raise RuntimeError("o modelo recusou o pedido")
    if r.stop_reason == "max_tokens":
        raise RuntimeError("resposta cortada (max_tokens)")
    novo = "".join(b.text for b in r.content if b.type == "text").strip()
    novo = re.sub(r"^```\w*\n|\n```$", "", novo).strip()
    if not novo:
        raise RuntimeError("resposta vazia")
    return novo


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    teste, forcar = "--teste" in sys.argv, "--forcar" in sys.argv
    if not args:
        sys.exit(__doc__)
    correcoes = json.load(open(args[0], encoding="utf-8"))
    if len(args) > 1:
        caminho = args[1]
    else:
        cands = sorted(glob.glob(os.path.join(RAIZ, "textos*.json")), key=os.path.getmtime)
        if not cands:
            sys.exit("ERRO: nenhum textos*.json na raiz do projeto.")
        caminho = cands[-1]
    textos = json.load(open(caminho, encoding="utf-8"))
    pessoas = ler_pessoas()

    faltam = [d for d in correcoes if d not in textos]
    if faltam:
        print(f"AVISO: datas sem pauta em {os.path.basename(caminho)}, ignoradas: {faltam}")
    alvo = {d: c.strip() for d, c in correcoes.items() if d in textos and c.strip()}
    if not alvo:
        sys.exit("Nada a corrigir.")

    if teste:
        for d, c in alvo.items():
            print(f"===== {d} =====\n[SISTEMA]\n{SISTEMA}\n\n[PEDIDO]\nCORREÇÕES DO EDITOR:\n{c}\n\nPAUTA ATUAL: ({len(textos[d])} caracteres)\n")
        print("Modo --teste: nada foi enviado nem gravado.")
        return

    try:
        import anthropic
    except ImportError:
        sys.exit("ERRO: falta a biblioteca. Rode: pip install anthropic")
    client = anthropic.Anthropic(max_retries=3)

    novos, problemas = {}, []
    for d, c in alvo.items():
        print(f"Corrigindo {d}…")
        try:
            novo = chamar(client, d, textos[d], c)
        except RuntimeError as e:
            problemas.append(f"{d}: {e}")
            continue
        # Conferência: nenhum nome novo que não estava na pauta nem na correção
        intrusos = nomes_em(novo, pessoas) - nomes_em(textos[d], pessoas) - nomes_em(c, pessoas)
        sumiram = cabecalhos(textos[d]) - cabecalhos(novo)
        if intrusos:
            problemas.append(f"{d}: nome(s) que não estavam na pauta nem na correção: {sorted(intrusos)}")
        if sumiram:
            problemas.append(f"{d}: seção(ões) que sumiram: {sorted(sumiram)}")
        diff = list(difflib.unified_diff(textos[d].splitlines(), novo.splitlines(), "antes", "depois", lineterm="", n=0))
        print("\n".join(diff[2:]) if diff else "  (sem mudança)")
        if (intrusos or sumiram) and not forcar:
            print(f"  → {d} NÃO gravado (rode com --forcar se estiver certo).")
            continue
        novos[d] = novo

    if novos:
        backup = f"{caminho}.bak-{datetime.now():%Y%m%d-%H%M}"
        shutil.copy2(caminho, backup)
        textos.update(novos)
        with open(caminho, "w", encoding="utf-8") as f:
            json.dump(textos, f, ensure_ascii=False, indent=1)
        print(f"\nGravado: {sorted(novos)} em {os.path.basename(caminho)} (backup: {os.path.basename(backup)}).")
        print("Agora rode: python scripts/build.py  e limpe as correções aplicadas na página.")
    if problemas:
        print("\nATENÇÃO:\n- " + "\n- ".join(problemas))
        sys.exit(1)


if __name__ == "__main__":
    main()
