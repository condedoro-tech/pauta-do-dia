# Pauta da Semana — UOL Esporte

Página interna, cifrada (AES-256-GCM, chave por PBKDF2 a partir da senha). Só `index.html` e `data.js` (cifrado) vão para o GitHub; textos, correções e lista de pessoas ficam na sua máquina (`.gitignore`).

**Como atualizar**
1. Edite o `textos*.json` (formato `{"AAAA-MM-DD": "texto da pauta"}`) e, se preciso, o `pessoas.txt`.
2. Rode `PAUTA_SENHA='sua-senha' python scripts/build.py` (requer `pip install cryptography`).
3. Recarregue a página (e faça commit/push do `data.js` se ela estiver publicada).

**Correções:** escreva no cartão "Correções desta pauta" de cada dia → "Baixar correções da semana" → `python scripts/corrigir.py correcoes.json` (requer `pip install anthropic` e `ANTHROPIC_API_KEY`; use `--teste` antes para ver o pedido sem gastar) → rode o build de novo. Alternativa sem script: "Copiar pedido para o Claude" e colar no chat.
