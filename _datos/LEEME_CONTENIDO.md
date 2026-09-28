# Contenido generado de la web (páginas, entradas, imágenes)

`src/content/` (1.600+ páginas y entradas en 6 idiomas), `public/images/` y `public/media/` se generan con los scripts
de `scripts/` a partir del HTML del WordPress (ver CLAUDE.md → "Construcción de páginas «Versión C»").
Se suben aquí empaquetados porque la subida por la web de GitHub no admite miles de archivos de una vez.

Para reconstruirlos en local, desde la raíz del repo:

    cat _datos/contenido-web.tgz.part* | tar -xz

Fecha del paquete: 28/09/2026 (commit local ae71fa5).
