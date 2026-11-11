import streamlit as st
import streamlit.components.v1 as components
import random
import base64
import json
import time
from collections import deque

# ==========================================
# FUNÇÕES DE SEED E GERADOR DE SUDOKU / JIGSAW
# ==========================================


def gerar_seed_codificada(config: dict) -> str:
    """Empacota as configurações e a semente aleatória em uma string curta Base64."""
    # Omitimos os espaços no JSON para encurtar a string final gerada
    json_str = json.dumps(config, separators=(",", ":"))
    # O rstrip("=") remove o padding para deixar a visualização da Seed mais limpa
    b64_str = base64.urlsafe_b64encode(json_str.encode()).decode().rstrip("=")
    return b64_str


def decodificar_seed(seed_str: str) -> dict | None:
    """Tenta extrair as configurações de uma Seed gerada pelo jogo."""
    try:
        # Restaura dinamicamente o padding necessário para decodificar o Base64
        padding = "=" * (4 - (len(seed_str) % 4))
        json_str = base64.urlsafe_b64decode((seed_str + padding).encode()).decode()
        return json.loads(json_str)
    except Exception:
        return None


def obter_dimensoes_padrao(tamanho: int) -> tuple[int, int]:
    """Encontra os fatores (br, bc) mais próximos da raiz quadrada de tamanho."""
    for br in range(int(tamanho**0.5), 0, -1):
        if tamanho % br == 0:
            return br, tamanho // br
    return 1, tamanho


def regiao_conectada(regioes: list[list[int]], reg_id: int, tamanho: int) -> bool:
    """Verifica via busca em largura (BFS) se todas as células de uma região continuam unidas."""
    celulas = [
        (r, c)
        for r in range(tamanho)
        for c in range(tamanho)
        if regioes[r][c] == reg_id
    ]
    if not celulas:
        return True

    visitados = {celulas[0]}
    fila = deque([celulas[0]])

    while fila:
        r, c = fila.popleft()
        for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            nr, nc = r + dr, c + dc
            if (nr, nc) in celulas and (nr, nc) not in visitados:
                visitados.add((nr, nc))
                fila.append((nr, nc))

    return len(visitados) == len(celulas)


def gerar_mapa_regioes(
    tamanho: int, br: int, bc: int, modo_jigsaw: bool, rng: random.Random
) -> list[list[int]]:
    """
    Cria a matriz de regiões (0 até N-1).
    Se modo_jigsaw=True, deforma os blocos para criar peças irregulares conectadas.
    """
    if not modo_jigsaw and br > 1 and bc > 1:
        return [
            [(r // br) * br + (c // bc) for c in range(tamanho)] for r in range(tamanho)
        ]

    # Base inicial: blocos retangulares (se composto) ou linhas horizontais (se primo)
    if br > 1 and bc > 1:
        regioes = [
            [(r // br) * br + (c // bc) for c in range(tamanho)] for r in range(tamanho)
        ]
    else:
        regioes = [[r for c in range(tamanho)] for r in range(tamanho)]

    # Algoritmo de deformação: embaralha as bordas trocando células entre regiões
    # vizinhas iterativamente, validando se nenhuma peça foi dividida (BFS).
    tentativas = tamanho * tamanho * 6
    for _ in range(tentativas):
        r1 = rng.randrange(tamanho)
        c1 = rng.randrange(tamanho)

        vizinhos = [
            (r1 + dr, c1 + dc)
            for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]
            if 0 <= r1 + dr < tamanho and 0 <= c1 + dc < tamanho
        ]

        if not vizinhos:
            continue

        r2, c2 = rng.choice(vizinhos)
        reg1, reg2 = regioes[r1][c1], regioes[r2][c2]

        if reg1 == reg2:
            continue

        # Procura uma segunda fronteira de contato para realizar a troca e
        # manter a área de todas as regiões estritamente igual a N
        fronteiras = []
        for rr in range(tamanho):
            for cc in range(tamanho):
                if regioes[rr][cc] == reg2 and (rr, cc) != (r2, c2):
                    for dr, dc in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                        nr, nc = rr + dr, cc + dc
                        if (
                            0 <= nr < tamanho
                            and 0 <= nc < tamanho
                            and regioes[nr][nc] == reg1
                            and (nr, nc) != (r1, c1)
                        ):
                            fronteiras.append((rr, cc))
                            break

        if not fronteiras:
            continue

        r3, c3 = rng.choice(fronteiras)

        # Faz a troca em caráter de teste
        regioes[r1][c1] = reg2
        regioes[r3][c3] = reg1

        # Reverte imediatamente caso a alteração fragmente a região original
        if not (
            regiao_conectada(regioes, reg1, tamanho)
            and regiao_conectada(regioes, reg2, tamanho)
        ):
            regioes[r1][c1] = reg1
            regioes[r3][c3] = reg2

    return regioes


def resolver_jigsaw_mrv(
    tamanho: int,
    regioes: list[list[int]],
    rng: random.Random,
    limite_tempo: float = 0.8,
) -> list[list[int]] | None:
    """Resolve qualquer grade irregular usando Backtracking com heurística MRV e Bitmask."""
    tabuleiro = [[0] * tamanho for _ in range(tamanho)]

    # Uso de operações bit-a-bit para rastrear os números usados de forma super rápida (O(1))
    usados_linha = [0] * tamanho
    usados_col = [0] * tamanho
    usados_reg = [0] * tamanho
    todos_bits = (1 << (tamanho + 1)) - 2

    inicio = time.time()

    def backtrack(preenchidas: int) -> bool:
        if preenchidas == tamanho * tamanho:
            return True
        if time.time() - inicio > limite_tempo:
            return False

        # Heurística MRV (Minimum Remaining Values): seleciona sempre a célula
        # com o menor número de possibilidades válidas para podar a árvore de busca cedo.
        melhor_r, melhor_c, melhor_mask, menor_opcoes = -1, -1, 0, tamanho + 1
        for r in range(tamanho):
            for c in range(tamanho):
                if tabuleiro[r][c] == 0:
                    reg = regioes[r][c]
                    livres = todos_bits & ~(
                        usados_linha[r] | usados_col[c] | usados_reg[reg]
                    )
                    qtd = livres.bit_count()

                    if qtd == 0:
                        return False

                    if qtd < menor_opcoes:
                        menor_opcoes = qtd
                        melhor_r, melhor_c, melhor_mask = r, c, livres
                        if qtd == 1:
                            break

            if menor_opcoes == 1:
                break

        # Extrai as opções viáveis a partir da máscara de bits e as tenta em ordem aleatória
        opcoes = [num for num in range(1, tamanho + 1) if (melhor_mask >> num) & 1]
        rng.shuffle(opcoes)
        reg = regioes[melhor_r][melhor_c]

        for num in opcoes:
            bit = 1 << num
            tabuleiro[melhor_r][melhor_c] = num
            usados_linha[melhor_r] |= bit
            usados_col[melhor_c] |= bit
            usados_reg[reg] |= bit

            if backtrack(preenchidas + 1):
                return True

            tabuleiro[melhor_r][melhor_c] = 0
            usados_linha[melhor_r] ^= bit
            usados_col[melhor_c] ^= bit
            usados_reg[reg] ^= bit

        return False

    if backtrack(0):
        return tabuleiro
    return None


def gerar_solucao_padrao(br: int, bc: int, rng: random.Random) -> list[list[int]]:
    """Gerador algébrico instantâneo para grades retangulares clássicas (até 100x100)."""
    tamanho = br * bc

    # Cria uma grade válida rotacionando um array base.
    # Extremamente performático por evitar o backtracking tradicional.
    def pattern(r, c):
        return (bc * (r % br) + r // br + c) % tamanho

    def shuffle(s):
        return rng.sample(list(s), len(s))

    linhas = [g * br + r for g in shuffle(range(bc)) for r in shuffle(range(br))]
    colunas = [g * bc + c for g in shuffle(range(br)) for c in shuffle(range(bc))]
    numeros = shuffle(range(1, tamanho + 1))

    return [[numeros[pattern(r, c)] for c in colunas] for r in linhas]


def gerar_partida_completa(
    tamanho: int, br: int, bc: int, modo_jigsaw: bool, rng: random.Random
):
    """Retorna (solucao, regioes) tanto para o modo Clássico quanto para o modo Jigsaw."""
    if not modo_jigsaw and br > 1 and bc > 1:
        regioes = gerar_mapa_regioes(tamanho, br, bc, False, rng)
        solucao = gerar_solucao_padrao(br, bc, rng)
        return solucao, regioes

    # Para Jigsaw ou dimensões primas, a geração demanda backtracking e pode dar timeout
    for _ in range(8):
        regioes = gerar_mapa_regioes(tamanho, br, bc, True, rng)
        solucao = resolver_jigsaw_mrv(tamanho, regioes, rng, limite_tempo=0.6)
        if solucao is not None:
            return solucao, regioes

    # Fallback algébrico garantido de corpo latino agrupado caso os sorteios acima excedam o limite
    solucao = gerar_solucao_padrao(1, tamanho, rng)
    regioes = [[(r + c) % tamanho for c in range(tamanho)] for r in range(tamanho)]
    return solucao, regioes


def criar_puzzle_sudoku(
    solucao: list[list[int]], vazios: int, rng: random.Random
) -> list[list[int]]:
    """Remove números da solução para formar o desafio inicial."""
    tamanho = len(solucao)
    puzzle = [linha[:] for linha in solucao]
    todas_posicoes = [(r, c) for r in range(tamanho) for c in range(tamanho)]

    posicoes_remover = rng.sample(todas_posicoes, min(vazios, len(todas_posicoes) - 1))

    for r, c in posicoes_remover:
        puzzle[r][c] = 0

    return puzzle


# ==========================================
# INTERFACE INTERATIVA HTML/JS DO SUDOKU
# ==========================================


def renderizar_tabuleiro_sudoku(
    puzzle: list, solucao: list, regioes: list, cfg: dict, seed_atual: str, run_id: int
):
    """
    Renderiza o tabuleiro de Sudoku suportando blocos clássicos ou regiões Jigsaw coloridas.
    """
    tamanho = cfg["n"]
    br = cfg.get("br", 3)
    bc = cfg.get("bc", 3)
    jigsaw = cfg.get("j", False)

    # Vincula o cache local à rodada atual, permitindo reset limpo ao gerar novos puzzles
    storage_key = f"sudoku_{seed_atual}_{run_id}"

    # Responsividade dinâmica do UI baseada no N da grade para evitar quebra de layout
    if tamanho <= 6:
        cell_size, font_size, note_size = 56, 24, 11
    elif tamanho <= 9:
        cell_size, font_size, note_size = 48, 20, 10
    elif tamanho <= 12:
        cell_size, font_size, note_size = 40, 16, 8
    elif tamanho <= 16:
        cell_size, font_size, note_size = 32, 13, 7
    elif tamanho <= 25:
        cell_size, font_size, note_size = 26, 11, 7
    else:
        cell_size, font_size, note_size = 22, 9, 6

    numpad_cols = 5 if tamanho > 16 else (4 if tamanho >= 10 else 3)
    note_cols = bc if (not jigsaw and bc <= 5) else int(tamanho**0.5) or 3
    note_rows = (
        br if (not jigsaw and br <= 5) else (tamanho + note_cols - 1) // note_cols
    )

    auxilios = cfg.get("h", [])
    hl_iguais = "Destacar números iguais e linha/coluna/região" in auxilios
    hl_conflitos = "Destacar conflitos (regras do Sudoku)" in auxilios
    verif_imediata = "Verificar erro imediatamente (gabarito)" in auxilios
    ocultar_completos = "Ocultar números já completados" in auxilios

    # A interface e lógica de preenchimento são inteiramente enviadas e executadas no cliente
    # (Vanilla JS/DOM). Isso garante fluidez e zero latência com o servidor do Streamlit.
    html_sudoku = f"""
    <style>
        * {{ box-sizing: border-box; user-select: none; }}
        body {{ margin: 0; padding: 4px; font-family: sans-serif; background: transparent; color: #fafafa; }}
        .top-bar {{
            display: flex; gap: 14px; justify-content: space-between; align-items: center;
            background: #1a1c24; border: 1px solid #333645; border-radius: 10px; padding: 12px 18px; margin-bottom: 16px;
        }}
        .stat-box {{ display: flex; flex-direction: column; gap: 2px; }}
        .stat-label {{ font-size: 12px; color: #a0a4b8; font-weight: 600; text-transform: uppercase; }}
        .stat-value {{ font-family: monospace; font-size: 22px; font-weight: bold; color: #ffffff; }}
        .timer-val {{ color: #ff4b4b; }}
        .timer-val.done {{ color: #00e676; }}
        
        .main-layout {{ display: flex; flex-wrap: wrap; gap: 24px; justify-content: center; align-items: flex-start; }}
        
        .board-wrapper {{
            background: #111318; padding: 10px; border-radius: 12px; border: 2px solid #4a4e69;
            max-width: 100%; max-height: 75vh; overflow: auto;
        }}
        .sudoku-grid {{
            display: grid;
            grid-template-columns: repeat({tamanho}, {cell_size}px);
            border: 3px solid #b0b8d4;
            background: #2b2e3d;
            width: max-content;
        }}
        .cell {{
            width: {cell_size}px; height: {cell_size}px;
            background: #1e202b; border: 1px solid rgba(255, 255, 255, 0.12);
            display: flex; align-items: center; justify-content: center;
            font-family: monospace; font-size: {font_size}px; font-weight: bold;
            color: #64b5f6; cursor: pointer; position: relative;
        }}
        .cell.fixed {{ color: #ffffff; }}
        .cell.selected {{ background: #2b4c7e !important; outline: 2px solid #64b5f6; z-index: 2; }}
        .cell.related {{ filter: brightness(1.35); }}
        .cell.same-num {{ background: #1b4d3e !important; color: #69f0ae !important; }}
        .cell.error {{ background: #4a151b !important; color: #ff5252 !important; }}
        
        .notes-grid {{
            display: grid; grid-template-columns: repeat({note_cols}, 1fr); grid-template-rows: repeat({note_rows}, 1fr);
            width: 100%; height: 100%; padding: 1px; pointer-events: none;
        }}
        .note-val {{
            font-size: {note_size}px; color: #c5cae9;
            display: flex; align-items: center; justify-content: center; line-height: 1;
        }}
        .notes-compact {{
            font-size: {note_size}px; color: #c5cae9; line-height: 1;
            text-align: center; overflow: hidden; word-break: break-all; padding: 1px; pointer-events: none;
        }}
        
        .controls-panel {{
            flex: 1; min-width: 280px; max-width: 380px;
            background: #1a1c24; border: 1px solid #333645; border-radius: 12px; padding: 16px;
            display: flex; flex-direction: column; gap: 14px;
        }}
        .panel-title {{ font-size: 14px; font-weight: 600; color: #a0a4b8; display: flex; justify-content: space-between; }}
        .action-row {{ display: grid; grid-template-columns: repeat(2, 1fr); gap: 8px; }}
        .btn-action {{
            background: #262730; border: 1px solid #4a4e69; color: #e0e0e0; border-radius: 8px;
            padding: 10px 8px; font-size: 13px; font-weight: 600; cursor: pointer; transition: 0.15s;
        }}
        .btn-action:hover {{ border-color: #8c92ac; background: #323546; }}
        .btn-action.active-mode {{ background: #14452f; border-color: #00e676; color: #69f0ae; }}
        
        .numpad-grid {{
            display: grid; grid-template-columns: repeat({numpad_cols}, 1fr); gap: 6px;
            max-height: 280px; overflow-y: auto; padding-right: 4px;
        }}
        .btn-num {{
            height: 44px; background: #2b2e3d; border: 1px solid #42465a; border-radius: 8px;
            color: #ffffff; font-family: monospace; font-size: 16px; font-weight: bold;
            cursor: pointer; display: flex; flex-direction: column; align-items: center; justify-content: center;
        }}
        .btn-num:hover {{ background: #3b3f54; border-color: #64b5f6; }}
        .btn-num.completed {{ opacity: 0.2; pointer-events: none; }}
        .num-count {{ font-size: 9px; color: #8c92ac; font-weight: normal; }}
        
        .banner-msg {{ padding: 14px; border-radius: 8px; font-weight: 600; font-size: 14px; display: none; }}
        .banner-msg.win {{ display: block; background: #14452f; border: 1px solid #00e676; color: #b9f6ca; }}
        .banner-msg.lose {{ display: block; background: #4a151b; border: 1px solid #ff4b4b; color: #ffcdd2; }}
        
        .kb-hint {{ font-size: 11px; color: #7c829c; text-align: center; line-height: 1.4; }}
    </style>

    <div class="top-bar">
        <div class="stat-box"><span class="stat-label">⏱️ Cronômetro</span><span class="stat-value timer-val" id="timerDisplay">00:00.0</span></div>
        <div class="stat-box"><span class="stat-label">❌ Erros</span><span class="stat-value" id="mistakesDisplay">0 / ∞</span></div>
        <div class="stat-box"><span class="stat-label">💡 Dicas</span><span class="stat-value" id="hintsDisplay">0</span></div>
        <div class="stat-box"><span class="stat-label">📊 Progresso</span><span class="stat-value" id="progressDisplay">0%</span></div>
    </div>

    <div class="main-layout">
        <div class="board-wrapper">
            <div class="sudoku-grid" id="sudokuGrid"></div>
        </div>
        <div class="controls-panel">
            <div id="statusBanner" class="banner-msg"></div>
            <div class="panel-title"><span>🛠️ Ferramentas</span><span style="font-size:11px; font-weight:normal;">[N] Notas</span></div>
            <div class="action-row">
                <button class="btn-action" id="btnNoteMode" onclick="toggleNoteMode()">✏️ Notas: OFF</button>
                <button class="btn-action" onclick="apagarCelula()">⌫ Apagar</button>
                <button class="btn-action" id="btnHint" onclick="usarDica()">💡 Usar Dica</button>
                <button class="btn-action" onclick="reiniciarTabuleiro()">🔄 Limpar Tudo</button>
            </div>
            <div class="panel-title"><span>🔢 Teclado Numérico (1 a {tamanho})</span></div>
            <div class="numpad-grid" id="numpadGrid"></div>
            <div class="kb-hint">
                💡 Clique na célula e use os botões acima, digite <b>1-9</b> ou letras <b>A-Z</b> (A=10, B=11...).
            </div>
        </div>
    </div>

    <script>
        const SIZE = {tamanho};
        const INITIAL = {json.dumps(puzzle)};
        const SOLUTION = {json.dumps(solucao)};
        const REGIONS = {json.dumps(regioes)};
        const IS_JIGSAW = {str(jigsaw).lower()};
        const MAX_MISTAKES = {cfg["m"]};
        const MAX_HINTS = {cfg["dicas_max"]};
        const STORAGE_KEY = "{storage_key}";

        const HL_IGUAIS = {str(hl_iguais).lower()};
        const HL_CONFLITOS = {str(hl_conflitos).lower()};
        const VERIF_IMEDIATA = {str(verif_imediata).lower()};
        const OCULTAR_COMPLETOS = {str(ocultar_completos).lower()};

        // Paleta suave para diferenciar as regiões no modo Jigsaw
        const JIGSAW_PALETTE = [
            "#242038", "#1d2d44", "#1b3a36", "#3b252c", "#2e2d1d",
            "#2d1e3e", "#1c3144", "#283618", "#3d2622", "#222738",
            "#1f363d", "#382232"
        ];

        // Estado gerenciado estritamente no frontend
        let state = {{
            board: INITIAL.map(r => [...r]),
            notes: Array.from({{length: SIZE}}, () => Array.from({{length: SIZE}}, () => [])),
            selected: [0, 0],
            noteMode: false, mistakes: 0, hintsUsed: 0,
            startTime: Date.now(), elapsedFinal: 0, gameOver: false, won: false
        }};

        function carregarEstado() {{
            try {{
                const salvo = sessionStorage.getItem(STORAGE_KEY);
                if (salvo) {{ const parsed = JSON.parse(salvo); if (parsed.board && parsed.board.length === SIZE) state = parsed; }}
            }} catch (e) {{}}
        }}

        function salvarEstado() {{
            try {{ sessionStorage.setItem(STORAGE_KEY, JSON.stringify(state)); }} catch (e) {{}}
        }}

        function atualizarCronometro() {{
            const el = document.getElementById('timerDisplay');
            if (!el) return;
            let diff = state.gameOver ? state.elapsedFinal : Math.max(0, (Date.now() - state.startTime) / 1000);
            el.classList.toggle('done', state.gameOver);
            el.innerText = String(Math.floor(diff / 60)).padStart(2, '0') + ':' + (diff % 60).toFixed(1).padStart(4, '0');
        }}
        setInterval(atualizarCronometro, 100);

        function temConflito(r, c, val) {{
            if (val === 0) return false;
            const reg = REGIONS[r][c];
            for (let i = 0; i < SIZE; i++) {{
                if (i !== c && state.board[r][i] === val) return true;
                if (i !== r && state.board[i][c] === val) return true;
            }}
            for (let rr = 0; rr < SIZE; rr++)
                for (let cc = 0; cc < SIZE; cc++)
                    if ((rr !== r || cc !== c) && REGIONS[rr][cc] === reg && state.board[rr][cc] === val) return true;
            return false;
        }}

        function celulaComErro(r, c) {{
            const val = state.board[r][c];
            if (val === 0) return false;
            if (VERIF_IMEDIATA && val !== SOLUTION[r][c]) return true;
            if (HL_CONFLITOS && temConflito(r, c, val)) return true;
            return false;
        }}

        function selecionarCelula(r, c) {{ state.selected = [r, c]; salvarEstado(); renderizarTudo(); }}
        function toggleNoteMode() {{ if (!state.gameOver) {{ state.noteMode = !state.noteMode; salvarEstado(); renderizarTudo(); }} }}

        function inserirNumero(num) {{
            if (state.gameOver) return;
            const [r, c] = state.selected;
            if (INITIAL[r][c] !== 0) return;

            if (state.noteMode) {{
                if (state.board[r][c] !== 0) return;
                const idx = state.notes[r][c].indexOf(num);
                idx >= 0 ? state.notes[r][c].splice(idx, 1) : state.notes[r][c].push(num);
            }} else {{
                if (state.board[r][c] === num) {{ state.board[r][c] = 0; }}
                else {{
                    state.board[r][c] = num; state.notes[r][c] = [];
                    
                    if ((VERIF_IMEDIATA && num !== SOLUTION[r][c]) || (!VERIF_IMEDIATA && HL_CONFLITOS && temConflito(r, c, num))) {{
                        state.mistakes++;
                        if (MAX_MISTAKES > 0 && state.mistakes >= MAX_MISTAKES) {{ 
                            state.gameOver = true; state.won = false; state.elapsedFinal = (Date.now() - state.startTime) / 1000; 
                        }}
                    }} else {{
                        // Limpa as anotações cruzadas quando um número correto é inserido
                        const reg = REGIONS[r][c];
                        for(let i=0; i<SIZE; i++) {{
                            state.notes[r][i] = state.notes[r][i].filter(n => n !== num);
                            state.notes[i][c] = state.notes[i][c].filter(n => n !== num);
                        }}
                        for (let rr = 0; rr < SIZE; rr++)
                            for (let cc = 0; cc < SIZE; cc++)
                                if (REGIONS[rr][cc] === reg)
                                    state.notes[rr][cc] = state.notes[rr][cc].filter(n => n !== num);

                        let vitoria = true;
                        for(let i=0; i<SIZE; i++) for(let j=0; j<SIZE; j++) if(state.board[i][j] !== SOLUTION[i][j]) vitoria = false;
                        if (vitoria) {{ state.gameOver = true; state.won = true; state.elapsedFinal = (Date.now() - state.startTime) / 1000; }}
                    }}
                }}
            }}
            salvarEstado(); renderizarTudo();
        }}

        function apagarCelula() {{
            if (state.gameOver) return;
            const [r, c] = state.selected;
            if (INITIAL[r][c] === 0) {{ state.board[r][c] = 0; state.notes[r][c] = []; salvarEstado(); renderizarTudo(); }}
        }}

        function usarDica() {{
            if (state.gameOver || state.hintsUsed >= MAX_HINTS) return;
            let [r, c] = state.selected;
            
            // Se a célula selecionada já estiver correta, procura a próxima vazia/errada
            if (state.board[r][c] === SOLUTION[r][c]) {{
                let achou = false;
                for (let rr = 0; rr < SIZE && !achou; rr++)
                    for (let cc = 0; cc < SIZE && !achou; cc++)
                        if (state.board[rr][cc] !== SOLUTION[rr][cc]) {{ r = rr; c = cc; achou = true; }}
            }}
            
            if (state.board[r][c] !== SOLUTION[r][c]) {{
                const correto = SOLUTION[r][c];
                state.board[r][c] = correto; state.notes[r][c] = []; state.hintsUsed++; state.selected = [r, c];
                
                let vitoria = true;
                for(let i=0; i<SIZE; i++) for(let j=0; j<SIZE; j++) if(state.board[i][j] !== SOLUTION[i][j]) vitoria = false;
                if (vitoria) {{ state.gameOver = true; state.won = true; state.elapsedFinal = (Date.now() - state.startTime) / 1000; }}
                
                salvarEstado(); renderizarTudo();
            }}
        }}

        function reiniciarTabuleiro() {{
            state.board = INITIAL.map(r => [...r]);
            state.notes = Array.from({{length: SIZE}}, () => Array.from({{length: SIZE}}, () => []));
            state.mistakes = 0; state.hintsUsed = 0; state.startTime = Date.now(); state.elapsedFinal = 0;
            state.gameOver = false; state.won = false; salvarEstado(); renderizarTudo();
        }}

        function renderizarTudo() {{
            document.getElementById('mistakesDisplay').innerText = MAX_MISTAKES > 0 ? `${{state.mistakes}} / ${{MAX_MISTAKES}}` : `${{state.mistakes}} (Livre)`;
            document.getElementById('hintsDisplay').innerText = `${{MAX_HINTS - state.hintsUsed}} / ${{MAX_HINTS}}`;
            
            let preenchidas = 0;
            let contadores = new Array(SIZE + 1).fill(0);
            for (let r=0; r<SIZE; r++) {{
                for (let c=0; c<SIZE; c++) {{
                    const v = state.board[r][c];
                    if (v !== 0 && !celulaComErro(r, c)) {{
                        preenchidas++;
                        contadores[v]++;
                    }}
                }}
            }}
            document.getElementById('progressDisplay').innerText = Math.floor((preenchidas / (SIZE*SIZE)) * 100) + '%';

            document.getElementById('btnNoteMode').innerText = state.noteMode ? '✏️ Notas: ON' : '✏️ Notas: OFF';
            document.getElementById('btnNoteMode').className = 'btn-action' + (state.noteMode ? ' active-mode' : '');
            
            const btnHint = document.getElementById('btnHint');
            btnHint.disabled = (state.hintsUsed >= MAX_HINTS || state.gameOver);
            btnHint.style.opacity = btnHint.disabled ? '0.4' : '1';

            const banner = document.getElementById('statusBanner');
            if (state.gameOver) {{
                banner.className = 'banner-msg ' + (state.won ? 'win' : 'lose');
                banner.innerHTML = state.won ? `🎉 <b>Parabéns!</b><br>Tempo: ${{state.elapsedFinal.toFixed(1)}}s | Erros: ${{state.mistakes}}` : 
                                               `💥 <b>Fim de Jogo!</b><br>Limite de erros atingido.`;
            }} else {{ banner.className = 'banner-msg'; banner.innerHTML = ''; }}

            // Re-renderização eficiente do Grid e seus atributos visuais
            const gridEl = document.getElementById('sudokuGrid');
            gridEl.innerHTML = '';
            const frag = document.createDocumentFragment();
            const [selR, selC] = state.selected;
            const selVal = state.board[selR][selC];
            const selReg = REGIONS[selR][selC];

            for (let r = 0; r < SIZE; r++) {{
                for (let c = 0; c < SIZE; c++) {{
                    const cell = document.createElement('div');
                    const val = state.board[r][c];
                    const reg = REGIONS[r][c];
                    
                    let classes = ['cell'];
                    if (INITIAL[r][c] !== 0) classes.push('fixed');
                    if (r === selR && c === selC) classes.push('selected');
                    else if (HL_IGUAIS) {{
                        if (selVal !== 0 && val === selVal) classes.push('same-num');
                        else if (r === selR || c === selC || reg === selReg) classes.push('related');
                    }}
                    if (celulaComErro(r, c)) classes.push('error');
                    cell.className = classes.join(' ');

                    // Renderização de cor de fundo específica para o modo Jigsaw ou normal
                    if (IS_JIGSAW) {{
                        cell.style.backgroundColor = JIGSAW_PALETTE[reg % JIGSAW_PALETTE.length];
                    }} else if (INITIAL[r][c] !== 0) {{
                        cell.style.backgroundColor = '#252836';
                    }}

                    // Renderização programática das bordas garantindo delimitação correta das regiões
                    const borderStyle = '2.5px solid #cbd5e1';
                    if (r > 0 && REGIONS[r - 1][c] !== reg) cell.style.borderTop = borderStyle;
                    if (r < SIZE - 1 && REGIONS[r + 1][c] !== reg) cell.style.borderBottom = borderStyle;
                    if (c > 0 && REGIONS[r][c - 1] !== reg) cell.style.borderLeft = borderStyle;
                    if (c < SIZE - 1 && REGIONS[r][c + 1] !== reg) cell.style.borderRight = borderStyle;

                    if (val !== 0) {{ 
                        cell.innerText = val; 
                    }} else if (state.notes[r][c].length > 0) {{
                        if (SIZE <= 16) {{
                            const nGrid = document.createElement('div'); nGrid.className = 'notes-grid';
                            for (let n = 1; n <= SIZE; n++) {{
                                const nSpan = document.createElement('div'); nSpan.className = 'note-val';
                                nSpan.innerText = state.notes[r][c].includes(n) ? n : ''; nGrid.appendChild(nSpan);
                            }}
                            cell.appendChild(nGrid);
                        }} else {{
                            const nComp = document.createElement('div'); nComp.className = 'notes-compact';
                            nComp.innerText = state.notes[r][c].sort((a,b)=>a-b).join(',');
                            cell.appendChild(nComp);
                        }}
                    }}
                    cell.onclick = () => selecionarCelula(r, c);
                    frag.appendChild(cell);
                }}
            }}
            gridEl.appendChild(frag);

            // Teclado numérico reativo 
            const numpadEl = document.getElementById('numpadGrid');
            numpadEl.innerHTML = '';
            const numFrag = document.createDocumentFragment();
            for (let n = 1; n <= SIZE; n++) {{
                let count = contadores[n];
                const btn = document.createElement('button');
                btn.className = 'btn-num' + ((OCULTAR_COMPLETOS && count >= SIZE) ? ' completed' : '');
                btn.innerHTML = `<span>${{n}}</span><span class="num-count">${{Math.max(0, SIZE - count)}} rest.</span>`;
                btn.onclick = () => inserirNumero(n);
                numFrag.appendChild(btn);
            }}
            numpadEl.appendChild(numFrag);
        }}

        // Mapeamento abrangente de navegação via teclado
        window.addEventListener('keydown', (e) => {{
            const [r, c] = state.selected;
            let valPretendido = -1;

            if (e.key >= '1' && e.key <= '9') {{
                valPretendido = parseInt(e.key);
            }} else if (SIZE >= 10 && e.key.length === 1) {{
                const charCode = e.key.toLowerCase().charCodeAt(0);
                if (charCode >= 97 && charCode <= 122) {{
                    valPretendido = charCode - 97 + 10;
                }}
            }}

            if (valPretendido > 0 && valPretendido <= SIZE) {{
                inserirNumero(valPretendido); e.preventDefault();
            }} else if (e.key === 'Backspace' || e.key === 'Delete' || e.key === '0') {{
                apagarCelula(); e.preventDefault();
            }} else if (e.key === 'n' || e.key === 'N' || e.key === ' ') {{
                toggleNoteMode(); e.preventDefault();
            }} else if (e.key === 'ArrowUp') {{ selecionarCelula((r - 1 + SIZE) % SIZE, c); e.preventDefault();
            }} else if (e.key === 'ArrowDown') {{ selecionarCelula((r + 1) % SIZE, c); e.preventDefault();
            }} else if (e.key === 'ArrowLeft') {{ selecionarCelula(r, (c - 1 + SIZE) % SIZE); e.preventDefault();
            }} else if (e.key === 'ArrowRight') {{ selecionarCelula(r, (c + 1) % SIZE); e.preventDefault();
            }}
        }});

        carregarEstado(); atualizarCronometro(); renderizarTudo();
    </script>
    """
    components.html(html_sudoku, height=760, scrolling=True)


# ==========================================
# FUNÇÃO PRINCIPAL DO JOGO
# ==========================================


def run():
    # Inicializa ou migra automaticamente as sessões no cache global para persistência de interface
    if (
        "sudoku_ativo" not in st.session_state
        or "sudoku_regioes" not in st.session_state
        or "br" not in st.session_state.get("sudoku_config", {})
    ):
        st.session_state.sudoku_ativo = False
        st.session_state.sudoku_puzzle = []
        st.session_state.sudoku_solucao = []
        st.session_state.sudoku_regioes = []
        st.session_state.sudoku_seed_atual = ""
        st.session_state.sudoku_config = {}
        st.session_state.sudoku_run_id = 0

    st.sidebar.header("⚙️ Configurações do Sudoku")

    modo_formato = st.sidebar.radio(
        "Modo de Formato",
        [
            "📐 Clássico (Padrões Rápidos)",
            "🧩 Jigsaw / Irregular (Inclui Primos 5x5, 7x7...)",
            "🛠️ Livre (Escolher Bloco Br x Bc)",
        ],
        index=0,
    )

    modo_jigsaw = False

    if modo_formato == "📐 Clássico (Padrões Rápidos)":
        opcoes_tamanho = {
            "4x4 (Mini - Blocos 2x2)": (2, 2),
            "6x6 (Médio - Blocos 2x3)": (2, 3),
            "8x8 (Blocos 2x4)": (2, 4),
            "9x9 (Clássico - Blocos 3x3)": (3, 3),
            "10x10 (Blocos 2x5)": (2, 5),
            "12x12 (Grande - Blocos 3x4)": (3, 4),
            "15x15 (Blocos 3x5)": (3, 5),
            "16x16 (Gigante - Blocos 4x4)": (4, 4),
            "20x20 (Blocos 4x5)": (4, 5),
            "25x25 (Blocos 5x5)": (5, 5),
        }
        label_tamanho = st.sidebar.selectbox(
            "Tamanho do Tabuleiro", list(opcoes_tamanho.keys()), index=3
        )
        br, bc = opcoes_tamanho[label_tamanho]
        tamanho = br * bc
        modo_jigsaw = st.sidebar.checkbox(
            "Deformar blocos no estilo Jigsaw (Irregular)", value=False
        )

    elif modo_formato == "🧩 Jigsaw / Irregular (Inclui Primos 5x5, 7x7...)":
        modo_jigsaw = True
        st.sidebar.caption(
            "No modo Jigsaw, as regiões têm formatos orgânicos coloridos, permitindo **qualquer número N** (inclusive primos como 5x5, 7x7 e 11x11)!"
        )
        tamanho = st.sidebar.slider(
            "Tamanho do Tabuleiro (N x N)", min_value=4, max_value=12, value=7
        )
        br, bc = obter_dimensoes_padrao(tamanho)

    else:
        st.sidebar.caption(
            "O tamanho do tabuleiro será **N = Altura × Largura do Bloco** (ex: 2 e 5 gera um **10x10**; 10 e 10 gera um **100x100**)."
        )
        col_br, col_bc = st.sidebar.columns(2)
        br = col_br.number_input(
            "Altura Bloco (Br)", min_value=1, max_value=10, value=2
        )
        bc = col_bc.number_input(
            "Largura Bloco (Bc)", min_value=1, max_value=10, value=5
        )

        if br * bc < 4:
            st.sidebar.warning(
                "Escolha dimensões cujo produto seja pelo menos 4 (ex: 2x2)."
            )
            br, bc = 2, 2

        tamanho = br * bc

        if br == 1 or bc == 1:
            st.sidebar.info(
                "💡 Como uma das dimensões do bloco é 1, o modo **Jigsaw Irregular** foi ativado automaticamente para criar regiões válidas!"
            )
            modo_jigsaw = True

    total_celulas = tamanho * tamanho
    tipo_regiao_txt = (
        "Regiões Jigsaw Irregulares" if modo_jigsaw else f"Blocos {br}x{bc}"
    )
    st.sidebar.info(
        f"📐 **Grade:** {tamanho}x{tamanho} ({total_celulas} células)\n\n🧩 **Formato:** {tipo_regiao_txt}"
    )

    dificuldade = st.sidebar.selectbox(
        "Nível de Dificuldade",
        ["Fácil", "Médio", "Difícil", "Extremo", "Personalizado"],
        index=1,
    )

    # Parametrização para distribuição controlada da dificuldade
    presets_proporcao = {
        "Fácil": {"taxa_vazios": 0.40, "erros": 5, "dicas": 5},
        "Médio": {"taxa_vazios": 0.53, "erros": 3, "dicas": 3},
        "Difícil": {"taxa_vazios": 0.64, "erros": 3, "dicas": 2},
        "Extremo": {"taxa_vazios": 0.74, "erros": 1, "dicas": 0},
    }

    if dificuldade != "Personalizado":
        p = presets_proporcao[dificuldade]
        vazios_padrao = max(1, int(total_celulas * p["taxa_vazios"]))
        qtd_vazios = st.sidebar.slider(
            "Células vazias para preencher", 1, total_celulas - 1, vazios_padrao
        )
        max_erros = st.sidebar.number_input(
            "Limite de erros (0 = sem limite)", 0, 100, p["erros"]
        )
        max_dicas = st.sidebar.number_input("Dicas disponíveis", 0, 100, p["dicas"])
    else:
        qtd_vazios = st.sidebar.slider(
            "Células vazias para preencher",
            1,
            total_celulas - 1,
            int(total_celulas * 0.5),
        )
        max_erros = st.sidebar.number_input(
            "Limite de erros (0 = sem limite)", 0, 100, 0
        )
        max_dicas = st.sidebar.number_input("Dicas disponíveis", 0, 100, 5)

    st.sidebar.subheader("💡 Auxílios Visuais e Regras")
    auxilios_selecionados = st.sidebar.multiselect(
        "Escolha quais auxílios ativar:",
        [
            "Destacar números iguais e linha/coluna/região",
            "Destacar conflitos (regras do Sudoku)",
            "Verificar erro imediatamente (gabarito)",
            "Ocultar números já completados",
        ],
        default=[
            "Destacar números iguais e linha/coluna/região",
            "Destacar conflitos (regras do Sudoku)",
            "Verificar erro imediatamente (gabarito)",
            "Ocultar números já completados",
        ],
    )

    st.sidebar.markdown("---")
    st.sidebar.subheader("🌱 Sistema de Seed")
    seed_input = st.sidebar.text_input(
        "Carregar Seed (deixe vazio para aleatória):",
        placeholder="Cole uma Seed aqui...",
    )

    col_btn1, col_btn2 = st.sidebar.columns(2)
    iniciar_novo = col_btn1.button(
        "🎲 Novo Jogo", use_container_width=True, type="primary"
    )
    carregar_seed_btn = col_btn2.button("📥 Carregar Seed", use_container_width=True)

    def iniciar_partida(usar_seed_carregada=False, manter_config_atual=False):
        """Gerencia reinicialização de estado validando consistência e parse de inputs/seeds."""
        if manter_config_atual and st.session_state.sudoku_config:
            cfg = st.session_state.sudoku_config

        elif usar_seed_carregada and seed_input.strip():
            dados_seed = decodificar_seed(seed_input.strip())

            if dados_seed and "n" in dados_seed and "v" in dados_seed:
                # Fallback de compatibilidade para seeds antigas sem block width/height
                if "br" not in dados_seed or "bc" not in dados_seed:
                    dados_seed["br"], dados_seed["bc"] = obter_dimensoes_padrao(
                        dados_seed["n"]
                    )
                if "j" not in dados_seed:
                    dados_seed["j"] = False

                cfg = dados_seed
                st.sidebar.success("Seed completa carregada com sucesso!")
            else:
                cfg = {
                    "d": dificuldade,
                    "n": tamanho,
                    "br": br,
                    "bc": bc,
                    "j": modo_jigsaw,
                    "v": qtd_vazios,
                    "m": int(max_erros),
                    "dicas_max": int(max_dicas),
                    "h": auxilios_selecionados,
                    "s": seed_input.strip(),
                }
                st.sidebar.info("Seed personalizada aplicada às configurações atuais!")
        else:
            cfg = {
                "d": dificuldade,
                "n": tamanho,
                "br": br,
                "bc": bc,
                "j": modo_jigsaw,
                "v": qtd_vazios,
                "m": int(max_erros),
                "dicas_max": int(max_dicas),
                "h": auxilios_selecionados,
                "s": str(random.randint(100000, 999999)),
            }

        rng = random.Random(str(cfg["s"]))
        solucao, regioes = gerar_partida_completa(
            cfg["n"], cfg["br"], cfg["bc"], cfg.get("j", False), rng
        )

        st.session_state.sudoku_config = cfg
        st.session_state.sudoku_solucao = solucao
        st.session_state.sudoku_regioes = regioes
        st.session_state.sudoku_puzzle = criar_puzzle_sudoku(solucao, cfg["v"], rng)
        st.session_state.sudoku_seed_atual = gerar_seed_codificada(cfg)
        st.session_state.sudoku_ativo = True

        # O increment de ID força o frontend (JS) a perder as caches antigas
        st.session_state.sudoku_run_id += 1

    # Roteamento dos eventos provindos da sidebar
    if iniciar_novo:
        iniciar_partida(usar_seed_carregada=False)
    elif carregar_seed_btn:
        if not seed_input.strip():
            st.sidebar.warning("Digite ou cole uma Seed.")
        else:
            iniciar_partida(usar_seed_carregada=True)
    elif not st.session_state.sudoku_ativo:
        iniciar_partida(usar_seed_carregada=False)

    cfg = st.session_state.sudoku_config
    br_cfg, bc_cfg = obter_dimensoes_padrao(cfg.get("n", 9))
    br_atual = cfg.get("br", br_cfg)
    bc_atual = cfg.get("bc", bc_cfg)

    col_titulo, col_seed = st.columns([1.5, 2], vertical_alignment="center")
    with col_titulo:
        st.title("🧩 Sudoku & Jigsaw Customizável")
        sub_formato = (
            "Jigsaw Irregular"
            if cfg.get("j", False)
            else f"Blocos {br_atual}x{bc_atual}"
        )
        st.caption(
            f"Grade: **{cfg['n']}x{cfg['n']}** ({sub_formato}) | Dificuldade: **{cfg['d']}** | Vazios: **{cfg['v']} / {cfg['n'] * cfg['n']}**"
        )
    with col_seed:
        st.markdown("**🌱 Seed desta Partida:**")
        st.code(st.session_state.sudoku_seed_atual, language="text")

    # Injeta todo o pacote HTML/JS processado no Streamlit para exibição no frontend
    renderizar_tabuleiro_sudoku(
        st.session_state.sudoku_puzzle,
        st.session_state.sudoku_solucao,
        st.session_state.sudoku_regioes,
        cfg,
        st.session_state.sudoku_seed_atual,
        st.session_state.sudoku_run_id,
    )


if __name__ == "__main__":
    st.set_page_config(page_title="Sudoku Customizável", page_icon="🧩", layout="wide")
    run()
