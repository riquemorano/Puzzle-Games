import streamlit as st
import streamlit.components.v1 as components
import random
import base64
import json


# ==========================================
# FUNÇÕES DE SEED E GERADOR
# ==========================================
def gerar_seed_codificada(config: dict) -> str:
    """Empacota as configurações e a semente aleatória em uma string curta Base64."""
    # Remove espaços do JSON para encurtar a string gerada
    json_str = json.dumps(config, separators=(",", ":"))
    # Remove o padding do Base64 para gerar uma URL/Seed mais limpa visualmente
    b64_str = base64.urlsafe_b64encode(json_str.encode()).decode().rstrip("=")
    return b64_str


def decodificar_seed(seed_str: str) -> dict | None:
    """Tenta extrair as configurações de uma Seed gerada pelo jogo."""
    try:
        # Restaura o padding necessário para o decode do Base64
        padding = "=" * (4 - (len(seed_str) % 4))
        json_str = base64.urlsafe_b64decode((seed_str + padding).encode()).decode()
        return json.loads(json_str)
    except Exception:
        return None


def gerar_tabuleiro_valido(
    tamanho: int, passos_embaralhamento: int, rng: random.Random
) -> list[list[int]]:
    """
    Gera um tabuleiro garantidamente solucionável partindo da solução
    e fazendo N movimentos aleatórios inversos.
    """
    # Para garantir matematicamente que o puzzle tem solução, partimos do estado
    # já resolvido (1 até N^2-1, terminando em 0) e o embaralhamos.
    board = [[r * tamanho + c + 1 for c in range(tamanho)] for r in range(tamanho)]
    board[-1][-1] = 0
    empty_r, empty_c = tamanho - 1, tamanho - 1
    last_move = None

    for _ in range(passos_embaralhamento):
        moves = []
        if empty_r > 0:
            moves.append((-1, 0))
        if empty_r < tamanho - 1:
            moves.append((1, 0))
        if empty_c > 0:
            moves.append((0, -1))
        if empty_c < tamanho - 1:
            moves.append((0, 1))

        # Otimização: evita desfazer o último movimento para garantir um embaralhamento mais eficiente
        if last_move:
            rev = (-last_move[0], -last_move[1])
            if rev in moves and len(moves) > 1:
                moves.remove(rev)

        move = rng.choice(moves)
        dr, dc = move
        nr, nc = empty_r + dr, empty_c + dc

        # Troca a peça selecionada com o espaço vazio (0)
        board[empty_r][empty_c], board[nr][nc] = board[nr][nc], board[empty_r][empty_c]
        empty_r, empty_c = nr, nc
        last_move = move

    return board


# ==========================================
# INTERFACE INTERATIVA HTML/JS
# ==========================================
def renderizar_sliding_puzzle(
    board_inicial: list, cfg: dict, seed_atual: str, run_id: int
):
    """
    Renderiza o quebra-cabeça deslizante com animações suaves via CSS translate,
    cronômetro, contador de movimentos e suporte a teclado e gestos (swipe).
    """
    tamanho = cfg["n"]
    # A chave vincula o estado do JS à seed e à rodada para limpar o cache quando o jogo reseta
    storage_key = f"sliding_{seed_atual}_{run_id}"

    auxilios = cfg.get("h", [])
    hl_corretos = "Destacar peças na posição correta" in auxilios

    # Ajuste responsivo básico para grades maiores (define o limite máximo em telas grandes,
    # mas usa 100% da largura disponível em telas de celular)
    board_px = 420
    if tamanho >= 6:
        board_px = 500
    tile_size = board_px // tamanho
    font_size = max(12, int(tile_size * 0.4))

    # Toda a lógica de jogo (movimentos, timer, vitórias) é enviada ao client-side.
    # Isso impede que o Streamlit recarregue o backend a cada peça movida, garantindo fluidez.
    html_puzzle = f"""
    <style>
        * {{
            box-sizing: border-box;
            user-select: none;
            -webkit-user-select: none;
            -webkit-tap-highlight-color: transparent;
        }}
        body {{ margin: 0; padding: 4px; font-family: sans-serif; background: transparent; color: #fafafa; }}
        
        .top-bar {{
            display: flex; gap: 14px; justify-content: space-between; align-items: center;
            background: #1a1c24; border: 1px solid #333645; border-radius: 10px; padding: 12px 18px; margin-bottom: 24px;
            max-width: {board_px}px; margin-left: auto; margin-right: auto;
        }}
        .stat-box {{ display: flex; flex-direction: column; gap: 2px; }}
        .stat-label {{ font-size: 12px; color: #a0a4b8; font-weight: 600; text-transform: uppercase; }}
        .stat-value {{ font-family: monospace; font-size: 22px; font-weight: bold; color: #ffffff; }}
        .timer-val {{ color: #ff4b4b; }}
        .timer-val.done {{ color: #00e676; }}
        
        .main-layout {{ display: flex; flex-direction: column; align-items: center; gap: 16px; width: 100%; }}
        
        .board-wrapper {{
            position: relative;
            width: 100%;
            max-width: {board_px}px;
            aspect-ratio: 1 / 1;
            background: #111318;
            border: 4px solid #333645;
            border-radius: 8px;
            box-shadow: 0 8px 32px rgba(0,0,0,0.5);
            overflow: hidden;
            touch-action: none;
        }}
        
        .tile {{
            position: absolute;
            top: 0;
            left: 0;
            width: calc(100% / {tamanho});
            height: calc(100% / {tamanho});
            background: #2b4c7e;
            border: 2px solid #111318;
            border-radius: 6px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: clamp(11px, calc(65vw / {tamanho}), {font_size}px);
            font-weight: bold;
            color: #ffffff;
            cursor: pointer;
            transition: transform 0.15s cubic-bezier(0.2, 0.8, 0.2, 1), background 0.2s;
            box-shadow: inset 0 0 12px rgba(255,255,255,0.1);
        }}
        
        .tile:hover {{
            background: #3b5c8e;
        }}
        
        .tile.correct {{
            background: #14452f;
            color: #69f0ae;
            box-shadow: inset 0 0 12px rgba(0,230,118,0.2);
        }}
        
        .banner-msg {{ width: 100%; max-width: {board_px}px; padding: 14px; border-radius: 8px; font-weight: 600; font-size: 14px; text-align: center; display: none; }}
        .banner-msg.win {{ display: block; background: #14452f; border: 1px solid #00e676; color: #b9f6ca; }}
        
        .kb-hint {{ font-size: 11px; color: #7c829c; text-align: center; margin-top: 8px; }}

        @media (max-width: 480px) {{
            .stat-value {{ font-size: 17px; }}
            .stat-label {{ font-size: 10px; }}
            .top-bar {{ padding: 8px 12px; margin-bottom: 14px; gap: 8px; }}
        }}
    </style>

    <div class="top-bar">
        <div class="stat-box"><span class="stat-label">⏱️ Cronômetro</span><span class="stat-value timer-val" id="timerDisplay">00:00.0</span></div>
        <div class="stat-box"><span class="stat-label">👣 Movimentos</span><span class="stat-value" id="movesDisplay">0</span></div>
        <div class="stat-box"><span class="stat-label">✅ Peças Corretas</span><span class="stat-value" id="correctDisplay">0</span></div>
    </div>

    <div class="main-layout">
        <div id="statusBanner" class="banner-msg"></div>
        <div class="board-wrapper" id="board"></div>
        <div class="kb-hint">
            💡 <b>Dica:</b> Você pode tocar na peça, <b>arrastar o dedo (swipe)</b> ou usar as <b>Setas do Teclado</b> para deslizar.
        </div>
    </div>

    <script>
        const SIZE = {tamanho};
        const TILE_SIZE = {tile_size};
        const INITIAL = {json.dumps(board_inicial)};
        const STORAGE_KEY = "{storage_key}";
        const HL_CORRECT = {str(hl_corretos).lower()};

        // Estado persistido no lado do cliente
        let state = {{
            board: INITIAL.map(r => [...r]),
            moves: 0,
            startTime: Date.now(),
            elapsedFinal: 0,
            gameOver: false
        }};

        // Estrutura auxiliar para manipular o DOM sem recriá-lo
        const tilesDOM = {{}};
        let emptyPos = {{r: 0, c: 0}};

        function initDOM() {{
            const boardEl = document.getElementById('board');
            boardEl.innerHTML = '';
            
            for (let r = 0; r < SIZE; r++) {{
                for (let c = 0; c < SIZE; c++) {{
                    const val = state.board[r][c];
                    if (val === 0) {{
                        emptyPos = {{r, c}};
                        continue;
                    }}
                    
                    const div = document.createElement('div');
                    div.className = 'tile';
                    div.innerText = val;
                    div.onclick = () => tryMove(val);
                    boardEl.appendChild(div);
                    
                    tilesDOM[val] = {{ el: div, r: r, c: c }};
                }}
            }}
        }}

        function carregarEstado() {{
            try {{
                const salvo = sessionStorage.getItem(STORAGE_KEY);
                if (salvo) {{ 
                    const parsed = JSON.parse(salvo); 
                    if (parsed.board && parsed.board.length === SIZE) state = parsed; 
                }}
            }} catch (e) {{}}
            initDOM();
        }}

        function salvarEstado() {{ sessionStorage.setItem(STORAGE_KEY, JSON.stringify(state)); }}

        function atualizarCronometro() {{
            const el = document.getElementById('timerDisplay');
            if (!el) return;
            
            let diff = state.gameOver ? state.elapsedFinal : Math.max(0, (Date.now() - state.startTime) / 1000);
            el.classList.toggle('done', state.gameOver);
            el.innerText = String(Math.floor(diff / 60)).padStart(2, '0') + ':' + (diff % 60).toFixed(1).padStart(4, '0');
        }}
        setInterval(atualizarCronometro, 100);

        function checkWin() {{
            let expected = 1;
            for (let r = 0; r < SIZE; r++) {{
                for (let c = 0; c < SIZE; c++) {{
                    // O buraco (0) deve ser sempre o último elemento
                    if (r === SIZE - 1 && c === SIZE - 1) return true;
                    if (state.board[r][c] !== expected) return false;
                    expected++;
                }}
            }}
            return true;
        }}

        function tryMove(val) {{
            if (state.gameOver) return;
            
            const tile = tilesDOM[val];
            const dr = Math.abs(tile.r - emptyPos.r);
            const dc = Math.abs(tile.c - emptyPos.c);
            
            // Valida se o movimento é vertical ou horizontal (bloqueia diagonais)
            if ((dr === 1 && dc === 0) || (dr === 0 && dc === 1)) {{
                
                // Atualiza array interno
                state.board[emptyPos.r][emptyPos.c] = val;
                state.board[tile.r][tile.c] = 0;
                
                // Atualiza posições na estrutura de memória para refletir na UI
                const tempR = emptyPos.r;
                const tempC = emptyPos.c;
                emptyPos.r = tile.r;
                emptyPos.c = tile.c;
                tile.r = tempR;
                tile.c = tempC;
                
                state.moves++;
                
                if (checkWin()) {{
                    state.gameOver = true;
                    state.elapsedFinal = (Date.now() - state.startTime) / 1000;
                }}
                
                salvarEstado();
                renderUI();
            }}
        }}

        function renderUI() {{
            document.getElementById('movesDisplay').innerText = state.moves;
            
            let corretasCount = 0;
            const targetTotal = (SIZE * SIZE) - 1;

            // Anima posições (em porcentagem para responsividade em qualquer tela) e avalia peças no lugar certo
            for (let val in tilesDOM) {{
                const t = tilesDOM[val];
                t.el.style.transform = `translate(${{t.c * 100}}%, ${{t.r * 100}}%)`;
                
                const valInt = parseInt(val);
                const correctR = Math.floor((valInt - 1) / SIZE);
                const correctC = (valInt - 1) % SIZE;
                
                if (t.r === correctR && t.c === correctC) {{
                    corretasCount++;
                    if (HL_CORRECT) t.el.classList.add('correct');
                }} else {{
                    if (HL_CORRECT) t.el.classList.remove('correct');
                }}
            }}
            
            document.getElementById('correctDisplay').innerText = `${{corretasCount}} / ${{targetTotal}}`;

            const banner = document.getElementById('statusBanner');
            if (state.gameOver) {{
                banner.className = 'banner-msg win';
                banner.innerHTML = `🎉 <b>Puzzle Resolvido!</b><br>Você usou ${{state.moves}} movimentos em ${{state.elapsedFinal.toFixed(1)}}s.`;
            }} else {{
                banner.className = 'banner-msg';
                banner.innerHTML = '';
            }}
        }}

        // Mapeamento de teclado (Setas e WASD)
        window.addEventListener('keydown', (e) => {{
            if (state.gameOver) return;
            
            // A lógica de setas inverte a direção para ser intuitiva:
            // "Cima" move a peça de baixo para o buraco que está acima.
            let targetR = emptyPos.r;
            let targetC = emptyPos.c;
            
            if (e.key === 'ArrowUp' || e.key === 'w' || e.key === 'W') targetR += 1;
            else if (e.key === 'ArrowDown' || e.key === 's' || e.key === 'S') targetR -= 1;
            else if (e.key === 'ArrowLeft' || e.key === 'a' || e.key === 'A') targetC += 1;
            else if (e.key === 'ArrowRight' || e.key === 'd' || e.key === 'D') targetC -= 1;
            else return;

            e.preventDefault();
            
            if (targetR >= 0 && targetR < SIZE && targetC >= 0 && targetC < SIZE) {{
                const valTarget = state.board[targetR][targetC];
                if (valTarget !== 0) tryMove(valTarget);
            }}
        }});

        // Suporte a gestos de deslizar o dedo (Swipe) para telas touch / celulares
        let touchStartX = 0;
        let touchStartY = 0;
        const boardEl = document.getElementById('board');

        boardEl.addEventListener('touchstart', (e) => {{
            if (e.touches.length === 1) {{
                touchStartX = e.touches[0].clientX;
                touchStartY = e.touches[0].clientY;
            }}
        }}, {{ passive: true }});

        boardEl.addEventListener('touchend', (e) => {{
            if (state.gameOver || e.changedTouches.length !== 1) return;
            const dx = e.changedTouches[0].clientX - touchStartX;
            const dy = e.changedTouches[0].clientY - touchStartY;
            const absDx = Math.abs(dx);
            const absDy = Math.abs(dy);

            // Considera swipe válido se o deslocamento passar de 24px
            if (Math.max(absDx, absDy) > 24) {{
                let targetR = emptyPos.r;
                let targetC = emptyPos.c;
                if (absDx > absDy) {{
                    targetC += (dx > 0) ? -1 : 1;
                }} else {{
                    targetR += (dy > 0) ? -1 : 1;
                }}
                if (targetR >= 0 && targetR < SIZE && targetC >= 0 && targetC < SIZE) {{
                    const valTarget = state.board[targetR][targetC];
                    if (valTarget !== 0) tryMove(valTarget);
                }}
            }}
        }}, {{ passive: true }});

        carregarEstado();
        atualizarCronometro();
        renderUI();
    </script>
    """
    # Altura fixa ajustável para evitar barras de rolagem desnecessárias
    components.html(html_puzzle, height=620 if tamanho <= 5 else 680, scrolling=False)


# ==========================================
# FUNÇÃO PRINCIPAL DO JOGO
# ==========================================
def run():
    # Protege variáveis do estado global contra os recarregamentos (re-runs) nativos do Streamlit
    if "sliding_ativo" not in st.session_state:
        st.session_state.sliding_ativo = False
        st.session_state.sliding_board = []
        st.session_state.sliding_seed_atual = ""
        st.session_state.sliding_config = {}
        st.session_state.sliding_run_id = 0

    st.sidebar.header("⚙️ Configurações do Quebra-Cabeça")

    opcoes_tamanho = st.sidebar.number_input(
        "Tamanho da Grade (N x N)", min_value=3, max_value=50, value=4, step=1
    )
    tamanho = opcoes_tamanho

    dificuldade = st.sidebar.selectbox(
        "Complexidade do Embaralhamento",
        ["Fácil", "Médio", "Difícil", "Insano"],
        index=1,
    )

    # Escala dinamicamente a quantidade de embaralhamentos conforme o tamanho da grade
    multiplicador_passos = {"Fácil": 10, "Médio": 30, "Difícil": 80, "Insano": 200}
    passos = tamanho * multiplicador_passos[dificuldade]

    st.sidebar.subheader("🛠️ Auxílios Visuais")
    auxilios_selecionados = st.sidebar.multiselect(
        "Escolha quais auxílios ativar:",
        ["Destacar peças na posição correta"],
        default=["Destacar peças na posição correta"],
    )

    st.sidebar.markdown("---")
    st.sidebar.subheader("🌱 Sistema de Seed")
    seed_input = st.sidebar.text_input(
        "Carregar Seed (deixe vazio para aleatória):",
        placeholder="Cole uma Seed aqui...",
    )

    col_btn1, col_btn2 = st.sidebar.columns(2)
    iniciar_novo = col_btn1.button(
        "🔄 Novo Jogo", use_container_width=True, type="primary"
    )
    carregar_seed_btn = col_btn2.button("📥 Carregar Seed", use_container_width=True)

    def iniciar_partida(usar_seed_carregada=False, manter_config_atual=False):
        """Gerencia as configurações da partida instanciando novas seeds ou resgatando configs salvas."""
        # Reaproveita a mesma seed caso seja solicitado
        if manter_config_atual and st.session_state.sliding_config:
            cfg = st.session_state.sliding_config
        elif usar_seed_carregada and seed_input.strip():
            dados_seed = decodificar_seed(seed_input.strip())
            # Valida integridade básica da seed
            if dados_seed and "n" in dados_seed and "p" in dados_seed:
                cfg = dados_seed
                st.sidebar.success("Seed completa carregada com sucesso!")
            else:
                # Fallback: assume a seed como string aleatória com as configurações atuais do painel
                cfg = {
                    "d": dificuldade,
                    "n": tamanho,
                    "p": passos,
                    "h": auxilios_selecionados,
                    "s": seed_input.strip(),
                }
                st.sidebar.info("Seed personalizada aplicada às configurações atuais!")
        else:
            cfg = {
                "d": dificuldade,
                "n": tamanho,
                "p": passos,
                "h": auxilios_selecionados,
                "s": str(random.randint(100000, 999999)),
            }

        rng = random.Random(str(cfg["s"]))
        st.session_state.sliding_config = cfg
        st.session_state.sliding_board = gerar_tabuleiro_valido(cfg["n"], cfg["p"], rng)
        st.session_state.sliding_seed_atual = gerar_seed_codificada(cfg)
        st.session_state.sliding_ativo = True
        # Incrementa o run_id forçando os componentes HTML persistentes a resetarem
        st.session_state.sliding_run_id += 1

    # Roteamento dos eventos da Sidebar
    if iniciar_novo:
        iniciar_partida(usar_seed_carregada=False)
    elif carregar_seed_btn:
        if not seed_input.strip():
            st.sidebar.warning("Digite ou cole uma Seed.")
        else:
            iniciar_partida(usar_seed_carregada=True)
    elif not st.session_state.sliding_ativo:
        iniciar_partida(usar_seed_carregada=False)

    cfg = st.session_state.sliding_config

    col_titulo, col_seed = st.columns([1.5, 2], vertical_alignment="center")
    with col_titulo:
        st.title("🧩 Sliding Puzzle")
        st.caption(f"Grade: **{cfg['n']}x{cfg['n']}** | Dificuldade: **{cfg['d']}**")
    with col_seed:
        st.markdown("**🌱 Seed desta Partida:**")
        st.code(st.session_state.sliding_seed_atual, language="text")

    renderizar_sliding_puzzle(
        st.session_state.sliding_board,
        cfg,
        st.session_state.sliding_seed_atual,
        st.session_state.sliding_run_id,
    )


if __name__ == "__main__":
    st.set_page_config(page_title="Sliding Puzzle", page_icon="🧩", layout="wide")
    run()
