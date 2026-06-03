# Error i18n Dictionaries

`errors.zh-CN.yaml` is the single source for RFC 7807 error text. `errors.en-US.yaml` is the key-parity fallback.

When adding a new `remediation_hint_key` in production problem-detail code:

1. Add `errors.<status-or-scope>.<name>` to both dictionaries.
2. Fill `title`, `detail`, and `remediation`.
3. Run `python scripts/error_message_i18n_single_source.py`.

The CI rule is `error-message-i18n-single-source`.
