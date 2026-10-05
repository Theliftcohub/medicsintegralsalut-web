# Contenido generado de la web (páginas, entradas, imágenes)

`src/content/`, `public/images/` y `public/media/` se generan con los scripts de `scripts/` a partir del HTML del WordPress (ver CLAUDE.md).
Se suben empaquetados porque la subida por la web de GitHub no admite miles de archivos de una vez.

Para reconstruirlos en local, desde la raíz del repo:

    cat _datos/contenido-web.tgz.part* | tar -xz

Fecha del paquete: 05/10/2026 (tras schema_posts.py y pulir_contenido.py; rama mejoras-menu-paginas-seo).
Para regenerarlo tras cambiar contenido:

    tar -cf - src/content public/images public/media | gzip -9 | split -b 9437184 -d -a 2 - _datos/contenido-web.tgz.part
