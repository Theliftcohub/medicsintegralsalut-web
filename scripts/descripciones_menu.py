#!/usr/bin/env python3
"""Meta description de las páginas del menú que no la tenían en el WordPress (blog, contacto y financiación, 6 idiomas;
07/10/2026, preparación del lanzamiento: Lighthouse SEO «meta-description»). Solo datos que ya figuran en la web
(dirección, teléfono, horario, Tu Medicina Financiada). Solo rellena si está vacía (idempotente). Registrado en NO_LITERAL.md.
Uso: python scripts/descripciones_menu.py"""
import glob, json

D = {
    "g0078": {  # contacto
        "es": "Contacta con Médics Integral Salut en Girona: Plaça Poeta Marquina 3 · 972 20 90 86. Primera valoración gratuita y sin compromiso, de lunes a viernes de 10 a 20 h.",
        "ca": "Contacta amb Médics Integral Salut a Girona: Plaça Poeta Marquina 3 · 972 20 90 86. Primera valoració gratuïta i sense compromís, de dilluns a divendres de 10 a 20 h.",
        "en": "Contact Médics Integral Salut in Girona: Plaça Poeta Marquina 3 · +34 972 20 90 86. Free, no-obligation first consultation, Monday to Friday, 10 am to 8 pm.",
        "fr": "Contactez Médics Integral Salut à Gérone : Plaça Poeta Marquina 3 · +34 972 20 90 86. Première consultation gratuite et sans engagement, du lundi au vendredi, 10 h-20 h.",
        "ru": "Свяжитесь с Médics Integral Salut в Жироне: Plaça Poeta Marquina 3 · +34 972 20 90 86. Первая консультация бесплатно и без обязательств, пн-пт с 10:00 до 20:00.",
        "uk": "Зв'яжіться з Médics Integral Salut у Жироні: Plaça Poeta Marquina 3 · +34 972 20 90 86. Перша консультація безкоштовна й без зобов'язань, пн-пт з 10:00 до 20:00.",
    },
    "g0031": {  # blog
        "es": "Artículos de cirugía plástica, medicina estética y pérdida de peso: precios, recuperación y consejos del equipo médico de Médics Integral Salut en Girona.",
        "ca": "Articles de cirurgia plàstica, medicina estètica i pèrdua de pes: preus, recuperació i consells de l'equip mèdic de Médics Integral Salut a Girona.",
        "en": "Articles on plastic surgery, aesthetic medicine and weight loss: prices, recovery and advice from the medical team at Médics Integral Salut in Girona.",
        "fr": "Articles sur la chirurgie plastique, la médecine esthétique et la perte de poids : prix, récupération et conseils de l'équipe de Médics Integral Salut à Gérone.",
        "ru": "Статьи о пластической хирургии, эстетической медицине и снижении веса: цены, восстановление и советы медицинской команды Médics Integral Salut в Жироне.",
        "uk": "Статті про пластичну хірургію, естетичну медицину та схуднення: ціни, відновлення й поради медичної команди Médics Integral Salut у Жироні.",
    },
    "g0099": {  # financiación
        "es": "Financia tu tratamiento de cirugía o medicina estética en Médics Integral Salut (Girona) con Tu Medicina Financiada: cuota a tu medida y respuesta inmediata.",
        "ca": "Finança el teu tractament de cirurgia o medicina estètica a Médics Integral Salut (Girona) amb Tu Medicina Financiada: quota a la teva mida i resposta immediata.",
        "en": "Finance your surgery or aesthetic medicine treatment at Médics Integral Salut (Girona) with Tu Medicina Financiada: instalments to suit you and an instant reply.",
        "fr": "Financez votre traitement de chirurgie ou de médecine esthétique chez Médics Integral Salut (Gérone) avec Tu Medicina Financiada : mensualités sur mesure, réponse immédiate.",
        "ru": "Оплатите лечение в рассрочку в Médics Integral Salut (Жирона) с Tu Medicina Financiada: удобный ежемесячный платёж и быстрый ответ.",
        "uk": "Оплатіть лікування в розстрочку в Médics Integral Salut (Жирона) з Tu Medicina Financiada: зручний щомісячний платіж і швидка відповідь.",
    },
}
n = 0
for f in glob.glob("src/content/pages/*/*.json"):
    j = json.load(open(f, encoding="utf-8"))
    g, L = j.get("i18nGroup"), j.get("lang")
    if g in D and L in D[g] and not (j["seo"].get("description") or "").strip():
        j["seo"]["description"] = D[g][L]
        json.dump(j, open(f, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        n += 1
        print(L, j["path"], len(D[g][L]), "caracteres")
print(n, "descripciones puestas")
