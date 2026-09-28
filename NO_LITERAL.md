# NO_LITERAL.md · textos que no son literales del WordPress

Cada fila: URL · campo · texto original · texto nuevo · motivo. El cliente lo revisa antes de lanzar.

| URL | Campo | Original | Nuevo | Motivo |
|---|---|---|---|---|
| (todas, pie) | enlaces redes sociales | iconos sin texto (Facebook, Instagram, YouTube) | texto "Facebook", "Instagram", "YouTube" | diseño nuevo; accesibilidad (enlaces con nombre) |
| / | reseñas | widget Trustindex (carrusel con estrellas) | tarjetas estáticas con el mismo texto y nombre, sin estrellas | no se afirma una puntuación que el HTML no expone por reseña |
| / | diseño | plantilla WPBakery | maqueta «Versión C» (The Lift, 28/09/2026; `migracion/diseno/home-version-c.html`) | decisión Oscar: integrar la home pensada para Medics |
| / | hero · subtítulo | — | "Cirugía plástica y medicina estética en el centro de Girona. Resultados naturales, criterio médico y acompañamiento en cada paso." | texto de la maqueta |
| / | hero · nota | "Sin compromiso · Atención médica" | "Sin compromiso · Atención médica · Respuesta el mismo día laborable" | maqueta |
| / | hero · CTA | un botón | + "WhatsApp 620 892 236" | maqueta |
| / | hero y opiniones · cifras | — | nota media y nº de reseñas de Google (4,8 · 220 a 28/09/2026, desde `site.json → rating`, dato de GBP), "2014 · Atendiendo en Girona" (año de apertura en GBP) | maqueta traía 4,7 · 206 (desactualizado) y "Años en Girona"; se usa el dato vivo |
| / | hero · cifras | — | "SECPRE · Cirujanos colegiados" y "Gratuita · Primera valoración" | maqueta — **validar con la clínica** (SECPRE es una sociedad, no un colegio) |
| / | etiquetas (kickers) | — | La clínica, Tratamientos, Especialidades, Opiniones, Testimonios, Medicina estética, El equipo, Contacto, Girona y Costa Brava; numeración I–IX | maqueta ("Medicina estética" añadido para la sección que la maqueta no tenía) |
| / | reseñas · subtítulo | — | "Elige estar en las mejores manos" (reutiliza el H3 del bloque NAP) y "Reseña en Google" bajo cada nombre | maqueta |
| / | reseñas · botón | — | "Ver las 220 reseñas en Google" (enlace a la ficha) | maqueta |
| / | vídeos · títulos | "Bypass gastrico-Amador-Emili", "Aumento pecho- mike-eli", "Rinoplastia-sergio-judith", "botoox-mike-lidia" | "Bypass gástrico: el testimonio de Emili", "Aumento de pecho: el testimonio de Elizabeth", "Rinoplastia: el testimonio de Judith", "Arrugas de expresión: el testimonio de Lidia" + etiqueta "Testimonio" | los originales son nombres internos; la maqueta ponía "Amador" como paciente, pero Amador García es el médico (lo dice la miniatura). Nombres de paciente = los que ya salen en cada miniatura. **Confirmar consentimiento** |
| / | vídeos · subtítulo | "Los buenos resultados nuestra principal motivación" | "Los buenos resultados, nuestra principal motivación" | coma (maqueta) |
| / | vídeos · enlace | ficha /portfolio_page/video-prueba-N/ | el vídeo de YouTube | maqueta |
| / | vídeos · alt | vacío | "Testimonio bypass gástrico", etc. | maqueta; accesibilidad |
| / | tratamientos · fotos | tarjetas sin foto | imagen destacada (og:image) de cada página de tratamiento; alt = nombre del tratamiento | la maqueta marcaba 4 huecos; se rellenan con fotos ya publicadas por la clínica (la de Liposucción lleva el texto incrustado) |
| / | equipo · nombres | "Dr. Valenti Puig Divi", "Dr. Alberto Gonzalez" | "Dr. Valentí Puig Divi", "Dr. Alberto González" | tildes (maqueta) |
| / | equipo · retratos | 300×300 | original 500×500 (275 en Puig Divi), B/N que pasa a color | maqueta; siguen sin ser retratos homogéneos 3:4 (pendiente sesión de fotos) |
| / | equipo · tarjeta | "Te orientamos personalmente / Respuesta en el mismo día laborable" junto al formulario | además como tarjeta con botón "Solicitar valoración" en la rejilla del equipo | maqueta |
| / | distintivos · alt | vacío | "SECPRE", "Clínica Diagonal", "Clínica Tres Torres", "Centro Médico Teknon", "SCCPRE" | maqueta; accesibilidad |
| / | contacto | bloque NAP con "T:", "W:", "Mail:", "Horario:" | filas Dirección / Teléfono / WhatsApp / Email / Horario, "cerrado" en minúscula, "A 5 minutos de la estación del AVE" | maqueta — **validar el dato del AVE** |
| / | contacto · mapa | enlace a Google Maps | mapa incrustado que se carga al pulsar "Ver el mapa" + aviso "Al cargar el mapa, Google puede instalar cookies." | maqueta con iframe; se carga bajo demanda por privacidad |
| / | cierre | — | H2 "Clínica de cirugía y medicina estética para toda la provincia de Girona" + párrafo con municipios + botones "Solicitar valoración" / "Ver financiación" | sección nueva de la maqueta (SEO local) — **validar** "financiación disponible y primera valoración gratuita" |
| / | cabecera | menú WordPress completo (mega menú) | menú corto: Clínica, Equipo, Unidades (#unidades), Financiación, Blog, Contacto + "Solicitar valoración"; menú móvil con WhatsApp; selector de idioma | maqueta |
| (todas) | pie | pie actual | mismo contenido y enlaces literales de cada idioma ordenados según la maqueta (logo de financiación incluido); línea "© año" + nombre literal del pie | maqueta |
| / | barra móvil | — | "Pedir valoración" / "WhatsApp" fija abajo en móvil | maqueta |
| / | imagen de la sección «La clínica» | clinica-estetica-Girona (maqueta) | mejor-clinica-estetica-girona.webp (imagen de la portada actual) | la de la maqueta es de 580 px con fondo negro y no aguanta el formato 3:4 |
| (todas) | cabecera | menú WordPress con mega menú | menú corto de la maqueta con las etiquetas literales del menú de cada idioma; "Medics Integral Salut" pasa a "Clínica" (ca Clínica, en Clinic, fr Clinique, ru Клиника, uk Клініка) | maqueta |
| /ca/ /en/ /fr/ /ru/ /uk/ | portada · textos nuevos de la maqueta | — | traducción propia de los textos nuevos de la maqueta (subtítulo, etiquetas, cifras, contacto, sección de cierre, títulos de vídeo) en `scripts/home_vc_textos.json` | **revisar por nativo** antes de lanzar |
| (entradas del blog) | H1 | "21 Mar ¿Cómo elegir…" (fecha dentro del H1 en Bridge) | H1 = título; la fecha va en la línea "Publicado … · Actualizado … · por …" | la fecha no es parte del título |
| (varias páginas) | shortcodes visibles | texto "[vc_row …][vc_raw_html]…" que el WordPress muestra por error | eliminado | fallo del sitio actual, no es contenido |
| (38 páginas) | imagen | `<img src="Sorry, I cannot process image files.">` (texto de una IA pegado como imagen) | eliminada | imagen rota en el sitio actual |
| (varias) | imágenes externas | enlazadas desde clinicarinos.com y medicstetics.com | no se muestran | no se copian imágenes de otras webs; revisar si alguna era propia |
| /portfolio_page/* | contenido | ficha vacía (solo navegación) | H1 con el título de la ficha | la página está vacía en el WordPress; propuesta: 301 al tratamiento |
| /w-lp-ginecomastia/, /w-lp-mamaria/ (6 idiomas) | formulario | Typeform ZTDKPHl5 | formulario propio con los campos del CF7 de /contacto/ del idioma | decisión Oscar: Typeform fuera siempre |
| (todas) | vídeos y mapas | iframe de YouTube / Google Maps cargado al abrir | fachada que carga el vídeo o el mapa al pulsar | privacidad (sin cookies de terceros antes del clic) |
| (páginas de tratamiento) | diseño | componentes .mpost | mismo marcado y textos con la piel «Versión C» (`vc-mpost.css`) | decisión Oscar: Versión C en toda la web |
| /unidades/ (6 idiomas) | contenido | página vacía en el WordPress (solo el botón flotante de WhatsApp) | índice de unidades literal de la portada del idioma, con su título como H1 | la página es destino del menú; vacía no sirve ni a usuarios ni a SEO |
