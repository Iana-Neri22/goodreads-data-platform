"""
Modo simples: serve o flow localmente sem precisar de servidor Prefect externo.
Inicia um servidor embutido e fica aguardando runs — use para desenvolvimento local.

Uso:
    python serve.py

Depois dispare um run em outro terminal:
    prefect deployment run 'goodreads-pipeline/local'
    prefect deployment run 'goodreads-pipeline/local' -p csv_path=data/outro.csv
"""

from flow import pipeline

if __name__ == "__main__":
    pipeline.serve(
        name="local",
        pause_on_shutdown=False,
        print_starting_message=True,
    )
