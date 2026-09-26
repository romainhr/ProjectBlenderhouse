// Vista «Reservas»: filtros con contadores, lista, detalle, cambios de estado, nota interna y eliminación.
// Los datos de huéspedes sólo se muestran con textContent y nunca pasan por la URL.
import { hoyIso } from "../../js/reserva-logica.js";
import { mensajeError } from "./errores.js";
import {
  ACCIONES, ESTADOS, ETIQUETA_ESTADO, ETIQUETA_SITUACION, LIMITE_NOTA, PERIODOS, PLURAL_ESTADO, accionesPermitidas,
  asuntoCorreo, contarPorEstado, enlaceCorreo, enlaceTelefono, filtrarReservas, nochesDe, pendientesPorResolver,
  reemplazar, situacion, validarNota,
} from "./logica-reservas.js";
import { anunciar, confirmar, el, mientras, vaciar } from "./ui.js";
import { formatearDia, formatearMomento, horaCorta, largo, rangoCorto } from "./util.js";

export function crearVistaReservas({ raiz, api, alCambiarPendientes = () => {} }) {
  const $ = (s) => raiz.querySelector(s);
  const nodos = {
    titulo: $("#t-reservas"), estados: $("#filtro-estado"), periodo: $("#filtro-periodo"), aviso: $("#reservas-aviso"),
    lista: $("#reservas-lista"), detalle: $("#reserva-detalle"), recargar: $("#reservas-recargar"),
  };
  let reservas = [];
  let cargada = false;
  let enCurso = null;                    // carga inicial en curso
  let generacion = 0;                    // sube al cerrar sesión: una respuesta tardía ya no se pinta
  let filtro = { estado: "todas", periodo: "proximas" };
  let seleccion = null;                   // id de la reserva abierta
  let mensajeDetalle = null;              // { texto, tipo } del último cambio
  let notaSucia = false;

  // ------------------------------------------------------------------ filtros
  for (const [valor, texto] of Object.entries(PERIODOS)) {
    nodos.periodo.append(el("option", { value: valor, texto, selected: valor === filtro.periodo }));
  }
  nodos.periodo.addEventListener("change", () => {
    filtro = { ...filtro, periodo: nodos.periodo.value };
    pintar();
  });
  const chips = {};
  for (const estado of ["todas", ...ESTADOS]) {
    const input = el("input", { type: "radio", name: "estado-reserva", value: estado, clase: "visually-hidden",
      checked: estado === filtro.estado, id: `estado-${estado}` });
    const cuenta = el("span", { clase: "cuenta", texto: "0" });
    input.addEventListener("change", () => {
      if (input.checked) {
        filtro = { ...filtro, estado };
        pintar();
      }
    });
    chips[estado] = cuenta;
    nodos.estados.append(el("label", { clase: `chip chip-${estado}`, for: input.id }, input,
      el("span", { clase: "chip-cuerpo" }, PLURAL_ESTADO[estado], " ", cuenta)));
  }
  nodos.recargar.addEventListener("click", () => cargar());

  // ------------------------------------------------------------------ datos
  async function cargar() {
    anunciar(nodos.aviso, "Cargando reservas…", "cargando");
    nodos.recargar.disabled = true;
    const gen = generacion;
    try {
      const lista = await api.reservas.listar();
      if (gen !== generacion) return;
      reservas = lista;
      cargada = true;
      anunciar(nodos.aviso, `Lista actualizada a las ${horaCorta()}.`, "ok");
    } catch (e) {
      if (gen !== generacion) return;
      anunciar(nodos.aviso, mensajeError(e), "error");
    } finally {
      nodos.recargar.disabled = false;
    }
    pintar({ detalle: true });
  }

  /** Cambiar un filtro sólo repinta contadores y lista; el detalle se rehace cuando cambia la reserva abierta. */
  function pintar({ detalle = false } = {}) {
    const hoy = hoyIso();
    const c = contarPorEstado(reservas, filtro.periodo, hoy);
    for (const [estado, nodo] of Object.entries(chips)) nodo.textContent = String(c[estado]);
    alCambiarPendientes(pendientesPorResolver(reservas, hoy));
    pintarLista(hoy);
    if (detalle) pintarDetalle(hoy);
  }

  function insignia(estado) {
    return el("span", { clase: `insignia estado-${estado}`, texto: ETIQUETA_ESTADO[estado] || estado });
  }

  function pintarLista(hoy) {
    vaciar(nodos.lista);
    const visibles = filtrarReservas(reservas, filtro, hoy);
    if (!visibles.length) {
      nodos.lista.append(el("li", { clase: "vacio", texto: cargada ? "No hay solicitudes con este filtro." : "" }));
      return;
    }
    for (const r of visibles) {
      const sit = ETIQUETA_SITUACION[situacion(r, hoy)];
      const n = nochesDe(r);
      const boton = el("button", {
        type: "button", clase: "tarjeta-reserva", "aria-current": r.id === seleccion ? "true" : null,
        onclick: () => abrir(r.id),
      },
      el("span", { clase: "tr-cabeza" }, el("span", { clase: "tr-fechas", texto: rangoCorto(r.entrada, r.salida) }), insignia(r.estado)),
      el("span", { clase: "tr-nombre", texto: r.nombre }),
      el("span", { clase: "tr-meta", texto: [`${n} ${n === 1 ? "noche" : "noches"}`,
        `${r.huespedes} ${r.huespedes === 1 ? "huésped" : "huéspedes"}`, sit].filter(Boolean).join(" · ") }));
      boton.dataset.id = r.id;
      nodos.lista.append(el("li", {}, boton));
    }
  }

  // ------------------------------------------------------------------ detalle
  async function abrir(id) {
    if (id !== seleccion && notaSucia) {
      const ok = await confirmar({ titulo: "Nota sin guardar", texto: "La nota interna tiene cambios sin guardar. ¿Descartarlos?",
        boton: "Descartar cambios", peligro: true });
      if (!ok) return;
    }
    seleccion = id;
    mensajeDetalle = null;
    notaSucia = false;
    pintar({ detalle: true });
    nodos.detalle.focus();
  }

  async function cerrar() {
    if (notaSucia) {
      const ok = await confirmar({ titulo: "Nota sin guardar", texto: "La nota interna tiene cambios sin guardar. ¿Descartarlos?",
        boton: "Descartar cambios", peligro: true });
      if (!ok) return;
    }
    const id = seleccion;
    seleccion = null;
    notaSucia = false;
    pintar({ detalle: true });
    const volver = [...nodos.lista.querySelectorAll("button.tarjeta-reserva")].find((b) => b.dataset.id === id);
    (volver || nodos.titulo).focus();
  }

  function dato(etiqueta, valor, clase = "") {
    return el("div", { clase: `dato ${clase}`.trim() }, el("dt", { texto: etiqueta }), el("dd", {}, valor));
  }

  function pintarDetalle(hoy) {
    const r = reservas.find((x) => x.id === seleccion);
    // si se rehace el detalle de la misma reserva con la nota a medio escribir, se conserva lo escrito
    const area = nodos.detalle.querySelector("#nota-interna");
    const borrador = r && notaSucia && area && area.dataset.id === r.id ? area.value : null;
    vaciar(nodos.detalle);
    raiz.classList.toggle("con-detalle", Boolean(r));          // en teléfono: sólo el detalle
    nodos.detalle.hidden = !r;
    if (!r) {
      seleccion = null;
      return;
    }
    const n = nochesDe(r);
    const correo = enlaceCorreo(r.email, asuntoCorreo(r));
    const fono = enlaceTelefono(r.telefono);
    const sit = ETIQUETA_SITUACION[situacion(r, hoy)];

    const aviso = el("p", { clase: "aviso-accion", role: "status", "aria-live": "polite", tabIndex: -1 });
    if (mensajeDetalle) anunciar(aviso, mensajeDetalle.texto, mensajeDetalle.tipo);

    const acciones = el("div", { clase: "acciones-reserva" });
    for (const destino of accionesPermitidas(r.estado)) {
      const a = ACCIONES[destino];
      acciones.append(el("button", { type: "button", clase: `boton ${a.clase}`, texto: a.texto,
        onclick: (ev) => cambiarEstado(r, destino, ev.currentTarget) }));
    }

    nodos.detalle.append(
      el("button", { type: "button", clase: "boton texto volver", onclick: () => cerrar() },
        el("span", { "aria-hidden": "true", texto: "← " }), "Volver a la lista"),
      el("h2", { id: "detalle-titulo", texto: r.nombre }),
      el("p", { clase: "detalle-sub" }, insignia(r.estado), sit ? el("span", { clase: "etiqueta", texto: sit }) : null,
        el("span", { clase: "codigo" }, "Código ", el("span", { clase: "mono", texto: r.codigo || "—" }))),
      el("dl", { clase: "datos" },
        dato("Llegada", formatearDia(r.entrada)),
        dato("Salida", formatearDia(r.salida)),
        dato("Noches", String(n)),
        dato("Huéspedes", String(r.huespedes)),
        dato("Correo", correo ? el("a", { href: correo, texto: r.email }) : el("span", { texto: r.email || "—" }), "ancho"),
        dato("Teléfono", fono ? el("a", { href: fono, texto: r.telefono }) : el("span", { texto: r.telefono || "—" })),
        dato("Mensaje", el("span", { clase: "mensaje-huesped", texto: r.mensaje || "—" }), "ancho"),
        dato("Creada", formatearMomento(r.creada)),
        dato("Última modificación", formatearMomento(r.actualizada))),
      correo || fono ? el("p", { clase: "contacto" },
        correo ? el("a", { clase: "boton secundario chico", href: correo }, "Escribir al huésped") : null,
        fono ? el("a", { clase: "boton secundario chico", href: fono }, "Llamar") : null) : null,
      el("h3", { clase: "subtitulo", texto: "Cambiar estado" }),
      acciones,
      aviso,
      formularioNota(r, borrador),
      el("div", { clase: "zona-peligro" },
        el("button", { type: "button", clase: "boton peligro", texto: "Eliminar solicitud",
          onclick: (ev) => eliminar(r, ev.currentTarget) }),
        el("p", { clase: "ayuda", texto: "Borra la solicitud y los datos personales del huésped. No se puede deshacer." })),
    );
  }

  function formularioNota(r, borrador) {
    const id = "nota-interna";
    const area = el("textarea", { id, rows: 4, value: borrador ?? (r.nota_interna || ""),
      "aria-describedby": "nota-ayuda nota-contador" });
    area.dataset.id = r.id;
    const contador = el("span", { id: "nota-contador", clase: "contador" });
    const estado = el("span", { clase: "indicador", role: "status", "aria-live": "polite" });
    const guardar = el("button", { type: "submit", clase: "boton secundario chico", texto: "Guardar nota", disabled: true });
    const original = r.nota_interna || "";
    const actualizar = () => {
      const l = largo(area.value);
      contador.textContent = `${l.toLocaleString("es-CL")} / ${LIMITE_NOTA.toLocaleString("es-CL")}`;
      contador.dataset.tipo = l > LIMITE_NOTA ? "error" : "";
      notaSucia = area.value !== original;
      guardar.disabled = !notaSucia;
      if (notaSucia) anunciar(estado, "Cambios sin guardar", "info");
    };
    area.addEventListener("input", actualizar);
    actualizar();
    anunciar(estado, "");
    const form = el("form", { clase: "nota", novalidate: true },
      el("label", { for: id, texto: "Nota interna" }),
      el("p", { id: "nota-ayuda", clase: "ayuda", texto: "Sólo la ves tú en este portal; el huésped no la recibe." }),
      area,
      el("div", { clase: "fila-pie" }, contador, guardar, estado));
    form.addEventListener("submit", async (ev) => {
      ev.preventDefault();
      const v = validarNota(area.value);
      if (!v.ok) {
        anunciar(estado, `La nota admite hasta ${LIMITE_NOTA.toLocaleString("es-CL")} caracteres.`, "error");
        area.focus();
        return;
      }
      anunciar(estado, "Guardando…", "cargando");
      try {
        const nueva = await mientras([guardar, area], () => api.reservas.guardarNota(r.id, v.valor));
        reservas = reemplazar(reservas, nueva);
        notaSucia = false;
        mensajeDetalle = null;
        pintar({ detalle: true });
        const nuevoEstado = nodos.detalle.querySelector(".nota .indicador");
        anunciar(nuevoEstado, `Nota guardada a las ${horaCorta()}.`, "ok");
        nodos.detalle.querySelector("#nota-interna").focus();
      } catch (e) {
        anunciar(estado, mensajeError(e), "error");
      }
    });
    return form;
  }

  // ------------------------------------------------------------------ acciones
  async function cambiarEstado(r, destino, boton) {
    const a = ACCIONES[destino];
    const ok = await confirmar({
      titulo: `${a.texto}: ${r.nombre}`,
      texto: `${rangoCorto(r.entrada, r.salida)} · ${nochesDe(r)} noches · estado actual: ${ETIQUETA_ESTADO[r.estado]}. ${a.explicacion}`,
      boton: a.texto, peligro: a.peligro,
    });
    if (!ok) return;
    const botones = [...nodos.detalle.querySelectorAll(".acciones-reserva button")];
    const aviso = nodos.detalle.querySelector(".aviso-accion");
    anunciar(aviso, "Guardando…", "cargando");
    try {
      const nueva = await mientras(botones, () => api.reservas.cambiarEstado(r.id, destino));
      reservas = reemplazar(reservas, nueva);
      mensajeDetalle = { texto: `Listo: la solicitud quedó ${ETIQUETA_ESTADO[destino].toLowerCase()}.` +
        (destino === "confirmada" || destino === "rechazada" || destino === "cancelada" ? " Recuerda avisar al huésped." : ""), tipo: "ok" };
      pintar({ detalle: true });
      nodos.detalle.querySelector(".aviso-accion").focus();
    } catch (e) {
      anunciar(aviso, mensajeError(e), "error");
      if (boton && boton.isConnected) boton.focus();
    }
  }

  async function eliminar(r, boton) {
    const ok = await confirmar({
      titulo: "Eliminar solicitud",
      texto: `Se borrará la solicitud de ${r.nombre} (${rangoCorto(r.entrada, r.salida)}, ${ETIQUETA_ESTADO[r.estado].toLowerCase()}) ` +
        "con sus datos personales. No se puede deshacer.",
      boton: "Eliminar", peligro: true,
    });
    if (!ok) return;
    const aviso = nodos.detalle.querySelector(".aviso-accion");
    anunciar(aviso, "Eliminando…", "cargando");
    try {
      await mientras([boton], () => api.reservas.eliminar(r.id));
      reservas = reservas.filter((x) => x.id !== r.id);
      seleccion = null;
      notaSucia = false;
      pintar({ detalle: true });
      anunciar(nodos.aviso, "Solicitud eliminada.", "ok");
      nodos.titulo.focus();
    } catch (e) {
      anunciar(aviso, mensajeError(e), "error");
    }
  }

  return {
    mostrar() {
      if (!cargada && !enCurso) enCurso = cargar().finally(() => { enCurso = null; });   // una sola carga a la vez
    },
    recargar: cargar,
    hayCambios: () => notaSucia,
    /** Al cerrar sesión: quita de la memoria y del DOM los datos de huéspedes. */
    reiniciar() {
      generacion++;
      reservas = [];
      cargada = false;
      seleccion = null;
      notaSucia = false;
      mensajeDetalle = null;
      vaciar(nodos.lista);
      vaciar(nodos.detalle);
      nodos.detalle.hidden = true;
      raiz.classList.remove("con-detalle");
      anunciar(nodos.aviso, "");
      for (const nodo of Object.values(chips)) nodo.textContent = "0";
    },
  };
}
