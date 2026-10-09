import os
import sys
import sqlite3
import tempfile
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime

try:
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas
    from reportlab.lib import colors
    from reportlab.platypus import Paragraph
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.enums import TA_LEFT
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False


APP_TITLE = "electroni K - Orden de Reparación e Instalación"
DB_FILENAME = "electronik_ordenes.db"


class Database:
    """Base de datos local SQLite para clientes y órdenes."""

    def __init__(self, db_path=None):
        if db_path is None:
            # La base queda junto al ejecutable/script.
            base_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
            db_path = os.path.join(base_dir, DB_FILENAME)
        self.db_path = db_path
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        self._create_tables()

    def _create_tables(self):
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS clientes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre TEXT NOT NULL,
                direccion TEXT DEFAULT '',
                telefono TEXT DEFAULT '',
                celular TEXT DEFAULT '',
                creado_en TEXT NOT NULL,
                actualizado_en TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS ordenes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                folio INTEGER UNIQUE NOT NULL,
                cliente_id INTEGER,
                fecha_entrada TEXT NOT NULL,
                cotizacion INTEGER DEFAULT 0,
                garantia INTEGER DEFAULT 0,
                reparacion INTEGER DEFAULT 0,
                equipo TEXT DEFAULT '',
                marca TEXT DEFAULT '',
                modelo TEXT DEFAULT '',
                serie TEXT DEFAULT '',
                rayado INTEGER DEFAULT 0,
                golpeado INTEGER DEFAULT 0,
                roto INTEGER DEFAULT 0,
                sin_accesorios INTEGER DEFAULT 0,
                falla TEXT DEFAULT '',
                reporte_reparacion TEXT DEFAULT '',
                presupuesto TEXT DEFAULT '',
                fecha_reparacion TEXT DEFAULT '',
                deja_equipo TEXT DEFAULT '',
                recibe_equipo TEXT DEFAULT '',
                creado_en TEXT NOT NULL,
                FOREIGN KEY(cliente_id) REFERENCES clientes(id)
            );
        """)
        self.conn.commit()

        # Si existe una instalación anterior sin folios, el primer folio será 1.
        # Los folios nuevos siempre se obtienen desde MAX(folio) + 1.
        self._ensure_sequence()

    def _ensure_sequence(self):
        # No hace falta una tabla de secuencia: SQLite conserva los folios
        # usados y el siguiente se calcula con MAX.
        self.conn.commit()

    def next_folio(self):
        row = self.conn.execute("SELECT COALESCE(MAX(folio), 0) + 1 AS siguiente FROM ordenes").fetchone()
        return int(row["siguiente"])

    def find_clients(self, term):
        term = term.strip()
        like = f"%{term}%"
        return self.conn.execute("""
            SELECT id, nombre, direccion, telefono, celular
            FROM clientes
            WHERE nombre LIKE ?
               OR telefono LIKE ?
               OR celular LIKE ?
               OR direccion LIKE ?
            ORDER BY nombre COLLATE NOCASE
            LIMIT 100
        """, (like, like, like, like)).fetchall()

    def get_client(self, client_id):
        return self.conn.execute(
            "SELECT * FROM clientes WHERE id = ?", (client_id,)
        ).fetchone()

    def save_or_update_client(self, data):
        now = datetime.now().isoformat(timespec="seconds")
        client_id = data.get("id")

        if client_id:
            self.conn.execute("""
                UPDATE clientes
                SET nombre=?, direccion=?, telefono=?, celular=?, actualizado_en=?
                WHERE id=?
            """, (
                data["nombre"], data["direccion"], data["telefono"],
                data["celular"], now, client_id
            ))
            self.conn.commit()
            return int(client_id)

        # Reutiliza un cliente existente si coincide exactamente el nombre
        # (sin distinguir mayúsculas/minúsculas).
        row = self.conn.execute("""
            SELECT id FROM clientes
            WHERE lower(nombre) = lower(?)
            LIMIT 1
        """, (data["nombre"],)).fetchone()

        if row:
            self.conn.execute("""
                UPDATE clientes
                SET direccion=?, telefono=?, celular=?, actualizado_en=?
                WHERE id=?
            """, (
                data["direccion"], data["telefono"], data["celular"],
                now, row["id"]
            ))
            self.conn.commit()
            return int(row["id"])

        cur = self.conn.execute("""
            INSERT INTO clientes
            (nombre, direccion, telefono, celular, creado_en, actualizado_en)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            data["nombre"], data["direccion"], data["telefono"],
            data["celular"], now, now
        ))
        self.conn.commit()
        return cur.lastrowid

    def save_order(self, data):
        now = datetime.now().isoformat(timespec="seconds")
        client_id = self.save_or_update_client({
            "id": data.get("cliente_id"),
            "nombre": data["cliente"],
            "direccion": data["direccion"],
            "telefono": data["telefono"],
            "celular": data["celular"],
        })

        folio = data.get("folio") or self.next_folio()

        self.conn.execute("""
            INSERT INTO ordenes (
                folio, cliente_id, fecha_entrada,
                cotizacion, garantia, reparacion,
                equipo, marca, modelo, serie,
                rayado, golpeado, roto, sin_accesorios,
                falla, reporte_reparacion, presupuesto,
                fecha_reparacion, deja_equipo, recibe_equipo, creado_en
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            folio, client_id, data["fecha_entrada"],
            int(data["cotizacion"]), int(data["garantia"]), int(data["reparacion"]),
            data["equipo"], data["marca"], data["modelo"], data["serie"],
            int(data["rayado"]), int(data["golpeado"]), int(data["roto"]),
            int(data["sin_accesorios"]),
            data["falla"], data["reporte_reparacion"], data["presupuesto"],
            data["fecha_reparacion"], data["deja_equipo"], data["recibe_equipo"],
            now
        ))
        self.conn.commit()
        return folio

    def close(self):
        self.conn.close()


class OrdenServicioApp:
    def __init__(self, root):
        self.root = root
        self.root.title(APP_TITLE)
        self.root.geometry("780x920")
        self.root.resizable(False, False)

        self.db = Database()
        self.current_client_id = None
        self.current_folio = self.db.next_folio()

        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

        style = ttk.Style()
        style.theme_use("clam")

        main_frame = ttk.Frame(root, padding="15")
        main_frame.pack(fill=tk.BOTH, expand=True)

        title_label = ttk.Label(
            main_frame, text="electroni K",
            font=("Helvetica", 36, "bold"), foreground="#1a365d"
        )
        title_label.pack(anchor="center", pady=(5, 2))

        subtitle_label = ttk.Label(
            main_frame,
            text="ORDEN DE REPARACIÓN E INSTALACIÓN DE EQUIPOS ELECTRÓNICOS",
            font=("Helvetica", 10, "bold")
        )
        subtitle_label.pack(anchor="center")

        info_label = ttk.Label(
            main_frame,
            text="Calle 37 x 24 Fracc. Montalbán | Tel: 9-48-96-01 | Cel: 9992 32 12 72",
            font=("Helvetica", 9)
        )
        info_label.pack(anchor="center", pady=(2, 8))

        ttk.Separator(main_frame, orient="horizontal").pack(fill="x", pady=5)

        # Folio + fecha + tipo de servicio
        frame_top = ttk.Frame(main_frame)
        frame_top.pack(fill="x", pady=5)

        ttk.Label(frame_top, text="Folio:", font=("Helvetica", 10, "bold")).grid(
            row=0, column=0, sticky="w", padx=5
        )
        self.lbl_folio = ttk.Label(
            frame_top, text=self.format_folio(self.current_folio),
            font=("Helvetica", 10, "bold"), foreground="#1a365d"
        )
        self.lbl_folio.grid(row=0, column=1, sticky="w", padx=(0, 15))

        ttk.Label(frame_top, text="Fecha de entrada:").grid(
            row=0, column=2, sticky="w", padx=5
        )
        self.entry_fecha_entrada = ttk.Entry(frame_top, width=12)
        self.entry_fecha_entrada.insert(0, datetime.now().strftime("%d/%m/%Y"))
        self.entry_fecha_entrada.grid(row=0, column=3, sticky="w", padx=5)

        self.var_cotizacion = tk.BooleanVar()
        self.var_garantia = tk.BooleanVar()
        self.var_reparacion = tk.BooleanVar()

        ttk.Checkbutton(frame_top, text="Cotización", variable=self.var_cotizacion).grid(
            row=0, column=4, padx=6
        )
        ttk.Checkbutton(frame_top, text="Garantía", variable=self.var_garantia).grid(
            row=0, column=5, padx=6
        )
        ttk.Checkbutton(frame_top, text="Reparación", variable=self.var_reparacion).grid(
            row=0, column=6, padx=6
        )

        # Datos del Cliente
        frame_cliente = ttk.LabelFrame(main_frame, text=" Datos del Cliente ", padding="10")
        frame_cliente.pack(fill="x", pady=5)

        ttk.Label(frame_cliente, text="Nombre del cliente:").grid(
            row=0, column=0, sticky="w", pady=2
        )
        self.entry_cliente = ttk.Entry(frame_cliente, width=48)
        self.entry_cliente.grid(row=0, column=1, columnspan=2, sticky="w", pady=2)

        self.btn_buscar_cliente = ttk.Button(
            frame_cliente, text="Buscar cliente", command=self.buscar_cliente
        )
        self.btn_buscar_cliente.grid(row=0, column=3, padx=(8, 0), pady=2)

        self.lbl_cliente_estado = ttk.Label(
            frame_cliente, text="Nuevo cliente", font=("Helvetica", 8, "italic")
        )
        self.lbl_cliente_estado.grid(row=0, column=4, padx=8, sticky="w")

        ttk.Label(frame_cliente, text="Dirección:").grid(
            row=1, column=0, sticky="w", pady=2
        )
        self.entry_direccion = ttk.Entry(frame_cliente, width=58)
        self.entry_direccion.grid(row=1, column=1, columnspan=4, sticky="w", pady=2)

        ttk.Label(frame_cliente, text="Teléfono:").grid(
            row=2, column=0, sticky="w", pady=2
        )
        self.entry_telefono = ttk.Entry(frame_cliente, width=22)
        self.entry_telefono.grid(row=2, column=1, sticky="w", pady=2)

        ttk.Label(frame_cliente, text="Celular:").grid(
            row=2, column=2, sticky="w", pady=2
        )
        self.entry_celular = ttk.Entry(frame_cliente, width=22)
        self.entry_celular.grid(row=2, column=3, sticky="w", pady=2)

        # Datos del Equipo
        frame_equipo = ttk.LabelFrame(main_frame, text=" Datos del Equipo ", padding="10")
        frame_equipo.pack(fill="x", pady=5)

        ttk.Label(frame_equipo, text="Equipo:").grid(row=0, column=0, sticky="w", pady=2)
        self.entry_equipo = ttk.Entry(frame_equipo, width=22)
        self.entry_equipo.grid(row=0, column=1, sticky="w", pady=2)

        ttk.Label(frame_equipo, text="Marca:").grid(row=0, column=2, sticky="w", pady=2)
        self.entry_marca = ttk.Entry(frame_equipo, width=22)
        self.entry_marca.grid(row=0, column=3, sticky="w", pady=2)

        ttk.Label(frame_equipo, text="Modelo:").grid(row=1, column=0, sticky="w", pady=2)
        self.entry_modelo = ttk.Entry(frame_equipo, width=22)
        self.entry_modelo.grid(row=1, column=1, sticky="w", pady=2)

        ttk.Label(frame_equipo, text="Serie:").grid(row=1, column=2, sticky="w", pady=2)
        self.entry_serie = ttk.Entry(frame_equipo, width=22)
        self.entry_serie.grid(row=1, column=3, sticky="w", pady=2)

        ttk.Label(frame_equipo, text="Observaciones:").grid(
            row=2, column=0, sticky="nw", pady=5
        )

        obs_frame = ttk.Frame(frame_equipo)
        obs_frame.grid(row=2, column=1, columnspan=3, sticky="w", pady=5)

        self.var_rayado = tk.BooleanVar()
        self.var_golpeado = tk.BooleanVar()
        self.var_roto = tk.BooleanVar()
        self.var_sin_accesorios = tk.BooleanVar()

        ttk.Checkbutton(obs_frame, text="Equipo rayado", variable=self.var_rayado).grid(
            row=0, column=0, sticky="w", padx=5
        )
        ttk.Checkbutton(obs_frame, text="Equipo golpeado", variable=self.var_golpeado).grid(
            row=0, column=1, sticky="w", padx=5
        )
        ttk.Checkbutton(obs_frame, text="Equipo roto", variable=self.var_roto).grid(
            row=1, column=0, sticky="w", padx=5
        )
        ttk.Checkbutton(obs_frame, text="Sin accesorios", variable=self.var_sin_accesorios).grid(
            row=1, column=1, sticky="w", padx=5
        )

        # Reportes
        frame_diagnostico = ttk.LabelFrame(
            main_frame, text=" Reportes de Servicio ", padding="10"
        )
        frame_diagnostico.pack(fill="x", pady=5)

        ttk.Label(frame_diagnostico, text="Falla reportada:").pack(anchor="w")
        self.txt_falla = tk.Text(frame_diagnostico, height=2, width=80)
        self.txt_falla.pack(fill="x", pady=(0, 5))

        ttk.Label(frame_diagnostico, text="Reporte de reparación:").pack(anchor="w")
        self.txt_reparacion = tk.Text(frame_diagnostico, height=2, width=80)
        self.txt_reparacion.pack(fill="x", pady=(0, 5))

        # Presupuesto y condiciones
        frame_costo = ttk.Frame(main_frame)
        frame_costo.pack(fill="x", pady=5)

        ttk.Label(
            frame_costo, text="Presupuesto $:",
            font=("Helvetica", 10, "bold")
        ).pack(side="left", padx=5)

        self.entry_presupuesto = ttk.Entry(
            frame_costo, width=15, font=("Helvetica", 10, "bold")
        )
        self.entry_presupuesto.pack(side="left", padx=5)

        ttk.Label(frame_costo, text="Fecha de reparación:").pack(
            side="left", padx=(20, 5)
        )
        self.entry_fecha_reparacion = ttk.Entry(frame_costo, width=15)
        self.entry_fecha_reparacion.pack(side="left", padx=5)

        terminos_text = (
            "Acepto presupuesto y condiciones de almacenamiento:\n"
            "Una vez aceptado el presupuesto, después de 05 días naturales desde la fecha de reparación "
            "tendrá un costo de almacenamiento de $ 50 pesos diarios, después de los 30 días se desechará el equipo."
        )
        lbl_terminos = ttk.Label(
            main_frame, text=terminos_text, font=("Helvetica", 7, "italic"),
            justify="center", foreground="#555"
        )
        lbl_terminos.pack(fill="x", pady=5)

        # Firmas
        frame_firmas = ttk.Frame(main_frame)
        frame_firmas.pack(fill="x", pady=5)

        ttk.Label(frame_firmas, text="Deja equipo:").grid(
            row=0, column=0, sticky="w", padx=5
        )
        self.entry_deja = ttk.Entry(frame_firmas, width=28)
        self.entry_deja.grid(row=0, column=1, sticky="w", padx=5)

        ttk.Label(frame_firmas, text="Recibe equipo:").grid(
            row=0, column=2, sticky="w", padx=5
        )
        self.entry_recibe = ttk.Entry(frame_firmas, width=28)
        self.entry_recibe.grid(row=0, column=3, sticky="w", padx=5)

        # Botones
        frame_botones = ttk.Frame(main_frame)
        frame_botones.pack(fill="x", pady=10)

        ttk.Button(
            frame_botones, text="Imprimir en PDF", command=self.generar_pdf
        ).pack(side="right", padx=5)

        ttk.Button(
            frame_botones, text="Guardar Orden", command=self.guardar_orden
        ).pack(side="right", padx=5)

        ttk.Button(
            frame_botones, text="Limpiar Formulario", command=self.limpiar_formulario
        ).pack(side="right", padx=5)

        ttk.Button(
            frame_botones, text="Buscar cliente", command=self.buscar_cliente
        ).pack(side="left", padx=5)

    @staticmethod
    def format_folio(folio):
        return f"{int(folio):06d}"

    def _client_data(self):
        return {
            "id": self.current_client_id,
            "nombre": self.entry_cliente.get().strip(),
            "direccion": self.entry_direccion.get().strip(),
            "telefono": self.entry_telefono.get().strip(),
            "celular": self.entry_celular.get().strip(),
        }

    def _order_data(self):
        return {
            "folio": self.current_folio,
            **self._client_data(),
            "fecha_entrada": self.entry_fecha_entrada.get().strip(),
            "cotizacion": self.var_cotizacion.get(),
            "garantia": self.var_garantia.get(),
            "reparacion": self.var_reparacion.get(),
            "equipo": self.entry_equipo.get().strip(),
            "marca": self.entry_marca.get().strip(),
            "modelo": self.entry_modelo.get().strip(),
            "serie": self.entry_serie.get().strip(),
            "rayado": self.var_rayado.get(),
            "golpeado": self.var_golpeado.get(),
            "roto": self.var_roto.get(),
            "sin_accesorios": self.var_sin_accesorios.get(),
            "falla": self.txt_falla.get("1.0", tk.END).strip(),
            "reporte_reparacion": self.txt_reparacion.get("1.0", tk.END).strip(),
            "presupuesto": self.entry_presupuesto.get().strip(),
            "fecha_reparacion": self.entry_fecha_reparacion.get().strip(),
            "deja_equipo": self.entry_deja.get().strip(),
            "recibe_equipo": self.entry_recibe.get().strip(),
        }

    def buscar_cliente(self):
        dialog = tk.Toplevel(self.root)
        dialog.title("Buscar cliente")
        dialog.geometry("700x430")
        dialog.transient(self.root)
        dialog.grab_set()

        ttk.Label(
            dialog, text="Buscar por nombre, teléfono, celular o dirección:"
        ).pack(anchor="w", padx=12, pady=(12, 4))

        search_frame = ttk.Frame(dialog)
        search_frame.pack(fill="x", padx=12)

        search_var = tk.StringVar()
        entry_busqueda = ttk.Entry(search_frame, textvariable=search_var)
        entry_busqueda.pack(side="left", fill="x", expand=True)

        columns = ("id", "nombre", "telefono", "celular", "direccion")
        tree = ttk.Treeview(dialog, columns=columns, show="headings", height=13)
        tree.pack(fill="both", expand=True, padx=12, pady=10)

        tree.heading("id", text="ID")
        tree.heading("nombre", text="Nombre")
        tree.heading("telefono", text="Teléfono")
        tree.heading("celular", text="Celular")
        tree.heading("direccion", text="Dirección")

        tree.column("id", width=45, anchor="center")
        tree.column("nombre", width=190)
        tree.column("telefono", width=100)
        tree.column("celular", width=100)
        tree.column("direccion", width=220)

        def refresh(*_):
            for item in tree.get_children():
                tree.delete(item)

            rows = self.db.find_clients(search_var.get())
            for row in rows:
                tree.insert(
                    "", "end",
                    iid=str(row["id"]),
                    values=(
                        row["id"], row["nombre"], row["telefono"],
                        row["celular"], row["direccion"]
                    )
                )

        def select_client(_event=None):
            selection = tree.selection()
            if not selection:
                return
            client_id = int(selection[0])
            row = self.db.get_client(client_id)
            if not row:
                return

            self.current_client_id = client_id
            self.entry_cliente.delete(0, tk.END)
            self.entry_cliente.insert(0, row["nombre"] or "")
            self.entry_direccion.delete(0, tk.END)
            self.entry_direccion.insert(0, row["direccion"] or "")
            self.entry_telefono.delete(0, tk.END)
            self.entry_telefono.insert(0, row["telefono"] or "")
            self.entry_celular.delete(0, tk.END)
            self.entry_celular.insert(0, row["celular"] or "")
            self.lbl_cliente_estado.config(text=f"Cliente ID: {client_id}")
            dialog.destroy()

        ttk.Button(
            search_frame, text="Buscar", command=refresh
        ).pack(side="left", padx=(8, 0))

        ttk.Button(
            dialog, text="Seleccionar cliente", command=select_client
        ).pack(side="right", padx=12, pady=(0, 12))

        entry_busqueda.bind("<Return>", refresh)
        tree.bind("<Double-1>", select_client)
        refresh()
        entry_busqueda.focus_set()

    def validar(self):
        cliente = self.entry_cliente.get().strip()
        equipo = self.entry_equipo.get().strip()

        if not cliente or not equipo:
            messagebox.showwarning(
                "Campos incompletos",
                "Complete al menos el Nombre del Cliente y el Equipo."
            )
            return False

        presupuesto = self.entry_presupuesto.get().strip()
        if presupuesto:
            try:
                float(presupuesto.replace(",", ""))
            except ValueError:
                messagebox.showwarning(
                    "Presupuesto inválido",
                    "El presupuesto debe ser una cantidad numérica."
                )
                return False

        return True

    def guardar_orden(self):
        if not self.validar():
            return

        try:
            # El folio se consume al guardar. Antes de guardar es solamente
            # una vista previa del próximo folio.
            folio = self.db.save_order(self._order_data())
            self.current_folio = self.db.next_folio()
            self.lbl_folio.config(text=self.format_folio(self.current_folio))

            messagebox.showinfo(
                "Orden guardada",
                f"La orden {self.format_folio(folio)} se guardó correctamente.\n\n"
                f"Cliente: {self.entry_cliente.get().strip()}"
            )
            self.limpiar_formulario(confirm=False)
        except Exception as e:
            messagebox.showerror("Error al guardar", f"No se pudo guardar la orden:\n{e}")

    def generar_pdf(self):
        if not self.validar():
            return

        if not REPORTLAB_AVAILABLE:
            messagebox.showerror(
                "Librería faltante",
                "ReportLab no está instalado en el sistema."
            )
            return

        data = self._order_data()
        pdf_path = os.path.join(
            tempfile.gettempdir(),
            f"orden_{self.format_folio(self.current_folio)}_"
            f"{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        )

        c = canvas.Canvas(pdf_path, pagesize=letter)
        width, height = letter
        y = height - 50

        c.setFont("Helvetica-Bold", 28)
        c.drawCentredString(width / 2, y, "electroni K")

        c.setFont("Helvetica-Bold", 10)
        c.drawCentredString(
            width / 2, y - 18,
            "ORDEN REPARACIÓN E INSTALACIÓN DE EQUIPOS ELECTRÓNICOS"
        )

        c.setFont("Helvetica-Bold", 10)
        c.drawString(width - 130, y, f"FOLIO: {self.format_folio(self.current_folio)}")

        c.setFont("Helvetica", 9)
        c.drawCentredString(
            width / 2, y - 32,
            "Calle 37 x 24 Fracc. Montalbán Tel. 9-48-96-01 Cel. 9992 32 12 72"
        )

        c.line(40, y - 40, width - 40, y - 40)
        y -= 60

        c.setFont("Helvetica-Bold", 9)
        c.drawString(40, y, "Fecha de entrada:")
        c.setFont("Helvetica", 9)
        c.drawString(125, y, data["fecha_entrada"])

        x_check = 280
        for label, val in [
            ("Cotización", data["cotizacion"]),
            ("Garantía", data["garantia"]),
            ("Reparación", data["reparacion"])
        ]:
            c.rect(x_check, y - 2, 10, 10)
            if val:
                c.setFont("Helvetica-Bold", 10)
                c.drawString(x_check + 2, y, "X")
            c.setFont("Helvetica", 9)
            c.drawString(x_check + 15, y, label)
            x_check += 95

        y -= 25

        campos_cliente = [
            ("Nombre del cliente:", data["cliente"]),
            ("Dirección:", data["direccion"]),
            ("Teléfono:", data["telefono"]),
        ]

        for lab, val in campos_cliente:
            c.setFont("Helvetica-Bold", 9)
            c.drawString(40, y, lab)
            c.setFont("Helvetica", 9)
            c.drawString(135, y, val[:85])
            c.line(130, y - 2, width - 40, y - 2)

            if lab == "Teléfono:":
                c.setFont("Helvetica-Bold", 9)
                c.drawString(320, y, "Celular:")
                c.setFont("Helvetica", 9)
                c.drawString(370, y, data["celular"][:28])

            y -= 20

        y -= 5
        campos_equipo = [
            [("Equipo:", data["equipo"]), ("Marca:", data["marca"])],
            [("Modelo:", data["modelo"]), ("Serie:", data["serie"])]
        ]

        for fila in campos_equipo:
            c.setFont("Helvetica-Bold", 9)
            c.drawString(40, y, fila[0][0])
            c.setFont("Helvetica", 9)
            c.drawString(95, y, fila[0][1][:28])
            c.line(90, y - 2, 280, y - 2)

            c.setFont("Helvetica-Bold", 9)
            c.drawString(310, y, fila[1][0])
            c.setFont("Helvetica", 9)
            c.drawString(360, y, fila[1][1][:28])
            c.line(355, y - 2, width - 40, y - 2)
            y -= 20

        c.setFont("Helvetica-Bold", 9)
        c.drawString(40, y, "Observaciones:")

        obs_items = [
            ("Equipo rayado", data["rayado"]),
            ("Equipo golpeado", data["golpeado"]),
            ("Equipo roto", data["roto"]),
            ("Sin accesorios", data["sin_accesorios"])
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

        # Función sencilla para texto multilínea en el PDF.
        def draw_wrapped(title, text_value, current_y, max_width=525):
            c.setFont("Helvetica-Bold", 9)
            c.drawString(40, current_y, title)
            style = getSampleStyleSheet()["Normal"]
            style.fontName = "Helvetica"
            style.fontSize = 9
            style.leading = 11
            style.alignment = TA_LEFT
            p = Paragraph(text_value.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("\n", "<br/>"), style)
            w, h = p.wrap(max_width, 55)
            p.drawOn(c, 40, current_y - 18 - h)
            c.line(40, current_y - 23 - h, width - 40, current_y - 23 - h)
            return current_y - 35 - h

        y = draw_wrapped("Falla reportada:", data["falla"], y)
        y = draw_wrapped("Reporte de reparación:", data["reporte_reparacion"], y)

        c.setFont("Helvetica-Bold", 10)
        c.drawString(40, y, "Presupuesto $")
        c.setFont("Helvetica", 10)
        c.drawString(120, y, data["presupuesto"])
        c.line(115, y - 2, 250, y - 2)

        y -= 30
        c.setFont("Helvetica-Bold", 8)
        c.drawString(40, y, "Acepto presupuesto y condiciones de almacenamiento")
        y -= 12
        c.setFont("Helvetica", 7.5)
        c.drawString(
            40, y,
            "Una vez aceptado el presupuesto, después de 05 días naturales desde la fecha de reparación tendrá"
        )
        y -= 10
        c.drawString(
            40, y,
            "un costo de almacenamiento de $ 50 pesos diarios, después de los 30 días se desechará el equipo."
        )
        y -= 10
        c.setFont("Helvetica-Bold", 8)
        c.drawString(40, y, "Si está de acuerdo firme la orden.")

        y -= 45
        c.line(40, y, 220, y)
        c.setFont("Helvetica-Bold", 8)
        c.drawCentredString(130, y - 10, f"Deja equipo: {data['deja_equipo'][:25]}")

        c.line(260, y, 420, y)
        c.drawCentredString(340, y - 10, f"Recibe equipo: {data['recibe_equipo'][:25]}")

        c.setFont("Helvetica-Bold", 8)
        c.drawString(440, y + 10, "Fecha de reparación")
        c.setFont("Helvetica", 8)
        c.drawString(440, y - 10, data["fecha_reparacion"])
        c.line(435, y - 12, width - 40, y - 12)

        c.save()

        try:
            if sys.platform == "win32":
                os.startfile(pdf_path)
            elif sys.platform == "darwin":
                import subprocess
                subprocess.Popen(["open", pdf_path])
            else:
                import subprocess
                subprocess.Popen(["xdg-open", pdf_path])

            messagebox.showinfo(
                "PDF generado",
                f"Se generó la orden {self.format_folio(self.current_folio)}:\n{pdf_path}"
            )
        except Exception as e:
            messagebox.showwarning(
                "PDF generado",
                f"PDF guardado en:\n{pdf_path}\n\n"
                f"No se pudo abrir automáticamente: {e}"
            )

    def limpiar_formulario(self, confirm=True):
        if confirm:
            # No se confirma para hacer más rápido el flujo de captura.
            pass

        for entry in [
            self.entry_cliente, self.entry_direccion, self.entry_telefono,
            self.entry_celular, self.entry_equipo, self.entry_marca,
            self.entry_modelo, self.entry_serie, self.entry_presupuesto,
            self.entry_fecha_reparacion, self.entry_deja, self.entry_recibe
        ]:
            entry.delete(0, tk.END)

        self.txt_falla.delete("1.0", tk.END)
        self.txt_reparacion.delete("1.0", tk.END)

        self.var_cotizacion.set(False)
        self.var_garantia.set(False)
        self.var_reparacion.set(False)
        self.var_rayado.set(False)
        self.var_golpeado.set(False)
        self.var_roto.set(False)
        self.var_sin_accesorios.set(False)

        self.current_client_id = None
        self.current_folio = self.db.next_folio()
        self.lbl_folio.config(text=self.format_folio(self.current_folio))
        self.lbl_cliente_estado.config(text="Nuevo cliente")
        self.entry_fecha_entrada.delete(0, tk.END)
        self.entry_fecha_entrada.insert(0, datetime.now().strftime("%d/%m/%Y"))

    def on_close(self):
        self.db.close()
        self.root.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    app = OrdenServicioApp(root)
    root.mainloop()
