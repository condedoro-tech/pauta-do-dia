# Pauta da Semana — UOL Esporte

Página interna, cifrada (AES-256-GCM, chave por PBKDF2 a partir da senha). Só `index.html`, `gerar.html` e `data.js` (cifrado) vão para o GitHub; textos e lista de pessoas ficam no seu computador (`.gitignore`).

**Como atualizar (sem instalar nada)**
1. Abra `gerar.html` (no navegador, do site ou da pasta), escolha o `textos*.json` da semana e o `pessoas.txt`, digite a senha e clique em "Gerar e baixar data.js".
2. No GitHub: Add file → Upload files → envie só o `data.js` → Commit changes.
3. Recarregue a página da pauta.

**Correções:** escreva no cartão "Correções desta pauta" do dia → "Copiar pedido para o Claude" → cole no chat → cole o texto corrigido no dia certo do `gerar.html` → gere e suba o `data.js` de novo → "Baixar textos corrigidos" para guardar o .json atualizado.

Alternativa com Python: `python scripts/build.py` (gera o data.js) e `python scripts/corrigir.py correcoes.json` (aplica correções via API; `--teste` antes).
