# Pauta da Semana — UOL Esporte

Página interna, cifrada (AES-256-GCM, chave por PBKDF2 a partir da senha). O repositório é público: só vão para cá arquivos cifrados (`data.js`, `pedidos/`, `propostas/`). Textos legíveis e lista de pessoas ficam no seu computador (`.gitignore`).

**Semana nova pelo Claude:** os arquivos da semana são enviados no chat; o Claude monta a pauta, cifra com `chave-publica.pem` (`scripts/enviar_semana.py`) e grava em `entrada/`. O Action "Publicar semana" abre com o segredo `PAUTA_CHAVE_PRIVADA` e gera o `data.js` com `PAUTA_SENHA`. A semana anterior sai.

**Semana nova sem o Claude (sem instalar nada)**
1. Abra `gerar.html`, escolha o `textos*.json` da semana e o `pessoas.txt`, digite a senha e clique em "Gerar e baixar data.js".
2. No GitHub: Add file → Upload files → envie só o `data.js` → Commit changes.

**Corrigir uma pauta pela própria página** (quem edita precisa do token do GitHub salvo no navegador)
1. No dia, escreva a correção e clique em "Aplicar correção".
2. O Action "Aplicar correção" aplica com o Claude Haiku e devolve uma proposta (1 a 3 minutos).
3. Revise o que muda, ajuste se quiser, e clique em "Publicar para a equipe" (ou "Descartar").
"Editar texto do dia" publica uma edição feita à mão, sem o Claude.

Segredos do repositório (Settings → Secrets and variables → Actions): `PAUTA_SENHA` (a mesma senha da página) e `ANTHROPIC_API_KEY`.

Alternativa com Python: `python scripts/build.py` e `python scripts/corrigir.py correcoes.json`.
