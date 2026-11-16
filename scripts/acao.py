#!/usr/bin/env python3
"""Roda no GitHub Actions: transforma pedidos/*.json (cifrados pela página) em propostas/*.json (cifradas).

Não altera o data.js: quem publica é o editor, pela página, depois de revisar a proposta.
Env: PAUTA_SENHA, ANTHROPIC_API_KEY.
"""
import base64
import glob
import hashlib
import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from corrigir import MODELO, cabecalhos, chamar, nomes_em  # noqa: E402

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BRT = timezone(timedelta(hours=-3))
b64d, b64e = base64.b64decode, (lambda b: base64.b64encode(b).decode())
_chaves = {}


def chave(senha, env):
    k = (env["sal"], env.get("iter", 600000))
    if k not in _chaves:
        _chaves[k] = hashlib.pbkdf2_hmac("sha256", senha.encode("utf-8"), b64d(env["sal"]), k[1], 32)
    return _chaves[k]


def abrir(env, k):
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    return json.loads(AESGCM(k).decrypt(b64d(env["iv"]), b64d(env["dados"]), None).decode("utf-8"))


def fechar(obj, k, base):
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    iv = os.urandom(12)
    corpo = AESGCM(k).encrypt(iv, json.dumps(obj, ensure_ascii=False).encode("utf-8"), None)
    return {"v": 1, "iter": base.get("iter", 600000), "sal": base["sal"], "iv": b64e(iv), "dados": b64e(corpo)}


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    pedidos = sorted(glob.glob(os.path.join(RAIZ, "pedidos", "*.json")))
    if not pedidos:
        print("Nenhum pedido.")
        return
    senha = os.environ.get("PAUTA_SENHA", "").strip()
    if not senha:
        sys.exit("ERRO: segredo PAUTA_SENHA não configurado.")

    bruto = open(os.path.join(RAIZ, "data.js"), encoding="utf-8").read()
    env_data = json.loads(re.search(r"=\s*(\{.*\})\s*;?\s*$", bruto, re.S).group(1))
    k_data = chave(senha, env_data)
    try:
        pacote = abrir(env_data, k_data)
    except Exception:
        sys.exit("ERRO: PAUTA_SENHA não abre o data.js. Confira se o segredo é a mesma senha da página.")
    pessoas = pacote.get("pessoas", [])

    import anthropic
    client = anthropic.Anthropic(max_retries=3)
    os.makedirs(os.path.join(RAIZ, "propostas"), exist_ok=True)

    for caminho in pedidos:
        base_id = re.sub(r"[^\w-]", "", os.path.basename(caminho)[:-5]) or datetime.now().strftime("%Y%m%d%H%M%S")
        prop = {"id": base_id, "modelo": MODELO, "em": datetime.now(BRT).isoformat(timespec="minutes"),
                "status": "ok", "problemas": []}
        try:
            env = json.load(open(caminho, encoding="utf-8"))
            ped = abrir(env, chave(senha, env))
            data, correcao = ped["data"], ped["correcao"].strip()
            prop.update({"data": data, "correcao": correcao, "pedidoEm": ped.get("em", "")})
            antes = pacote["dias"].get(data)
            if antes is None:
                raise RuntimeError(f"não há pauta para {data} no data.js")
            if not correcao:
                raise RuntimeError("correção vazia")
            depois = chamar(client, data, antes, correcao)
            intrusos = nomes_em(depois, pessoas) - nomes_em(antes, pessoas) - nomes_em(correcao, pessoas)
            sumiram = cabecalhos(antes) - cabecalhos(depois)
            if intrusos:
                prop["problemas"].append("Nome(s) que não estavam na pauta nem na correção: " + ", ".join(sorted(intrusos)))
            if sumiram:
                prop["problemas"].append("Seção(ões) que sumiram: " + ", ".join(sorted(sumiram)))
            prop.update({"antes": antes, "depois": depois})
        except (RuntimeError, SystemExit, KeyError, ValueError) as e:
            prop.update({"status": "erro", "erro": str(e) or e.__class__.__name__})
        except Exception as e:  # pedido ilegível (senha diferente, arquivo corrompido)
            prop.update({"status": "erro", "erro": f"pedido ilegível ({e.__class__.__name__})"})
        destino = os.path.join(RAIZ, "propostas", base_id + ".json")
        json.dump(fechar(prop, k_data, env_data), open(destino, "w", encoding="utf-8"))
        os.remove(caminho)
        print(f"- {base_id}: {prop.get('data', '?')} → {prop['status']}"
              + (f" ({prop['erro']})" if prop["status"] == "erro" else f" | avisos: {len(prop['problemas'])}"))


if __name__ == "__main__":
    main()
