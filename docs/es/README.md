# Páginas traducidas (ES)

Esta carpeta contiene **solo** las traducciones al español de las páginas de
`docs/` — es una carpeta de control, no forma parte de la documentación renderizada.

Reglas:

- Las páginas en portugués de `docs/*.md` siguen siendo la **fuente única** que
  renderiza el producto (menú Docs + popup de Ayuda IA).
- Solo se traducen las páginas listadas en el mapa `PARES` de
  `tools/readme_check.py`. Hoy: `00-visao-geral`, `01-arquitetura`,
  `02-como-executar`, `12-api-reference`.
- Cada archivo traducido lleva un marcador `<!-- sync: <origen>@<hash> -->` en sus
  primeras líneas. La verificación falla cuando la página en portugués cambia y la
  traducción no:

      python tools/readme_check.py        # falla si está desincronizado
      python tools/readme_check.py --lista
      python tools/readme_check.py --sync # regraba los hashes (solo tras revisar)

- Los archivos que empiezan con `_` y `README.md` nunca son renderizados por el
  producto; los dos árboles traducidos viven en subcarpetas, por lo que también son
  invisibles para `tools/doc_check.py` (que escanea solo `docs/*.md`, sin recursión).
