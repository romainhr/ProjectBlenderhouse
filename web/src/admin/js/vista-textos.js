// Vista «Textos»: filas de public.contenido agrupadas por grupo; cada fila se edita y se guarda por separado.
// Cada texto tiene tres campos: español (obligatorio), inglés y francés (opcionales: vacío = el sitio en ese idioma
// muestra el texto fijo de la página, que es el original en español mientras esa página no esté traducida). Los precios
// tienen uno solo, porque no se traducen. Si la base todavía no tiene las columnas de traducción (migración 0005 sin
// aplicar), se avisa y se edita sólo el español.
// Guardar manda sólo las columnas de los campos que cambiaron (columnasCambiadas): los otros idiomas no se reenvían
// tal como se cargaron, así no se pisa lo que se haya guardado entretanto en otra pestaña o en el panel de Supabase.
import { mensajeError } from "./errores.js";
import {
  AVISO_SIN_IDIOMAS, MENSAJES_VALOR, agruparContenido, ayudaCampo, columnasCambiadas, hayCambiosFila, idiomasDeFila,
  rotuloIdioma, validarFila, valoresDeFila,
} from "./logica-contenido.js";
import { anunciar, confirmar, el, mientras, oculto, vaciar } from "./ui.js";
import { formatearMomento, horaCorta, unaALaVez } from "./util.js";

// atributo lang de cada campo: corrector ortográfico y lector de pantalla en el idioma del texto
const LANG = Object.freeze({ es: "es", en: "en", fr: "fr" });

export function crearVistaTextos({ raiz, api }) {
  const nodos = { grupos: raiz.querySelector("#textos-grupos"), aviso: raiz.querySelector("#textos-aviso"),
    recargar: raiz.querySelector("#textos-recargar") };
  let cargada = false;
  let generacion = 0;                    // sube al cerrar sesión: una respuesta tardía ya no se pinta
  let idiomas = true;                    // false: la base no tiene valor_en ni valor_fr (0005 sin aplicar)
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
      const { filas, idiomas: conIdiomas } = await api.contenido.listar();
      if (gen !== generacion) return;
      cargada = true;
      idiomas = conIdiomas !== false;
      sucias.clear();
      pintar(filas);
      if (!filas.length) anunciar(nodos.aviso, "No hay textos editables todavía (la semilla de la migración 0003 los crea).", "error");
      else if (!idiomas) anunciar(nodos.aviso, AVISO_SIN_IDIOMAS, "aviso");
      else anunciar(nodos.aviso, "");
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

  /** Un campo de la fila (un idioma): control, ayuda y error propios. */
  function campo(f, idBase, idioma, valor, idError) {
    const id = `${idBase}-${idioma}`;
    const idAyuda = `${id}-ayuda`, idErrorCampo = `${id}-error`;
    const esPrecio = f.tipo === "precio";
    const control = f.tipo === "parrafo"
      ? el("textarea", { id, rows: 5, value: valor, lang: LANG[idioma] })
      : el("input", { id, type: "text", value: valor, autocomplete: "off", inputMode: esPrecio ? "numeric" : null,
        spellcheck: !esPrecio, lang: LANG[idioma] });
    control.setAttribute("aria-describedby", `${idAyuda} ${idErrorCampo} ${idError}`);
    const ayuda = el("p", { id: idAyuda, clase: "ayuda" });
    const error = el("p", { id: idErrorCampo, clase: "error-campo" });
    const refrescarAyuda = () => { ayuda.textContent = ayudaCampo({ tipo: f.tipo, idioma, valor: control.value }); };
    refrescarAyuda();
    return { idioma, id, control, ayuda, error, refrescarAyuda };
  }

  function fila(f, i) {
    const id = `texto-${i}`;
    const idError = `${id}-error`, idTitulo = `${id}-titulo`;
    const etiqueta = f.etiqueta || f.clave;
    const lista = idiomasDeFila(f, { idiomas });              // ["es"] en precios o sin la 0005
    const varios = lista.length > 1;
    let guardada = f;                                          // la fila tal como la conoce la vista (columnas)
    let original = valoresDeFila(guardada);                    // lo mismo, por idioma, para comparar con los campos
    const campos = lista.map((idioma) => campo(f, id, idioma, original[idioma], idError));
    const errorFila = el("p", { id: idError, clase: "error-campo" });   // errores del servidor (no de un campo)
    const guardar = el("button", { type: "submit", clase: "boton primario chico", disabled: true },
      "Guardar", oculto(`: ${etiqueta}`));
    const estado = el("span", { clase: "indicador", role: "status", "aria-live": "polite" });
    const actualizado = el("span", { clase: "actualizado", texto: f.actualizado ? `Última edición: ${formatearMomento(f.actualizado)}` : "" });

    const leer = () => Object.fromEntries(campos.map((c) => [c.idioma, c.control.value]));

    function marcar() {
      const sucia = hayCambiosFila(original, leer());
      if (sucia) sucias.add(f.clave); else sucias.delete(f.clave);
      guardar.disabled = !sucia;
      anunciar(estado, sucia ? "Cambios sin guardar" : "", "info");
      errorFila.textContent = "";
      for (const c of campos) {
        c.error.textContent = "";
        c.control.removeAttribute("aria-invalid");
        c.refrescarAyuda();
      }
    }
    for (const c of campos) c.control.addEventListener("input", marcar);

    // Un solo idioma (precio, o base sin la 0005): la etiqueta es el rótulo del campo, como antes de la 0005.
    // Tres idiomas: la etiqueta nombra el grupo (role=group) y cada campo lleva el nombre de su idioma.
    let cuerpo;
    if (varios) {
      cuerpo = [
        el("div", { clase: "fila-cabeza" }, el("span", { id: idTitulo, clase: "fila-titulo", texto: etiqueta }),
          el("code", { clase: "clave", texto: f.clave })),
        el("div", { clase: "idiomas", role: "group", "aria-labelledby": idTitulo },
          campos.map((c) => {
            const r = rotuloIdioma(c.idioma);
            return el("div", { clase: "campo-idioma" },
              el("label", { for: c.id }, r.nombre, el("span", { clase: "requisito", texto: ` (${r.requisito})` })),
              c.control, c.ayuda, c.error);
          })),
      ];
    } else {
      const [c] = campos;
      cuerpo = [
        el("div", { clase: "fila-cabeza" }, el("label", { for: c.id, texto: etiqueta }), el("code", { clase: "clave", texto: f.clave })),
        c.control, c.ayuda, c.error,
      ];
    }
    const form = el("form", { clase: "fila-texto", novalidate: true }, cuerpo, errorFila,
      el("div", { clase: "fila-pie" }, guardar, estado, actualizado));

    form.addEventListener("submit", async (ev) => {
      ev.preventDefault();
      const escritos = leer();
      const v = validarFila(f, escritos, { idiomas });
      if (!v.ok) {
        let primero = null;
        for (const c of campos) {
          const codigo = v.errores[c.idioma];
          if (!codigo) continue;
          c.error.textContent = MENSAJES_VALOR[codigo] || MENSAJES_VALOR.tipo;
          c.control.setAttribute("aria-invalid", "true");
          primero = primero || c.control;
        }
        if (primero) primero.focus();
        return;
      }
      // sólo las columnas cuyo campo cambió: los idiomas sin tocar no se reenvían y no pisan lo guardado en otro lado
      const cambios = columnasCambiadas(v.cambios, original, escritos);
      if (!Object.keys(cambios).length) { marcar(); return; }
      anunciar(estado, "Guardando…", "cargando");
      const controles = campos.map((c) => c.control);
      try {
        controles.forEach((c) => { c.readOnly = true; });          // readOnly y no disabled: el foco no se pierde
        const nueva = await mientras([guardar], () => api.contenido.guardar(f.clave, cambios, { idiomas })).finally(() => {
          controles.forEach((c) => { c.readOnly = false; });
        });
        // lo que devolvió la base (null -> ""): trae también los idiomas que se cambiaron en otro lado
        guardada = { ...guardada, ...cambios, ...nueva };
        original = valoresDeFila(guardada);
        for (const c of campos) c.control.value = original[c.idioma];
        marcar();
        anunciar(estado, `Guardado a las ${horaCorta()}`, "ok");
        if (nueva && nueva.actualizado) actualizado.textContent = `Última edición: ${formatearMomento(nueva.actualizado)}`;
      } catch (e) {
        anunciar(estado, "No se guardó", "error");
        errorFila.textContent = mensajeError(e);
        guardar.disabled = !hayCambiosFila(original, leer());
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
      idiomas = true;
      sucias.clear();
      vaciar(nodos.grupos);
      anunciar(nodos.aviso, "");
    },
  };
}
