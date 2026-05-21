# hs-backend

## Comandos

### Instalar dependencias

```bash
uv sync
```

### Rodar o projeto

```bash
uv run uvicorn main:app --reload
```

Swagger: `http://127.0.0.1:8000/api/docs`

### Rodar testes

```bash
uv run pytest/ou na própria aba 'Tests' do VSCode
```

Os testes devem focar nas regras de negócio em `services/`.
Não criaremos testes de endpoints.

### Rodar lint

```bash
uv run ruff check . && uv run ruff format --check .
```

Esse comando agrupa a validacao de lint e a checagem de formatacao usadas no CI.

## Estrutura do projeto

- `main.py`: ponto de entrada da aplicação FastAPI.
- `controllers/`: define as rotas/endpoints HTTP e recebe as requisições.
- `services/`: concentra as regras de negócio e a lógica principal da aplicação.
- `repositories/`: concentra o acesso ao banco de dados.
- `domain/models/`: contem os models SQLAlchemy que representam as tabelas.
- `domain/schemas/`: contem os schemas Pydantic de entrada e saida da API.
- `domain/errors/`: contem excecoes e erros especificos do dominio.
- `schedules/`: contem jobs e tarefas periodicas.
- `utils/`: contem funcoes auxiliares reutilizaveis.
