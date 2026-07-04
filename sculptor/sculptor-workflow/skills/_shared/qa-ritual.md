# The Q&A ritual (shared)

These rules govern every Q&A turn in the sculptor-workflow skills.
The skill that sent you here adds its own step-specific content (what
to ask, which artifact to update) on top of these; the rules below are
non-negotiable in every skill.

## Every turn ends by asking the user a question with your question tool

**Every turn in a Q&A loop MUST end by asking the user a question with
your question tool.** This is the single rule that determines whether
the turn succeeded. If you end a turn without it, you have stopped
silently — the user has nothing to respond to and the skill is stuck.

Before ending any turn, verify: *did this turn end by asking the user
a question with your question tool?* If not, do so now.

The ritual holds regardless of what happened earlier in the turn —
research, answering the user's question, long discussion, a
back-and-forth. Every one of those ends by asking the user a question
with your question tool.

## The one exception: spawn turns

When a skill spawns the next agent (a Mock, Architect, Plan, Build,
Review, or fixer agent — each skill names its own target), the
spawning turn ends with **text instructions** pointing the user at the
new tab instead of a question. This is deliberate: the workspace's
"waiting for input" state must belong to the spawned agent while the
user works there — a question from this agent would mask the spawned
agent's attention signals.

The exception applies only to the spawn turn itself. Once the user
replies, you're in a normal Q&A turn again and the ritual resumes.
When the user returns, infer their intent from free-form text rather
than prescribing reply phrases.

## When the user asks a question back or pushes back

The user will often:

- Ask a question back (e.g. "How will this work with X?")
- Push back on your options ("none of these fit — what if we did Y?")
- Want to drill into a topic before committing to an answer

This is a feature, not a problem. When it happens, the conversational
frame shifts: you owe the user a response before asking anything new.
**This is the moment the skill fails most often** — the agent goes
into "answer the user" mode and forgets to close the turn by asking
the user a question with your question tool.

Handle it like this:

1. **Engage with what the user said.** Answer their question. Push
   back on their pushback. Do research (Grep, Read) if needed to
   answer concretely.
2. **Update the skill's artifact** (the spec, architecture, plan,
   review, or mock file — whichever this skill owns) to reflect
   anything new the conversation surfaced.
3. **End the turn by asking the user a question with your question
   tool.** Usually a follow-up that builds on what you just discussed,
   but it can also be "keep drilling into this, or move on?" — so the
   user stays in control of the pace.

The turn still ends with you asking. The user drives the conversation;
you drive the artifact forward.

## When the user's answer requires research

The silent-stop failure is especially likely when a user's answer
prompts more exploration (Grep, Read, or another round of codebase
digging) before the next question. Research output eats your output
budget, and the final synthesis step — including asking the user a
question — gets skipped.

Do the research. Then still update the artifact and still ask the user
a question with your question tool in the same turn. Research does not
excuse skipping the ritual.

## Do not announce upcoming tool calls in text

When you're about to ask the user a question, do **not** announce the
call in text first. Just make the call.

Any sentence that announces an upcoming tool call — whether it ends in
a colon before a list, or a period before a transition — is a known
failure trigger. The model frequently emits an end-of-turn token
*after the announcement* instead of continuing into the tool call.
Examples of announcement preambles that trigger this:

- "Here are the options:" / "A few approaches:" / "The reasonable
  paths are:"
- "Let me offer the choice to finalize."
- "Let me ask the next round."
- "Now let me pose the remaining questions."
- "A few more questions."
- "Next I'll ask about X."

Delete any such sentence and ask the user directly. Options,
questions, and choices go INSIDE the question you ask, not as preamble
describing what you're about to do.

**Context about the prior state is fine** (e.g. "I updated the User
Scenarios section with that flow.", "Grepping turned up one related
helper in `foo.py`."). **Announcements about the next action are
not.** The rule: say nothing about what you're *about to* do — just
do it.

## How to ask

For every question, ask with your question tool — the built-in
`AskUserQuestion`. Never ask in plain text: only the tool call puts
the workspace into the "waiting for input" state that alerts the user.

Provide 1-4 concrete, distinct options grounded in what you found in
the codebase or the upstream artifacts. Sculptor's UI always shows a
free-text field alongside the options, so you do not need an explicit
"Other" option. For genuinely open-ended questions, provide no options
and rely on the free-text field.

Ask 1-4 questions per round. One sharp question is better than four
padded ones.
