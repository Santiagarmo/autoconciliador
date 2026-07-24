/**
 * DTOs espejo de `backend/app/schemas/*.py`.
 *
 * Los montos (`Decimal` en el backend) se tipan como `string` para no perder
 * precisión al viajar por JSON — nunca se parsean a `number` para almacenar,
 * solo para mostrar (ver `utils/format.ts`).
 */
import type {
  EstadoMovimiento,
  EstadoPago,
  EstadoPedido,
  RolUsuario,
  TipoConciliacion,
} from "./enums";

export interface Token {
  access_token: string;
  token_type: string;
}

export interface UserRead {
  id: string;
  email: string;
  rol: RolUsuario;
  activo: boolean;
  created_at: string;
}

export interface UserCreate {
  email: string;
  password: string;
  rol: RolUsuario;
}

export interface PedidoRead {
  id: string;
  codigo_pedido: string;
  cliente_whatsapp: string;
  monto_total: string;
  estado_pedido: EstadoPedido;
  created_at: string;
  updated_at: string;
}

export interface PedidoCreate {
  codigo_pedido: string;
  cliente_whatsapp: string;
  monto_total: string;
}

export interface PedidoUpdate {
  cliente_whatsapp?: string;
  estado_pedido?: EstadoPedido;
}

export interface PagoDeclaradoRead {
  id: string;
  pedido_id: string;
  banco_destino: string;
  monto_declarado: string;
  numero_referencia: string;
  ultimos_4_digitos: string | null;
  estado_pago: EstadoPago;
  created_at: string;
}

export interface PagoDeclaradoCreate {
  pedido_id: string;
  banco_destino: string;
  monto_declarado: string;
  numero_referencia: string;
  ultimos_4_digitos?: string | null;
}

export interface MovimientoBancarioRead {
  id: string;
  banco_origen: string;
  fecha_movimiento: string;
  monto_real: string;
  saldo_posterior: string;
  numero_referencia: string | null;
  descripcion_concepto: string;
  hash_idempotencia: string;
  estado_movimiento: EstadoMovimiento;
  created_at: string;
}

export interface ConciliacionRead {
  id: string;
  pago_declarado_id: string;
  movimiento_bancario_id: string;
  tipo_conciliacion: TipoConciliacion;
  created_at: string;
}

export interface ReconSummaryRead {
  conciliados: number;
}
