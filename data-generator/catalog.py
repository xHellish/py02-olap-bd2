"""
Catálogo del dominio — basado en el seed del PY01 y extendido con geo.
Zonas de Ciudad de Guatemala con coordenadas reales.
"""

ZONES = {
    "zona_1":  {"name": "Zona 1",  "lat": 14.6407, "lon": -90.5133},
    "zona_4":  {"name": "Zona 4",  "lat": 14.6257, "lon": -90.5218},
    "zona_9":  {"name": "Zona 9",  "lat": 14.6032, "lon": -90.5172},
    "zona_10": {"name": "Zona 10", "lat": 14.5994, "lon": -90.5069},
    "zona_11": {"name": "Zona 11", "lat": 14.6050, "lon": -90.5333},
    "zona_13": {"name": "Zona 13", "lat": 14.5775, "lon": -90.5283},
    "antigua": {"name": "Antigua", "lat": 14.5586, "lon": -90.7295},
}

CATEGORIES = [
    {"name": "Entradas",      "description": "Aperitivos y bocas para compartir",            "icon": "🥗"},
    {"name": "Platos Fuertes","description": "Platos principales de la casa",                 "icon": "🍖"},
    {"name": "Pastas",        "description": "Pastas artesanales con salsas caseras",         "icon": "🍝"},
    {"name": "Mariscos",      "description": "Pescados y mariscos frescos del Pacífico",      "icon": "🦐"},
    {"name": "Postres",       "description": "Dulces y postres artesanales",                  "icon": "🍰"},
    {"name": "Bebidas",       "description": "Refrescos naturales, cócteles y café",          "icon": "🥤"},
    {"name": "Pizzas",        "description": "Pizzas al horno de leña con ingredientes premium","icon": "🍕"},
    {"name": "Ensaladas",     "description": "Ensaladas frescas y nutritivas",                "icon": "🥬"},
]

# cat_idx coincide con el índice en CATEGORIES (0-based)
PRODUCTS = [
    # Entradas (cat 0)
    {"name": "Guacamole Artesanal",        "price": 45.00, "cat_idx": 0, "available": True,
     "description": "Aguacate Hass fresco con tomate, cilantro, chile serrano y limón. Servido con totopos de maíz criollo."},
    {"name": "Ceviche de Camarón",         "price": 65.00, "cat_idx": 0, "available": True,
     "description": "Camarones del Pacífico marinados en limón con cebolla morada, tomate, cilantro y salsa de habanero."},
    {"name": "Empanadas de Loroco",        "price": 35.00, "cat_idx": 0, "available": True,
     "description": "Empanadas crujientes rellenas de loroco y queso Zacapa. Acompañadas de salsa de tomate asado."},
    {"name": "Nachos Supremos",            "price": 55.00, "cat_idx": 0, "available": True,
     "description": "Totopos artesanales cubiertos con frijoles volteados, guacamole, crema, jalapeños y queso fundido."},
    # Platos Fuertes (cat 1)
    {"name": "Pepián de Pollo",            "price": 85.00, "cat_idx": 1, "available": True,
     "description": "Recado tradicional de pepitoria, chile pasa y tomate. Pollo de granja cocido lentamente con papas y güisquil."},
    {"name": "Hilachas en Salsa Roja",     "price": 75.00, "cat_idx": 1, "available": True,
     "description": "Carne de res deshebrada en salsa de tomate y chile guaque. Acompañada de arroz y tamalitos de chipilín."},
    {"name": "Churrasco Angus",            "price": 145.00,"cat_idx": 1, "available": True,
     "description": "Corte prime de res Angus a la parrilla, término a elección. Con chimichurri argentino, papas rústicas y ensalada."},
    {"name": "Pollo en Jocón",             "price": 78.00, "cat_idx": 1, "available": True,
     "description": "Pollo de granja en salsa verde de miltomate, cilantro y pepitoria. Servido con arroz y tortillas recién hechas."},
    {"name": "Lomo Saltado",               "price": 95.00, "cat_idx": 1, "available": True,
     "description": "Lomo fino salteado al wok con cebolla, tomate, ají amarillo y sillao. Acompañado de arroz y papas fritas."},
    # Pastas (cat 2)
    {"name": "Fettuccine Alfredo",         "price": 82.00, "cat_idx": 2, "available": True,
     "description": "Pasta fresca al huevo con salsa cremosa de parmesano reggiano y pollo a la plancha."},
    {"name": "Spaghetti alla Puttanesca",  "price": 72.00, "cat_idx": 2, "available": True,
     "description": "Spaghetti con salsa de tomate San Marzano, aceitunas negras, alcaparras, anchoas y ajo."},
    {"name": "Ravioli de Ricotta",         "price": 88.00, "cat_idx": 2, "available": True,
     "description": "Ravioli artesanal relleno de ricotta fresca y espinaca, bañado en salsa de mantequilla y salvia."},
    {"name": "Penne al Pesto Genovese",    "price": 70.00, "cat_idx": 2, "available": True,
     "description": "Penne con pesto de albahaca genovesa, parmesano y piñones tostados."},
    # Mariscos (cat 3)
    {"name": "Robalo a la Parrilla",       "price": 125.00,"cat_idx": 3, "available": True,
     "description": "Filete de robalo del Pacífico a la parrilla con mantequilla de hierbas, puré de camote y vegetales asados."},
    {"name": "Camarones al Ajillo",        "price": 110.00,"cat_idx": 3, "available": True,
     "description": "Camarones jumbo salteados en aceite de oliva con abundante ajo dorado, chile guajillo y perejil fresco."},
    {"name": "Paella Valenciana",          "price": 165.00,"cat_idx": 3, "available": False,
     "description": "Arroz bomba con azafrán, mariscos mixtos, chorizo español y guisantes."},
    {"name": "Pulpo a la Gallega",         "price": 135.00,"cat_idx": 3, "available": True,
     "description": "Pulpo cocido al vapor con pimentón ahumado, aceite de oliva y patatas."},
    # Postres (cat 4)
    {"name": "Tres Leches Artesanal",      "price": 42.00, "cat_idx": 4, "available": True,
     "description": "Bizcocho esponjoso bañado en leche condensada, evaporada y crema. Coronado con merengue italiano."},
    {"name": "Churros con Chocolate",      "price": 38.00, "cat_idx": 4, "available": True,
     "description": "Churros crujientes espolvoreados con azúcar y canela. Acompañados de chocolate caliente para dipping."},
    {"name": "Flan de Coco",               "price": 45.00, "cat_idx": 4, "available": True,
     "description": "Flan de coco rallado con caramelo de piloncillo y un toque de ron guatemalteco Zacapa."},
    {"name": "Tiramisú Clásico",           "price": 52.00, "cat_idx": 4, "available": True,
     "description": "Capas de bizcocho de café espresso, mascarpone italiano y cacao amargo. Receta original de Venecia."},
    # Bebidas (cat 5)
    {"name": "Limonada de Hierbabuena",    "price": 22.00, "cat_idx": 5, "available": True,
     "description": "Limonada natural con hojas frescas de hierbabuena y un toque de jengibre. Servida con hielo."},
    {"name": "Café Huehuetenango",         "price": 28.00, "cat_idx": 5, "available": True,
     "description": "Café de altura 100% arábica de Huehuetenango. Tostado medio, notas de chocolate y frutos rojos."},
    {"name": "Horchata de Morro",          "price": 25.00, "cat_idx": 5, "available": True,
     "description": "Bebida tradicional de semilla de morro, cacao, canela y ajonjolí. Servida bien fría."},
    {"name": "Mojito Clásico",             "price": 55.00, "cat_idx": 5, "available": True,
     "description": "Ron blanco, menta fresca, jugo de limón, azúcar y soda. Presentación clásica habanera."},
    # Pizzas (cat 6)
    {"name": "Pizza Margherita DOP",       "price": 95.00, "cat_idx": 6, "available": True,
     "description": "Base de masa madre, salsa San Marzano DOP, mozzarella di bufala, albahaca fresca y aceite de oliva extra virgen."},
    {"name": "Pizza Quattro Formaggi",     "price": 105.00,"cat_idx": 6, "available": True,
     "description": "Cuatro quesos: mozzarella, gorgonzola, fontina y parmesano reggiano sobre base blanca de crema."},
    {"name": "Pizza Prosciutto e Funghi",  "price": 110.00,"cat_idx": 6, "available": True,
     "description": "Jamón prosciutto crudo di Parma, hongos porcini, mozzarella fior di latte y rúcula fresca."},
    {"name": "Pizza Diavola",              "price": 98.00, "cat_idx": 6, "available": True,
     "description": "Salami picante, chile calabrés, mozzarella y salsa de tomate. Para los amantes del picante."},
    # Ensaladas (cat 7)
    {"name": "Ensalada César",             "price": 48.00, "cat_idx": 7, "available": True,
     "description": "Lechuga romana, crutones artesanales, parmesano en lascas y aderezo César casero con anchoas."},
    {"name": "Ensalada Mediterránea",      "price": 52.00, "cat_idx": 7, "available": True,
     "description": "Mix de lechugas, tomate cherry, pepino, aceitunas kalamata, queso feta y vinagreta de orégano."},
    {"name": "Ensalada de Quinoa",         "price": 58.00, "cat_idx": 7, "available": True,
     "description": "Quinoa tricolor con aguacate, mango, pepino, cebolla morada y vinagreta de limón."},
]

RESTAURANTS = [
    {"name": "La Cocina de Doña María",
     "address": "4ta Avenida 12-30 Zona 10, Ciudad de Guatemala",
     "phone": "+502 2334-5678",
     "description": "Cocina tradicional guatemalteca con un toque moderno.",
     "rating": 4.7, "zone": "zona_10", "lat": 14.5994, "lon": -90.5069},
    {"name": "El Fogón Chapín",
     "address": "6ta Calle 3-52 Zona 1, Antigua Guatemala",
     "phone": "+502 7832-1234",
     "description": "Restaurante rústico con ambiente colonial.",
     "rating": 4.5, "zone": "antigua", "lat": 14.5586, "lon": -90.7295},
    {"name": "Mare Nostrum",
     "address": "Boulevard Los Próceres 18-29 Zona 10, Ciudad de Guatemala",
     "phone": "+502 2368-9012",
     "description": "Alta cocina mediterránea con los mejores mariscos importados.",
     "rating": 4.8, "zone": "zona_10", "lat": 14.6010, "lon": -90.5055},
    {"name": "Sakura Sushi Bar",
     "address": "13 Calle 2-75 Zona 10, Ciudad de Guatemala",
     "phone": "+502 2337-4567",
     "description": "Fusión japonesa-guatemalteca.",
     "rating": 4.3, "zone": "zona_10", "lat": 14.5980, "lon": -90.5088},
    {"name": "Pizzería Don Corleone",
     "address": "Avenida Reforma 8-60 Zona 9, Ciudad de Guatemala",
     "phone": "+502 2331-8901",
     "description": "Auténtica pizza napolitana horneada en horno de leña a 450°C.",
     "rating": 4.6, "zone": "zona_9", "lat": 14.6032, "lon": -90.5172},
]

MENUS = [
    {"name": "Menú Ejecutivo",    "description": "Almuerzo de lunes a viernes.",
     "rest_idx": 0, "product_indices": [0, 4, 21, 17]},
    {"name": "Menú Degustación",  "description": "Experiencia gastronómica de 5 tiempos.",
     "rest_idx": 2, "product_indices": [1, 13, 14, 19, 24]},
    {"name": "Menú Familiar",     "description": "Para compartir en familia.",
     "rest_idx": 1, "product_indices": [0, 3, 5, 6, 21, 23, 17, 18]},
    {"name": "Menú Italiano",     "description": "Lo mejor de nuestra cocina italiana.",
     "rest_idx": 4, "product_indices": [9, 10, 25, 19]},
    {"name": "Menú de Mariscos",  "description": "Selección especial del chef.",
     "rest_idx": 2, "product_indices": [1, 13, 14, 15]},
]

# Grupos de afinidad de co-compra (para Neo4J — top-5 productos comprados juntos)
# Cada grupo es una lista de índices de productos (0-based de PRODUCTS)
# El generador usará estos grupos para crear ítems de pedido con sesgo de co-compra.
AFFINITY_GROUPS = [
    # Snack casual: guacamole + nachos + limonada/horchata
    {"weight": 0.20, "products": [0, 3, 21, 23]},
    # Comida típica completa: plato fuerte + bebida + postre
    {"weight": 0.25, "products": [4, 5, 7, 21, 22, 17, 18]},
    # Parrilla premium: churrasco + ensalada + café
    {"weight": 0.10, "products": [6, 8, 29, 22]},
    # Pasta + postre + bebida
    {"weight": 0.15, "products": [9, 10, 11, 12, 19, 20, 21]},
    # Mariscos + mojito
    {"weight": 0.10, "products": [13, 14, 16, 24]},
    # Pizza + ensalada + bebida
    {"weight": 0.20, "products": [24, 25, 26, 27, 29, 21, 23]},
]

COURIERS = [
    {"name": "Roberto Ajú",      "vehicle": "moto",      "base_zone": "zona_10"},
    {"name": "María Coyoy",      "vehicle": "moto",      "base_zone": "zona_9"},
    {"name": "Carlos Tziná",     "vehicle": "bicicleta", "base_zone": "zona_4"},
    {"name": "Ana Coc",          "vehicle": "moto",      "base_zone": "zona_10"},
    {"name": "Luis Xicay",       "vehicle": "carro",     "base_zone": "zona_13"},
    {"name": "Sandra Ajpop",     "vehicle": "moto",      "base_zone": "zona_1"},
    {"name": "Diego Caal",       "vehicle": "moto",      "base_zone": "zona_10"},
    {"name": "Elena Pérez",      "vehicle": "bicicleta", "base_zone": "zona_11"},
    {"name": "Fernando Boc",     "vehicle": "moto",      "base_zone": "zona_9"},
    {"name": "Isabel Choc",      "vehicle": "carro",     "base_zone": "zona_13"},
    {"name": "Jorge Sacol",      "vehicle": "moto",      "base_zone": "zona_10"},
    {"name": "Lucía Tzoc",       "vehicle": "moto",      "base_zone": "zona_4"},
]
