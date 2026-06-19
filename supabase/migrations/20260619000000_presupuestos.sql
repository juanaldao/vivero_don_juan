CREATE TABLE IF NOT EXISTS presupuestos (
    id              SERIAL PRIMARY KEY,
    nombre_cliente  TEXT NOT NULL,
    telefono_cliente TEXT,
    total           NUMERIC NOT NULL,
    pdf_url         TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- Public storage bucket for PDF quotes
INSERT INTO storage.buckets (id, name, public)
VALUES ('presupuestos', 'presupuestos', true)
ON CONFLICT (id) DO NOTHING;
