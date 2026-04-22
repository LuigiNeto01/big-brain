# Big Brain

CLI em Python que atua como **camada de memoria e documentacao automatica** para
projetos de desenvolvimento. Integra-se ao fluxo de trabalho no terminal,
mantem um vault global de notas Markdown e conversa com modelos via
[`codex-bridge`](https://github.com/Elian-Abrao/codex-bridge) local.

## Instalacao

Modo de desenvolvimento (editavel):

```bash
pip install -e .
```

Com `pipx` (recomendado para uso global):

```bash
pipx install .
```

Apos a instalacao, o executavel `big-brain` fica disponivel no `PATH`.

Para respostas reais no chat, instale e rode o broker local do codex-bridge:

```bash
pip install git+https://github.com/Elian-Abrao/codex-bridge.git
codex-bridge login
codex-bridge serve
```

Sem o broker ativo, o `big-brain chat` continua funcionando em modo offline.

## Comandos

### `big-brain init`

Inicializa o big-brain no projeto atual. Cria `~/.big-brain/config.json` (se
nao existir), executa inferencia automatica (git + filesystem) e grava
`.big-brain/project.json` na raiz do projeto. Tambem prepara o vault global
de notas configurado em `notes_dir` e cria/atualiza o `_index.md` central.

```bash
big-brain init            # inicializa a partir do diretorio atual
big-brain init --force    # regenera o project.json mesmo que ja exista
```

### `big-brain chat`

Abre o modo interativo. Cada mensagem do usuario:

1. Enriquece silenciosamente o `project.json` (stack, descricao).
2. Detecta gatilhos de nota (regra, decisao, bug, feature, etc.).
3. Chama o `codex-bridge` local com o contexto injetado via system prompt.
4. Cria/atualiza notas automaticamente, gera `[[wikilinks]]` bidirecionais,
   atualiza o `_index.md` e (opcional) faz `git add/commit/pull/push`.

Durante o chat:

```
/notas    # lista as notas
/status   # exibe o project.json atual
/sair     # encerra
```

### `big-brain notes ...`

```bash
big-brain notes list
big-brain notes show <slug>
big-brain notes search <query>
big-brain notes delete <slug> --confirm
```

### `big-brain status`

Exibe o `project.json` vigente, a lista de notas e o ultimo commit
`big-brain:` no repositorio.

## Configuracao

### Global — `~/.big-brain/config.json`

Criado automaticamente. Chaves principais:

| chave | padrao | descricao |
|---|---|---|
| `language` | `pt-BR` | idioma das respostas do LLM |
| `git_auto_sync` | `true` | faz commit e push automaticos no repo do vault de notas, quando houver |
| `auto_link` | `true` | detecta e cria wikilinks bidirecionais |
| `commit_message_pattern` | `big-brain: {action} {note}` | gabarito de mensagem de commit |
| `notes_dir` | `notes` | pasta global onde notas sao salvas; caminhos relativos partem de `~/.big-brain` |
| `default_note_types` | `[context, rule, request, decision, feature, bug]` | tipos aceitos de nota |
| `llm.provider` | `codex-bridge` | broker local usado pelo chat |
| `llm.model` | `gpt-5.4` | modelo enviado ao codex-bridge |
| `llm.reasoning_effort` | `medium` | esforco de raciocinio enviado ao codex-bridge |
| `llm.base_url` | `http://127.0.0.1:47831` | URL do broker local |

### Local — `.big-brain/project.json`

Nunca criado manualmente. Gerado por inferencia no `big-brain init` e
enriquecido a cada mensagem do `big-brain chat`.

## Estrutura de uma nota

Cada nota e um arquivo markdown com frontmatter YAML no vault global
configurado em `notes_dir`, usando o nome `{tipo}__{slug}.md`:

```markdown
---
title: Pedidos cancelados nao reabrem
type: rule
project: api-pedidos
created: 2026-04-22
updated: 2026-04-22
tags: [dominio, pedidos]
links: [context__arquitetura-geral]
source: conversation
summary: Um pedido cancelado nunca pode voltar ao estado ativo.
---

# Pedidos cancelados nao reabrem

Um pedido cancelado nunca pode voltar ao estado ativo. Essa regra
vale em qualquer fluxo, inclusive no retry de pagamento.
```

## Arquitetura

```
big-brain/                 # raiz do projeto
|- main.py                 # entry point Typer (modulo top-level)
|- core/
|  |- config.py            # merge global + local
|  |- inference.py         # git + filesystem + conversa
|  |- notes.py             # CRUD + modelo Note
|  |- linker.py            # [[wikilinks]] bidirecionais
|  |- git_sync.py          # add, commit, pull --rebase, push
|  `- session.py           # estado, LLM, triggers
|- cli/
|  |- init.py
|  |- chat.py
|  |- notes_cmd.py
|  `- status.py
|- utils/
|  |- frontmatter.py
|  |- slugify.py
|  `- ui.py
|- tests/
|- pyproject.toml
`- README.md
```

## Desenvolvimento

Rodar testes:

```bash
pip install -e '.[dev]'
pytest
```

Tipagem e lint:

```bash
ruff check big-brain
mypy big-brain
```
