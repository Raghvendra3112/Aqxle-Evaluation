# Mercurion-Evaluation

Mercurion Evaluation is a private Python library containing standardized evaluation utilities for:
- **Likert scale scoring**
- **Elo rating updates**
- **Standardized LLM querying**

mercurion-evaluation/
│
├── .gitignore          # Ignore unwanted files
├── README.md           # Project documentation
├── requirements.txt    # Python dependencies
├── setup.py            # Packaging configuration
│
├── mercurion_eval/     # Source package
│   ├── __init__.py
│   ├── Likert.py       # Likert scale scoring functions
│   ├── Elo.py          # Elo rating update functions
│   ├── llm_query.py    # Standardized LLM query function
│
└── tests/              # Unit tests
    ├── test_likert.py
    ├── test_elo.py
    ├── test_llm.py

## 📦 Installation

### SSH (recommended for private repos)
```bash
pip install git+ssh://git@github.com/Raghvendra3112/mercurion-evaluation.git
