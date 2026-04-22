# AGENTS.md

Instrucoes para agentes de codigo (Claude Code, Codex CLI, Cursor, etc.)
trabalhando neste repositorio.

## Sobre o projeto

**Big Brain** e um CLI em Python que atua como camada de memoria para projetos
de desenvolvimento. Detecta gatilhos em conversas via regex, cria notas
markdown com frontmatter YAML, mantem wikilinks bidirecionais entre elas,
e sincroniza tudo com git automaticamente.

Stack: Python 3.11+, Typer, Rich, Pydantic v2, python-frontmatter, GitPython,
httpx (para chamadas ao broker local codex-bridge).

## Layout (flat, sem pacote raiz)

```
big-brain/
|- main.py          # entry point Typer (modulo top-level)
|- core/
|  |- config.py     # merge ~/.big-brain/config.json + .big-brain/project.json
|  |- inference.py  # git + filesystem + enrich via conversa
|  |- notes.py      # CRUD, modelo Note, _index.md
|  |- linker.py     # [[wikilinks]] bidirecionais
|  |- git_sync.py   # add/commit/pull --rebase/push
|  `- session.py    # estado em memoria, LLMClient codex-bridge, detect_triggers
|- cli/             # comandos Typer: init, chat, notes_cmd, status
|- utils/           # slugify, frontmatter, ui (Rich)
|- tests/
`- pyproject.toml
```

**Importante:** nao existe pacote `big_brain/` — os modulos `core`, `cli`,
`utils` sao top-level. Imports sao `from core.notes import ...`, nunca
`from big_brain.core.notes import ...`. Nao recrie esse pacote.

## Comandos de desenvolvimento

```bash
pip install -e '.[dev]'      # instala em modo editavel com pytest/mypy/ruff
pytest                       # roda os 26 testes unitarios
ruff check .                 # lint
mypy .                       # type check (strict)
```

Apos `pip install -e .`, o comando `big-brain` fica disponivel no `PATH`.

## Convencoes obrigatorias

### Nomenclatura
- Nome do **produto** e do **comando CLI**: `big-brain` (com hifen).
- Nome de **modulo Python** nao existe (layout flat) — se for preciso um
  identificador Python referente ao projeto, use `big_brain` com underscore.
- **Slug** de nota: lowercase, sem acentos, hifens no lugar de espacos. Use
  sempre `utils.slugify.slugify()`.
- **Arquivo de nota:** `{tipo}__{slug}.md` (duplo underscore entre tipo e
  slug). Tipos validos: `context`, `rule`, `request`, `decision`, `feature`,
  `bug`.

### Datas
Sempre ISO 8601 (`YYYY-MM-DD`). Use `datetime.date` no codigo, `isoformat()`
ao serializar.

### I/O
- Nunca use strings de caminho — sempre `pathlib.Path`.
- Nunca use `input()` fora do comando `big-brain chat`.
- Frontmatter: sempre via `utils.frontmatter.read_note` / `write_note`
  (que embrulham `python-frontmatter`).

### Git
- Mensagens de commit que o proprio app gera seguem o padrao
  `big-brain: {action} {note_slug}`. Nao mude o prefixo sem atualizar
  `core/git_sync.py`, `core/config.py` e `cli/status.py`
  (`_last_big_brain_commit` filtra por esse prefixo).
- `git_sync` nunca deve fazer `push --force`, `reset --hard`, ou apagar
  branches. Em conflito, levanta `GitConflictError` e para.

### Tratamento de erros
- `NoteDeleteError` exige confirmacao explicita (`--confirm` na CLI).
- `GitConflictError` suspende o push, preserva a nota local.
- `InferenceError` e fallback silencioso — nunca deixe `big-brain init`
  falhar, grave `confidence: "low"` se necessario.
- Erros criticos: renderize com `utils.ui.error_panel` (borda vermelha).

### UX
- Toda saida no terminal passa por `utils.ui.console` (Rich).
- Status pos-acao sempre em cinza discreto (`status_line`), nunca antes da
  resposta principal.
- Icones padronizados: 📂 ativo, 📝 criada, 🔄 atualizada, 🔗 links,
  ✅ git, ⚠️ atencao, ⚙️ config.

## Configuracao em dois niveis

- **Global** (`~/.big-brain/config.json`): preferencias do usuario, criado
  automaticamente. Inclui `notes_dir`, a pasta global onde ficam notas de
  todos os projetos. Caminhos relativos partem de `~/.big-brain`. Schema em
  `core/config.GlobalConfig`.
- **Local** (`.big-brain/project.json`): gerado por `infer_project()`, nunca
  editado manualmente. Schema em `core/config.ProjectConfig`. Descoberta
  sobe o filesystem a partir do cwd, igual ao `.git`.

`load_config()` faz deep-merge da config global. A config local identifica o
projeto atual, mas as notas sao sempre salvas no vault global configurado em
`notes_dir`.

## Detectores de gatilho

Ficam em `core/session.TRIGGERS` como `dict[NoteType, list[str_regex]]`.
Para adicionar padroes novos:
1. Edite o dict.
2. Adicione um teste em `tests/test_session.py`.
3. Lembre: regex sao aplicadas sobre o texto ja normalizado (sem acentos).

## LLM

Provider default: `codex-bridge`, via broker HTTP local. Configurado em
`config.GlobalConfig.llm` (`model`, `reasoning_effort`, `base_url`,
`timeout_seconds`). O endpoint default e `http://127.0.0.1:47831/v1/chat`.
Sem o broker ativo, `LLMClient` cai num modo offline que preserva o fluxo
(notas ainda sao criadas, so a resposta do chat vira um eco).

Para trocar de provider, reescreva `LLMClient.chat` em `core/session.py` —
o resto do codigo nao depende do formato da resposta.

## O que NAO fazer

- Nao introduza um pacote `big_brain/` ou `brainhub/` — layout e flat de
  proposito.
- Nao adicione dependencies alem do necessario; o runtime e enxuto.
- Nao escreva arquivos markdown de "plan"/"decisions" no repo — use as
  proprias notas do Big Brain para isso (vault global em `notes_dir`).
- Nao commite com `--no-verify` nem mexa em hooks.
- Nao coloque `input()` ou prompts interativos em comandos que nao sejam
  `big-brain chat`.
- Nao edite `.big-brain/project.json` manualmente — sempre pela API em
  `core/config.save_project_config`.

## Testes

Rode `pytest` antes de abrir um PR. Os testes sao rapidos (<1s) e cobrem:
- merge de config e descoberta da raiz
- inferencia por sentinela (Python, Node+Next, etc.)
- CRUD de nota + regeneracao do `_index.md`
- deletes exigem `confirmed=True`
- triggers (rule / request / decision)
- `git_sync` num repo git real criado em `tmp_path`
- slugify (acentos, caracteres especiais, fallback)

Ao adicionar funcionalidade, adicione teste unitario no arquivo
correspondente ou crie um novo `test_*.py`.

## Fluxo tipico de uma mudanca

1. Leia o modulo afetado e seus testes primeiro.
2. Faca a mudanca minima necessaria — este codebase evita abstracoes
   especulativas.
3. Rode `pytest` localmente.
4. Atualize o README apenas se houver mudanca de UX ou comando visivel.
5. Commits manuais do humano nao usam o prefixo `big-brain:` (esse prefixo
   e exclusivo do sync automatico).
