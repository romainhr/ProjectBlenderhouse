// Vista «Fotos»: por espacio, subir (reducida en el navegador), texto alternativo, orden, visibilidad y borrado.
import { publicarFoto, quitarFoto, reordenarFoto } from "./acciones-fotos.js";
import { mensajeError } from "./errores.js";
import { ErrorImagen, prepararImagen } from "./imagen.js";
import {
  ESPACIOS, LIMITE_ALT, MAX_ORIGINAL, MENSAJES_FOTO, contarPorEspacio, fotosDeEspacio, nombreEspacio, validarAlt,
} from "./logica-fotos.js";
import { anunciar, confirmar, el, mientras, oculto, vaciar } from "./ui.js";
import { peso } from "./util.js";

function mensaje(e) {
  if (e instanceof ErrorImagen || (e && Object.prototype.hasOwnProperty.call(MENSAJES_FOTO, e.codigo))) {
    return MENSAJES_FOTO[e.codigo] || MENSAJES_FOTO.decodificar;
  }
  return mensajeError(e);
}

export function crearVistaFotos({ raiz, api }) {
  const $ = (s) => raiz.querySelector(s);
  const n = {
    espacios: $("#filtro-espacio"), aviso: $("#fotos-aviso"), lista: $("#fotos-lista"), recargar: $("#fotos-recargar"),
    form: $("#form-subir"), tituloSubir: $("#subir-espacio"), archivo: $("#subir-archivo"), previa: $("#subir-previa"),
    previaImg: $("#subir-img"), previaInfo: $("#subir-info"), alt: $("#subir-alt"), altError: $("#subir-alt-error"),
    visible: $("#subir-visible"), boton: $("#subir-boton"), estado: $("#subir-estado"), tituloLista: $("#t-lista-fotos"),
  };
  let fotos = [];
  let cargada = false;
  let enCurso = null;                    // carga inicial en curso
  let generacion = 0;                    // sube al cerrar sesión: una respuesta tardía ya no se pinta
  let espacio = ESPACIOS[0].id;
  let preparada = null;              // resultado de prepararImagen
  let urlPrevia = null;
  let preparando = null;             // promesa en curso (para no subir antes de terminar de reducir)

  // ------------------------------------------------------------------ selector de espacio
  const cuentas = {};
  for (const e of ESPACIOS) {
    const input = el("input", { type: "radio", name: "espacio-foto", value: e.id, id: `espacio-${e.id}`,
      clase: "visually-hidden", checked: e.id === espacio });
    input.addEventListener("change", () => {
      if (!input.checked) return;
      espacio = e.id;
      pintar();
    });
    cuentas[e.id] = el("span", { clase: "cuenta", texto: "0" });
    n.espacios.append(el("label", { clase: "chip", for: input.id }, input,
      el("span", { clase: "chip-cuerpo" }, e.nombre, " ", cuentas[e.id])));
  }
  n.recargar.addEventListener("click", () => cargar());
  n.archivo.setAttribute("aria-describedby", "subir-archivo-ayuda subir-estado");
  $("#subir-archivo-ayuda").textContent =
    `JPEG, PNG o WebP de hasta ${MAX_ORIGINAL / 1024 / 1024} MB. Se reduce a 1600 px de ancho y se guarda como WebP ` +
    "(o JPEG); el archivo original y sus datos de ubicación no se suben.";
  n.alt.maxLength = LIMITE_ALT;

  // ------------------------------------------------------------------ subir
  function limpiarPrevia() {
    if (urlPrevia) URL.revokeObjectURL(urlPrevia);
    urlPrevia = null;
    preparada = null;
    n.previa.hidden = true;
    n.previaImg.removeAttribute("src");
    n.previaInfo.textContent = "";
  }

  n.archivo.addEventListener("change", () => {
    limpiarPrevia();
    const archivo = n.archivo.files && n.archivo.files[0];
    if (!archivo) {
      anunciar(n.estado, "");
      return;
    }
    anunciar(n.estado, "Preparando la imagen…", "cargando");
    const esta = (preparando = prepararImagen(archivo).then((p) => {
      if (preparando !== esta) return;              // el usuario eligió otro archivo mientras tanto
      preparada = p;
      urlPrevia = URL.createObjectURL(p.blob);
      n.previaImg.src = urlPrevia;
      n.previaImg.alt = "Vista previa de la foto que se va a subir";
      n.previaInfo.textContent = `Original ${p.anchoOrigen} × ${p.altoOrigen} px, ${peso(p.pesoOrigen)} → se sube ` +
        `${p.ancho} × ${p.alto} px en ${p.tipo === "image/webp" ? "WebP" : "JPEG"}, ${peso(p.blob.size)}.`;
      n.previa.hidden = false;
      anunciar(n.estado, "Imagen lista. Escribe su descripción y súbela.", "ok");
    }).catch((e) => {
      if (preparando !== esta) return;
      n.archivo.value = "";
      anunciar(n.estado, mensaje(e), "error");
    }).finally(() => {
      if (preparando === esta) preparando = null;
    }));
  });

  n.alt.addEventListener("input", () => {
    n.altError.textContent = "";
    n.alt.removeAttribute("aria-invalid");
  });

  n.form.addEventListener("submit", async (ev) => {
    ev.preventDefault();
    if (preparando) await preparando.catch(() => {});
    if (!preparada) {
      anunciar(n.estado, MENSAJES_FOTO.sin_imagen, "error");
      n.archivo.focus();
      return;
    }
    const a = validarAlt(n.alt.value);
    if (!a.ok) {
      n.altError.textContent = MENSAJES_FOTO[a.error];
      n.alt.setAttribute("aria-invalid", "true");
      n.alt.focus();
      return;
    }
    anunciar(n.estado, "Subiendo la foto…", "cargando");
    try {
      await mientras([n.boton, n.archivo], () => publicarFoto({
        api, espacio, blob: preparada.blob, alt: a.valor, visible: n.visible.checked,
        fotosEspacio: fotosDeEspacio(fotos, espacio),
      }));
      n.form.reset();
      limpiarPrevia();
      await cargar({ silencioso: true });
      anunciar(n.estado, `Foto agregada a ${nombreEspacio(espacio)}.`, "ok");
    } catch (e) {
      anunciar(n.estado, mensaje(e), "error");
    }
  });

  // ------------------------------------------------------------------ lista
  async function cargar({ silencioso = false } = {}) {
    if (!silencioso) anunciar(n.aviso, "Cargando fotos…", "cargando");
    n.recargar.disabled = true;
    const gen = generacion;
    try {
      const lista = await api.fotos.listar();
      if (gen !== generacion) return;
      fotos = lista;
      cargada = true;
      if (!silencioso) anunciar(n.aviso, "");
    } catch (e) {
      if (gen !== generacion) return;
      anunciar(n.aviso, mensajeError(e), "error");
    } finally {
      n.recargar.disabled = false;
    }
    pintar();
  }

  function pintar() {
    const c = contarPorEspacio(fotos);
    for (const [id, nodo] of Object.entries(cuentas)) nodo.textContent = String(c[id]);
    const nombre = nombreEspacio(espacio);
    n.tituloSubir.textContent = nombre;
    n.tituloLista.textContent = `Fotos de ${nombre}`;
    // descripciones a medio escribir: se conservan al repintar (p. ej. al cambiar la visibilidad de otra foto)
    const borradores = new Map([...n.lista.querySelectorAll("li.foto")].map((li) => [li.dataset.id,
      li.querySelector(".foto-alt input").value]));
    vaciar(n.lista);
    const lista = fotosDeEspacio(fotos, espacio);
    if (!lista.length) {
      n.lista.append(el("li", { clase: "vacio", texto: cargada
        ? `${nombre} no tiene fotos propias: el sitio muestra el render de ejemplo.` : "" }));
      return;
    }
    const principal = lista.find((f) => f.visible);
    lista.forEach((f, i) => n.lista.append(tarjeta(f, i, lista, f === principal, borradores.get(f.id))));
  }

  function tarjeta(f, i, lista, esPrincipal, borrador) {
    const idAlt = `alt-${f.id}`, idVis = `vis-${f.id}`;
    const estado = el("p", { clase: "indicador", role: "status", "aria-live": "polite" });
    const alt = el("input", { id: idAlt, type: "text", value: f.alt, maxLength: LIMITE_ALT, autocomplete: "off" });
    const guardarAlt = el("button", { type: "submit", clase: "boton secundario chico", disabled: true }, "Guardar descripción");
    alt.addEventListener("input", () => { guardarAlt.disabled = alt.value.trim() === f.alt; });
    if (borrador !== undefined && borrador.trim() !== f.alt) {
      alt.value = borrador;
      guardarAlt.disabled = false;
    }
    const formAlt = el("form", { clase: "foto-alt", novalidate: true },
      el("label", { for: idAlt, texto: "Descripción (texto alternativo)" }), alt, guardarAlt);
    formAlt.addEventListener("submit", async (ev) => {
      ev.preventDefault();
      const a = validarAlt(alt.value);
      if (!a.ok) {
        anunciar(estado, MENSAJES_FOTO[a.error], "error");
        alt.focus();
        return;
      }
      await cambiar(f, { alt: a.valor }, estado, "Descripción guardada.");
    });

    const visible = el("input", { id: idVis, type: "checkbox", checked: Boolean(f.visible) });
    visible.addEventListener("change", () => cambiar(f, { visible: visible.checked }, estado,
      visible.checked ? "Ahora se muestra en el sitio." : "Oculta: ya no se muestra en el sitio."));

    const nombre = `«${f.alt}»`;
    const subir = el("button", { type: "button", clase: "boton secundario chico", disabled: i === 0, "data-accion": "subir",
      onclick: () => mover(f, -1, lista) }, el("span", { "aria-hidden": "true", texto: "↑ " }), "Subir", oculto(` ${nombre}`));
    const bajar = el("button", { type: "button", clase: "boton secundario chico", disabled: i === lista.length - 1,
      "data-accion": "bajar",
      onclick: () => mover(f, 1, lista) }, el("span", { "aria-hidden": "true", texto: "↓ " }), "Bajar", oculto(` ${nombre}`));
    const borrar = el("button", { type: "button", clase: "boton peligro chico", onclick: () => eliminar(f) },
      "Borrar", oculto(` ${nombre}`));

    return el("li", { clase: `foto${f.visible ? "" : " oculta"}`, "data-id": f.id },
      el("div", { clase: "foto-imagen" },
        el("img", { src: api.fotos.url(f.ruta), alt: f.alt, loading: "lazy", decoding: "async", referrerPolicy: "no-referrer",
          width: 320, height: 200 }),
        esPrincipal ? el("span", { clase: "etiqueta-foto", texto: "Principal en el sitio" }) : null,
        !f.visible ? el("span", { clase: "etiqueta-foto gris", texto: "Oculta" }) : null),
      el("div", { clase: "foto-datos" },
        el("p", { clase: "foto-posicion", texto: `Posición ${i + 1} de ${lista.length}` }),
        formAlt,
        el("label", { clase: "check", for: idVis }, visible, " Visible en el sitio"),
        el("div", { clase: "foto-acciones" }, subir, bajar, borrar),
        estado));
  }

  async function cambiar(f, cambios, estado, ok) {
    anunciar(estado, "Guardando…", "cargando");
    try {
      const nueva = await api.fotos.actualizar(f.id, cambios);
      fotos = fotos.map((x) => (x.id === f.id ? { ...x, ...nueva } : x));
      pintar();
      anunciarEn(f.id, ok, "ok");
    } catch (e) {
      anunciar(estado, mensajeError(e), "error");
      await cargar({ silencioso: true });                       // vuelve a mostrar lo que hay en la base
      anunciarEn(f.id, mensajeError(e), "error");
    }
  }

  /** Tras repintar, deja el aviso en la tarjeta nueva de esa foto y le devuelve el foco a un control de ella. */
  function anunciarEn(id, texto, tipo, enfocar = null) {
    const li = [...n.lista.querySelectorAll("li.foto")].find((x) => x.dataset.id === id);
    if (!li) return;
    anunciar(li.querySelector(".indicador"), texto, tipo);
    if (enfocar) {
      const b = [...li.querySelectorAll(".foto-acciones button")].find((x) => x.dataset.accion === enfocar);
      if (b && !b.disabled) b.focus();
      else li.querySelector(".foto-alt input").focus();
    }
  }

  async function mover(f, delta, lista) {
    anunciar(n.aviso, "Guardando el orden…", "cargando");
    try {
      const nueva = await reordenarFoto({ api, fotosEspacio: lista, id: f.id, delta });
      const porId = new Map(nueva.map((x) => [x.id, x.orden]));
      fotos = fotos.map((x) => (porId.has(x.id) ? { ...x, orden: porId.get(x.id) } : x));
      pintar();
      anunciar(n.aviso, "");
      anunciarEn(f.id, "Orden guardado.", "ok", delta < 0 ? "subir" : "bajar");
    } catch (e) {
      anunciar(n.aviso, mensajeError(e), "error");
      await cargar({ silencioso: true });
    }
  }

  async function eliminar(f) {
    const ok = await confirmar({ titulo: "Borrar foto",
      texto: `Se borrará la foto «${f.alt}» de ${nombreEspacio(f.espacio)}: sale del sitio y se elimina el archivo de Storage. No se puede deshacer.`,
      boton: "Borrar foto", peligro: true });
    if (!ok) return;
    anunciar(n.aviso, "Borrando…", "cargando");
    try {
      const r = await quitarFoto({ api, foto: f });
      fotos = fotos.filter((x) => x.id !== f.id);
      pintar();
      if (r.objetoBorrado) anunciar(n.aviso, "Foto borrada.", "ok");
      else anunciar(n.aviso, `La foto ya no aparece en el sitio, pero el archivo quedó en Storage (${f.ruta}): ` +
        `${mensajeError(r.error)} Puedes borrarlo en el panel de Supabase (Storage → fotos).`, "error");
      n.tituloLista.focus();
    } catch (e) {
      anunciar(n.aviso, mensajeError(e), "error");
    }
  }

  return {
    mostrar() {
      if (!cargada && !enCurso) enCurso = cargar().finally(() => { enCurso = null; });   // una sola carga a la vez
    },
    hayCambios: () => Boolean(preparada) || n.alt.value.trim() !== "",
    reiniciar() {
      generacion++;
      fotos = [];
      cargada = false;
      preparando = null;
      limpiarPrevia();
      n.form.reset();
      vaciar(n.lista);
      anunciar(n.aviso, "");
      anunciar(n.estado, "");
    },
  };
}
