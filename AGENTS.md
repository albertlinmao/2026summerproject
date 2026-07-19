<!-- SPECKIT START -->

For additional context about technologies to be used, project structure,
shell commands, and other important information, read the current plan

<!-- SPECKIT END -->

## AGENTS: Local AI assistant guide

**Purpose**: Provide minimal, actionable guidance so AI coding agents can be immediately productive in this repository.

**Repo Layout**

- **Top-level:** links to key artifacts:[SyncroSwimmingTeamsandGames_datamodeling.txt](SyncroSwimmingTeamsandGames_datamodeling.txt)
- **Data samples:** see [swim-meets](swim-meets/)

**Agent Guidelines**

- **Minimal by default:** Prefer linking to existing docs rather than copying them.
- **Ask when unsure:** If build/test commands, environment, or model info are missing, ask the human rather than guessing.
- **No secrets:** Never create, persist, or suggest committing API keys, tokens, or credentials.

**Ollama Integration**

- **When relevant:** If a developer indicates they use Ollama (local or remote), prefer local model usage and ask for the model name and any local host/port if not provided.
- **Config hints:** Ask the human to provide the Ollama model identifier or the environment variable they use (for example a `OLLAMA_MODEL` or `OLLAMA_HOST`), and whether they use the `ollama` CLI or an HTTP proxy.
- **Safe behavior:** Do not assume availability of specific models or CLI flags; validate by asking and prefer reproducible commands the developer can run locally. Link to upstream docs: https://ollama.com/docs

**Next steps / Suggestions**

- If you want, I can add a short `.github/copilot-instructions.md` or expand this file with language-specific run/test commands when you tell me which environment tooling you use (Python venv, Docker, etc.).
