"""Modelos SQLAlchemy para la base de datos SQLite.

Estos modelos son ADAPTADORES de infraestructura. Mapean las tablas de la BD
a las entidades de dominio. NUNCA se usan en la capa de dominio ni de aplicación.
"""

from sqlalchemy import (
    Column, Integer, String, Float, Boolean, DateTime, ForeignKey, Text,
    UniqueConstraint, Index
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.infrastructure.database.connection import Base


class RubroModel(Base):
    __tablename__ = "rubros"

    id = Column(Integer, primary_key=True, autoincrement=True)
    nombre = Column(String(100), nullable=False)
    activo = Column(Boolean, default=True, nullable=False)

    articulos = relationship("ArticuloModel", back_populates="rubro")

    def __repr__(self):
        return f"<Rubro(id={self.id}, nombre='{self.nombre}')>"


class ArticuloModel(Base):
    __tablename__ = "articulos"

    codigo = Column(String(20), primary_key=True)
    descripcion = Column(String(200), nullable=False)
    rubro_id = Column(Integer, ForeignKey("rubros.id"), nullable=False)
    precio_publico = Column(Float, nullable=False, default=0.0)
    precio_mayorista = Column(Float, nullable=False, default=0.0)
    stock_actual = Column(Integer, nullable=False, default=0)
    stock_minimo = Column(Integer, nullable=False, default=0)
    inventario_estado = Column(String(10), nullable=False, default="ALTO")
    codigo_barra = Column(String(50), nullable=True, default="")
    codigo_rapido = Column(String(20), nullable=True, default="")
    activo = Column(Boolean, default=True, nullable=False)

    rubro = relationship("RubroModel", back_populates="articulos")

    __table_args__ = (
        Index("ix_articulos_rubro_id", "rubro_id"),
        Index("ix_articulos_inventario_estado", "inventario_estado"),
        Index("ix_articulos_codigo_barra", "codigo_barra"),
        Index("ix_articulos_codigo_rapido", "codigo_rapido"),
    )

    def __repr__(self):
        return f"<Articulo(codigo='{self.codigo}', descripcion='{self.descripcion}')>"


class ClienteModel(Base):
    __tablename__ = "clientes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    razon_social = Column(String(200), nullable=False)
    cuit = Column(String(13), nullable=False, unique=True)
    condicion_iva = Column(String(30), nullable=False, default="CONSUMIDOR_FINAL")
    direccion = Column(String(200), nullable=True, default="")
    telefono = Column(String(50), nullable=True, default="")
    email = Column(String(100), nullable=True, default="")
    activo = Column(Boolean, default=True, nullable=False)

    comprobantes = relationship("ComprobanteModel", back_populates="cliente")

    def __repr__(self):
        return f"<Cliente(id={self.id}, razon_social='{self.razon_social}')>"


class VendedorModel(Base):
    __tablename__ = "vendedores"

    id = Column(Integer, primary_key=True, autoincrement=True)
    nombre = Column(String(100), nullable=False)
    activo = Column(Boolean, default=True, nullable=False)

    comprobantes = relationship("ComprobanteModel", back_populates="vendedor")
    cajas = relationship("CajaModel", back_populates="vendedor")
    pedidos = relationship("PedidoStockModel", back_populates="vendedor")

    def __repr__(self):
        return f"<Vendedor(id={self.id}, nombre='{self.nombre}')>"


class CajaModel(Base):
    __tablename__ = "cajas"

    id = Column(Integer, primary_key=True, autoincrement=True)
    vendedor_id = Column(Integer, ForeignKey("vendedores.id"), nullable=False)
    fecha_apertura = Column(DateTime, nullable=False, server_default=func.now())
    fecha_cierre = Column(DateTime, nullable=True)
    saldo_inicial = Column(Float, nullable=False, default=0.0)
    diferencia = Column(Float, default=0.0)
    estado = Column(String(10), nullable=False, default="ABIERTA")

    vendedor = relationship("VendedorModel", back_populates="cajas")
    comprobantes = relationship("ComprobanteModel", back_populates="caja")

    def __repr__(self):
        return f"<Caja(id={self.id}, estado='{self.estado}')>"


class ComprobanteModel(Base):
    __tablename__ = "comprobantes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tipo = Column(String(20), nullable=False)
    punto_venta = Column(Integer, nullable=False, default=1)
    numero = Column(Integer, nullable=False, default=0)
    cliente_id = Column(Integer, ForeignKey("clientes.id"), nullable=False)
    vendedor_id = Column(Integer, ForeignKey("vendedores.id"), nullable=False)
    caja_id = Column(Integer, ForeignKey("cajas.id"), nullable=False)
    consumidor_final = Column(Boolean, default=False, nullable=False)
    lista_mayorista = Column(Boolean, default=False, nullable=False)
    fecha = Column(DateTime, nullable=False, server_default=func.now())
    subtotal = Column(Float, nullable=False, default=0.0)
    descuento_pie = Column(Float, default=0.0)
    total = Column(Float, nullable=False, default=0.0)
    estado_sincronizacion = Column(String(15), nullable=False, default="PENDIENTE")
    cotizacion_origen_id = Column(Integer, ForeignKey("comprobantes.id"), nullable=True)
    canal = Column(String(20), default="WEB", nullable=False)

    cliente = relationship("ClienteModel", back_populates="comprobantes")
    vendedor = relationship("VendedorModel", back_populates="comprobantes")
    caja = relationship("CajaModel", back_populates="comprobantes")
    detalles = relationship("DetalleComprobanteModel", back_populates="comprobante", cascade="all, delete-orphan")
    formas_pago = relationship("ComprobanteFormaPagoModel", back_populates="comprobante", cascade="all, delete-orphan")
    cotizacion_origen = relationship("ComprobanteModel", remote_side=[id], foreign_keys=[cotizacion_origen_id])

    __table_args__ = (
        UniqueConstraint("punto_venta", "numero", "tipo", name="uq_comprobante_punto_numero_tipo"),
        Index("ix_comprobantes_cliente_id", "cliente_id"),
        Index("ix_comprobantes_caja_id", "caja_id"),
        Index("ix_comprobantes_tipo_estado", "tipo", "estado_sincronizacion"),
        Index("ix_comprobantes_fecha", "fecha"),
        Index("ix_comprobantes_cotizacion_origen", "cotizacion_origen_id"),
    )

    def __repr__(self):
        return f"<Comprobante(id={self.id}, tipo='{self.tipo}', numero='{self.punto_venta}-{self.numero:08d}')>"


class DetalleComprobanteModel(Base):
    __tablename__ = "detalles_comprobante"

    id = Column(Integer, primary_key=True, autoincrement=True)
    comprobante_id = Column(Integer, ForeignKey("comprobantes.id"), nullable=False)
    articulo_codigo = Column(String(20), ForeignKey("articulos.codigo"), nullable=False)
    cantidad = Column(Integer, nullable=False)
    precio_unitario = Column(Float, nullable=False)
    imp_int = Column(Float, default=0.0)
    porc_dto = Column(Float, default=0.0)
    descuento = Column(Float, default=0.0)
    porc_alicuota = Column(Float, default=21.0)
    subtotal = Column(Float, nullable=False)

    comprobante = relationship("ComprobanteModel", back_populates="detalles")
    articulo = relationship("ArticuloModel")

    __table_args__ = (
        Index("ix_detalles_comprobante_id", "comprobante_id"),
    )

    def __repr__(self):
        return f"<Detalle(id={self.id}, articulo='{self.articulo_codigo}', cant={self.cantidad})>"


class FormaPagoModel(Base):
    __tablename__ = "formas_pago"

    id = Column(Integer, primary_key=True, autoincrement=True)
    nombre = Column(String(50), nullable=False)
    tiene_recargo = Column(Boolean, default=False, nullable=False)
    recargo_financiero = Column(Float, default=0.0)

    comprobantes_formas_pago = relationship("ComprobanteFormaPagoModel", back_populates="forma_pago")

    def __repr__(self):
        return f"<FormaPago(id={self.id}, nombre='{self.nombre}')>"


class ComprobanteFormaPagoModel(Base):
    __tablename__ = "comprobantes_formas_pago"

    id = Column(Integer, primary_key=True, autoincrement=True)
    comprobante_id = Column(Integer, ForeignKey("comprobantes.id"), nullable=False)
    forma_pago_id = Column(Integer, ForeignKey("formas_pago.id"), nullable=False)
    monto = Column(Float, nullable=False)
    cuotas = Column(Integer, default=1)
    lote = Column(String(50), nullable=True, default="")
    nro_cupon = Column(String(50), nullable=True, default="")
    recargo_financiero = Column(Float, default=0.0)

    comprobante = relationship("ComprobanteModel", back_populates="formas_pago")
    forma_pago = relationship("FormaPagoModel", back_populates="comprobantes_formas_pago")

    def __repr__(self):
        return f"<ComprobanteFormaPago(id={self.id}, comprobante={self.comprobante_id})>"


class PedidoStockModel(Base):
    __tablename__ = "pedidos_stock"

    id = Column(Integer, primary_key=True, autoincrement=True)
    vendedor_id = Column(Integer, ForeignKey("vendedores.id"), nullable=False)
    fecha = Column(DateTime, nullable=False, server_default=func.now())
    estado = Column(String(10), nullable=False, default="PENDIENTE")
    estado_sincronizacion = Column(String(15), nullable=False, default="PENDIENTE")

    vendedor = relationship("VendedorModel", back_populates="pedidos")
    detalles = relationship("DetallePedidoStockModel", back_populates="pedido", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<PedidoStock(id={self.id}, estado='{self.estado}')>"


class DetallePedidoStockModel(Base):
    __tablename__ = "detalles_pedido_stock"

    id = Column(Integer, primary_key=True, autoincrement=True)
    pedido_id = Column(Integer, ForeignKey("pedidos_stock.id"), nullable=False)
    articulo_codigo = Column(String(20), ForeignKey("articulos.codigo"), nullable=False)
    rubro_id = Column(Integer, ForeignKey("rubros.id"), nullable=False)
    cantidad = Column(Integer, nullable=False)
    precio_unitario = Column(Float, nullable=False)
    total = Column(Float, nullable=False, default=0.0)
    stock_actual_al_pedido = Column(Integer, nullable=False, default=0)
    stock_minimo = Column(Integer, nullable=False, default=0)
    stock_pedido = Column(Integer, default=0)
    multiplo = Column(Integer, default=1)
    inventario_estado = Column(String(10), nullable=False, default="ALTO")

    pedido = relationship("PedidoStockModel", back_populates="detalles")
    articulo = relationship("ArticuloModel")
    rubro = relationship("RubroModel")

    __table_args__ = (
        Index("ix_detalles_pedido_pedido_id", "pedido_id"),
    )

    def __repr__(self):
        return f"<DetallePedido(id={self.id}, articulo='{self.articulo_codigo}', cant={self.cantidad})>"