# Copilot autoflow review guardrails

- Task: `AUTOFLOW-COPILOT-REVIEW-001`
- Base integration SHA: `5a8e423e9bb4893a85f5b1e9e3666ca7ff21b4c2`
- Branch target: draft PR into `feat/logres-reconstruction`

## Scope

- Allowed scope: `docs/logres/copilot-autoflow-review.md`
- Forbidden scope: `main`, direct commits or merges to `feat/logres-reconstruction`, and files outside the allowed scope
- Gameplay impact: none; this review records control-plane guardrails only

## Evidence policy

- Evidence mode: control-plane review only
- Historical behavior claims are out of scope
- If historical behavior becomes necessary to resolve the review, stop and report `BLOCKED_EVIDENCE`

## No-auto-merge guardrails

- Work only from an isolated `copilot/*` branch
- Do not commit directly to `feat/logres-reconstruction`
- Open a draft PR targeting `feat/logres-reconstruction`
- Do not self-merge or otherwise auto-merge the PR
- Keep the change limited to this document so gameplay code remains unchanged
