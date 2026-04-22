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

Para integrar o Big Brain automaticamente nas proximas conversas com agents
Codex, rode uma vez:

```bash
big-brain setup-agent
```

Esse comando localiza e atualiza arquivos de instrucoes personalizadas dos
agents, instala uma skill `big-brain`, um plugin local com hooks de sessao e um
marketplace local. A partir dai, a propria IA deve inicializar o projeto,
atualizar o contexto e capturar notas sem voce precisar pedir isso a cada
conversa.

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

### `big-brain context`

Imprime um bloco Markdown com o contexto do projeto e notas globais. E pensado
para agents usarem no inicio de uma tarefa. Se o projeto ainda nao estiver
inicializado, cria `.big-brain/project.json` automaticamente.

```bash
big-brain context
```

### `big-brain capture`

Captura informacoes duraveis de uma conversa de agent, detecta gatilhos e cria
notas no vault global.

```bash
printf '%s\n' "Nao pode remover notas sem confirmacao." | big-brain capture --stdin
big-brain capture "Decidimos usar o vault global para todos os projetos."
```

### `big-brain setup-agent`

Instala a integracao global para agents Codex:

```bash
big-brain setup-agent
```

Depois disso, em novas conversas, o agent deve chamar `big-brain context` no
inicio da tarefa e `big-brain capture --stdin` quando voce declarar regras,
decisoes, pedidos, bugs, features ou contexto que valem para o futuro.

O setup escreve esse comportamento nas instrucoes personalizadas globais:

```text
~/.codex/AGENTS.md
~/.claude/CLAUDE.md          # quando ~/.claude existir
~/.cursor/rules/big-brain.mdc # quando ~/.cursor existir
```

O trecho instalado diz explicitamente para a IA:

- rodar `big-brain context` no inicio de tarefas em repositorios;
- usar a memoria retornada antes de decisoes de projeto;
- rodar `big-brain capture --stdin` quando voce declarar algo duravel;
- registrar um resumo antes da resposta final se algo importante ainda nao foi
  capturado;
- nao pedir para voce rodar esses comandos.

Tambem instala um plugin local inspirado no modelo do `claude-brain`, como
camada extra de automacao:

| Hook | Quando | Acao |
|---|---|---|
| `SessionStart` | abertura/retomada de sessao | roda `big-brain hook session-start`, inicializa o projeto se preciso e atualiza `~/.big-brain/agent-context.md` |
| `SessionEnd` | fim de sessao | roda `big-brain hook session-end` e tenta capturar notas a partir do transcript fornecido pelo agent |
| `PreCompact` | antes de compactacao automatica | roda `big-brain hook pre-compact` para salvar informacoes duraveis antes da compactacao |

Arquivos instalados pelo setup:

```text
~/.codex/AGENTS.md
~/.claude/CLAUDE.md          # se Claude estiver configurado
~/.codex/skills/big-brain/SKILL.md
~/plugins/big-brain/.codex-plugin/plugin.json
~/plugins/big-brain/hooks.json
~/.agents/plugins/marketplace.json
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
|- .codex-plugin/
|  `- plugin.json          # manifesto de plugin Codex
|- .claude-plugin/
|  `- plugin.json          # manifesto compatível com plugin Claude
|- hooks.json              # hooks Codex
|- hooks/
|  `- hooks.json           # hooks em layout Claude-style
|- scripts/
|  |- big-brain-session-start.sh
|  |- big-brain-session-end.sh
|  `- big-brain-pre-compact.sh
|- skills/
|  `- big-brain/SKILL.md
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
|  |- agent.py
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
