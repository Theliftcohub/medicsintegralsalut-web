# Datos de extracción comprimidos

Para respetar los límites de subida de GitHub, dos piezas del inventario van comprimidas:

- `inventory.json.gz` → `gunzip -k migracion/inventory.json.gz`
- `content.tgz.part00` + `content.tgz.part01` → `cat migracion/content.tgz.part0* | tar -xz` (crea `migracion/content/`)

El HTML íntegro del WordPress (`html_cache`, 530 MB) no está en el repo: se regenera con `scripts/extract_wp.py` o se recupera de `Claude WS\medics-transfer\cache.tgz` en el ordenador de Oscar.
