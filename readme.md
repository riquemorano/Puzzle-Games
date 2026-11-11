# 🎮 Central de Jogos (Streamlit)

Uma plataforma interativa de jogos clássicos de lógica e quebra-cabeças, desenvolvida inteiramente em Python utilizando a biblioteca **Streamlit**.

O projeto demonstra como contornar as limitações de re-renderização do Streamlit injetando Vanilla JavaScript e CSS através de componentes HTML (`streamlit.components.v1`), garantindo uma experiência de jogo fluida, com animações suaves e zero latência de servidor durante as jogadas.

## 🕹️ Jogos Disponíveis

### 1. 🔐 Desafio do Cadeado (Number Password)

Descubra a combinação secreta do cadeado utilizando pura dedução lógica.

- **Dificuldades:** Fácil ao Extremo (ou Personalizado).
- **Recursos:** Matriz interativa de dedução, pistas dinâmicas (números no lugar certo/errado, soma dos dígitos) e histórico de palpites.

### 2. 🧩 Sudoku & Jigsaw

O clássico Sudoku reimaginado, suportando os blocos tradicionais e o formato **Jigsaw Irregular** (que permite matrizes de qualquer tamanho, incluindo números primos como 5x5 e 7x7).

- **Recursos:** Teclado numérico na tela, suporte a atalhos de teclado, sistema de notas (rascunho), dicas e detecção de conflitos em tempo real.
- **Solver Integrado:** Gera os tabuleiros instantaneamente usando backtracking e heurística MRV (Minimum Remaining Values).

### 3. 🧩 Quebra-Cabeça Deslizante (Sliding Puzzle)

O clássico jogo de organizar peças numeradas deslizando-as para o espaço vazio.

- **Recursos:** Tabuleiros dinâmicos (N x N), navegação pelo teclado (Setas/WASD), contador de movimentos, cronômetro e animações CSS responsivas.

## ✨ Principais Funcionalidades (Gerais)

- **Sistema de Seeds (Sementes):** Todo jogo gerado possui uma *Seed* única (codificada em Base64). Você pode copiar essa Seed e enviá-la para um amigo para que ele jogue exatamente o mesmo tabuleiro/desafio que você.
- **Client-Side Rendering:** As interações de alta frequência (como mover peças ou preencher números) rodam no navegador (JS/DOM), preservando a comunicação com o servidor Python apenas para validações de fim de jogo e configurações iniciais.
- **Layout Dinâmico:** A interface alterna automaticamente entre os modos *centered* (menu) e *wide* (durante o jogo) para melhor aproveitamento da tela.

## 🚀 Como executar o projeto localmente

Siga os passos abaixo para rodar a aplicação na sua máquina:

1. **Clone este repositório:**

```bash
   git clone https://github.com/riquemorano/Puzzle-Games.git
   cd Puzzle-Games

```

2. **Crie um ambiente virtual (Opcional, mas recomendado):**

```bash
python -m venv venv

# No Windows:
venv\Scripts\activate

# No Linux/Mac:
source venv/bin/activate

```

1. **Instale as dependências:**

```bash
pip install -r requirements.txt

```

1. **Inicie o servidor do Streamlit:**

```bash
streamlit run app.py

```

1. O painel será aberto automaticamente no seu navegador padrão (geralmente em `http://localhost:8501`).

## 📂 Estrutura do Projeto

```text
├── app.py                   # Ponto de entrada da aplicação e roteamento do Menu
├── requirements.txt         # Lista de dependências do Python
└── games/                   # Módulos independentes de cada jogo
    ├── __init__.py
    ├── number_password.py   # Lógica e UI do Desafio do Cadeado
    ├── sliding_puzzle.py    # Lógica e UI do Quebra-Cabeça Deslizante
    └── sudoku.py            # Lógica (Solver) e UI do Sudoku Clássico/Irregular

```

## 🛠️ Como adicionar novos jogos

O projeto foi estruturado para ser facilmente escalável. Para adicionar um novo jogo:

1. Crie o arquivo do jogo dentro da pasta `games/` (ex: `meu_jogo.py`) e implemente uma função `run()`.
2. Em `app.py`, importe o módulo recém-criado.
3. Adicione-o ao dicionário global `JOGOS` no `app.py`. O menu principal gerará o card automaticamente!

## 🤝 Contribuições

Contribuições, relatórios de bugs e *pull requests* são bem-vindos! Sinta-se à vontade para abrir uma *Issue* caso tenha alguma ideia de melhoria ou um novo jogo para adicionar.

## 📄 Licença

Este projeto está licenciado sob a [MIT License](https://www.google.com/search?q=LICENSE).

