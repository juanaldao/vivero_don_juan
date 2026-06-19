import asyncio
import io
import os
from datetime import datetime
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (
    HRFlowable, Image as RLImage, SimpleDocTemplate,
    Spacer, Table, TableStyle, Paragraph,
)
from supabase import create_client

from . import config

_supabase = create_client(config.SUPABASE_URL, config.SUPABASE_SERVICE_KEY)

LOGO_PATH = str(Path(__file__).parent.parent / "logo.png")
STORAGE_BUCKET = "presupuestos"

CONTACTO = {
    "direccion": "Av. de las Rosas 123, Tigre, Buenos Aires",
    "telefono":  "+54 9 11 1234-5678",
    "website":   "www.viverodonjuan.com.ar",
    "email":     "contacto@viverodonjuan.com.ar",
    "horario":   "L a V de 8 a 18hs - Sabados de 9 a 18hs",
}


def buscar_variante(nombre: str, envase_lts=None) -> dict | None:
    q = (
        _supabase.table("catalogo")
        .select("*")
        .ilike("nombre_comun", f"%{nombre}%")
        .gt("stock", 0)
    )
    if envase_lts is not None:
        q = q.eq("tamano_envase_lts", envase_lts)
    result = q.order("elegibilidad", desc=True).limit(1).execute()
    return result.data[0] if result.data else None


def generar_pdf(
    items_detalle: list[dict],
    numero: str,
    nombre_cliente: str,
    telefono_cliente: str = "",
) -> bytes:
    def fmt_monto(val: int) -> str:
        s = f"{int(val):,}".replace(",", ".")
        return f"$ {s},00"

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        leftMargin=1.5*cm, rightMargin=1.5*cm,
        topMargin=1.5*cm, bottomMargin=1.5*cm,
    )

    styles      = getSampleStyleSheet()
    verde       = colors.HexColor("#00913f")
    negro       = colors.HexColor("#111111")
    gris_header = colors.HexColor("#2b2b2b")
    gris_fila   = colors.HexColor("#f2f2f2")
    gris_borde  = colors.HexColor("#bbbbbb")

    s_emp_nom  = ParagraphStyle("emp_n", parent=styles["Normal"],
                                fontSize=14, textColor=verde,
                                fontName="Helvetica-Bold", alignment=2, spaceAfter=4)
    s_emp_det  = ParagraphStyle("emp_d", parent=styles["Normal"],
                                fontSize=8, textColor=negro,
                                fontName="Helvetica", alignment=2, spaceAfter=1)
    s_titulo   = ParagraphStyle("titulo", parent=styles["Normal"],
                                fontSize=14, textColor=negro,
                                fontName="Helvetica-Bold", spaceAfter=2)
    s_subtit   = ParagraphStyle("subtit", parent=styles["Normal"],
                                fontSize=8, textColor=negro,
                                fontName="Helvetica")
    s_cli_nom  = ParagraphStyle("cli_n", parent=styles["Normal"],
                                fontSize=10, textColor=negro,
                                fontName="Helvetica-Bold", spaceAfter=2)
    s_cli_det  = ParagraphStyle("cli_d", parent=styles["Normal"],
                                fontSize=9, textColor=negro,
                                fontName="Helvetica", spaceAfter=1)
    s_meta_lbl = ParagraphStyle("meta_l", parent=styles["Normal"],
                                fontSize=8.5, textColor=negro,
                                fontName="Helvetica")
    s_meta_val = ParagraphStyle("meta_v", parent=styles["Normal"],
                                fontSize=8.5, textColor=negro,
                                fontName="Helvetica-Bold")
    s_obs      = ParagraphStyle("obs", parent=styles["Normal"],
                                fontSize=8, textColor=negro,
                                fontName="Helvetica")

    story = []

    # Header: logo left, company info right
    col_logo = [RLImage(LOGO_PATH, width=4*cm, height=3.5*cm, kind="proportional")] \
               if os.path.exists(LOGO_PATH) else [Spacer(1, 3.5*cm)]

    col_empresa = [
        Paragraph("Vivero Don Juan", s_emp_nom),
        Paragraph(CONTACTO["direccion"], s_emp_det),
        Paragraph(f'Tel: {CONTACTO["telefono"]}', s_emp_det),
        Paragraph(f'WhatsApp: {CONTACTO["telefono"]}', s_emp_det),
        Paragraph(CONTACTO["website"], s_emp_det),
        Paragraph(CONTACTO["email"], s_emp_det),
        Paragraph(CONTACTO["horario"], s_emp_det),
    ]

    header = Table([[col_logo, col_empresa]], colWidths=[5.5*cm, 12.5*cm])
    header.setStyle(TableStyle([
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING",   (0, 0), (-1, -1), 0),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 0),
        ("TOPPADDING",    (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))
    story.append(header)
    story.append(Spacer(1, 0.3*cm))
    story.append(HRFlowable(width="100%", thickness=1, color=negro))
    story.append(Spacer(1, 0.3*cm))

    story.append(Paragraph("COTIZACIÓN", s_titulo))
    story.append(Paragraph("- Documento No Válido Como Factura -", s_subtit))
    story.append(Spacer(1, 0.4*cm))

    fecha_str = datetime.now().strftime("%d/%m/%Y")
    meta_rows = [
        [Paragraph("Cotización :", s_meta_lbl), Paragraph(numero, s_meta_val)],
        [Paragraph("Fecha :",      s_meta_lbl), Paragraph(fecha_str, s_meta_val)],
    ]
    meta_inner = Table(meta_rows, colWidths=[2.8*cm, 4.7*cm])
    meta_inner.setStyle(TableStyle([
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING",    (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING",   (0, 0), (-1, -1), 6),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 6),
    ]))

    cli_block = []
    if nombre_cliente:
        cli_block.append(Paragraph(nombre_cliente.upper(), s_cli_nom))
    if telefono_cliente:
        cli_block.append(Paragraph(f"Cel: {telefono_cliente}", s_cli_det))
    if not cli_block:
        cli_block = [Spacer(1, 1*cm)]

    info_row = Table([[cli_block, meta_inner]], colWidths=[10*cm, 8*cm])
    info_row.setStyle(TableStyle([
        ("VALIGN",        (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING",   (0, 0), (0,  -1), 0),
        ("RIGHTPADDING",  (0, 0), (0,  -1), 0),
        ("TOPPADDING",    (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ("LEFTPADDING",   (1, 0), (1,  -1), 0),
        ("RIGHTPADDING",  (1, 0), (1,  -1), 0),
        ("BOX",           (1, 0), (1,   0), 0.5, gris_borde),
    ]))
    story.append(info_row)
    story.append(Spacer(1, 0.4*cm))

    header_row = [["Descripción", "Cantidad", "Unitario", "Total"]]
    filas = []
    total = 0
    for it in items_detalle:
        subtotal = it["precio"] * it["cantidad"]
        total += subtotal
        desc = it["nombre"].upper()
        if it.get("envase_lts"):
            desc += f" {it['envase_lts']} LTS"
        filas.append([
            desc,
            f"{it['cantidad']},00",
            fmt_monto(it["precio"]),
            fmt_monto(subtotal),
        ])

    tabla = Table(
        header_row + filas,
        colWidths=[9.5*cm, 2.5*cm, 3.5*cm, 2.5*cm],
        repeatRows=1,
    )
    tabla.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, 0),  gris_header),
        ("TEXTCOLOR",     (0, 0), (-1, 0),  colors.white),
        ("FONTNAME",      (0, 0), (-1, 0),  "Helvetica-Bold"),
        ("FONTSIZE",      (0, 0), (-1, 0),  9),
        ("ALIGN",         (0, 0), (0,  0),  "LEFT"),
        ("ALIGN",         (1, 0), (-1, 0),  "RIGHT"),
        ("TOPPADDING",    (0, 0), (-1, 0),  7),
        ("BOTTOMPADDING", (0, 0), (-1, 0),  7),
        ("FONTNAME",      (0, 1), (-1, -1), "Helvetica"),
        ("FONTSIZE",      (0, 1), (-1, -1), 9),
        ("ROWBACKGROUNDS",(0, 1), (-1, -1), [colors.white, gris_fila]),
        ("ALIGN",         (0, 1), (0,  -1), "LEFT"),
        ("ALIGN",         (1, 1), (-1, -1), "RIGHT"),
        ("TOPPADDING",    (0, 1), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 1), (-1, -1), 5),
        ("LEFTPADDING",   (0, 0), (-1, -1), 6),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 6),
        ("LINEBELOW",     (0, 0), (-1, -1), 0.3, gris_borde),
        ("BOX",           (0, 0), (-1, -1), 0.5, gris_borde),
    ]))
    story.append(tabla)
    story.append(Spacer(1, 0.2*cm))

    ancho_total = 9.5 + 2.5 + 3.5 + 2.5
    total_row = Table(
        [["TOTAL:", fmt_monto(total)]],
        colWidths=[(ancho_total - 5)*cm, 5*cm],
    )
    total_row.setStyle(TableStyle([
        ("FONTNAME",      (0, 0), (-1, -1), "Helvetica-Bold"),
        ("FONTSIZE",      (0, 0), (-1, -1), 11),
        ("ALIGN",         (0, 0), (0,  0),  "RIGHT"),
        ("ALIGN",         (1, 0), (1,  0),  "RIGHT"),
        ("TOPPADDING",    (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING",   (0, 0), (-1, -1), 6),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 6),
        ("BOX",           (0, 0), (-1, -1), 0.8, negro),
    ]))
    story.append(total_row)
    story.append(Spacer(1, 0.5*cm))

    story.append(Paragraph(
        "Presupuesto válido por 7 días. Precios en pesos argentinos. Stock sujeto a disponibilidad.",
        s_obs,
    ))

    doc.build(story)
    return buffer.getvalue()


def _armar_presupuesto_sync(args: dict) -> tuple[str, str | None]:
    items_input      = args.get("items", [])
    nombre_cliente   = args.get("nombre_cliente", "")
    telefono_cliente = args.get("telefono_cliente", "")

    items_detalle  = []
    no_encontrados = []

    for item in items_input:
        nombre   = item["nombre"]
        envase   = item.get("envase_lts")
        cantidad = int(item.get("cantidad", 1))

        variante = buscar_variante(nombre, envase)
        if not variante:
            no_encontrados.append(nombre)
            continue

        items_detalle.append({
            "nombre":     variante.get("nombre_comun", nombre),
            "envase_lts": variante.get("tamano_envase_lts"),
            "cantidad":   cantidad,
            "precio":     variante["precio"],
            "stock":      variante["stock"],
        })

    if not items_detalle:
        return "No se encontraron los productos solicitados en el catálogo.", None

    total = sum(it["precio"] * it["cantidad"] for it in items_detalle)

    reg = _supabase.table("presupuestos").insert({
        "nombre_cliente":   nombre_cliente,
        "telefono_cliente": telefono_cliente,
        "total":            total,
    }).execute()
    presupuesto_id = reg.data[0]["id"]
    numero   = f"PRE-{presupuesto_id:04d}"
    filename = f"{numero}.pdf"

    pdf_bytes = generar_pdf(items_detalle, numero, nombre_cliente, telefono_cliente)

    _supabase.storage.from_(STORAGE_BUCKET).upload(
        path=filename,
        file=pdf_bytes,
        file_options={"content-type": "application/pdf", "upsert": "true"},
    )
    pdf_url = _supabase.storage.from_(STORAGE_BUCKET).get_public_url(filename)

    _supabase.table("presupuestos").update({"pdf_url": pdf_url}).eq("id", presupuesto_id).execute()

    lineas = [f"Presupuesto {numero} generado exitosamente."]
    for it in items_detalle:
        subtotal = it["precio"] * it["cantidad"]
        lineas.append(f"- {it['nombre']} {it['envase_lts']}lts x{it['cantidad']} = ${subtotal:,}")
    lineas.append(f"TOTAL: ${total:,}")
    if no_encontrados:
        lineas.append(f"No encontrados: {', '.join(no_encontrados)}")
    lineas.append(f"PDF disponible en: {pdf_url}")

    return "\n".join(lineas), pdf_url


async def ejecutar_armar_presupuesto(args: dict) -> tuple[str, str | None]:
    return await asyncio.to_thread(_armar_presupuesto_sync, args)
