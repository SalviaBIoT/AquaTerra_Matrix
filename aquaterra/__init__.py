"""AquaTerra Matrix — Software Matriz de Administración Ecológica, Agrícola y Bio-IoT.

Ecosistema TerraBit (Nodo INTI, InBeersa, Sigatoka, Conservación Polylepis).
Autor y arquitecto: Daniel Felipe Duque Lizarralde.

Arquitectura por capas (dependencias apuntan siempre hacia adentro):

    ui  ──►  application  ──►  core
                 │
                 ▼
          infrastructure  ──►  core

- ``core``           : dominio puro (entidades, validadores, ciencia agronómica). Sin I/O.
- ``application``    : casos de uso / servicios (orquestan core + infraestructura).
- ``infrastructure`` : SQLite, seguridad, migración legacy, ingesta IoT.
- ``api``            : servidor FastAPI local 1:1 sobre ``application`` + frontend web.
- ``desktop``        : lanzador nativo PyWebView (Edge WebView2) y modo ``--web``.
- ``ui``             : respaldo legacy ttkbootstrap (``--legacy-ui``).
"""

__version__ = "6.0.0"
__autor__ = "Daniel Felipe Duque Lizarralde"
