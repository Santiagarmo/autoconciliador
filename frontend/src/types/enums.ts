/**
 * Enums espejo de `backend/app/domain/enums.py`.
 *
 * Cada enum trae un mapa de metadata (label legible + variante visual) en
 * lugar de esparcir `if/switch` por los componentes: agregar un estado nuevo
 * es agregar una entrada aquí (Open/Closed), no tocar cada `BaseBadge`.
 */

export enum EstadoPedido {
  PENDIENTE_PAGO = "PENDIENTE_PAGO",
  EN_VERIFICACION = "EN_VERIFICACION",
  LISTO_PARA_DESPACHO = "LISTO_PARA_DESPACHO",
  ALERTA_PAGO = "ALERTA_PAGO",
  DESPACHADO = "DESPACHADO",
  CANCELADO = "CANCELADO",
}

export enum EstadoPago {
  REGISTRADO = "REGISTRADO",
  CONCILIADO = "CONCILIADO",
  RECHAZADO = "RECHAZADO",
  ALERTA_NO_ENCONTRADO = "ALERTA_NO_ENCONTRADO",
}

export enum EstadoMovimiento {
  DISPONIBLE = "DISPONIBLE",
  CONCILIADO = "CONCILIADO",
  NO_OPERATIVO = "NO_OPERATIVO",
}

export enum TipoConciliacion {
  AUTOMATICA = "AUTOMATICA",
  MANUAL_AUDITOR = "MANUAL_AUDITOR",
}

export enum RolUsuario {
  ASESOR = "ASESOR",
  AUDITOR = "AUDITOR",
}

/** Veredicto de StatementVerifier (tier 1) para una ingesta de extracto. */
export enum ResultadoVerificacion {
  OK = "OK",
  DISCREPANCIA = "DISCREPANCIA",
  NO_VERIFICABLE = "NO_VERIFICABLE",
  ERROR = "ERROR",
}

/** Variantes de color soportadas por `BaseBadge`. */
export type BadgeVariant =
  | "neutral"
  | "info"
  | "success"
  | "warning"
  | "danger";

interface StatusMeta {
  label: string;
  variant: BadgeVariant;
}

export const ESTADO_PEDIDO_META: Record<EstadoPedido, StatusMeta> = {
  [EstadoPedido.PENDIENTE_PAGO]: { label: "Pendiente de pago", variant: "neutral" },
  [EstadoPedido.EN_VERIFICACION]: { label: "En verificación", variant: "info" },
  [EstadoPedido.LISTO_PARA_DESPACHO]: { label: "Listo para despacho", variant: "success" },
  [EstadoPedido.ALERTA_PAGO]: { label: "Alerta de pago", variant: "danger" },
  [EstadoPedido.DESPACHADO]: { label: "Despachado", variant: "success" },
  [EstadoPedido.CANCELADO]: { label: "Cancelado", variant: "neutral" },
};

export const ESTADO_PAGO_META: Record<EstadoPago, StatusMeta> = {
  [EstadoPago.REGISTRADO]: { label: "Registrado", variant: "info" },
  [EstadoPago.CONCILIADO]: { label: "Conciliado", variant: "success" },
  [EstadoPago.RECHAZADO]: { label: "Rechazado", variant: "danger" },
  [EstadoPago.ALERTA_NO_ENCONTRADO]: { label: "Alerta: no encontrado", variant: "warning" },
};

export const ESTADO_MOVIMIENTO_META: Record<EstadoMovimiento, StatusMeta> = {
  [EstadoMovimiento.DISPONIBLE]: { label: "Disponible", variant: "info" },
  [EstadoMovimiento.CONCILIADO]: { label: "Conciliado", variant: "success" },
  [EstadoMovimiento.NO_OPERATIVO]: { label: "No operativo", variant: "neutral" },
};

export const TIPO_CONCILIACION_META: Record<TipoConciliacion, StatusMeta> = {
  [TipoConciliacion.AUTOMATICA]: { label: "Automática", variant: "success" },
  [TipoConciliacion.MANUAL_AUDITOR]: { label: "Manual (auditor)", variant: "info" },
};

export const ROL_USUARIO_META: Record<RolUsuario, StatusMeta> = {
  [RolUsuario.ASESOR]: { label: "Asesor", variant: "info" },
  [RolUsuario.AUDITOR]: { label: "Auditor", variant: "success" },
};

export const RESULTADO_VERIFICACION_META: Record<ResultadoVerificacion, StatusMeta> = {
  [ResultadoVerificacion.OK]: { label: "OK", variant: "success" },
  [ResultadoVerificacion.DISCREPANCIA]: { label: "Discrepancia", variant: "danger" },
  [ResultadoVerificacion.NO_VERIFICABLE]: { label: "No verificable", variant: "neutral" },
  [ResultadoVerificacion.ERROR]: { label: "Error", variant: "danger" },
};

/**
 * Bancos que el asesor puede declarar al registrar un pago (según el spec
 * de negocio: Nequi, Davivienda, Bancolombia). Distinto de los bancos con
 * parser de ingesta implementado (ver `BANCOS_INGESTA_DISPONIBLES`) — el
 * asesor puede registrar un pago a un banco cuyo extracto aún no se sube.
 */
export const BANCOS_DECLARABLES = ["NEQUI", "BANCOLOMBIA", "DAVIVIENDA"] as const;

/** Bancos con `BankParserStrategy` registrado en el worker de ingesta (Fase 3-4). */
export const BANCOS_INGESTA_DISPONIBLES = ["BANCOLOMBIA"] as const;
export type BancoIngesta = (typeof BANCOS_INGESTA_DISPONIBLES)[number];
