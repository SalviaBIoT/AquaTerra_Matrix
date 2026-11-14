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
- ``ui``             : vistas ttkbootstrap; solo hablan con ``application``.
"""

__version__ = "5.0.0"
__autor__ = "Daniel Felipe Duque Lizarralde"
