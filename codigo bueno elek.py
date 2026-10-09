import os
import sys
import tempfile
import sqlite3
import webbrowser
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime

# Importación de ReportLab para el PDF
try:
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False


class DatabaseManager:
    """Manejador de la base de datos SQLite."""
    def __init__(self, db_name="electronik.db"):
        self.db_name = db_name
        self.init_db()

    def get_connection(self):
        return sqlite3.connect(self.db_name)

    def init_db(self):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            # Tabla de clientes
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS clientes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    nombre TEXT NOT NULL,
                    direccion TEXT,
                    telefono TEXT,
                    celular TEXT
                )
            ''')
            # Tabla de órdenes
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS ordenes (
                    folio INTEGER PRIMARY KEY AUTOINCREMENT,
                    fecha_entrada TEXT,
                    tipo_servicio TEXT,
                    cliente_nombre TEXT,
                    direccion TEXT,
                    telefono TEXT,
                    celular TEXT,
                    equipo TEXT,
                    marca TEXT,
                    modelo TEXT,
                    serie TEXT,
                    observaciones TEXT,
                    falla TEXT,
                    reparacion TEXT,
                    presupuesto TEXT,
                    fecha_reparacion TEXT,
                    deja TEXT,
                    recibe TEXT
                )
            ''')
            conn.commit()

    def obtener_siguiente_folio(self):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT MAX(folio) FROM ordenes")
            row = cursor.fetchone()
            max_id = row[0] if row[0] is not None else 0
            return max_id + 1

    def guardar_o_actualizar_cliente(self, nombre, direccion, telefono, celular):
        if not nombre.strip():
            return
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM clientes WHERE LOWER(nombre) = LOWER(?)", (nombre.strip(),))
            row = cursor.fetchone()
            if row:
                cursor.execute('''
                    UPDATE clientes SET direccion=?, telefono=?, celular=? WHERE id=?
                ''', (direccion, telefono, celular, row[0]))
            else:
                cursor.execute('''
                    INSERT INTO clientes (nombre, direccion, telefono, celular)
                    VALUES (?, ?, ?, ?)
                ''', (nombre.strip(), direccion, telefono, celular))
            conn.commit()

    def buscar_clientes(self, termino):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            query = "%" + termino.strip() + "%"
            cursor.execute('''
                SELECT nombre, direccion, telefono, celular FROM clientes 
                WHERE nombre LIKE ? OR telefono LIKE ? OR celular LIKE ?
            ''', (query, query, query))
            return cursor.fetchall()

    def guardar_orden(self, datos):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO ordenes (
                    fecha_entrada, tipo_servicio, cliente_nombre, direccion, telefono, celular,
                    equipo, marca, modelo, serie, observaciones, falla, reparacion,
                    presupuesto, fecha_reparacion, deja, recibe
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', datos)
            conn.commit()
            return cursor.lastrowid


class OrdenServicioApp:
    def __init__(self, root):
        self.root = root
        self.root.title("electroni K - Orden de Reparación e Instalación")
        self.root.geometry("760x900")
        self.root.resizable(True, True)

        self.db = DatabaseManager()

        # Estilos centrados
        style = ttk.Style()
        style.theme_use('clam')
        style.configure("Center.TEntry", justify="center")

        main_frame = ttk.Frame(root, padding="15")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Encabezado
        title_label = ttk.Label(main_frame, text="electroni K", font=("Helvetica", 32, "bold"), foreground="#1a365d", anchor="center")
        title_label.pack(fill="x", pady=(2, 2))

        subtitle_label = ttk.Label(main_frame, text="ORDEN DE REPARACIÓN E INSTALACIÓN DE EQUIPOS ELECTRÓNICOS", font=("Helvetica", 9, "bold"), anchor="center")
        subtitle_label.pack(fill="x")

        info_label = ttk.Label(main_frame, text="Calle 37 x 24 Fracc. Montalbán | Tel: 9-48-96-01 | Cel: 9992 32 12 72", font=("Helvetica", 9), anchor="center")
        info_label.pack(fill="x", pady=(2, 5))

        ttk.Separator(main_frame, orient='horizontal').pack(fill='x', pady=5)

        # Folio, Fecha y Tipo de Servicio
        frame_top = ttk.Frame(main_frame)
        frame_top.pack(fill="x", pady=5)

        ttk.Label(frame_top, text="FOLIO:", font=("Helvetica", 11, "bold"), foreground="red").grid(row=0, column=0, sticky="e", padx=(5, 2))
        self.lbl_folio = ttk.Label(frame_top, text="ORD-0000", font=("Helvetica", 11, "bold"), foreground="red")
        self.lbl_folio.grid(row=0, column=1, sticky="w", padx=(0, 15))

        ttk.Label(frame_top, text="Fecha de entrada:").grid(row=0, column=2, sticky="e", padx=5)
        self.entry_fecha_entrada = ttk.Entry(frame_top, width=12, style="Center.TEntry")
        self.entry_fecha_entrada.insert(0, datetime.now().strftime("%d/%m/%Y"))
        self.entry_fecha_entrada.grid(row=0, column=3, sticky="w", padx=5)

        self.var_cotizacion = tk.BooleanVar()
        self.var_garantia = tk.BooleanVar()
        self.var_reparacion = tk.BooleanVar()

        ttk.Checkbutton(frame_top, text="Cotización", variable=self.var_cotizacion).grid(row=0, column=4, padx=8)
        ttk.Checkbutton(frame_top, text="Garantía", variable=self.var_garantia).grid(row=0, column=5, padx=8)
        ttk.Checkbutton(frame_top, text="Reparación", variable=self.var_reparacion).grid(row=0, column=6, padx=8)

        # Datos del Cliente
        frame_cliente = ttk.LabelFrame(main_frame, text=" Datos del Cliente ", padding="10")
        frame_cliente.pack(fill="x", pady=5)
        frame_cliente.columnconfigure(1, weight=1)

        ttk.Label(frame_cliente, text="Nombre del cliente:").grid(row=0, column=0, sticky="e", pady=2)
        self.entry_cliente = ttk.Entry(frame_cliente, style="Center.TEntry")
        self.entry_cliente.grid(row=0, column=1, columnspan=2, sticky="ew", pady=2, padx=5)

        btn_buscar_cli = ttk.Button(frame_cliente, text="🔍 Buscar Cliente", command=self.abrir_ventana_buscar_cliente)
        btn_buscar_cli.grid(row=0, column=3, padx=5, pady=2)

        ttk.Label(frame_cliente, text="Dirección:").grid(row=1, column=0, sticky="e", pady=2)
        self.entry_direccion = ttk.Entry(frame_cliente, style="Center.TEntry")
        self.entry_direccion.grid(row=1, column=1, columnspan=3, sticky="ew", pady=2, padx=5)

        ttk.Label(frame_cliente, text="Teléfono:").grid(row=2, column=0, sticky="e", pady=2)
        self.entry_telefono = ttk.Entry(frame_cliente, width=20, style="Center.TEntry")
        self.entry_telefono.grid(row=2, column=1, sticky="w", pady=2, padx=5)

        ttk.Label(frame_cliente, text="Celular:").grid(row=2, column=2, sticky="e", pady=2)
        self.entry_celular = ttk.Entry(frame_cliente, width=20, style="Center.TEntry")
        self.entry_celular.grid(row=2, column=3, sticky="w", pady=2, padx=5)

        # Datos del Equipo
        frame_equipo = ttk.LabelFrame(main_frame, text=" Datos del Equipo ", padding="10")
        frame_equipo.pack(fill="x", pady=5)

        ttk.Label(frame_equipo, text="Equipo:").grid(row=0, column=0, sticky="e", pady=2)
        self.entry_equipo = ttk.Entry(frame_equipo, width=22, style="Center.TEntry")
        self.entry_equipo.grid(row=0, column=1, sticky="w", pady=2, padx=5)

        ttk.Label(frame_equipo, text="Marca:").grid(row=0, column=2, sticky="e", pady=2)
        self.entry_marca = ttk.Entry(frame_equipo, width=22, style="Center.TEntry")
        self.entry_marca.grid(row=0, column=3, sticky="w", pady=2, padx=5)

        ttk.Label(frame_equipo, text="Modelo:").grid(row=1, column=0, sticky="e", pady=2)
        self.entry_modelo = ttk.Entry(frame_equipo, width=22, style="Center.TEntry")
        self.entry_modelo.grid(row=1, column=1, sticky="w", pady=2, padx=5)

        ttk.Label(frame_equipo, text="Serie:").grid(row=1, column=2, sticky="e", pady=2)
        self.entry_serie = ttk.Entry(frame_equipo, width=22, style="Center.TEntry")
        self.entry_serie.grid(row=1, column=3, sticky="w", pady=2, padx=5)

        ttk.Label(frame_equipo, text="Observaciones:").grid(row=2, column=0, sticky="e", pady=5)
        
        obs_frame = ttk.Frame(frame_equipo)
        obs_frame.grid(row=2, column=1, columnspan=3, sticky="w", pady=5)

        self.var_rayado = tk.BooleanVar()
        self.var_golpeado = tk.BooleanVar()
        self.var_roto = tk.BooleanVar()
        self.var_sin_accesorios = tk.BooleanVar()

        ttk.Checkbutton(obs_frame, text="Equipo rayado", variable=self.var_rayado).grid(row=0, column=0, sticky="w", padx=10)
        ttk.Checkbutton(obs_frame, text="Equipo golpeado", variable=self.var_golpeado).grid(row=0, column=1, sticky="w", padx=10)
        ttk.Checkbutton(obs_frame, text="Equipo roto", variable=self.var_roto).grid(row=1, column=0, sticky="w", padx=10)
        ttk.Checkbutton(obs_frame, text="Sin accesorios", variable=self.var_sin_accesorios).grid(row=1, column=1, sticky="w", padx=10)

        # Diagnóstico y Reparación
        frame_diagnostico = ttk.LabelFrame(main_frame, text=" Reportes de Servicio ", padding="10")
        frame_diagnostico.pack(fill="x", pady=5)

        ttk.Label(frame_diagnostico, text="Falla reportada:", anchor="center").pack(fill="x")
        self.txt_falla = tk.Text(frame_diagnostico, height=2, width=80)
        self.txt_falla.tag_configure("center", justify='center')
        self.txt_falla.pack(fill="x", pady=(0, 5))

        ttk.Label(frame_diagnostico, text="Reporte de reparación:", anchor="center").pack(fill="x")
        self.txt_reparacion = tk.Text(frame_diagnostico, height=2, width=80)
        self.txt_reparacion.tag_configure("center", justify='center')
        self.txt_reparacion.pack(fill="x", pady=(0, 5))

        # Presupuesto y Condiciones
        frame_costo = ttk.Frame(main_frame)
        frame_costo.pack(fill="x", pady=5)

        ttk.Label(frame_costo, text="Presupuesto $:", font=("Helvetica", 10, "bold")).pack(side="left", padx=5)
        self.entry_presupuesto = ttk.Entry(frame_costo, width=15, font=("Helvetica", 10, "bold"), style="Center.TEntry")
        self.entry_presupuesto.pack(side="left", padx=5)

        ttk.Label(frame_costo, text="Fecha de reparación:").pack(side="left", padx=(20, 5))
        self.entry_fecha_reparacion = ttk.Entry(frame_costo, width=15, style="Center.TEntry")
        self.entry_fecha_reparacion.pack(side="left", padx=5)

        terminos_text = (
            "Acepto presupuesto y condiciones de almacenamiento:\n"
            "Una vez aceptado el presupuesto, después de 05 días naturales desde la fecha de reparación "
            "tendrá un costo de almacenamiento de $ 50 pesos diarios, después de los 30 días se desechará el equipo."
        )
        lbl_terminos = ttk.Label(main_frame, text=terminos_text, font=("Helvetica", 7, "italic"), justify="center", anchor="center", foreground="#555")
        lbl_terminos.pack(fill="x", pady=5)

        # Firmas
        frame_firmas = ttk.Frame(main_frame)
        frame_firmas.pack(fill="x", pady=5)

        ttk.Label(frame_firmas, text="Deja equipo:").grid(row=0, column=0, sticky="e", padx=5)
        self.entry_deja = ttk.Entry(frame_firmas, width=28, style="Center.TEntry")
        self.entry_deja.grid(row=0, column=1, sticky="w", padx=5)

        ttk.Label(frame_firmas, text="Recibe equipo:").grid(row=0, column=2, sticky="e", padx=5)
        self.entry_recibe = ttk.Entry(frame_firmas, width=28, style="Center.TEntry")
        self.entry_recibe.grid(row=0, column=3, sticky="w", padx=5)

        # Botones de Acción
        frame_botones = ttk.Frame(main_frame)
        frame_botones.pack(fill="x", pady=10)

        btn_pdf = ttk.Button(frame_botones, text="Imprimir en PDF", command=self.generar_pdf)
        btn_pdf.pack(side="right", padx=5)

        btn_guardar = ttk.Button(frame_botones, text="Guardar Orden", command=self.guardar_orden)
        btn_guardar.pack(side="right", padx=5)

        btn_limpiar = ttk.Button(frame_botones, text="Limpiar Formulario", command=self.limpiar_formulario)
        btn_limpiar.pack(side="right", padx=5)

        # Inicializar Folio Actual
        self.actualizar_folio_ui()

    def actualizar_folio_ui(self):
        siguiente_folio = self.db.obtener_siguiente_folio()
        self.lbl_folio.config(text=f"ORD-{siguiente_folio:04d}")

    def abrir_ventana_buscar_cliente(self):
        ventana = tk.Toplevel(self.root)
        ventana.title("Buscar Cliente")
        ventana.geometry("500x350")
        ventana.transient(self.root)
        ventana.grab_set()

        lbl_inst = ttk.Label(ventana, text="Buscar cliente por Nombre o Teléfono:", font=("Helvetica", 9, "bold"))
        lbl_inst.pack(pady=(10, 5))

        entry_busqueda = ttk.Entry(ventana, width=40, style="Center.TEntry")
        entry_busqueda.pack(pady=5)
        entry_busqueda.focus()

        columns = ("nombre", "direccion", "telefono", "celular")
        tree = ttk.Treeview(ventana, columns=columns, show="headings", height=8)

        tree.heading("nombre", text="Nombre")
        tree.heading("direccion", text="Dirección")
        tree.heading("telefono", text="Teléfono")
        tree.heading("celular", text="Celular")

        tree.column("nombre", width=130, anchor="center")
        tree.column("direccion", width=150, anchor="center")
        tree.column("telefono", width=90, anchor="center")
        tree.column("celular", width=90, anchor="center")

        tree.pack(fill="both", expand=True, padx=10, pady=5)

        def ejecutar_busqueda(event=None):
            for item in tree.get_children():
                tree.delete(item)
            resultados = self.db.buscar_clientes(entry_busqueda.get())
            for res in resultados:
                tree.insert("", "end", values=res)

        entry_busqueda.bind("<KeyRelease>", ejecutar_busqueda)

        def seleccionar_cliente():
            selected = tree.selection()
            if not selected:
                messagebox.showwarning("Selección requerida", "Por favor, seleccione un cliente de la lista.", parent=ventana)
                return
            item = tree.item(selected[0])
            vals = item["values"]
            
            # Autocompletar campos
            self.entry_cliente.delete(0, tk.END)
            self.entry_cliente.insert(0, str(vals[0]))
            
            self.entry_direccion.delete(0, tk.END)
            self.entry_direccion.insert(0, str(vals[1]))
            
            self.entry_telefono.delete(0, tk.END)
            self.entry_telefono.insert(0, str(vals[2]))
            
            self.entry_celular.delete(0, tk.END)
            self.entry_celular.insert(0, str(vals[3]))

            ventana.destroy()

        btn_seleccionar = ttk.Button(ventana, text="Seleccionar Cliente", command=seleccionar_cliente)
        btn_seleccionar.pack(pady=10)

        ejecutar_busqueda()

    def obtener_observaciones_texto(self):
        obs = []
        if self.var_rayado.get(): obs.append("Equipo rayado")
        if self.var_golpeado.get(): obs.append("Equipo golpeado")
        if self.var_roto.get(): obs.append("Equipo roto")
        if self.var_sin_accesorios.get(): obs.append("Sin accesorios")
        return ", ".join(obs) if obs else "Ninguna"

    def guardar_orden(self):
        cliente = self.entry_cliente.get().strip()
        equipo = self.entry_equipo.get().strip()

        if not cliente or not equipo:
            messagebox.showwarning("Campos incompletos", "Por favor, ingrese al menos el Nombre del Cliente y el Equipo.")
            return

        # 1. Guardar o actualizar cliente en BD
        self.db.guardar_o_actualizar_cliente(
            cliente,
            self.entry_direccion.get().strip(),
            self.entry_telefono.get().strip(),
            self.entry_celular.get().strip()
        )

        # 2. Guardar orden en BD
        tipos = []
        if self.var_cotizacion.get(): tipos.append("Cotización")
        if self.var_garantia.get(): tipos.append("Garantía")
        if self.var_reparacion.get(): tipos.append("Reparación")
        tipo_servicio = ", ".join(tipos)

        datos = (
            self.entry_fecha_entrada.get(),
            tipo_servicio,
            cliente,
            self.entry_direccion.get(),
            self.entry_telefono.get(),
            self.entry_celular.get(),
            equipo,
            self.entry_marca.get(),
            self.entry_modelo.get(),
            self.entry_serie.get(),
            self.obtener_observaciones_texto(),
            self.txt_falla.get('1.0', tk.END).strip(),
            self.txt_reparacion.get('1.0', tk.END).strip(),
            self.entry_presupuesto.get(),
            self.entry_fecha_reparacion.get(),
            self.entry_deja.get(),
            self.entry_recibe.get()
        )

        folio = self.db.guardar_orden(datos)
        messagebox.showinfo("Orden Registrada", f"La orden ORD-{folio:04d} y los datos del cliente se han guardado exitosamente en la Base de Datos.")
        self.actualizar_folio_ui()

    def generar_pdf(self):
        cliente = self.entry_cliente.get().strip()
        equipo = self.entry_equipo.get().strip()

        if not cliente or not equipo:
            messagebox.showwarning("Campos Incompletos", "Complete al menos el Nombre del Cliente y el Equipo para generar el PDF.")
            return

        if not REPORTLAB_AVAILABLE:
            messagebox.showerror("Librería Faltante", "ReportLab no está instalado en el sistema.")
            return

        folio_str = self.lbl_folio.cget("text")
        pdf_path = os.path.join(tempfile.gettempdir(), f"{folio_str}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf")
        
        c = canvas.Canvas(pdf_path, pagesize=letter)
        width, height = letter

        # Encabezado
        c.setFont("Helvetica-Bold", 26)
        c.drawCentredString(width / 2, height - 45, "electroni K")
        
        c.setFont("Helvetica-Bold", 10)
        c.drawCentredString(width / 2, height - 62, "ORDEN REPARACIÓN E INSTALACIÓN DE EQUIPOS ELECTRÓNICOS")
        
        c.setFont("Helvetica", 9)
        c.drawCentredString(width / 2, height - 76, "Calle 37 x 24 Fracc. Montalbán Tel. 9-48-96-01 Cel. 9992 32 12 72")

        c.setLineWidth(1)
        c.line(40, height - 82, width - 40, height - 82)

        # Folio y Fecha
        y = height - 100
        c.setFont("Helvetica-Bold", 11)
        c.setFillColorRGB(0.8, 0, 0)
        c.drawString(40, y, f"FOLIO: {folio_str}")
        c.setFillColorRGB(0, 0, 0)

        c.setFont("Helvetica-Bold", 9)
        c.drawString(180, y, "Fecha de entrada:")
        c.setFont("Helvetica", 9)
        c.drawString(265, y, self.entry_fecha_entrada.get())

        # Checkboxes
        x_check = 360
        for label, val in [("Cotización", self.var_cotizacion.get()), ("Garantía", self.var_garantia.get()), ("Reparación", self.var_reparacion.get())]:
            c.rect(x_check, y - 2, 10, 10)
            if val:
                c.setFont("Helvetica-Bold", 10)
                c.drawString(x_check + 2, y, "X")
            c.setFont("Helvetica", 9)
            c.drawString(x_check + 15, y, label)
            x_check += 75

        # Datos del Cliente
        y -= 25
        campos_cliente = [
            ("Nombre del cliente:", self.entry_cliente.get()),
            ("Dirección:", self.entry_direccion.get()),
            ("Teléfono:", self.entry_telefono.get()),
        ]

        for lab, val in campos_cliente:
            c.setFont("Helvetica-Bold", 9)
            c.drawString(40, y, lab)
            c.setFont("Helvetica", 9)
            c.drawString(135, y, val)
            c.line(130, y - 2, width - 40, y - 2)
            if lab == "Teléfono:":
                c.setFont("Helvetica-Bold", 9)
                c.drawString(320, y, "Celular:")
                c.setFont("Helvetica", 9)
                c.drawString(370, y, self.entry_celular.get())
            y -= 20

        # Datos del Equipo
        y -= 5
        campos_equipo = [
            [("Equipo:", self.entry_equipo.get()), ("Marca:", self.entry_marca.get())],
            [("Modelo:", self.entry_modelo.get()), ("Serie:", self.entry_serie.get())]
        ]

        for fila in campos_equipo:
            c.setFont("Helvetica-Bold", 9)
            c.drawString(40, y, fila[0][0])
            c.setFont("Helvetica", 9)
            c.drawString(95, y, fila[0][1])
            c.line(90, y - 2, 280, y - 2)

            c.setFont("Helvetica-Bold", 9)
            c.drawString(310, y, fila[1][0])
            c.setFont("Helvetica", 9)
            c.drawString(360, y, fila[1][1])
            c.line(355, y - 2, width - 40, y - 2)
            y -= 20

        # Observaciones
        c.setFont("Helvetica-Bold", 9)
        c.drawString(40, y, "Observaciones:")

        obs_items = [
            ("Equipo rayado", self.var_rayado.get()),
            ("Equipo golpeado", self.var_golpeado.get()),
            ("Equipo roto", self.var_roto.get()),
            ("Sin accesorios", self.var_sin_accesorios.get())
        ]

        x_obs = 135
        y_obs = y
        for i, (label, val) in enumerate(obs_items):
            curr_x = x_obs if i % 2 == 0 else x_obs + 160
            curr_y = y_obs if i < 2 else y_obs - 18
            c.rect(curr_x, curr_y - 2, 10, 10)
            if val:
                c.setFont("Helvetica-Bold", 10)
                c.drawString(curr_x + 2, curr_y, "X")
            c.setFont("Helvetica", 9)
            c.drawString(curr_x + 15, curr_y, label)

        y -= 45

        # Falla y Reporte
        c.setFont("Helvetica-Bold", 9)
        c.drawString(40, y, "Falla reportada:")
        c.setFont("Helvetica", 9)
        c.drawString(40, y - 15, self.txt_falla.get('1.0', tk.END).strip())
        c.line(40, y - 20, width - 40, y - 20)

        y -= 45
        c.setFont("Helvetica-Bold", 9)
        c.drawString(40, y, "Reporte de reparación:")
        c.setFont("Helvetica", 9)
        c.drawString(40, y - 15, self.txt_reparacion.get('1.0', tk.END).strip())
        c.line(40, y - 20, width - 40, y - 20)

        # Presupuesto
        y -= 45
        c.setFont("Helvetica-Bold", 10)
        c.drawString(40, y, "Presupuesto $")
        c.setFont("Helvetica", 10)
        c.drawString(120, y, self.entry_presupuesto.get())
        c.line(115, y - 2, 250, y - 2)

        # Términos y Condiciones
        y -= 30
        c.setFont("Helvetica-Bold", 8)
        c.drawString(40, y, "Acepto presupuesto y condiciones de almacenamiento")
        y -= 12
        c.setFont("Helvetica", 7.5)
        c.drawString(40, y, "Una vez aceptado el presupuesto, después de 05 días naturales desde la fecha de reparación tendrá")
        y -= 10
        c.drawString(40, y, "un costo de almacenamiento de $ 50 pesos diarios, después de los 30 días se desechará el equipo.")
        y -= 10
        c.setFont("Helvetica-Bold", 8)
        c.drawString(40, y, "Si está de acuerdo firme la orden.")

        # Firmas
        y -= 45
        c.line(40, y, 220, y)
        c.setFont("Helvetica-Bold", 8)
        c.drawCentredString(130, y - 10, "Deja equipo")

        c.line(260, y, 420, y)
        c.drawCentredString(340, y - 10, "Recibe equipo")

        c.setFont("Helvetica-Bold", 8)
        c.drawString(440, y + 10, "Fecha de reparación")
        c.setFont("Helvetica", 8)
        c.drawString(440, y - 10, self.entry_fecha_reparacion.get())
        c.line(435, y - 12, width - 40, y - 12)

        c.save()

        # Abrir PDF en el navegador o visor predeterminado
        try:
            webbrowser.open(pdf_path)
            messagebox.showinfo("PDF Generado", f"Se ha generado la orden {folio_str} correctamente:\n{pdf_path}")
        except Exception as e:
            messagebox.showwarning("PDF Generado", f"PDF guardado en: {pdf_path}\nError al abrir automáticamente: {e}")

    def limpiar_formulario(self):
        self.entry_cliente.delete(0, tk.END)
        self.entry_direccion.delete(0, tk.END)
        self.entry_telefono.delete(0, tk.END)
        self.entry_celular.delete(0, tk.END)
        self.entry_equipo.delete(0, tk.END)
        self.entry_marca.delete(0, tk.END)
        self.entry_modelo.delete(0, tk.END)
        self.entry_serie.delete(0, tk.END)
        self.entry_presupuesto.delete(0, tk.END)
        self.entry_fecha_reparacion.delete(0, tk.END)
        self.entry_deja.delete(0, tk.END)
        self.entry_recibe.delete(0, tk.END)
        
        self.txt_falla.delete("1.0", tk.END)
        self.txt_reparacion.delete("1.0", tk.END)

        self.var_cotizacion.set(False)
        self.var_garantia.set(False)
        self.var_reparacion.set(False)
        self.var_rayado.set(False)
        self.var_golpeado.set(False)
        self.var_roto.set(False)
        self.var_sin_accesorios.set(False)

        self.actualizar_folio_ui()


if __name__ == "__main__":
    root = tk.Tk()
    app = OrdenServicioApp(root)
    root.mainloop()