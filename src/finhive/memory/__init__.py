"""Memoria de dos niveles: sesión (thread_id) y hechos de largo plazo (MemGPT), sobre Delta/UC.

Sin imports propios acá a propósito: `finhive.memory.nodes` importa
`finhive.graph.state` (para el tipo `FinHiveState`), y `finhive.graph`
importa de vuelta `finhive.memory.nodes` desde `top_supervisor.py` — un
import eager acá (`from finhive.memory.nodes import ...`) crea un ciclo real
cuando algo entra por `finhive.memory` primero (ej.
`infra/databricks/setup_memory_tables.py`, que solo necesita `store.py` y
nunca toca `finhive.graph`). Quien necesite los nodos importa directo de
`finhive.memory.nodes`.
"""
