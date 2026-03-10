"""
set_to_csv.py — Convertidor de archivos EEGLAB (.set) a CSV para NEURODAC
DUNNE · División Universitaria de Neuroingeniería

Uso:
    python set_to_csv.py archivo.set [archivo_salida.csv]

Si no se especifica nombre de salida, se genera automáticamente.
Compatible con archivos .set continuos (raw) y con epochs (los concatena).
"""

import sys
import os
import time
import numpy as np
import pandas as pd
import mne


def convert_set_to_csv(input_path, output_path=None):
    """
    Convierte un archivo EEGLAB .set a CSV compatible con NEURODAC.
    
    Parámetros:
        input_path (str): Ruta al archivo .set
        output_path (str): Ruta de salida para el CSV. Si es None, se genera automáticamente.
    
    Retorna:
        str: Ruta del archivo CSV generado.
    """
    if not os.path.exists(input_path):
        raise FileNotFoundError(f"No se encontró el archivo: {input_path}")
    
    if not input_path.lower().endswith('.set'):
        raise ValueError("El archivo debe tener extensión .set")
    
    # Generar nombre de salida si no se especificó
    if output_path is None:
        base = os.path.splitext(os.path.basename(input_path))[0]
        output_path = os.path.join(os.path.dirname(input_path), f"{base}.csv")
    
    print(f"Leyendo: {input_path}")
    
    # --- Intentar leer como raw (continuo) ---
    raw = None
    try:
        raw_data = mne.io.read_raw_eeglab(input_path, preload=True, verbose=False)
        print(f"  Tipo: Señal continua (raw)")
        print(f"  Canales: {len(raw_data.ch_names)}")
        print(f"  Frecuencia de muestreo: {raw_data.info['sfreq']} Hz")
        print(f"  Duración: {raw_data.times[-1]:.2f} segundos")
        print(f"  Muestras: {raw_data.n_times}")
        
        data = raw_data.get_data()  # shape: (n_channels, n_samples)
        ch_names = raw_data.ch_names
        sfreq = raw_data.info['sfreq']
        n_samples = raw_data.n_times
        
    except TypeError:
        # --- Si falla, leer como epochs y concatenar ---
        print("  Detectado como archivo con epochs; concatenando...")
        epochs = mne.io.read_epochs_eeglab(input_path, verbose=False)
        
        n_epochs, n_channels, n_times_per_epoch = epochs.get_data().shape
        print(f"  Tipo: Epochs ({n_epochs} epochs de {n_times_per_epoch} muestras)")
        print(f"  Canales: {n_channels}")
        print(f"  Frecuencia de muestreo: {epochs.info['sfreq']} Hz")
        
        # Concatenar epochs en una señal continua
        # Shape: (n_epochs, n_channels, n_times) -> (n_channels, n_epochs * n_times)
        epoch_data = epochs.get_data()
        data = np.concatenate([epoch_data[i] for i in range(n_epochs)], axis=1)
        
        ch_names = epochs.ch_names
        sfreq = epochs.info['sfreq']
        n_samples = data.shape[1]
        
        print(f"  Total de muestras concatenadas: {n_samples}")
        print(f"  Duración total: {n_samples / sfreq:.2f} segundos")
    
    # --- Generar timestamps ---
    # Usar tiempo actual como base (similar al formato del CSV original)
    base_timestamp = time.time()
    timestamps = base_timestamp + np.arange(n_samples) / sfreq
    
    # --- Determinar si los datos ya están en µV o en Volts ---
    # MNE lee en Volts, pero algunos archivos .set ya almacenan en µV.
    # Si la media absoluta de los canales es > 1 (en "Volts"), es porque
    # los datos ya estaban en µV y MNE no los escaló correctamente.
    mean_abs = np.mean(np.abs(data.mean(axis=1)))
    
    if mean_abs > 0.1:  # Los datos ya están en µV (MNE los leyó sin escalar)
        data_uv = data * 1e6  # MNE asume Volts; si el .set ya tiene µV, esto da valores enormes
        # Revertir: usar los datos crudos directamente del archivo
        import scipy.io
        mat = scipy.io.loadmat(input_path, squeeze_me=True)
        raw_values = mat['data']
        if raw_values.shape[0] == len(ch_names):
            data_uv = raw_values.astype(float)
            print(f"  Datos le\u00EDdos directamente del .set (ya en \u00B5V)")
        else:
            data_uv = data * 1e6
            print(f"  Advertencia: no se pudo leer data cruda; usando conversi\u00F3n est\u00E1ndar")
    else:
        # Datos en Volts (caso normal); convertir a µV
        data_uv = data * 1e6
        print(f"  Datos convertidos de Volts a \u00B5V")
    
    # --- Remover offset DC (restar media de cada canal) ---
    for i in range(data_uv.shape[0]):
        data_uv[i] -= data_uv[i].mean()
    print(f"  Offset DC removido (media restada por canal)")
    
    df = pd.DataFrame(data_uv.T, columns=ch_names)
    df.insert(0, 'Timestamp', timestamps)
    
    # Redondear los valores de señal a enteros (como en el CSV original)
    for col in ch_names:
        df[col] = df[col].round(0).astype(int)
    
    # --- Guardar CSV ---
    df.to_csv(output_path, index=False)
    
    print(f"\nCSV generado: {output_path}")
    print(f"  Filas: {len(df)}")
    print(f"  Columnas: {list(df.columns[:5])}... ({len(df.columns)} total)")
    print(f"  Tamaño: {os.path.getsize(output_path) / (1024*1024):.1f} MB")
    
    return output_path


def main():
    if len(sys.argv) < 2:
        print("Uso: python set_to_csv.py archivo.set [salida.csv]")
        print("  Si no se especifica salida, se genera con el mismo nombre del .set")
        sys.exit(1)
    
    input_path = sys.argv[1]
    output_path = sys.argv[2] if len(sys.argv) > 2 else None
    
    try:
        result = convert_set_to_csv(input_path, output_path)
        print(f"\nConversión exitosa.")
    except Exception as e:
        print(f"\nError: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
