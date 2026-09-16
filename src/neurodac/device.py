"""Selección de dispositivo de cómputo con diagnóstico explícito."""

from __future__ import annotations

import warnings
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import torch


def get_device(require_cuda: bool = False) -> torch.device:
    """Devuelve el dispositivo de cómputo y reporta por qué.

    Parameters
    ----------
    require_cuda : bool, default=False
        Si True, lanza RuntimeError cuando CUDA no está disponible. Úsalo en
        scripts de entrenamiento; déjalo en False para depuración y CI.

    Returns
    -------
    torch.device
        "cuda" si hay GPU disponible, "cpu" en caso contrario.

    Raises
    ------
    RuntimeError
        Si `require_cuda=True` y no hay GPU accesible.

    Notes
    -----
    El modo de falla más común no es la ausencia de GPU sino una rueda de torch
    compilada solo para CPU: `torch.version.cuda` devuelve None y todo corre
    lento sin error visible. Por eso se reporta explícitamente.
    """
    import torch

    if torch.cuda.is_available():
        print(f"GPU activa: {torch.cuda.get_device_name(0)} | CUDA {torch.version.cuda}")
        return torch.device("cuda")

    build = torch.version.cuda
    motivo = (
        "la instalación de torch no incluye soporte CUDA (rueda CPU-only)"
        if build is None
        else f"torch se compiló contra CUDA {build} pero no detecta una GPU accesible"
    )
    mensaje = f"CUDA no disponible: {motivo}."

    if require_cuda:
        raise RuntimeError(mensaje)

    warnings.warn(f"{mensaje} Continuando en CPU.", RuntimeWarning, stacklevel=2)
    return torch.device("cpu")
