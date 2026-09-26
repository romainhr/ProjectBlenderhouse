// Comportamiento común del sitio: menú de teléfono, aparición al hacer scroll y la tarjeta de reserva de la portada.
import { TARIFA, clp, hoyIso, noches, sumarDias, total, validarRango, MENSAJES } from "./reserva-logica.js";

const $ = (s, r = document) => r.querySelector(s);

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

// aparición al hacer scroll
const aparecen = document.querySelectorAll(".aparece");
if ("IntersectionObserver" in window && !matchMedia("(prefers-reduced-motion: reduce)").matches) {
  const obs = new IntersectionObserver((entradas) => {
    for (const e of entradas) if (e.isIntersecting) { e.target.classList.add("visible"); obs.unobserve(e.target); }
  }, { rootMargin: "0px 0px -8% 0px" });
  aparecen.forEach((el) => obs.observe(el));
} else {
  aparecen.forEach((el) => el.classList.add("visible"));
}

// precios de ejemplo escritos en el HTML con data-precio
document.querySelectorAll("[data-precio]").forEach((el) => { el.textContent = clp(TARIFA[el.dataset.precio]); });
const anio = $("#anio");
if (anio) anio.textContent = String(new Date().getFullYear());

// tarjeta rápida de la portada: fechas y huéspedes -> página de reserva con esos datos
const rapida = $("#reserva-rapida");
if (rapida) {
  const ent = $("#r-entrada", rapida), sal = $("#r-salida", rapida), hue = $("#r-huespedes", rapida);
  const est = $("#r-estimado", rapida), err = $("#r-error", rapida);
  const hoy = hoyIso();
  ent.min = hoy;
  ent.max = sumarDias(hoy, TARIFA.anticipacionMaxDias);
  const actualizar = () => {
    if (ent.value) {
      sal.min = sumarDias(ent.value, TARIFA.minNoches);
      if (!sal.value || sal.value < sal.min) sal.value = sal.min;
    }
    const v = validarRango(ent.value, sal.value, [], hoy);
    err.textContent = ent.value && sal.value && !v.ok ? MENSAJES[v.error] : "";
    est.textContent = v.ok ? `${noches(ent.value, sal.value)} noches · total estimado ${clp(total(v.noches).total)}` : "";
  };
  ent.addEventListener("change", actualizar);
  sal.addEventListener("change", actualizar);
  rapida.addEventListener("submit", (e) => {
    e.preventDefault();
    const q = new URLSearchParams({ huespedes: hue.value });
    if (ent.value) q.set("entrada", ent.value);
    if (sal.value) q.set("salida", sal.value);
    location.href = `reserva.html?${q}#calendario`;
  });
}
