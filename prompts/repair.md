Your previous attempt failed to compile. Fix only the reported errors.
Do not restructure working code. Do not add features.

Current source:
{current_source}

Errors:
{errors_with_context}

Reference:
{symbol_lookups}

If a symbol's reference entry lists `valid_parents`, that statement is
only legal nested inside one of those parent blocks -- if your current
source has it outside all of them, the fix is to nest it inside one,
not to repeat the same top-level line again.
