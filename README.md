# NeuroDAC

## Descripción

*(Objetivo del repositorio: pregunta de investigación, paradigma, dataset.)*

## Estructura

```
data/raw/          INMUTABLE. Datos crudos, idealmente en layout BIDS-EEG. No versionado.
data/processed/    Derivados: épocas, features, matrices filtradas. No versionado.
notebooks/         Exploración interactiva. No contiene lógica reutilizable.
results/           Figuras y métricas. No versionado.
src/neurodac/    Código fuente. Paquete instalable.
tests/             Pruebas.
```

## Entorno

Python 3.12, gestionado con [uv](https://docs.astral.sh/uv/).

**Replicación (recomendada, exacta):**

```powershell
uv sync --extra gpu
```

Esto crea `.venv`, instala desde `uv.lock` e instala el paquete en modo editable.

**Replicación con pip (colaboradores sin uv):**

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
pip install -e . --no-deps
```

> **Advertencia para Windows sin uv:** `requirements.txt` no conserva el índice de
> PyTorch (limitación conocida de `uv export`). En Windows, las ruedas de PyPI son
> solo CPU. Si necesitas GPU, instala torch aparte:
> `pip install torch torchvision --index-url https://download.pytorch.org/whl/cu130`.
> La función `get_device()` del paquete avisa si CUDA no quedó disponible.

## Importar desde libretas

El paquete está instalado en modo editable, así que no hace falta tocar `sys.path`:

```python
from neurodac.reproducibility import set_seed, get_run_context
from neurodac.device import get_device
```

## Flujo de dependencias

`pyproject.toml` -> `uv.lock` (fuente de verdad) -> `requirements.txt` (export).

Para agregar una dependencia: `uv add nombre_paquete`. El hook de *pre-commit*
regenera `uv.lock` y `requirements.txt` automáticamente al hacer commit.

## Notas

*(Hardware, montaje de electrodos, esquema de validación cruzada usado.)*
