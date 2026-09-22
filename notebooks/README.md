# Aroogula Research Notebooks

These notebooks document the evolution of Aroogula's FinBERT news-analysis pipeline.

## Notebooks

- `01_finbert_multitask_prototype.ipynb` — historical first multitask prototype.
- `02_finbert_multitask_training.ipynb` — current training, evaluation, threshold calibration and deployment-preparation workflow.

## Data layout

The notebooks expect:

```text
data/
└── training/
    └── FINBERT_V3_TRAINING_DATA.xlsx
```

The workbook contains the labeled train / validation / test splits used by the experiments.

## Generated artifacts

Model checkpoints and training runs are written to `../artifacts/` and should normally be ignored by Git because they can be large and are reproducible from the notebook and dataset.

## Scope

These notebooks are research/development artifacts. Production inference and trading orchestration belong in the Aroogula backend, not in the notebook layer.
