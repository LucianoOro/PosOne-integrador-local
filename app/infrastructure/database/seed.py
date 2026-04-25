"""Seed data: pobla la base de datos con datos iniciales si está vacía.

Se ejecuta en el evento de lifespan de FastAPI (main.py).
"""

from sqlalchemy.orm import Session

from app.infrastructure.database.models import (
    RubroModel,
    ArticuloModel,
    ClienteModel,
    VendedorModel,
    CajaModel,
    FormaPagoModel,
)
from app.domain.value_objects.enums import (
    CondicionIVA,
    InventarioEstado,
    EstadoCaja,
)


def seed_database(db: Session) -> None:
    """Inserta datos iniciales si la base de datos está vacía."""
    # Verificar si ya hay datos
    if db.query(ArticuloModel).first() is not None:
        return  # Ya hay datos, no hacer seed

    # ─── Rubros ────────────────────────────────────────────────
    rubro_bicicletas = RubroModel(id=1, nombre="Bicicletas y Rodados", activo=True)
    rubro_repuestos = RubroModel(id=2, nombre="Repuestos y Accesorios", activo=True)
    rubro_indumentaria = RubroModel(id=3, nombre="Indumentaria", activo=True)
    rubro_componentes = RubroModel(id=4, nombre="Componentes", activo=True)
    db.add_all([rubro_bicicletas, rubro_repuestos, rubro_indumentaria, rubro_componentes])
    db.flush()

    # ─── Artículos (10 variados) ─────────────────────────────
    articulos = [
        ArticuloModel(
            codigo="BIC-001", descripcion="Bicicleta Mountain Bike Ranger 29",
            rubro_id=1, precio_publico=450000.0, precio_mayorista=380000.0,
            stock_actual=8, stock_minimo=3, inventario_estado="ALTO",
            codigo_barra="7791234567890", codigo_rapido="MBR29", activo=True,
        ),
        ArticuloModel(
            codigo="BIC-002", descripcion="Bicicleta Ruta Speed Pro Carbon",
            rubro_id=1, precio_publico=850000.0, precio_mayorista=720000.0,
            stock_actual=3, stock_minimo=2, inventario_estado="MEDIO",
            codigo_barra="7791234567891", codigo_rapido="RSPC", activo=True,
        ),
        ArticuloModel(
            codigo="BIC-003", descripcion="Bicicleta Urbana Comfort Lite",
            rubro_id=1, precio_publico=280000.0, precio_mayorista=235000.0,
            stock_actual=12, stock_minimo=5, inventario_estado="ALTO",
            codigo_barra="7791234567892", codigo_rapido="BUCL", activo=True,
        ),
        ArticuloModel(
            codigo="REP-001", descripcion="Casco de Seguridad ProRider",
            rubro_id=2, precio_publico=45000.0, precio_mayorista=35000.0,
            stock_actual=25, stock_minimo=10, inventario_estado="ALTO",
            codigo_barra="7799876543210", codigo_rapido="CSPR", activo=True,
        ),
        ArticuloModel(
            codigo="REP-002", descripcion="Cubierta MTB 29x2.10 Plegable",
            rubro_id=2, precio_publico=35000.0, precio_mayorista=28000.0,
            stock_actual=15, stock_minimo=8, inventario_estado="MEDIO",
            codigo_barra="7799876543211", codigo_rapido="CMTB", activo=True,
        ),
        ArticuloModel(
            codigo="REP-003", descripcion="Cadena 9V Gold Power",
            rubro_id=2, precio_publico=22000.0, precio_mayorista=17000.0,
            stock_actual=30, stock_minimo=15, inventario_estado="ALTO",
            codigo_barra="7799876543212", codigo_rapido="C9GP", activo=True,
        ),
        ArticuloModel(
            codigo="REP-004", descripcion="Asiento Ergonómico Gel Classic",
            rubro_id=2, precio_publico=28000.0, precio_mayorista=22000.0,
            stock_actual=2, stock_minimo=5, inventario_estado="BAJO",
            codigo_barra="7799876543213", codigo_rapido="ASEG", activo=True,
        ),
        ArticuloModel(
            codigo="IND-001", descripcion="Campera Térmica WindBlock Pro",
            rubro_id=3, precio_publico=95000.0, precio_mayorista=78000.0,
            stock_actual=6, stock_minimo=4, inventario_estado="MEDIO",
            codigo_barra="7795554443332", codigo_rapido="CTWB", activo=True,
        ),
        ArticuloModel(
            codigo="IND-002", descripcion="Guantes Ciclismo Spectra Gel",
            rubro_id=3, precio_publico=18000.0, precio_mayorista=14000.0,
            stock_actual=20, stock_minimo=10, inventario_estado="ALTO",
            codigo_barra="7795554443333", codigo_rapido="GCSG", activo=True,
        ),
        ArticuloModel(
            codigo="CMP-001", descripcion="Grupo Shimano Deore 12V",
            rubro_id=4, precio_publico=180000.0, precio_mayorista=150000.0,
            stock_actual=1, stock_minimo=2, inventario_estado="BAJO",
            codigo_barra="7791112223334", codigo_rapido="GSD12", activo=True,
        ),
    ]
    db.add_all(articulos)
    db.flush()

    # ─── Clientes ─────────────────────────────────────────────
    clientes = [
        ClienteModel(
            id=1, razon_social="Consumidor Final",
            cuit="27000000001", condicion_iva=CondicionIVA.CONSUMIDOR_FINAL.value,
            direccion="", telefono="", email="", activo=True,
        ),
        ClienteModel(
            id=2, razon_social="Distribuidora Mendocina SRL",
            cuit="30123456780", condicion_iva=CondicionIVA.RESPONSABLE_INSCRIPTO.value,
            direccion="Av. San Martín 1250, Mendoza", telefono="2614445555",
            email="ventas@distmendocina.com", activo=True,
        ),
        ClienteModel(
            id=3, razon_social="Bicicleteras Juan Pérez",
            cuit="23456789012", condicion_iva=CondicionIVA.MONOTRIBUTO.value,
            direccion="Belgrano 340, San Rafael", telefono="2614333222",
            email="jperez@bicicleteras.com", activo=True,
        ),
    ]
    db.add_all(clientes)
    db.flush()

    # ─── Vendedor (1 default) ─────────────────────────────────
    vendedor = VendedorModel(id=1, nombre="Vendedor Default", activo=True)
    db.add(vendedor)
    db.flush()

    # ─── Formas de Pago (6) ──────────────────────────────────
    formas_pago = [
        FormaPagoModel(
            id=1, nombre="Efectivo",
            tiene_recargo=False, recargo_financiero=0.0,
        ),
        FormaPagoModel(
            id=2, nombre="Tarjeta CRÉDITO",
            tiene_recargo=True, recargo_financiero=12.0,  # % anual aproximado
        ),
        FormaPagoModel(
            id=3, nombre="Tarjeta DÉBITO",
            tiene_recargo=False, recargo_financiero=0.0,
        ),
        FormaPagoModel(
            id=4, nombre="Cuenta Corriente",
            tiene_recargo=False, recargo_financiero=0.0,
        ),
        FormaPagoModel(
            id=5, nombre="Cheque",
            tiene_recargo=False, recargo_financiero=0.0,
        ),
        FormaPagoModel(
            id=6, nombre="Transferencia Bancaria",
            tiene_recargo=False, recargo_financiero=0.0,
        ),
    ]
    db.add_all(formas_pago)

    # ─── Caja inicial abierta ──────────────────────────────────
    caja = CajaModel(
        id=1, vendedor_id=1, saldo_inicial=0.0,
        diferencia=0.0, estado=EstadoCaja.ABIERTA.value,
    )
    db.add(caja)

    db.commit()