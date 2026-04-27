"""Seed data: pobla la base de datos con datos iniciales si está vacía.

Se ejecuta en el evento de lifespan de FastAPI (main.py).
"""

from datetime import datetime

from sqlalchemy.orm import Session

from app.infrastructure.database.models import (
    RubroModel,
    ArticuloModel,
    ClienteModel,
    VendedorModel,
    CajaModel,
    FormaPagoModel,
    ComprobanteModel,
    DetalleComprobanteModel,
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

    # ─── Artículos (20) ──────────────────────────────────────
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
            codigo="BIC-004", descripcion="Bicicleta Eléctrica E-City 500",
            rubro_id=1, precio_publico=1200000.0, precio_mayorista=980000.0,
            stock_actual=2, stock_minimo=2, inventario_estado="BAJO",
            codigo_barra="7791234567893", codigo_rapido="BEC5", activo=True,
        ),
        ArticuloModel(
            codigo="BIC-005", descripcion="Bicicleta Plegable Urban Fold 20",
            rubro_id=1, precio_publico=320000.0, precio_mayorista=265000.0,
            stock_actual=7, stock_minimo=3, inventario_estado="MEDIO",
            codigo_barra="7791234567894", codigo_rapido="BUF2", activo=True,
        ),
        ArticuloModel(
            codigo="REP-001", descripcion="Casco de Seguridad ProRider",
            rubro_id=2, precio_publico=45000.0, precio_mayorista=35000.0,
            stock_actual=0, stock_minimo=10, inventario_estado="BLOQUEADO",
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
            stock_actual=0, stock_minimo=5, inventario_estado="BLOQUEADO",
            codigo_barra="7799876543213", codigo_rapido="ASEG", activo=True,
        ),
        ArticuloModel(
            codigo="REP-005", descripcion="Luces LED Recargables 1200lm",
            rubro_id=2, precio_publico=42000.0, precio_mayorista=33000.0,
            stock_actual=18, stock_minimo=8, inventario_estado="ALTO",
            codigo_barra="7799876543214", codigo_rapido="LLR1", activo=True,
        ),
        ArticuloModel(
            codigo="REP-006", descripcion="Porta Bidón Aluminio Pro",
            rubro_id=2, precio_publico=12000.0, precio_mayorista=9000.0,
            stock_actual=40, stock_minimo=15, inventario_estado="ALTO",
            codigo_barra="7799876543215", codigo_rapido="PBAP", activo=True,
        ),
        ArticuloModel(
            codigo="REP-007", descripcion="Inflador Portátil Zefal",
            rubro_id=2, precio_publico=18000.0, precio_mayorista=14000.0,
            stock_actual=22, stock_minimo=10, inventario_estado="ALTO",
            codigo_barra="7799876543216", codigo_rapido="IPZ1", activo=True,
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
            codigo="IND-003", descripcion="Jersey Cycling Team Edition",
            rubro_id=3, precio_publico=65000.0, precio_mayorista=52000.0,
            stock_actual=10, stock_minimo=5, inventario_estado="MEDIO",
            codigo_barra="7795554443334", codigo_rapido="JCTE", activo=True,
        ),
        ArticuloModel(
            codigo="IND-004", descripcion="Calza Ciclismo Comfort Pro",
            rubro_id=3, precio_publico=38000.0, precio_mayorista=30000.0,
            stock_actual=15, stock_minimo=8, inventario_estado="ALTO",
            codigo_barra="7795554443335", codigo_rapido="CCCP", activo=True,
        ),
        ArticuloModel(
            codigo="IND-005", descripcion="Zapatillas SPD Race Carbon",
            rubro_id=3, precio_publico=145000.0, precio_mayorista=118000.0,
            stock_actual=3, stock_minimo=3, inventario_estado="BAJO",
            codigo_barra="7795554443336", codigo_rapido="ZSRC", activo=True,
        ),
        ArticuloModel(
            codigo="CMP-001", descripcion="Grupo Shimano Deore 12V",
            rubro_id=4, precio_publico=180000.0, precio_mayorista=150000.0,
            stock_actual=1, stock_minimo=2, inventario_estado="BAJO",
            codigo_barra="7791112223334", codigo_rapido="GSD12", activo=True,
        ),
        ArticuloModel(
            codigo="CMP-002", descripcion="Frenos Disco Hidráulico Shimano",
            rubro_id=4, precio_publico=95000.0, precio_mayorista=78000.0,
            stock_actual=4, stock_minimo=3, inventario_estado="BAJO",
            codigo_barra="7791112223335", codigo_rapido="FDH1", activo=True,
        ),
        ArticuloModel(
            codigo="CMP-003", descripcion="Rueda Trasera Refuerzo Pro",
            rubro_id=4, precio_publico=75000.0, precio_mayorista=61000.0,
            stock_actual=6, stock_minimo=4, inventario_estado="MEDIO",
            codigo_barra="7791112223336", codigo_rapido="RTR1", activo=True,
        ),
    ]
    db.add_all(articulos)
    db.flush()

    # ─── Clientes (6) ─────────────────────────────────────────
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
        ClienteModel(
            id=4, razon_social="Ciclo Aventura SA",
            cuit="30567890123", condicion_iva=CondicionIVA.RESPONSABLE_INSCRIPTO.value,
            direccion="Las Heras 580, Godoy Cruz", telefono="2614888999",
            email="info@cicloaventura.com", activo=True,
        ),
        ClienteModel(
            id=5, razon_social="Bike Shop Rodríguez",
            cuit="20234567891", condicion_iva=CondicionIVA.MONOTRIBUTO.value,
            direccion="San Martín 220, Mendoza", telefono="2614777666",
            email="ventas@bikeshop.com", activo=True,
        ),
        ClienteModel(
            id=6, razon_social="Deportes del Sur SRL",
            cuit="30111222333", condicion_iva=CondicionIVA.RESPONSABLE_INSCRIPTO.value,
            direccion="España 890, Mendoza", telefono="2614111222",
            email="compras@deportessur.com", activo=True,
        ),
    ]
    db.add_all(clientes)
    db.flush()

    # ─── Vendedores (3) ───────────────────────────────────────
    vendedores = [
        VendedorModel(id=1, nombre="Ana Rodríguez", activo=True),
        VendedorModel(id=2, nombre="Lucía Martínez", activo=True),
        VendedorModel(id=3, nombre="Carlos Gómez", activo=True),
    ]
    db.add_all(vendedores)
    db.flush()

    # ─── Formas de Pago (6) ──────────────────────────────────
    formas_pago = [
        FormaPagoModel(
            id=1, nombre="Efectivo",
            tiene_recargo=False, recargo_financiero=0.0,
        ),
        FormaPagoModel(
            id=2, nombre="Tarjeta CRÉDITO",
            tiene_recargo=True, recargo_financiero=12.0,
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
        id=1, vendedor_id=1, saldo_inicial=50000.0,
        diferencia=0.0, estado=EstadoCaja.ABIERTA.value,
    )
    db.add(caja)
    db.flush()

    # ─── Comprobantes históricos ────────────────────────────────
    comprobante_1 = ComprobanteModel(
        tipo="FACTURA_B", punto_venta=1, numero=1,
        cliente_id=1, vendedor_id=1, caja_id=1,
        consumidor_final=True, lista_mayorista=False,
        fecha=datetime(2026, 4, 27, 9, 30, 0),
        subtotal=324000.0, descuento_pie=0.0, total=324000.0,
        estado_sincronizacion="SINCRONIZADO", canal="WEB",
    )
    comprobante_2 = ComprobanteModel(
        tipo="FACTURA_B", punto_venta=1, numero=2,
        cliente_id=2, vendedor_id=2, caja_id=1,
        consumidor_final=False, lista_mayorista=True,
        fecha=datetime(2026, 4, 27, 10, 15, 0),
        subtotal=872000.0, descuento_pie=0.0, total=872000.0,
        estado_sincronizacion="SINCRONIZADO", canal="WEB",
    )
    comprobante_3 = ComprobanteModel(
        tipo="COTIZACION", punto_venta=1, numero=3,
        cliente_id=4, vendedor_id=1, caja_id=1,
        consumidor_final=False, lista_mayorista=False,
        fecha=datetime(2026, 4, 27, 11, 0, 0),
        subtotal=1010000.0, descuento_pie=0.0, total=1010000.0,
        estado_sincronizacion="PENDIENTE", canal="WHATSAPP",
    )
    comprobante_4 = ComprobanteModel(
        tipo="COTIZACION", punto_venta=1, numero=4,
        cliente_id=5, vendedor_id=3, caja_id=1,
        consumidor_final=False, lista_mayorista=True,
        fecha=datetime(2026, 4, 27, 11, 30, 0),
        subtotal=885000.0, descuento_pie=0.0, total=885000.0,
        estado_sincronizacion="PENDIENTE", canal="WHATSAPP",
    )
    comprobante_5 = ComprobanteModel(
        tipo="FACTURA_B", punto_venta=1, numero=5,
        cliente_id=3, vendedor_id=2, caja_id=1,
        consumidor_final=False, lista_mayorista=False,
        fecha=datetime(2026, 4, 27, 12, 45, 0),
        subtotal=310000.0, descuento_pie=0.0, total=310000.0,
        estado_sincronizacion="SINCRONIZADO", canal="WEB",
    )
    db.add_all([comprobante_1, comprobante_2, comprobante_3, comprobante_4, comprobante_5])
    db.flush()

    # ─── Detalles de comprobantes ───────────────────────────────
    detalles = [
        # Comprobante 1: FACTURA_B consumidor final
        DetalleComprobanteModel(
            comprobante_id=comprobante_1.id, articulo_codigo="BIC-003",
            cantidad=1, precio_unitario=280000.0,
            imp_int=0.0, porc_dto=0.0, descuento=0.0,
            porc_alicuota=21.0, subtotal=280000.0,
        ),
        DetalleComprobanteModel(
            comprobante_id=comprobante_1.id, articulo_codigo="REP-003",
            cantidad=2, precio_unitario=22000.0,
            imp_int=0.0, porc_dto=0.0, descuento=0.0,
            porc_alicuota=21.0, subtotal=44000.0,
        ),
        # Comprobante 2: FACTURA_B mayorista
        DetalleComprobanteModel(
            comprobante_id=comprobante_2.id, articulo_codigo="BIC-001",
            cantidad=2, precio_unitario=380000.0,
            imp_int=0.0, porc_dto=0.0, descuento=0.0,
            porc_alicuota=21.0, subtotal=760000.0,
        ),
        DetalleComprobanteModel(
            comprobante_id=comprobante_2.id, articulo_codigo="REP-002",
            cantidad=4, precio_unitario=28000.0,
            imp_int=0.0, porc_dto=0.0, descuento=0.0,
            porc_alicuota=21.0, subtotal=112000.0,
        ),
        # Comprobante 3: COTIZACION pública
        DetalleComprobanteModel(
            comprobante_id=comprobante_3.id, articulo_codigo="BIC-001",
            cantidad=1, precio_unitario=450000.0,
            imp_int=0.0, porc_dto=0.0, descuento=0.0,
            porc_alicuota=21.0, subtotal=450000.0,
        ),
        DetalleComprobanteModel(
            comprobante_id=comprobante_3.id, articulo_codigo="BIC-003",
            cantidad=2, precio_unitario=280000.0,
            imp_int=0.0, porc_dto=0.0, descuento=0.0,
            porc_alicuota=21.0, subtotal=560000.0,
        ),
        # Comprobante 4: COTIZACION mayorista
        DetalleComprobanteModel(
            comprobante_id=comprobante_4.id, articulo_codigo="BIC-002",
            cantidad=1, precio_unitario=720000.0,
            imp_int=0.0, porc_dto=0.0, descuento=0.0,
            porc_alicuota=21.0, subtotal=720000.0,
        ),
        DetalleComprobanteModel(
            comprobante_id=comprobante_4.id, articulo_codigo="REP-005",
            cantidad=5, precio_unitario=33000.0,
            imp_int=0.0, porc_dto=0.0, descuento=0.0,
            porc_alicuota=21.0, subtotal=165000.0,
        ),
        # Comprobante 5: FACTURA_B pública
        DetalleComprobanteModel(
            comprobante_id=comprobante_5.id, articulo_codigo="IND-002",
            cantidad=5, precio_unitario=18000.0,
            imp_int=0.0, porc_dto=0.0, descuento=0.0,
            porc_alicuota=21.0, subtotal=90000.0,
        ),
        DetalleComprobanteModel(
            comprobante_id=comprobante_5.id, articulo_codigo="REP-003",
            cantidad=10, precio_unitario=22000.0,
            imp_int=0.0, porc_dto=0.0, descuento=0.0,
            porc_alicuota=21.0, subtotal=220000.0,
        ),
    ]
    db.add_all(detalles)

    db.commit()