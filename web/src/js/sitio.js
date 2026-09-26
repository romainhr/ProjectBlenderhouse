// Comportamiento común del sitio: menú de teléfono, aparición al entrar en pantalla, precios de ejemplo, encabezado
// sobre el hero, barra fija de la portada y progreso del carrusel de Espacios (web/diseno/ESPEC-v4.md §6.2).
import { TARIFA, clp } from "./reserva-logica.js";

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

// precios de ejemplo escritos en el HTML con data-precio (el texto del HTML es el respaldo sin JS)
document.querySelectorAll("[data-precio]").forEach((el) => { el.textContent = clp(TARIFA[el.dataset.precio]); });
const anio = $("#anio");
if (anio) anio.textContent = String(new Date().getFullYear());

// Encabezado transparente sobre el hero y barra fija oculta en el hero y sobre Tarifas (solo en la portada).
const hero = $(".hero"), barra = $(".barra"), movil = $(".barra-movil"), tarifas = $("#tarifas");
if (hero && barra) {
  if ("IntersectionObserver" in window) {
    let enHero = true, enTarifas = false;
    const aplicar = () => {
      barra.classList.toggle("sobre-hero", enHero);
      movil?.classList.toggle("oculta", enHero || enTarifas);
    };
    new IntersectionObserver(([e]) => { enHero = e.isIntersecting; aplicar(); },
      { rootMargin: `-${barra.offsetHeight}px 0px 0px 0px` }).observe(hero);
    if (tarifas && movil) {
      new IntersectionObserver(([e]) => { enTarifas = e.isIntersecting; aplicar(); },
        { rootMargin: `-${barra.offsetHeight}px 0px -${movil.offsetHeight}px 0px` }).observe(tarifas);
    }
    // la barra se desliza sólo después del primer estado: al cargar no aparece y se va
    requestAnimationFrame(() => requestAnimationFrame(() => movil?.classList.add("lista")));
  } else {
    barra.classList.remove("sobre-hero");
    movil?.classList.remove("oculta");            // en el HTML parte oculta (sin JS la muestra el <noscript>)
  }
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
