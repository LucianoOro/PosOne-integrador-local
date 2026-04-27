"""Generador de PDF para comprobantes fiscales estilo AFIP."""

from datetime import date

from fpdf import FPDF

from app.domain.entities.entities import Comprobante
from app.domain.value_objects.enums import TipoComprobante


class _ComprobantePDF(FPDF):
    """Clase interna que arma el layout del PDF."""

    def __init__(self, comprobante: Comprobante, nombres: dict):
        super().__init__(orientation="P", unit="mm", format="A4")
        self.comp = comprobante
        self.nombres = nombres
        self.set_auto_page_break(auto=True, margin=20)
        self.set_margins(left=15, top=15, right=15)

    # ── Helpers de encoding ────────────────────────────────────────────
    @staticmethod
    def _safe(text: str) -> str:
        """Reemplaza caracteres no latin-1 para Helvetica."""
        replacements = {
            "á": "a", "é": "e", "í": "i", "ó": "o", "ú": "u",
            "Á": "A", "É": "E", "Í": "I", "Ó": "O", "Ú": "U",
            "ñ": "n", "Ñ": "N",
            "ü": "u", "Ü": "U",
        }
        for k, v in replacements.items():
            text = text.replace(k, v)
        return text

    def _cell(self, w, h=0, txt="", border=0, ln=0, align="", fill=False, link=""):
        """Wrapper que sanitiza texto antes de pasarlo a cell."""
        txt = self._safe(str(txt))
        super().cell(w=w, h=h, txt=txt, border=border, new_x="LMARGIN" if ln else "RIGHT",
                     new_y="NEXT" if ln else "TOP", align=align, fill=fill, link=link)

    def _multi_cell(self, w, h, txt="", border=0, align=""):
        """Wrapper que sanitiza texto antes de pasarlo a multi_cell."""
        txt = self._safe(str(txt))
        super().multi_cell(w=w, h=h, txt=txt, border=border, align=align)

    # ── Construcción del PDF ─────────────────────────────────────────────
    def build(self) -> bytes:
        """Arma todas las secciones y devuelve los bytes del PDF."""
        self.add_page()
        self._header_empresa()
        self._header_comprobante()
        self._datos_cliente()
        self._tabla_items()
        self._totales()
        self._formas_pago()
        self._footer_warnings()
        return bytes(self.output())

    # ── Secciones ────────────────────────────────────────────────────────
    def _header_empresa(self):
        """Nombre de empresa y datos generales."""
        self.set_font("Helvetica", "B", 14)
        self._cell(0, 8, "PosONE", ln=1)
        self.set_font("Helvetica", "", 9)
        self._cell(0, 5, "Av. Siempre Viva 742 - Springfield", ln=1)
        fecha_str = self.comp.fecha.strftime("%d/%m/%Y") if self.comp.fecha else date.today().strftime("%d/%m/%Y")
        vendedor = self.nombres.get("vendedor_nombre") or ""
        self._cell(0, 5, f"Fecha: {fecha_str}    Vendedor: {vendedor}", ln=1)
        self.ln(4)

    def _header_comprobante(self):
        """Tipo y numero de comprobante."""
        tipo_label = self._tipo_label()
        numero = f"{self.comp.punto_venta:04d}-{self.comp.numero:08d}"
        self.set_font("Helvetica", "B", 12)
        self._cell(0, 8, f"{tipo_label}    Nro: {numero}", ln=1)
        # Show origin channel if WHATSAPP
        if hasattr(self.comp, 'canal') and self.comp.canal == "WHATSAPP":
            self.set_font("Helvetica", "", 8)
            self.set_text_color(128, 128, 128)
            self._cell(0, 4, "Origen: WhatsApp", ln=1)
            self.set_text_color(0, 0, 0)
        self.ln(2)

    def _datos_cliente(self):
        """Informacion del cliente."""
        if self.comp.consumidor_final:
            razon = "Consumidor Final"
            cuit = "-"
            cond_iva = "Consumidor Final"
        else:
            razon = self.nombres.get("cliente_razon_social") or "-"
            cuit = self.nombres.get("cliente_cuit") or "-"
            cond_iva = self.nombres.get("cliente_condicion_iva") or "-"

        self.set_font("Helvetica", "", 9)
        self._cell(90, 5, f"Cliente: {razon}")
        self._cell(0, 5, f"CUIT: {cuit}", ln=1)
        self._cell(0, 5, f"Cond. IVA: {cond_iva}", ln=1)
        self.ln(4)

    def _tabla_items(self):
        """Tabla de items del comprobante."""
        # Anchos de columna
        cols = [25, 65, 18, 25, 18, 25]  # Codigo, Desc, Cant, P.Unit, %Dto, Subtotal
        headers = ["Codigo", "Descripcion", "Cant.", "P.Unit.", "%Dto", "Subtotal"]

        # Header
        self.set_font("Helvetica", "B", 8)
        self.set_fill_color(220, 220, 220)
        for i, (w, h) in enumerate(zip(cols, headers)):
            align = "R" if i >= 2 else "L"
            self._cell(w, 6, h, border=1, align=align, fill=True)
        self.ln()

        # Filas
        self.set_font("Helvetica", "", 8)
        for det in self.comp.detalles:
            desc = self.nombres.get("articulos_map", {}).get(det.articulo_codigo, det.articulo_codigo)
            subtotal_fmt = f"{det.subtotal:,.2f}"
            precio_fmt = f"{det.precio_unitario:,.2f}"
            dto_fmt = f"{det.porc_dto:.1f}"
            cant_fmt = str(det.cantidad)

            self._cell(cols[0], 5, det.articulo_codigo, border=1, align="L")
            self._cell(cols[1], 5, desc, border=1, align="L")
            self._cell(cols[2], 5, cant_fmt, border=1, align="R")
            self._cell(cols[3], 5, precio_fmt, border=1, align="R")
            self._cell(cols[4], 5, dto_fmt, border=1, align="R")
            self._cell(cols[5], 5, subtotal_fmt, border=1, align="R")
            self.ln()

    def _totales(self):
        """Seccion de totales alineados a la derecha."""
        self.ln(4)
        x_right = self.w - 15  # margen derecho

        self.set_font("Helvetica", "", 9)
        # Subtotal
        label_x = x_right - 80
        self.set_x(label_x)
        self._cell(50, 5, "Subtotal:", align="R")
        self._cell(30, 5, f"${self.comp.subtotal:,.2f}", align="R", ln=1)

        # Descuento
        if self.comp.descuento_pie > 0:
            self.set_x(label_x)
            self._cell(50, 5, "Descuento:", align="R")
            self._cell(30, 5, f"-${self.comp.descuento_pie:,.2f}", align="R", ln=1)

        # Total (negrita)
        self.set_font("Helvetica", "B", 11)
        self.set_x(label_x)
        self._cell(50, 7, "TOTAL:", align="R")
        self._cell(30, 7, f"${self.comp.total:,.2f}", align="R", ln=1)
        self.ln(2)

    def _formas_pago(self):
        """Formas de pago si existen."""
        if not self.comp.formas_pago:
            return

        self.set_font("Helvetica", "B", 9)
        self._cell(0, 5, "Formas de Pago", ln=1)

        self.set_font("Helvetica", "", 8)
        fp_map = self.nombres.get("formas_pago_map", {})
        for fp in self.comp.formas_pago:
            nombre = fp_map.get(fp.forma_pago_id, f"ID {fp.forma_pago_id}")
            monto_fmt = f"${fp.monto:,.2f}"
            cuotas_str = f" ({fp.cuotas} cuotas)" if fp.cuotas > 1 else ""
            self._cell(0, 5, f"  {nombre}{cuotas_str}: {monto_fmt}", ln=1)
        self.ln(2)

    def _footer_warnings(self):
        """Avisos legales segun tipo de comprobante."""
        tipo = self.comp.tipo

        if tipo == TipoComprobante.COTIZACION:
            self.set_font("Helvetica", "B", 10)
            self.set_text_color(180, 0, 0)
            self._cell(0, 6, "PRESUPUESTO - Sin valor fiscal", align="C", ln=1)
            self._cell(0, 5, "Documento no valido como factura", align="C", ln=1)
            self.set_text_color(0, 0, 0)

        if tipo == TipoComprobante.FACTURA_B:
            self.set_font("Helvetica", "", 8)
            self.set_text_color(100, 100, 100)
            self._cell(0, 5, "Documento no valido como factura", align="C", ln=1)
            self.set_text_color(0, 0, 0)

    # ── Util ──────────────────────────────────────────────────────────────
    def _tipo_label(self) -> str:
        mapping = {
            TipoComprobante.FACTURA_A: "FACTURA A",
            TipoComprobante.FACTURA_B: "FACTURA B",
            TipoComprobante.FACTURA_C: "FACTURA C",
            TipoComprobante.COTIZACION: "COTIZACION",
            TipoComprobante.PRESUPUESTO: "PRESUPUESTO",
            TipoComprobante.NOTA_CREDITO: "NOTA DE CREDITO",
        }
        return mapping.get(self.comp.tipo, self.comp.tipo.value)


class ComprobantePDFService:
    """Servicio de generacion de PDF para comprobantes."""

    def generar_pdf(self, comprobante: Comprobante, nombres: dict) -> bytes:
        """Genera un PDF de comprobante fiscal y devuelve los bytes.

        Args:
            comprobante: Entidad de dominio con datos del comprobante.
            nombres: Dict con nombres resueltos (cliente, vendedor, articulos, formas de pago).

        Returns:
            Bytes del documento PDF generado.
        """
        pdf = _ComprobantePDF(comprobante, nombres)
        return pdf.build()