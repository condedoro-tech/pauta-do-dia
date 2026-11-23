#!/usr/bin/env python3
"""Roda no GitHub Actions: abre entrada/*.json (chave privada) e regrava o data.js com a senha da página.

Substitui a semana inteira (a anterior sai). Mantém o sal do data.js atual, para quem já está
com a página aberta não precisar digitar a senha de novo. Apaga pedidos/propostas de dias que saíram.
Env: PAUTA_CHAVE_PRIVADA (PEM), PAUTA_SENHA.
"""
import base64, glob, hashlib, json, os, re, sys
from datetime import datetime, timedelta, timezone
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BRT = timezone(timedelta(hours=-3))
b64d, b64e = base64.b64decode, (lambda b: base64.b64encode(b).decode())


def abrir_entrada(env, priv):
    epk = b64d(env["epk"])
    from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PublicKey
    segredo = priv.exchange(X25519PublicKey.from_public_bytes(epk))
    chave = HKDF(algorithm=hashes.SHA256(), length=32, salt=epk, info=b"pauta-do-dia/entrada").derive(segredo)
    return json.loads(AESGCM(chave).decrypt(b64d(env["iv"]), b64d(env["dados"]), None).decode("utf-8"))


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    entradas = sorted(glob.glob(os.path.join(RAIZ, "entrada", "*.json")))
    if not entradas:
        print("Nenhuma semana nova.")
        return
    pem, senha = os.environ.get("PAUTA_CHAVE_PRIVADA", "").strip(), os.environ.get("PAUTA_SENHA", "").strip()
    faltam = [n for n, v in (("PAUTA_CHAVE_PRIVADA", pem), ("PAUTA_SENHA", senha)) if not v]
    if faltam:
        sys.exit("ERRO: segredo(s) ausente(s) no repositório: " + ", ".join(faltam))
    # tolera colagem sem quebras de linha ou sem as linhas BEGIN/END
    corpo64 = re.sub(r"-----(BEGIN|END)[^-]*-----", "", pem)
    corpo64 = re.sub(r"[^A-Za-z0-9+/=]", "", corpo64)
    try:
        priv = serialization.load_der_private_key(b64d(corpo64), password=None)
    except Exception:
        sys.exit(f"ERRO: PAUTA_CHAVE_PRIVADA não é uma chave válida ({len(corpo64)} caracteres úteis; o esperado é 64).")
    pacotes = [abrir_entrada(json.load(open(e, encoding="utf-8")), priv) for e in entradas]
    semanas = [p for p in pacotes if "dias" in p]
    trocas = [t for p in pacotes if "trocas" in p for t in p["trocas"]]

    caminho = os.path.join(RAIZ, "data.js")
    sal, it = os.urandom(16), 600000
    vigente = None
    if os.path.exists(caminho):
        atual = json.loads(re.search(r"=\s*(\{.*\})\s*;?\s*$", open(caminho, encoding="utf-8").read(), re.S).group(1))
        chave_atual = hashlib.pbkdf2_hmac("sha256", senha.encode(), b64d(atual["sal"]), atual.get("iter", it), 32)
        try:
            vigente = json.loads(AESGCM(chave_atual).decrypt(b64d(atual["iv"]), b64d(atual["dados"]), None).decode("utf-8"))
            sal, it = b64d(atual["sal"]), atual.get("iter", it)   # mesma senha: mantém o sal
        except Exception:
            print("AVISO: PAUTA_SENHA não abre o data.js atual; gerando sal novo (quem estiver logado digita a senha de novo).")
    if semanas:   # semana nova substitui a anterior inteira (a mais recente vale)
        p = semanas[-1]
        dias = {d: t for d, t in p["dias"].items() if re.fullmatch(r"\d{4}-\d{2}-\d{2}", d)}
        if not dias:
            sys.exit("ERRO: a semana enviada não tem dias válidos.")
        novo = {"fonte": p.get("fonte", ""), "dias": dias, "pessoas": p.get("pessoas", [])}
    elif vigente:
        novo = vigente
        dias = novo["dias"]
    else:
        sys.exit("ERRO: trocas exigem um data.js que a PAUTA_SENHA abra.")
    for t in trocas:   # trocas pontuais: só o trecho exato, preserva o resto (inclusive correções da página)
        alvo = t.get("dias") or list(dias)
        feitas = 0
        for d in alvo:
            if d in dias and t["de"] in dias[d]:
                dias[d] = dias[d].replace(t["de"], t["para"]); feitas += 1
        print(f"troca em {feitas} dia(s): {t['de'][:50]!r}")
    novo["geradoEm"] = datetime.now(BRT).strftime("%Y-%m-%dT%H:%M")
    chave = hashlib.pbkdf2_hmac("sha256", senha.encode(), sal, it, 32)
    iv = os.urandom(12)
    corpo = AESGCM(chave).encrypt(iv, json.dumps(novo, ensure_ascii=False).encode("utf-8"), None)
    env = {"v": 1, "iter": it, "sal": b64e(sal), "iv": b64e(iv), "dados": b64e(corpo)}
    open(caminho, "w", encoding="utf-8").write("window.PAUTA_CIFRADA = " + json.dumps(env) + ";\n")

    for e in entradas:
        os.remove(e)
    # pedidos/propostas de dias que saíram da página não servem mais
    for pasta in (("pedidos", "propostas") if semanas else ()):
        for f in glob.glob(os.path.join(RAIZ, pasta, "*.json")):
            if os.path.basename(f)[:10] not in dias:
                os.remove(f)
    print(f"data.js publicado | {len(dias)} dias ({min(dias)} a {max(dias)}) | {len(novo['pessoas'])} pessoas")


if __name__ == "__main__":
    main()
