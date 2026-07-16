-- ============================================================
--  Schema ERP de exemplo (BlueShift demo)
--  Criado automaticamente pelo container postgres:16 no boot.
-- ============================================================

-- Tabela de clientes (pessoas jurídicas do piloto Seguradora+Banco)
CREATE TABLE IF NOT EXISTS clientes (
    id_cliente   TEXT PRIMARY KEY,
    razao_social TEXT NOT NULL,
    nome_fantasia TEXT,
    cnpj         TEXT,
    segmento     TEXT,            -- varejo, corporate, agronegocio...
    uf           CHAR(2),
    score        INTEGER,         -- 0-100, saude do relacionamento
    limite_credito NUMERIC(12,2) DEFAULT 0,
    desde        DATE,
    ativo        BOOLEAN DEFAULT TRUE
);

-- Tabela de pedidos (ordens de venda / apolices)
CREATE TABLE IF NOT EXISTS pedidos (
    id_pedido    TEXT PRIMARY KEY,
    id_cliente   TEXT NOT NULL REFERENCES clientes(id_cliente),
    data_emissao DATE NOT NULL,
    valor        NUMERIC(12,2) NOT NULL,
    status       TEXT NOT NULL,   -- emitido, pendente, cancelado, pago
    canal        TEXT,            -- web, telefone, corretor
    produto      TEXT
);

-- Tabela de oportunidades de vendas (CRM/ERP)
CREATE TABLE IF NOT EXISTS oportunidades (
    id_oportunidade SERIAL PRIMARY KEY,
    id_cliente      TEXT NOT NULL REFERENCES clientes(id_cliente),
    titulo          TEXT NOT NULL,
    valor_estimado  NUMERIC(12,2) NOT NULL,
    probabilidade   INTEGER NOT NULL DEFAULT 10,  -- %
    etapa           TEXT NOT NULL DEFAULT 'prospecção',
    criado_em       TIMESTAMP NOT NULL DEFAULT now(),
    itens           JSONB
);

-- Índices
CREATE INDEX IF NOT EXISTS idx_pedidos_cliente ON pedidos(id_cliente);
CREATE INDEX IF NOT EXISTS idx_op_cliente ON oportunidades(id_cliente);

-- ============================================================
--  Dados de demonstração
-- ============================================================

INSERT INTO clientes (id_cliente, razao_social, nome_fantasia, cnpj, segmento, uf, score, limite_credito, desde)
VALUES
    ('C001', 'Agro Sul Comercio de Insumos LTDA', 'Agro Sul', '12.345.678/0001-90', 'agronegocio', 'MT', 88, 250000.00, '2019-03-12'),
    ('C002', 'Tech Nordeste Sistemas SA', 'TechNE', '98.765.432/0001-21', 'corporate', 'CE', 74, 500000.00, '2020-07-01'),
    ('C003', 'Mercado Bom Preco ME', 'Bom Preco', '11.222.333/0001-44', 'varejo', 'SP', 61, 80000.00, '2021-11-20'),
    ('C004', 'Construtora Pampa Ltda', 'Pampa', '22.333.444/0001-55', 'corporate', 'RS', 45, 120000.00, '2022-02-15')
ON CONFLICT (id_cliente) DO NOTHING;

INSERT INTO pedidos (id_pedido, id_cliente, data_emissao, valor, status, canal, produto)
VALUES
    ('P2024-001', 'C001', '2024-01-15', 45000.00, 'pago',      'corretor', 'Apolice Agricola'),
    ('P2024-002', 'C001', '2024-03-22', 32000.00, 'emitido',   'web',      'Apolice Maquinas'),
    ('P2024-003', 'C002', '2024-02-10', 120000.00, 'pago',     'telefone', 'Seguro Cyber'),
    ('P2024-004', 'C002', '2024-05-30', 98000.00, 'pendente',  'web',      'Seguro Responsabilidade'),
    ('P2024-005', 'C003', '2024-04-05', 15000.00, 'emitido',   'web',      'Seguro Loja'),
    ('P2024-006', 'C004', '2024-06-18', 64000.00, 'cancelado', 'corretor', 'Seguro Obra')
ON CONFLICT (id_pedido) DO NOTHING;
