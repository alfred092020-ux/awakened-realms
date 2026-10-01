# Logres ChatGPT Bridge

This draft pull request is a permanent event bus between the Logres control plane and the owner ChatGPT account.

It is intentionally not part of the game integration branch and should not be merged.

VM to ChatGPT marker: LOGRES_CHATGPT_BRIDGE:VM

ChatGPT to VM marker: LOGRES_CHATGPT_BRIDGE:CHATGPT

The VM listener accepts only structured JSON payloads from the configured GitHub account. It never evaluates comment text as shell code.
