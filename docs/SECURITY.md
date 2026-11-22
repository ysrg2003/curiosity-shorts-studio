# Security and operation

- Generation has no OAuth credentials and no upload call. Public Action logs must never include private account information, tokens, client files or private source text.
- Publication is workflow_dispatch only, from main, with an exact reviewed video hash and explicit audience. Do not run untrusted pull request code with publication secrets.
- Store YOUTUBE_TOKEN_JSON in Actions secrets. Keep the youtube-publish environment protected by an owner review if available. Never use pull_request_target with these secrets.
- Source retrieval accepts public HTTPS addresses only, has time and size limits, and sends source text only to a local model. Source instructions are not code.
- A persistent reservation is committed before upload. An uncertain state blocks a later retry. If the runner crashes, inspect YouTube Studio before changing the ledger.
- Revocation: remove the Actions secret and revoke the app in the Google account's third-party access controls. Deleting a local token file alone does not revoke remote authorization.
- Count and runtime caps are editable safeguards, not product limitations or permission to spend. Preserve a zero-overage Actions budget when using a private repository.
- Changing a public repository to private later cannot recall forks, clones, downloaded artifacts or previously visible logs.

## Test levels

Unit tests mock YouTube. Rendering tests check streams, duration, aspect ratio, loudness and clipping. A contact sheet is an aid, not a replacement for watching the full video. Listen for pronunciations and inspect diagram/word alignment before public publication.
