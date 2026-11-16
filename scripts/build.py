#!/usr/bin/env python3
"""Gera data.js (cifrado) a partir do JSON de textos da pauta e de pessoas.txt.

Uso:
  PAUTA_SENHA='...' python scripts/build.py [textos.json]

Sem argumento, usa o textos*.json mais recente da raiz do projeto.
Sem PAUTA_SENHA no ambiente, a senha é pedida no terminal.
Requer: pip install cryptography
"""
import base64
import getpass
import glob
import hashlib
import json
import os
import re
import sys
from datetime import datetime

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ITERACOES = 600_000
SECOES = ["ALERTAS", "EVENTO DO DIA", "EVENTOS DO DIA", "EVENTO ESPECIAL DO DIA", "HOME E ERROS",
          "CANAIS DE WHATSAPP", "INVESTIMENTOS DO DIA", "AGENDA", "JOGOS DO DIA",
          "SETORISTAS", "PENDENCIAS"]


def sem_acento(s):
    import unicodedata
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


def achar_textos():
    if len(sys.argv) > 1:
        return sys.argv[1]
    candidatos = sorted(glob.glob(os.path.join(RAIZ, "textos*.json")), key=os.path.getmtime)
    if not candidatos:
        sys.exit("ERRO: nenhum textos*.json na raiz do projeto.")
    return candidatos[-1]


def ler_pessoas():
    caminho = os.path.join(RAIZ, "pessoas.txt")
    if not os.path.exists(caminho):
        print("AVISO: pessoas.txt não encontrado; nomes não serão destacados.")
        return []
    pessoas = []
    for linha in open(caminho, encoding="utf-8"):
        linha = linha.strip()
        if not linha or linha.startswith("#"):
            continue
        nomes = [n.strip() for n in linha.split("|") if n.strip()]
        if nomes:
            pessoas.append(nomes)
    return pessoas


def conferir(dias):
    """Só avisa; não altera nada. Aponta cabeçalhos depois de ____ que a página vai jogar em 'Outros'."""
    for data, texto in dias.items():
        try:
            datetime.strptime(data, "%Y-%m-%d")
        except ValueError:
            print(f"AVISO: chave '{data}' não é uma data AAAA-MM-DD; a página vai ignorá-la.")
            continue
        blocos = re.split(r"^_{3,}\s*$", texto, flags=re.M)
        for b in blocos:
            primeira = next((l.strip() for l in b.splitlines() if l.strip()), "")
            if primeira and not any(sem_acento(primeira).upper().startswith(s) for s in SECOES):
                print(f"AVISO {data}: seção não reconhecida, vai para 'Outros': {primeira[:60]!r}")


def cifrar(texto, senha):
    try:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    except ImportError:
        sys.exit("ERRO: falta a biblioteca. Rode: pip install cryptography")
    sal, iv = os.urandom(16), os.urandom(12)
    chave = hashlib.pbkdf2_hmac("sha256", senha.encode("utf-8"), sal, ITERACOES, 32)
    corpo = AESGCM(chave).encrypt(iv, texto.encode("utf-8"), None)
    b64 = lambda b: base64.b64encode(b).decode()
    return {"v": 1, "iter": ITERACOES, "sal": b64(sal), "iv": b64(iv), "dados": b64(corpo)}


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    caminho = achar_textos()
    dias = json.load(open(caminho, encoding="utf-8"))
    conferir(dias)
    senha = os.environ.get("PAUTA_SENHA") or getpass.getpass("Senha da pauta: ")
    if len(senha) < 10:
        sys.exit("ERRO: use uma senha com pelo menos 10 caracteres.")
    pacote = {
        "geradoEm": datetime.now().isoformat(timespec="minutes"),
        "fonte": os.path.basename(caminho),
        "dias": dias,
        "pessoas": ler_pessoas(),
    }
    cifrado = cifrar(json.dumps(pacote, ensure_ascii=False), senha)
    with open(os.path.join(RAIZ, "data.js"), "w", encoding="utf-8") as f:
        f.write("window.PAUTA_CIFRADA = " + json.dumps(cifrado) + ";\n")
    print(f"data.js gerado (cifrado) | {len(dias)} dias | {len(pacote['pessoas'])} pessoas | fonte {pacote['fonte']}")


if __name__ == "__main__":
    main()
