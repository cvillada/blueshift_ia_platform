# Translated pages (EN)

This folder holds **only** the English translations of `docs/` pages — it is a
control folder, not part of the rendered documentation.

Rules:

- The Portuguese pages in `docs/*.md` remain the **single source** rendered by the
  product (Docs menu + AI Help popup).
- Only pages listed in the `PARES` map of `tools/readme_check.py` are translated.
  Today: `00-visao-geral`, `01-arquitetura`, `02-como-executar`, `12-api-reference`.
- Every translated file carries a `<!-- sync: <origem>@<hash> -->` marker on its
  first lines. The checker fails when the Portuguese page changes and the
  translation does not:

      python tools/readme_check.py        # fails if out of sync
      python tools/readme_check.py --lista
      python tools/readme_check.py --sync # rewrites hashes (only after reviewing)

- Files starting with `_` and `README.md` are never rendered by the product; both
  translated trees live in subfolders, so they are also invisible to
  `tools/doc_check.py` (which scans `docs/*.md` only, non-recursive).
