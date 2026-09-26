// Reexporta three.js autoalojado (web/src/vendor/three/) con un import corto y en un solo lugar: si el
// vendorizado se mueve, solo hay que tocar esta línea. Sin import map (la CSP del tour es script-src 'self'
// sin nada en línea), así que el resto del visor hace `import { THREE } from "./three.js"`.
export * as THREE from "../../vendor/three/three.module.min.js";
