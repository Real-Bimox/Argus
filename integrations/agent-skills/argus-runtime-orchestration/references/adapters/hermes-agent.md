# Hermes Agent adapter

**Evidence level:** documented from current official Hermes Agent docs/README; Hermes was not installed for local execution testing.

- Discovery: Hermes uses `~/.hermes/skills/` as its primary skill store and can scan configured `skills.external_dirs`, including `~/.agents/skills`. Installed skills become slash commands and can also load by relevance. External directories are mutable if writable; filesystem permissions, not `external_dirs`, provide write protection.
- Shell/process: enable terminal/file tooling. Hermes documents `terminal(..., background=true)` returning a session id and a `process` tool for list/poll/wait/log/kill/write. PTY mode supports interactive CLIs. Terminal execution environments include local and isolated/remote options.
- Durability: process management is environment- and version-dependent. Current official docs state that some remote/container environments persist files but not live processes and that the Vercel environment has no native detached-process recovery after cleanup/restart. Verify the active environment; use Argus `--daemon` and durable project state as the invariant, and treat Hermes process handles as conditional live monitoring.
- Approvals: `smart`, `manual`, and `off` modes guard dangerous commands; timeout fails closed. Messaging surfaces can route approval questions. Hardline blocks remain even in YOLO; isolated container environments may use the container as the boundary. Do not disable safeguards to obtain unattended operation.
- Limit: when terminal, process, PTY, or a reachable approval surface is disabled for the current toolset/platform, fall back exactly as the core describes.
- Model: Hermes Agent is the outer operator; Argus is the other party. Do not elevate Argus's configured internal provider CLI into a Hermes peer.

Sources: https://hermes-agent.nousresearch.com/docs/user-guide/features/skills ; https://hermes-agent.nousresearch.com/docs/user-guide/features/tools ; https://hermes-agent.nousresearch.com/docs/user-guide/security ; https://github.com/NousResearch/hermes-agent
