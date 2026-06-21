-- ─────────────────────────────────────────────────────────────────────────────
--  Fuente OLTP — Restaurantes P2 (modelo extendido)
--  Incluye catálogo heredado del PY01 + pedidos, entregas y geo propios del PY02
-- ─────────────────────────────────────────────────────────────────────────────

-- Catálogo

CREATE TABLE IF NOT EXISTS categories (
    id          SERIAL PRIMARY KEY,
    name        VARCHAR(100) NOT NULL UNIQUE,
    description TEXT,
    icon        VARCHAR(10)
);

CREATE TABLE IF NOT EXISTS restaurants (
    id          SERIAL PRIMARY KEY,
    name        VARCHAR(200) NOT NULL,
    address     VARCHAR(300),
    phone       VARCHAR(30),
    description TEXT,
    rating      NUMERIC(3,1) DEFAULT 0,
    zone        VARCHAR(50),
    lat         NUMERIC(10,6),
    lon         NUMERIC(10,6),
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS products (
    id          SERIAL PRIMARY KEY,
    name        VARCHAR(200) NOT NULL,
    description TEXT,
    price       NUMERIC(10,2) NOT NULL,
    image_url   TEXT,
    available   BOOLEAN DEFAULT TRUE,
    category_id INT REFERENCES categories(id),
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS menus (
    id            SERIAL PRIMARY KEY,
    name          VARCHAR(200) NOT NULL,
    description   TEXT,
    active        BOOLEAN DEFAULT TRUE,
    restaurant_id INT REFERENCES restaurants(id),
    created_at    TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS menu_products (
    id            SERIAL PRIMARY KEY,
    menu_id       INT REFERENCES menus(id),
    product_id    INT REFERENCES products(id),
    display_order INT DEFAULT 0,
    UNIQUE (menu_id, product_id)
);

-- Usuarios (80 clientes para variedad analítica)

CREATE TABLE IF NOT EXISTS users (
    id            SERIAL PRIMARY KEY,
    name          VARCHAR(200) NOT NULL,
    email         VARCHAR(200) NOT NULL UNIQUE,
    password_hash VARCHAR(200),
    role          VARCHAR(20) DEFAULT 'customer',
    zone          VARCHAR(50),
    lat           NUMERIC(10,6),
    lon           NUMERIC(10,6),
    created_at    TIMESTAMPTZ DEFAULT NOW()
);

-- ─── Entidades nuevas del PY02 ────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS couriers (
    id         SERIAL PRIMARY KEY,
    name       VARCHAR(200) NOT NULL,
    vehicle    VARCHAR(30),   -- moto | bicicleta | carro
    base_zone  VARCHAR(50),
    base_lat   NUMERIC(10,6),
    base_lon   NUMERIC(10,6),
    active     BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS orders (
    id             SERIAL PRIMARY KEY,
    user_id        INT REFERENCES users(id),
    restaurant_id  INT REFERENCES restaurants(id),
    order_ts       TIMESTAMPTZ NOT NULL,
    status         VARCHAR(20) NOT NULL,  -- pending|confirmed|preparing|delivering|completed|cancelled
    total          NUMERIC(10,2),
    payment_method VARCHAR(30),           -- card|cash|wallet
    created_at     TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS order_items (
    id          SERIAL PRIMARY KEY,
    order_id    INT REFERENCES orders(id),
    product_id  INT REFERENCES products(id),
    quantity    INT NOT NULL DEFAULT 1,
    unit_price  NUMERIC(10,2) NOT NULL,
    line_total  NUMERIC(10,2) NOT NULL
);

CREATE TABLE IF NOT EXISTS deliveries (
    id           SERIAL PRIMARY KEY,
    order_id     INT REFERENCES orders(id) UNIQUE,
    courier_id   INT REFERENCES couriers(id),
    dest_zone    VARCHAR(50),
    dest_lat     NUMERIC(10,6),
    dest_lon     NUMERIC(10,6),
    distance_km  NUMERIC(6,2),
    eta_min      INT,
    delivered_ts TIMESTAMPTZ,
    created_at   TIMESTAMPTZ DEFAULT NOW()
);

-- Índices para acelerar las consultas OLAP y de Spark

CREATE INDEX IF NOT EXISTS idx_orders_ts           ON orders(order_ts);
CREATE INDEX IF NOT EXISTS idx_orders_status       ON orders(status);
CREATE INDEX IF NOT EXISTS idx_orders_user         ON orders(user_id);
CREATE INDEX IF NOT EXISTS idx_orders_restaurant   ON orders(restaurant_id);
CREATE INDEX IF NOT EXISTS idx_order_items_order   ON order_items(order_id);
CREATE INDEX IF NOT EXISTS idx_order_items_product ON order_items(product_id);
CREATE INDEX IF NOT EXISTS idx_deliveries_courier  ON deliveries(courier_id);
