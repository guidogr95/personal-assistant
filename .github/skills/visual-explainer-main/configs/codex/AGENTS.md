Use the canonical `visual-explainer` skill from `plugins/visual-explainer/`.

For Codex CLI, copy the skill to `~/.codex/skills/visual-explainer`. If your Codex build supports prompt templates, you may also copy `plugins/visual-explainer/commands/*.md` to `~/.codex/prompts/`.

Activate by asking Codex to use `$visual-explainer` or the `visual-explainer` skill before generating diagrams, diff reviews, plan reviews, slide decks, or complex tables. Generated pages go to `~/.agent/diagrams/`; opening the browser may depend on Codex sandbox permissions.

Command-template support varies by Codex version. If prompts are unavailable, read the relevant command file and follow the skill workflow manually. `/share-page` depends on the Pi-compatible `vercel-deploy` script and may not work unless that dependency exists in a compatible location.
