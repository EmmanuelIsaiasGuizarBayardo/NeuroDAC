"""Pruebas de humo: el paquete es importable."""

from __future__ import annotations


def test_paquete_importable() -> None:
    """El paquete debe resolverse sin manipular sys.path."""
    import neurodac

    assert neurodac.__name__ == "neurodac"
