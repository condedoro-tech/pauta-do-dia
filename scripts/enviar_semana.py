#!/usr/bin/env python3
"""Cifra a semana com a CHAVE PÚBLICA do repositório e grava em entrada/ (quem publica é o Action).

Uso: python scripts/enviar_semana.py textos.json pessoas.txt
Não precisa da senha da página: só o Action, com a chave privada (segredo PAUTA_CHAVE_PRIVADA), abre o arquivo.
"""
import base64, json, os, sys
from datetime import datetime
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
b64 = lambda b: base64.b64encode(b).decode()


def ler_pessoas(caminho):
    out = []
    for l in open(caminho, encoding="utf-8"):
        l = l.strip()
        if l and not l.startswith("#"):
            out.append([n.strip() for n in l.split("|") if n.strip()])
    return out


def main():
    textos, pessoas = sys.argv[1], sys.argv[2]
    dias = json.load(open(textos, encoding="utf-8"))
    for d in dias:
        datetime.strptime(d, "%Y-%m-%d")
    pacote = {"dias": dias, "pessoas": ler_pessoas(pessoas), "fonte": os.path.basename(textos)}
    pub = serialization.load_pem_public_key(open(os.path.join(RAIZ, "chave-publica.pem"), "rb").read())
    efemera = X25519PrivateKey.generate()
    segredo = efemera.exchange(pub)
    epk = efemera.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    chave = HKDF(algorithm=hashes.SHA256(), length=32, salt=epk, info=b"pauta-do-dia/entrada").derive(segredo)
    iv = os.urandom(12)
    corpo = AESGCM(chave).encrypt(iv, json.dumps(pacote, ensure_ascii=False).encode("utf-8"), None)
    os.makedirs(os.path.join(RAIZ, "entrada"), exist_ok=True)
    destino = os.path.join(RAIZ, "entrada", f"semana-{datetime.now():%Y%m%d-%H%M%S}.json")
    json.dump({"v": 1, "alg": "X25519-HKDF-SHA256-AESGCM", "epk": b64(epk), "iv": b64(iv), "dados": b64(corpo)},
              open(destino, "w", encoding="utf-8"))
    print(f"{destino} | {len(dias)} dias ({min(dias)} a {max(dias)}) | {len(pacote['pessoas'])} pessoas")


if __name__ == "__main__":
    main()
