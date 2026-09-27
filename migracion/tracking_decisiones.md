# Decisiones de medición · Medics

- G-4N, G-7, G-B, G-L, G-Y: falsos positivos del detector (coinciden dentro de archivos binarios servidos por URLs de /wp-content/ que el rastreo guardó). No son IDs de GA4. GA4 real (propiedad 452228366 "GA4- Medics Salut") se carga desde GTM-K63QVGT.
- GTM-K63QVGT: se mantiene idéntico.
- Píxel de Meta 1839689313580301: hoy va incrustado fuera de GTM. DECIDIDO (Oscar 27/09/2026): se mueve DENTRO de GTM con Consent Mode. Acción previa al lanzamiento: crear la etiqueta del píxel en GTM-K63QVGT (quien gestione el contenedor) y verificarlo con el gestor de eventos de Meta en staging.
- google-site-verification ADI8CxJ20viWN2iHsYFqV7gukVJm7aH_fqSewhM1_eU y msvalidate.01 95BFB6A60C12C3589CF205FDE62D5E88: se mantienen en el <head> (GSC ya es propiedad de dominio, pero se conservan por seguridad).
- CMP: la web actual NO tiene banner de cookies detectable. La nueva sí lo lleva (Consent Mode v2, rechazar al mismo nivel que aceptar). Cambio a mejor, obligatorio en el EEE.

- Verificado en el Administrador de eventos de Meta (27/09/2026, cuenta publicitaria Medics Aesthetics Girona 1372216830459638):
  - 1839689313580301 "Pixel Medics Landing (TheLift)": EL BUENO. 532 eventos en 28 días. Es el que se mete en GTM.
  - 339816866888771 (etiqueta antigua en GTM): sin acceso desde el negocio de The Lift → píxel heredado de otro propietario. Se PAUSA en GTM el día del lanzamiento.
  - 1410565256779456 "Pixel Medics Integral Salut Web": existe, sin actividad. No se usa.
  - Meta marca restricciones de uso compartido de datos (categoría salud) en el píxel bueno: solo PageView/Lead estándar, sin parámetros sensibles en URL.
