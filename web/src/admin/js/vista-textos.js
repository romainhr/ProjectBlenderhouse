// Vista «Textos»: filas de public.contenido agrupadas por grupo; cada fila se edita y se guarda por separado.
import { mensajeError } from "./errores.js";
import { LIMITE_VALOR, MENSAJES_VALOR, agruparContenido, previaPrecio, validarValor } from "./logica-contenido.js";
import { anunciar, confirmar, el, mientras, oculto, vaciar } from "./ui.js";
import { formatearMomento, horaCorta, largo, unaALaVez } from "./util.js";

export function crearVistaTextos({ raiz, api }) {
  const nodos = { grupos: raiz.querySelector("#textos-grupos"), aviso: raiz.querySelector("#textos-aviso"),
    recargar: raiz.querySelector("#textos-recargar") };
  let cargada = false;
  let generacion = 0;                    // sube al cerrar sesión: una respuesta tardía ya no se pinta
  const sucias = new Set();          // claves con cambios sin guardar

  nodos.recargar.addEventListener("click", async () => {
    if (sucias.size) {
      const ok = await confirmar({ titulo: "Textos sin guardar", texto: "Hay textos con cambios sin guardar. ¿Descartarlos y volver a cargar?",
        boton: "Descartar y recargar", peligro: true });
      if (!ok) return;
    }
    cargar();
  });
  const cargaInicial = unaALaVez(() => cargar());          // una sola carga inicial a la vez (se suelta al cerrar sesión)

  async function cargar() {
    anunciar(nodos.aviso, "Cargando textos…", "cargando");
    nodos.recargar.disabled = true;
    const gen = generacion;
    try {
      const filas = await api.contenido.listar();
      if (gen !== generacion) return;
      cargada = true;
      sucias.clear();
      pintar(filas);
      anunciar(nodos.aviso, filas.length ? "" : "No hay textos editables todavía (la semilla de la migración 0003 los crea).",
        filas.length ? "info" : "error");
    } catch (e) {
      if (gen !== generacion) return;
      anunciar(nodos.aviso, mensajeError(e), "error");
    } finally {
      nodos.recargar.disabled = false;
    }
  }

  function pintar(filas) {
    vaciar(nodos.grupos);
    let i = 0;
    for (const g of agruparContenido(filas)) {
      const idTitulo = `grupo-${i}`;
      const seccion = el("section", { clase: "grupo-textos", "aria-labelledby": idTitulo },
        el("h2", { id: idTitulo, texto: g.titulo }));
      for (const f of g.filas) seccion.append(fila(f, i++));
      nodos.grupos.append(seccion);
    }
  }

  function fila(f, i) {
    const id = `texto-${i}`;
    const idAyuda = `${id}-ayuda`, idError = `${id}-error`;
    let original = String(f.valor ?? "");
    const esPrecio = f.tipo === "precio";
    const control = f.tipo === "parrafo"
      ? el("textarea", { id, rows: 5, value: original })
      : el("input", { id, type: "text", value: original, autocomplete: "off", inputMode: esPrecio ? "numeric" : null,
        spellcheck: !esPrecio });
    control.setAttribute("aria-describedby", `${idAyuda} ${idError}`);
    const ayuda = el("p", { id: idAyuda, clase: "ayuda" });
    const error = el("p", { id: idError, clase: "error-campo" });
    const guardar = el("button", { type: "submit", clase: "boton primario chico", disabled: true },
      "Guardar", oculto(`: ${f.etiqueta || f.clave}`));
    const estado = el("span", { clase: "indicador", role: "status", "aria-live": "polite" });
    const actualizado = el("span", { clase: "actualizado", texto: f.actualizado ? `Última edición: ${formatearMomento(f.actualizado)}` : "" });

    function refrescarAyuda() {
      if (esPrecio) {
        const p = previaPrecio(control.value);
        ayuda.textContent = p ? `En el sitio se verá como «${p}». Monto en pesos, sin decimales.` : "Monto en pesos, sin decimales.";
      } else {
        const l = largo(control.value);
        ayuda.textContent = f.tipo === "parrafo" || l > LIMITE_VALOR * 0.8
          ? `${l.toLocaleString("es-CL")} / ${LIMITE_VALOR.toLocaleString("es-CL")} caracteres` : "";
      }
    }

    function marcar() {
      const sucia = control.value !== original;
      if (sucia) sucias.add(f.clave); else sucias.delete(f.clave);
      guardar.disabled = !sucia;
      anunciar(estado, sucia ? "Cambios sin guardar" : "", "info");
      error.textContent = "";
      control.removeAttribute("aria-invalid");
      refrescarAyuda();
    }
    control.addEventListener("input", marcar);
    refrescarAyuda();

    const form = el("form", { clase: "fila-texto", novalidate: true },
      el("div", { clase: "fila-cabeza" }, el("label", { for: id, texto: f.etiqueta || f.clave }),
        el("code", { clase: "clave", texto: f.clave })),
      control, ayuda, error,
      el("div", { clase: "fila-pie" }, guardar, estado, actualizado));

    form.addEventListener("submit", async (ev) => {
      ev.preventDefault();
      const v = validarValor(f.tipo, control.value, f.clave);
      if (!v.ok) {
        error.textContent = MENSAJES_VALOR[v.error] || MENSAJES_VALOR.tipo;
        control.setAttribute("aria-invalid", "true");
        control.focus();
        return;
      }
      anunciar(estado, "Guardando…", "cargando");
      try {
        control.readOnly = true;                     // readOnly y no disabled: el foco no se pierde
        const nueva = await mientras([guardar], () => api.contenido.guardar(f.clave, v.valor)).finally(() => {
          control.readOnly = false;
        });
        original = String(nueva.valor ?? v.valor);
        control.value = original;
        marcar();
        anunciar(estado, `Guardado a las ${horaCorta()}`, "ok");
        if (nueva.actualizado) actualizado.textContent = `Última edición: ${formatearMomento(nueva.actualizado)}`;
      } catch (e) {
        anunciar(estado, "No se guardó", "error");
        error.textContent = mensajeError(e);
        guardar.disabled = control.value === original;
      }
    });
    return form;
  }

  return {
    mostrar() {
      if (!cargada) cargaInicial();
    },
    hayCambios: () => sucias.size > 0,
    reiniciar() {
      generacion++;
      cargaInicial.soltar();                 // si la carga vieja sigue colgada, el próximo ingreso carga de nuevo
      cargada = false;
      sucias.clear();
      vaciar(nodos.grupos);
      anunciar(nodos.aviso, "");
    },
  };
}
