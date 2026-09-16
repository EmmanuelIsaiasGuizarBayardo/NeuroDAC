"""Punto de entrada de NeuroDAC."""

from __future__ import annotations

from neurodac.reproducibility import get_run_context, set_seed


def main() -> None:
    """Ejecuta el pipeline principal."""
    set_seed(42)
    ctx = get_run_context(seed=42)
    print("Entorno de NeuroDAC listo.")
    print(f"commit={ctx.git_sha[:8]} dirty={ctx.git_dirty} seed={ctx.seed}")


if __name__ == "__main__":
    main()
