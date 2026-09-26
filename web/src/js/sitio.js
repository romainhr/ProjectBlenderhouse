// Comportamiento común del sitio: menú de teléfono, selector de idioma, aparición al entrar en pantalla, precios de
// ejemplo, encabezado sobre el hero, barra fija de la portada y progreso del carrusel de Espacios
// (web/diseno/ESPEC-v4.md §6.2).
// El locale de la página sale de idioma.js y no de i18n.js: este módulo no escribe textos del diccionario, así que
// no pide ninguno por la red ni espera nada para poner los precios (ADR 0007, decisión 2).
import { TARIFA, clp } from "./reserva-logica.js";
import { IDIOMAS, LOCALE } from "./idioma.js";

const $ = (s, r = document) => r.querySelector(s);
document.documentElement.classList.add("js");        // el CSS muestra lo que sólo tiene sentido con JS (.progreso)

// menú de teléfono
const boton = $(".hamburguesa");
const panel = $("#panel-menu");
if (boton && panel) {
  const cerrar = () => { panel.hidden = true; boton.setAttribute("aria-expanded", "false"); };
  boton.addEventListener("click", () => {
    const abrir = panel.hidden;
    panel.hidden = !abrir;
    boton.setAttribute("aria-expanded", String(abrir));
  });
  panel.addEventListener("click", (e) => { if (e.target.closest("a")) cerrar(); });
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && !panel.hidden) { cerrar(); boton.focus(); }
  });
}

// Selector de idioma: <a data-i18n-alternar="es|en|fr">, con el href que le pone web/build.py. Al elegir, antes de
// que el enlace navegue, se guarda la cookie nf_lang: en Netlify reemplaza la detección por el idioma del navegador
// (ADR 0007, decisión 4), así quien eligió español se queda en español aunque su navegador pida inglés. También con
// el clic central (abre otra pestaña). El tour no carga este módulo: hace lo mismo en web/src/tour/js/interfaz.js.
const guardarIdioma = (e) => {
  if (e.type === "auxclick" && e.button !== 1) return;
  const idioma = e.target.closest?.("a[data-i18n-alternar]")?.getAttribute("data-i18n-alternar");
  if (IDIOMAS.includes(idioma)) document.cookie = `nf_lang=${idioma}; path=/; max-age=31536000; SameSite=Lax; Secure`;
};
document.addEventListener("click", guardarIdioma);
document.addEventListener("auxclick", guardarIdioma);

// aparición al entrar en pantalla. El contenido nunca queda oculto (RA-16): sin JS, sin IntersectionObserver o sin
// desplazarse se ve igual. Sólo se anima (.visible) lo que entra desde abajo después de la carga; lo que ya estaba en
// pantalla o se cruza hacia arriba queda quieto.
if ("IntersectionObserver" in window && !matchMedia("(prefers-reduced-motion: reduce)").matches) {
  let inicial = true;
  const obs = new IntersectionObserver((entradas) => {
    for (const e of entradas) {
      if (!e.isIntersecting) continue;
      obs.unobserve(e.target);
      if (!inicial && e.boundingClientRect.top > 0) e.target.classList.add("visible");
    }
    inicial = false;
  });
  document.querySelectorAll(".aparece").forEach((el) => obs.observe(el));
}

// precios de ejemplo escritos en el HTML con data-precio (el texto del HTML es el respaldo sin JS), con el formato del
// idioma de la página: CLP 58.000, CLP 58,000 o CLP 58 000
document.querySelectorAll("[data-precio]").forEach((el) => { el.textContent = clp(TARIFA[el.dataset.precio], LOCALE); });
const anio = $("#anio");
if (anio) anio.textContent = String(new Date().getFullYear());

// Encabezado transparente sobre el hero y barra fija oculta en el hero y sobre Tarifas (solo en la portada).
// index.html ya trae .sobre-hero (ESPEC-v4 §2.2): al cargar no parpadea de papel a transparente. Sin JS lo vuelve sólido
// el <noscript>; sin IntersectionObserver, este módulo le quita la clase para que el menú no quede blanco sobre papel.
const hero = $(".hero"), barra = $(".barra"), movil = $(".barra-movil"), tarifas = $("#tarifas");
if (hero && barra) {
  if ("IntersectionObserver" in window) {
    let enHero = hero.getBoundingClientRect().bottom > barra.offsetHeight, enTarifas = false;
    const aplicar = () => {
      barra.classList.toggle("sobre-hero", enHero);
      movil?.classList.toggle("oculta", enHero || enTarifas);
    };
    aplicar();                                     // al iniciar, sin esperar la primera respuesta del observador
    new IntersectionObserver(([e]) => { enHero = e.isIntersecting; aplicar(); },
      { rootMargin: `-${barra.offsetHeight}px 0px 0px 0px` }).observe(hero);
    if (tarifas && movil) {
      new IntersectionObserver(([e]) => { enTarifas = e.isIntersecting; aplicar(); },
        { rootMargin: `-${barra.offsetHeight}px 0px -${movil.offsetHeight}px 0px` }).observe(tarifas);
    }
    // la barra se desliza sólo después del primer estado: al cargar no aparece y se va
    requestAnimationFrame(() => requestAnimationFrame(() => movil?.classList.add("lista")));
  } else {
    barra.classList.remove("sobre-hero");         // no se sabría cuándo sale del hero: queda sólido
    movil?.classList.remove("oculta");            // en el HTML parte oculta (sin JS la muestra el <noscript>)
  }
}

// Carruseles (.desliza): parada de Tab solo mientras se desplazan (bajo 700 px). En la retícula de escritorio no se
// mueven, y un tabindex=0 dejaba una parada que mostraba el anillo y no hacía nada. Sin JS conservan el del HTML.
const carruseles = document.querySelectorAll(".desliza[tabindex]");
if (carruseles.length) {
  const paradas = () => carruseles.forEach((c) => {
    if (c.scrollWidth > c.clientWidth + 1) c.setAttribute("tabindex", "0");
    else if (document.activeElement !== c) c.removeAttribute("tabindex");
  });
  addEventListener("resize", paradas);
  paradas();
}

// Barra de progreso del carrusel de Espacios (decorativa: aria-hidden).
const car = $(".espacios"), relleno = $(".progreso i");
if (car && relleno) {
  const avance = () => {
    if (!car.scrollWidth) return;
    const f = car.clientWidth / car.scrollWidth, max = car.scrollWidth - car.clientWidth;
    relleno.style.width = `${Math.min(1, f) * 100}%`;
    relleno.style.transform = `translateX(${max > 0 ? (car.scrollLeft / max) * (1 / f - 1) * 100 : 0}%)`;
  };
  car.addEventListener("scroll", avance, { passive: true });
  addEventListener("resize", avance);
  avance();
}
